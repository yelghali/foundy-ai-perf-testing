# AI response performance on Microsoft Foundry

## Controlled lab report

- **Measurement date:** 4 September 2026
- **Region:** East US 2
- **Status:** Completed reproducible experiment
- **Audience:** AI application developers and architects selecting response-latency experiments
**Repository:** [foundy-ai-perf-testing](https://github.com/yelghali/foundy-ai-perf-testing)

## Abstract

AI response latency is not one variable. A request can spend time processing
input, generating output, decoding an image, rendering a document, selecting a
tool, opening a Model Context Protocol (MCP) session, executing tools, or
waiting for another model round. This lab tested those stages independently
before combining the strongest compatible findings.

The accepted final dataset contains **2,040 measured attempts** across text,
image, file, native-tool, MCP, and Microsoft Foundry toolbox workloads. The
full publication process executed 2,160 measurements; 120 early client-lifecycle
rows were superseded after finding that client construction was outside the
timer.

The strongest one-lever p50 findings among correctly completed attempts were:

- parallel document-page processing: **56.8% faster**;
- two-tool orchestration in one model-selection round: **28.2% faster**;
- concise output: **26.0% lower for text** with 29/30 correct completions and
  **24.9% lower for images** with 30/30;
- warm prompt caching: **14.9% faster for text** and **23.6% for images**;
- exposing five tools instead of 20: **16.8% faster**;
- minimal tool descriptions: **14.4% faster**;
- already-extracted text instead of a native PDF: **17.2% faster**;
- warm MCP reuse: avoided a **34.1% cold-session penalty**.

The combined optimized software + Priority Processing configuration reduced
p50 versus the non-optimized Standard (PAYGO) configuration by **41.0% for
text, 49.6% for images, 23.0% for files, and 37.3% for tools**. Each paired
95% interval excluded zero. Standard (PAYGO) configurations completed
correctly 240/240 times; the Priority Processing configuration completed
correctly 119/120 times.

The results also reject several tempting shortcuts. The smaller model was not
consistently faster and was 25.0% slower for the tested image workload. SDK
client recreation had no detectable p50 effect. Image resizing improved the
median but worsened p95. Microsoft Foundry tool search reduced input tokens but
added median latency in this 50-tool task.

These are measurements of one controlled environment, not service-level
guarantees. The intended output is a method and a set of testable decisions,
not universal percentages.

In this report, **AI-path latency** means the timed model request or composed
model-and-tool loop after local input preparation. It does not cover the full
path from a user click to a rendered result. Section 2.6 defines the boundary
and its implications.

> **Decision scope:** This is a performance-first, data-driven guide for
> choosing which latency levers to test on a real workload. It does not select
> a complete production architecture by itself. Answer quality, cost, data
> residency, privacy and security, compliance, availability, quotas, and
> operational complexity remain separate production gates.

Use the report based on the decision at hand:

- **Choose candidate levers:** start with the performance story and Section 9.
- **Audit the evidence:** inspect Sections 2, 3, 7, 8, 10, 11, and 14.
- **Run the lab:** follow Section 13, beginning with a smoke test before paid
  measurement runs.

To design a new comparison in an application workspace, install the
[AI response performance skill](../.github/skills/ai-response-performance/SKILL.md)
as a project or personal skill. GitHub Copilot loads it for relevant requests
in VS Code agent mode.

## Processing options in scope

- **Standard (pay-as-you-go, or PAYGO)** uses shared processing capacity and
  pay-per-token billing. Both the non-optimized and optimized Standard
  configurations use this mode.
- **Priority Processing** is also pay-as-you-go, at the Priority Processing
  rate. It provides a model-specific latency target for supported deployments
  without reserving capacity in advance. The lab accepts this label only when
  the response reports `service_tier=priority`.
- **Provisioned Throughput** reserves dedicated processing capacity measured
  in Provisioned Throughput Units (PTUs), billed per PTU per hour or through
  reservations. This lab did not compare PTU.

See Microsoft's
[deployment-category comparison](https://learn.microsoft.com/azure/foundry/openai/concepts/provisioned-throughput#deployment-categories-compared)
and [Priority Processing documentation](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing).

## Performance story at a glance

The results support an order of operations, not a shopping list of percentages:

| Step | Performance action | Evidence from this lab |
|---|---|---|
| 1. Remove unnecessary work | Generate less, use only the image detail required, avoid document rendering when prepared text is already available, and expose a smaller relevant tool surface | Clear p50 improvements from concise text/image output, low image detail, prepared text, five tools, and minimal descriptions |
| 2. Reuse prior work | Keep stable prompt prefixes cacheable and reuse MCP connection and discovery state | Warm text/image caches improved p50; cold MCP setup added a 34.1% penalty |
| 3. Remove serial waits and model rounds | Fan out independent page requests; request independent tools in one model turn and execute them together | Parallel pages improved p50 by 56.8%; two-tool orchestration improved it by 28.2% |
| 4. Accelerate residual provider work | Evaluate Priority Processing only after software changes | Priority Processing clearly improved optimized text and image p50; incremental file and tool effects were inconclusive |
| 5. Apply release gates | Check correctness, reliability, tails, and cost instead of accepting a median alone | One fast text treatment lost a completion; some median improvements had worse descriptive p95 |

The two parallelism findings measure different mechanisms. The page comparison
makes the same three model calls concurrently instead of sequentially. The tool
comparison keeps the same user task and two tool invocations, but the parallel
arm allows both calls in one model-selection response and then executes them
together. The sequential arm requires another model-selection round. Because
the synthetic tools themselves averaged under 5 ms, the tool result primarily
demonstrates the value of removing a model round; it is not a pure backend
parallelism benchmark.

The headline confirmation numbers measure **task completion**, not perceived
first response. Only the streaming text screen records time to first token.
The combined Standard (PAYGO) and Priority Processing confirmation is
non-streaming and makes no claim about first-token or first-audio latency.

Throughput is a third, separate question. These confirmation runs use
concurrency one to isolate treatment effects; they do not show how many
simultaneous users the deployment can sustain. In short, this lab primarily
tests **correct-task completion latency**, reports limited **first-token
latency**, and leaves **capacity under load** to a separate experiment.

The lab intentionally defines no universal production SLO or reliability
threshold. Its relative effects help select candidates; each application must
confirm them against its own latency, quality, reliability, and traffic
targets.

## 1. Research questions

The lab asked six questions:

1. Which software levers reduce measured AI-path latency without reducing task
   correctness?
2. Which findings transfer across text, image, file, and tool workloads?
3. How much do tool count, description length, schema shape, MCP lifecycle,
   and execution scheduling matter?
4. What does Microsoft Foundry tool search trade for its smaller initial tool
   surface?
5. Does verified Priority Processing improve the same optimized workload on
   the same model deployment?
6. How much is gained when compatible winners are combined?

Retrieval-augmented generation (RAG) was intentionally excluded. RAG adds
embedding, retrieval, filtering, reranking, chunking, and context-construction
variables and needs a separate experiment.

## 2. Experimental principles

### 2.1 Change one lever at a time

The first phase used a stable baseline for each scenario. Every treatment
changed one factor and restored the baseline before the next treatment. This
avoids an exponential configuration matrix and makes attribution possible.

### 2.2 Separate correctness from latency

Each scenario had an automated quality gate:

| Scenario | Correctness gate |
|---|---|
| Text | Required factual terms from the fixture appear in the answer |
| Image | Invoice ID, total, and status match the generated receipt |
| File | Project code and approved budget match the generated document |
| Tools | Expected tool or tools selected, arguments valid, requested values present in the final answer |

The report uses two release gates:

1. correct-completion rate over every attempted request;
2. latency conditional on a successful, quality-passing completion.

Failed and incorrect requests remain in the first metric and are excluded from
the second because a fast wrong answer is not a successful optimization. The
lab does not blend failures into a synthetic latency value or calculate
retry-adjusted time to success. A production workflow that retries must time
the complete retry policy and report its extra cost.

This exploratory study did not impose a universal acceptable completion rate.
A production benchmark must set that threshold before running. A treatment can
have a lower conditional p50 and still fail release because of reliability.

### 2.3 Rotate fixtures

Each scenario used five deterministic fixtures:

- five text prompts with required facts;
- five generated receipt images;
- five generated three-page PDF documents plus extracted-text equivalents;
- five city-based weather and local-time tool tasks.

During a round, every treatment in a scenario used the same fixture index.
Fixture rotation reduces the chance that one unusually easy prompt determines
the result.

### 2.4 Randomize order by round

Confirmation runs used a seeded randomized complete-block design:

- three unmeasured warm-ups per case;
- 30 measured rounds;
- one execution of every case per round;
- deterministic seed `20260904`;
- a randomized case order inside every round.

This design reduces time-of-run, transient-load, and fixture confounding while
preserving a paired treatment/control comparison.

### 2.5 Preserve tails and failures

Every summary records:

- p50, p95, and p99 total latency;
- time to first token where streaming applies;
- request success and correct-completion rate;
- input, output, reasoning, and cached tokens;
- actual and requested processing tier;
- model, API, SDK, image, fixture, round, and schedule metadata;
- model-selection, tool-execution, MCP-discovery, and final-generation stages
  where applicable.

No failed publication observation was silently retried.

### 2.6 Name the timing boundary

The main `total_ms` metric is narrower than a complete application journey:

- for single-response text, image, and file cases, timing starts immediately
  before the Responses API call and stops when that response completes;
- for page, cascade, and tool workflows, timing covers the composed model calls
  and tool stages after their fixtures are prepared;
- the corrected one-shot-client comparison additionally includes client
  construction;
- deterministic fixture creation, request-object construction, image
  generation and resize, PDF generation, and extracted-text preparation occur
  before the primary timer;
- user-to-application network time, UI rendering, and audio playback are not
  part of this lab.

This boundary isolates model and orchestration choices, but it narrows some
claims. In particular, the extracted-text treatment measures the AI call after
text is already available, and the resized-image treatment excludes local
resize time. A production pipeline must add parsing, OCR, resize, upload, and
rendering stages before calling either result end-to-end.

## 3. Statistical method

Latency is heavily skewed, so medians and percentile tails are more useful than
means alone.

- Every confirmation cohort contains 30 attempts.
- Median intervals use 5,000 bootstrap resamples.
- Treatment effects use paired bootstrap resampling by randomized round when
  treatment and control were in the same execution.
- Percentage change is:

  ```text
  100 x (treatment p50 - control p50) / control p50
  ```

- A finding is labelled **faster** or **slower** only when the 95% p50-effect
  interval excludes zero.
- That label describes p50 among correctly completed attempts only. A
  production recommendation must also pass its predefined correctness and
  reliability thresholds.
- Intervals were not adjusted for multiple comparisons. They establish
  direction in this experiment, not universal proof.
- Raw milliseconds are never averaged across different scenarios.

With 30 observations, p95 and p99 are descriptive diagnostics, not adequately
sampled production-tail estimates. The p50 paired intervals are the inferential
evidence in this report. A production p95 or p99 release gate needs a separate,
larger run across multiple time windows.

For the combined confirmation only, the report includes a descriptive
geometric mean of the four scenario p50 ratios. It is not a pooled latency
result and has no aggregate confidence interval.

## 4. Azure environment

| Component | Configuration |
|---|---|
| Resource group | `rg-aiperf-6l2kni` |
| Region | `eastus2` |
| Azure OpenAI account | `oai-aiperf-6l2kni` |
| Baseline deployment | `gpt-4.1-mini`, version `2025-04-14`, Global Standard, 100K TPM |
| Smaller-model deployment | `gpt-4.1-nano`, version `2025-04-14`, Global Standard, 100K TPM |
| Deployment used for Priority Processing | `gpt-4.1`, version `2025-04-14`, Global Standard, 100K TPM |
| Container Apps job | `job-aiperf-6l2kni`; Consumption profile, one replica, 1 vCPU, 2 GiB |
| Foundry project | `foundry-aiperf-6l2kni` / `tools` |
| Toolbox | `ai-perf-tools`, version 1 |
| Remote MCP app | `mcp-aiperf-6l2kni` |
| Result storage | Private Azure Blob Storage |
| Authentication | Microsoft Entra ID and managed identity; local keys disabled |

Terraform provisions the account, deployments, registry, network, job,
managed identity, private result storage, MCP host, role assignments, and
Foundry project. The benchmark container runs inside the VNet-integrated
Container Apps environment.

The synthetic MCP endpoint is intentionally public and anonymous because it
contains only deterministic read-only tools and no secrets. That is a lab
convenience, not a production security pattern.

## 5. Request and scenario implementation

The benchmark uses the Azure OpenAI Responses API through the OpenAI Python
SDK and Microsoft Entra authentication. Official documentation describes
Responses API support for text, image, file, tool, and stateful response
flows: [Use the Azure OpenAI Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses).

### 5.1 Text

The normal text task asks for four concise bullets and includes a 12-turn
irrelevant history. Treatments reduce output, remove history, change client
lifecycle, compare warm and cold long prefixes, change model, request
Priority Processing, or disable streaming.

### 5.2 Image

Generated receipt images contain deterministic invoice fields. Treatments
change response size, image dimensions, detail level, cache state, model, and
a low-detail-first cascade. The `low` detail mode trades fine-grained visual
information for lower token and processing requirements; whether that trade
is acceptable must be decided by field accuracy.

`detail="low"` is an API processing hint, not the same operation as locally
resizing the image. Microsoft documents that low detail processes a
lower-resolution 512 x 512 representation instead of activating high-resolution
tiling. That can reduce visual tokens and response time when coarse objects or
large text are sufficient, but it can miss small print and fine visual
evidence. The original image is still uploaded; the separate resized-image
treatment is the one that changes the source pixels before the request. See
[Configure image detail level](https://learn.microsoft.com/azure/foundry/openai/how-to/gpt-with-vision#configure-image-detail-level).
The cascade tries low detail first and sends a second high-detail request only
when the deterministic field scorer rejects the low-detail answer; an
escalated attempt includes both requests in its total time and token usage.

### 5.3 File

Generated three-page PDFs distribute the relevant values across pages.
Treatments compare:

- native PDF input;
- only the relevant page;
- extracted text;
- three sequential page calls;
- the same three calls in parallel.

The sequential and parallel page cases make the same number of model calls.
Their difference isolates scheduling rather than hidden work reduction.

### 5.4 Tools and MCP

The deterministic catalogue contains 50 tools. The first two are
`lookup_weather` and `get_local_time`; all other tools return stable synthetic
results.

The tool experiments change:

- 5, 20, or 50 exposed definitions;
- minimal, concise, or verbose descriptions;
- simple, many-parameter, or nested schemas;
- distinct or ambiguous descriptions;
- stable or reordered definitions;
- native functions, local MCP, remote MCP, or Foundry toolbox tool search;
- cold or reused MCP sessions;
- sequential or parallel execution of the same two-tool task.

The two-tool comparison is an orchestration test. The sequential arm permits
one tool call per model-selection round, executes it, returns its output, and
asks the model to select the second tool. The parallel arm permits both
function calls in the first selection response and executes both invocations
concurrently before final generation. Both perform the same two deterministic
tool invocations, but the parallel arm uses one fewer model call.

#### Practical Responses API pattern

For custom function tools, the model requests calls but does not execute
application code. A Responses API application can:

1. send the tool definitions with `parallel_tool_calls=True`;
2. collect every `function_call` item returned in that response;
3. validate the tool names, arguments, independence, and side-effect safety;
4. run independent async handlers together, for example with
   `asyncio.gather`;
5. create one `function_call_output` item per result using the original
   `call_id`; and
6. submit all outputs in one follow-up request with the prior response ID.

The parameter allows the model to request multiple calls but does not force it
to do so. The application must still test that the correct calls were selected
and that the final answer uses every required result. `asyncio.gather` overlaps
async I/O; blocking synchronous handlers need a suitable thread, process, or
service-level concurrency mechanism if their execution itself is to overlap.

Do not run calls together when one requires another's output or when concurrent
side effects are unsafe. Also test quota use, downstream saturation, timeout,
partial-failure, and retry behavior before adopting the pattern in production.

Microsoft documents
[parallel function calling](https://learn.microsoft.com/azure/foundry/openai/how-to/function-calling#parallel-function-calling-with-multiple-functions)
and the
[Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses).
The benchmark's complete Responses API loop is in
[`src/ai_perf/scenarios.py`](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/src/ai_perf/scenarios.py#L1093-L1169).

MCP timing is decomposed as:

```text
connection and discovery
-> model tool selection
-> tool execution
-> final model generation
-> correctly completed task
```

### 5.5 Microsoft Foundry tool search

The same 50-tool remote MCP catalogue backs both comparison arms:

1. direct remote MCP exposes all 50 definitions to the model;
2. the Foundry toolbox initially exposes `tool_search` and `call_tool`.

Microsoft Foundry tool search uses BM25 over tool names, descriptions, and
parameter information and returns only matching definitions. The official
flow is documented in
[Enable tool search in a toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search).

## 6. Prompt-cache control

Prompt caching helps only when enough prefix content is identical. A naive
warm/cold test can accidentally hit the same cache in both cohorts.

This lab used:

- a long otherwise-identical instruction prefix;
- a stable cache key for the warm case;
- a per-request nonce placed before the long prefix for the cold case;
- observed cached-token counts as the validation signal.

Cold cohorts reported zero cache hits. Warm cohorts reported approximately
93-100% cache hits. Microsoft documents that prompt caching reuses identical
leading content and that cache behavior should be verified from actual usage:
[Prompt caching](https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching).

## 7. One-lever results

All values below are measured AI-path milliseconds. "Change" is the p50 change
from the stated control. An interval crossing zero is reported as inconclusive.
Each row contains 30 attempted requests, so 100% means 30/30 correct and 96.7%
means 29/30.

The four "New client per request" rows use the reused-client arm from the
separate corrected client-lifecycle run as their paired control, rather than
the broader screen baseline shown at the top of each table.

### 7.1 Text chat

| Variant | Correct (of 30) | p50 | p95 | p50 change [95% CI] | Interpretation |
|---|---:|---:|---:|---:|---|
| Baseline | 100% | 2078 | 4715 | - | Control |
| Concise output | 96.7% | 1537 | 2204 | -26.0% [-36.1%, -13.4%] | Lower conditional p50; 29/30 correct |
| Reduced history | 100% | 1813 | 4203 | -12.7% [-25.5%, +2.2%] | Inconclusive |
| New client per request | 100% | 2213 | 3280 | -1.9% [-13.4%, +5.6%] | Inconclusive |
| Cache cold | 100% | 1935 | 5120 | - | Cache control |
| Cache warm | 100% | 1647 | 2129 | -14.9% [-25.2%, -6.9%] | Faster |
| Priority Processing requested | 100% | 1960 | 4042 | -5.7% [-18.2%, +5.0%] | Invalid; served as Standard |
| Smaller model | 100% | 1869 | 3424 | -10.1% [-22.2%, +14.5%] | Inconclusive |
| Non-streaming | 100% | 2349 | 4210 | +13.0% [-6.4%, +34.1%] | Total latency inconclusive |

The streaming baseline delivered its first token in 912 ms on average. Warm
caching reduced average first-token latency from 991 ms in the cold control to
602 ms.

### 7.2 Image understanding

| Variant | Correct (of 30) | p50 | p95 | p50 change [95% CI] | Interpretation |
|---|---:|---:|---:|---:|---|
| Baseline | 100% | 1646 | 5087 | - | Control |
| Concise JSON | 100% | 1237 | 4751 | -24.9% [-32.3%, -16.2%] | Faster |
| Resized image | 100% | 1435 | 8802 | -12.8% [-21.9%, -3.4%] | Faster median, worse tail |
| New client per request | 100% | 1715 | 4142 | +1.3% [-10.7%, +17.0%] | Inconclusive |
| Cache cold | 100% | 1897 | 8040 | - | Cache control |
| Cache warm | 100% | 1449 | 4210 | -23.6% [-42.0%, -7.8%] | Faster |
| Priority Processing requested | 100% | 1669 | 6352 | +1.4% [-10.6%, +25.6%] | Invalid; served as Standard |
| Smaller model | 100% | 2058 | 5416 | +25.0% [+16.3%, +61.4%] | Slower |
| Low detail | 100% | 1352 | 3846 | -17.8% [-24.6%, -2.5%] | Faster |
| Low-detail cascade | 100% | 1476 | 4714 | -10.3% [-18.7%, -2.5%] | Faster |

Resizing is the clearest example of why p50 alone is insufficient. Median
latency improved, but p95 rose from 5.1 to 8.8 seconds and p99 rose from 7.6 to
10.4 seconds. The resize itself occurred before the primary timer, so this is
an API-path comparison rather than a complete image-pipeline comparison.

### 7.3 File processing

| Variant | Correct (of 30) | p50 | p95 | p50 change [95% CI] | Interpretation |
|---|---:|---:|---:|---:|---|
| Baseline PDF | 100% | 1445 | 3004 | - | Control |
| Concise JSON | 100% | 1215 | 5566 | -15.9% [-30.8%, +6.6%] | Inconclusive; worse tail |
| Relevant page only | 100% | 1465 | 2857 | +1.4% [-6.5%, +21.6%] | Inconclusive |
| New client per request | 100% | 1423 | 5061 | -4.8% [-19.2%, +8.2%] | Inconclusive |
| Cache cold | 100% | 1544 | 7601 | - | Cache control |
| Cache warm | 100% | 1776 | 2954 | +15.0% [-16.4%, +34.7%] | Inconclusive |
| Priority Processing requested | 100% | 1487 | 8020 | +2.9% [-6.3%, +24.6%] | Invalid; served as Standard |
| Smaller model | 100% | 1329 | 4917 | -8.0% [-24.5%, +16.0%] | Inconclusive |
| Extracted text | 100% | 1197 | 1752 | -17.2% [-22.1%, -3.2%] | Faster |
| Sequential pages | 100% | 2811 | 6517 | - | Page control |
| Parallel pages | 100% | 1216 | 3784 | -56.8% [-63.2%, -45.1%] | Faster |

With text already prepared, extracted-text input produced the strongest
single-call file result. Extraction or OCR time was outside the timer, so a
full document-pipeline decision must add that stage. When a workflow must
process independent pages separately, scheduling those calls in parallel
produced the largest median improvement in the entire screen.

### 7.4 Tool catalogue and prompt design

| Variant | Correct (of 30) | p50 | p95 | p50 change [95% CI] | Interpretation |
|---|---:|---:|---:|---:|---|
| Native 20-tool baseline | 100% | 2289 | 4488 | - | Control |
| Concise output | 100% | 2350 | 8077 | +2.7% [-20.7%, +20.8%] | Inconclusive |
| Five exposed tools | 100% | 1904 | 4005 | -16.8% [-34.3%, -9.9%] | Faster |
| New client per request | 100% | 2173 | 3605 | +2.7% [-8.7%, +20.5%] | Inconclusive |
| Cache cold | 100% | 2294 | 2883 | - | Cache control |
| Cache warm | 100% | 2226 | 5374 | -3.0% [-12.0%, +18.3%] | Inconclusive |
| Priority Processing requested | 100% | 2100 | 5639 | -8.2% [-25.4%, +1.0%] | Invalid; served as Standard |
| Smaller model | 100% | 2187 | 4721 | -4.4% [-22.3%, +5.8%] | Inconclusive |
| Fifty tools | 100% | 2492 | 4288 | +8.9% [-16.9%, +15.1%] | Inconclusive |
| Minimal descriptions | 100% | 1959 | 4185 | -14.4% [-31.8%, -4.4%] | Faster |
| Verbose descriptions | 100% | 1954 | 3863 | -14.6% [-31.7%, -8.5%] | Cache-confounded |
| Many-parameter schema | 100% | 2443 | 7818 | +6.7% [-15.5%, +32.6%] | Inconclusive; worse tail |
| Nested schema | 100% | 2309 | 4340 | +0.9% [-19.8%, +9.7%] | Inconclusive |
| Ambiguous descriptions | 100% | 2502 | 3480 | +9.3% [-13.3%, +17.6%] | Inconclusive |
| Reordered definitions | 100% | 2655 | 6583 | +19.3% [-4.6%, +52.4%] | Inconclusive |

The verbose-description treatment recorded a 90% cache-hit rate while its
baseline recorded none. Its apparent improvement cannot be attributed to
description length. The minimal-description finding is cleaner because neither
side recorded cache hits.

### 7.5 Tool integration and execution

| Variant | Correct (of 30) | p50 | p95 | p50 change [95% CI] | Interpretation |
|---|---:|---:|---:|---:|---|
| Native baseline | 100% | 2057 | 5645 | - | Integration control |
| Warm local MCP | 100% | 2283 | 4353 | +11.0% [-7.1%, +22.6%] | Inconclusive |
| Cold local MCP | 100% | 3061 | 3704 | +34.1% [+20.9%, +58.0%] | Slower than warm |
| Direct remote MCP, 50 tools | 96.7% | 2528 | 7797 | - | Toolbox control |
| Foundry toolbox tool search | 100% | 3614 | 4751 | +43.0% [+26.1%, +76.4%] | Slower median |
| Sequential two-tool orchestration | 100% | 3646 | 8688 | - | Orchestration control |
| Single-round two-tool orchestration | 100% | 2617 | 4761 | -28.2% [-36.5%, -9.3%] | Faster |

Cold MCP connection and discovery averaged 1,016 ms; the deterministic local
tool itself averaged under 5 ms.

The 28.2% tool effect combines one fewer model-selection round with concurrent
execution of the two tool invocations. It should not be attributed to backend
parallelism alone.

Foundry toolbox tool search used 1,431 average input tokens versus 1,941 for
direct remote MCP, a 26% reduction. It added a model search round and increased
p50 by 43%. However, it achieved 100% correctness and a lower p95, while the
direct MCP answer omitted the requested value once. Tool search is therefore a
latency, token, and reliability trade-off--not a feature to accept or reject
from one number.

## 8. Combined non-optimized-to-optimized confirmation

Percentages from separate one-lever tests should not be added. Interactions,
model behavior, caching, and tail latency can change once levers are combined.
The lab therefore ran a separate 12-case bundle profile.

### 8.1 Confirmation arms

Every scenario used the same `gpt-4.1` deployment, model version, region,
fixtures, and schedule:

1. **Non-optimized Standard (PAYGO):** deliberately non-optimized but valid;
2. **Optimized Standard (PAYGO):** compatible supported software findings;
3. **Optimized + Priority Processing:** the identical optimized configuration
   with request-level Priority Processing.

These presentation labels map to the existing code variants
`bundle-worst-standard`, `bundle-best-standard`, and `bundle-best-priority`.
The internal variant names remain stable so existing artifacts are
reproducible.

| Scenario | Non-optimized Standard (PAYGO) | Optimized Standard (PAYGO) and Optimized + Priority Processing |
|---|---|---|
| Text | Cold long prefix, full history, normal output | Warm prefix cache, concise output |
| Image | Cold long prefix, high detail, normal output | Warm prefix cache, low detail, concise JSON |
| File | Native full PDF | Extracted text |
| Tools | 20 concise tools, one tool selection per model round | Five minimal tools, both tools selected in one model round and executed concurrently |

The bundle uses non-streaming Responses calls. Microsoft documents that actual
service tier must be verified from the response, and streaming tier reporting
has had limitations. A Priority Processing result was accepted only when
successful responses reported `service_tier=priority`.

The earlier one-lever Priority Processing rows used `gpt-4.1-mini`, which was
not listed as supported for Priority Processing and was served as Standard.
The valid bundle uses a supported `gpt-4.1` version `2025-04-14` Global
Standard deployment. See
[Enable Priority Processing for Microsoft Foundry models](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing).

The one-lever findings were selected on `gpt-4.1-mini`, while this confirmation
uses the `gpt-4.1` deployment used for Priority Processing. The confirmation
therefore validates the complete configurations below on `gpt-4.1`; it does
not prove that every individual effect transferred independently. The
inconclusive Optimized Standard (PAYGO) text result illustrates that
distinction.

### 8.2 Confirmation results

| Scenario | Non-optimized Standard (PAYGO) p50 / p95 | Optimized Standard (PAYGO) p50 / p95 | Software change [95% CI] | Optimized + Priority Processing p50 / p95 | Priority Processing over Optimized Standard (PAYGO) [95% CI] | Optimized + Priority Processing over non-optimized Standard (PAYGO) [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| Text | 2070 / 4859 | 2125 / 4636 | +2.7% [-10.4%, +13.3%] | 1222 / 2009 | -42.5% [-46.7%, -37.5%] | **-41.0% [-47.3%, -34.8%]** |
| Image | 2872 / 6211 | 2234 / 5722 | -22.2% [-33.7%, -16.5%] | 1448 / 4963 | -35.2% [-42.3%, -22.5%] | **-49.6% [-57.0%, -39.9%]** |
| File | 1512 / 4824 | 1245 / 2895 | -17.7% [-27.0%, -5.7%] | 1165 / 4949 | -6.5% [-17.9%, +0.3%] | **-23.0% [-33.2%, -13.7%]** |
| Tools | 3817 / 8098 | 2824 / 4026 | -26.0% [-35.7%, -19.1%] | 2393 / 8023 | -15.3% [-25.2%, +3.9%] | **-37.3% [-48.9%, -25.2%]** |

The direct Optimized + Priority Processing versus non-optimized Standard
(PAYGO) interval excludes zero for all four scenarios. The software
contribution and Priority Processing contribution are not uniform:

- software alone clearly helped image, file, and tool workloads but not text
  on `gpt-4.1`;
- Priority Processing clearly improved text and image p50;
- incremental Priority Processing effects for file and tools were
  inconclusive;
- descriptive Priority Processing p95 was worse than Optimized Standard
  (PAYGO) for file and tools.

The geometric mean of the four p50 ratios was 16.5% lower for Optimized
Standard (PAYGO) and 38.4% lower for Optimized + Priority Processing versus
the non-optimized Standard (PAYGO) configuration. This is a descriptive
normalized summary only.

### 8.3 Confirmation reliability

- Standard (PAYGO) configurations completed correctly 240/240 times.
- The Priority Processing configuration completed correctly 119/120 times.
- All 119 successful Priority Processing calls reported the `priority` tier.
- One Priority Processing tool request returned HTTP 400: `No tool call found for
  function call output`.
- The failed request remains in the reliability denominator and is excluded
  only from latency percentiles.

These counts describe this run; they are not tight production reliability
estimates. A release decision needs more observations and a predefined
completion-rate objective.

## 9. What the data supports

### 9.1 Strong recommendations for these workloads

1. **Constrain output to the smallest valid contract, but do not ship a
   latency gain that misses the required completion-rate objective.**
2. **Place stable long content first and verify actual cache hits.**
3. **Use low image detail only when the task does not require small text or
   fine visual evidence and extraction accuracy still passes.**
4. **Prefer prepared text when visual PDF layout is unnecessary and the full
   extraction pipeline is faster.**
5. **Parallelize independent page requests. For tools, allow one model turn to
   request all required functions, and test concurrent backend execution as a
   separate lever.**
6. **Expose only relevant tools and keep descriptions economical.**
7. **Reuse MCP sessions and discovered catalogues.**
8. **Evaluate Priority Processing on the exact supported model and verify the
   returned tier.**

### 9.2 Decisions that remain workload-specific

- smaller versus larger model;
- streaming for perceived latency versus total latency;
- image resizing;
- page selection;
- prompt caching for file and tool tasks;
- complex tool schemas;
- Foundry toolbox tool search versus full direct exposure;
- Priority Processing effects on p95 and p99.

### 9.3 Findings not supported here

- A smaller model is always faster.
- Recreating the SDK client materially changes p50 in this environment.
- Fewer input tokens necessarily produce lower full-pipeline latency.
- Priority Processing always improves every percentile.
- Percentages from isolated levers can be summed.

## 10. Reliability events retained in the evidence

Three publication reliability events were intentionally preserved:

1. one concise text stream ended without a `response.completed` event;
2. one direct remote MCP response called the correct tool but omitted the
   requested temperature in its final answer;
3. one Priority Processing single-round two-tool turn received an invalid
   function-call-output response from the API.

Every other final-result row achieved 100% correct completion.

## 11. Threats to validity

### Synthetic fixtures

The fixtures are deterministic and support exact scoring, but they do not
represent every production prompt, image, document, or tool catalogue.

### Narrow correctness contracts

The deterministic scorers verify the explicit fields, terms, tools, and
arguments required by these synthetic tasks. They do not measure broader prose
quality, safety, groundedness, or user satisfaction. A production benchmark
needs a correctness contract that represents those release requirements.

### One region and measurement window

All accepted runs used one Azure account in East US 2 on 4 September 2026.
Service load, model versions, regional routing, quotas, and product behavior
can change.

### Multiple comparisons

The study reports many intervals without family-wise correction. Results should
be independently replicated before being presented as broad claims.

### Heavy tails

Thirty observations characterize a median better than a high percentile.
p95 and p99 are reported only as descriptive diagnostics. Larger samples
across multiple time windows are required for tail-latency service objectives.

### No confirmation load test

The combined confirmation used concurrency 1 to preserve paired randomized
rounds. Concurrency, rate limits, cache-key distribution, and quota contention
need a separate capacity test.

### No production SLO

The experiment compares relative effects; it was not designed around one
application's p50, p95, completion-rate, or throughput objective. A production
team must define those thresholds before accepting a treatment.

### Performance focus, not a full architecture scorecard

Latency is the primary subject. Token usage and processing tiers were recorded,
but the report does not normalize cost. It also does not rank data residency,
privacy and security, compliance, availability, quota, or operational
complexity. Those concerns, together with broader answer quality, remain
required inputs to a production architecture decision.

### Retry-adjusted user latency was not measured

Failures remain visible in correct-completion rates, but the percentile tables
condition on correct completions. They do not estimate how long a user waits
after application retries or fallback behavior. That requires a separate
full-workflow policy test.

### Selection and fixture reuse

The screen and bundle confirmation use the same synthetic fixture families.
The bundle validates those complete configurations but is not an independent
replication on held-out production inputs. Selected effects can be optimistic
until repeated on new fixtures and another time window.

### Tool search is task-dependent

The toolbox result uses one deterministic 50-tool catalogue and BM25-friendly
descriptions. Different naming, metadata, ambiguity, or task distributions can
change discovery quality and latency.

### Synthetic tools are unusually fast

The local tool backend averaged under 5 ms. The tool experiment therefore
reveals model-round and orchestration cost more than realistic downstream API
latency. Network-bound tools, rate limits, side effects, and dependency
failures require their own execution-policy test.

## 12. Recommended next experiments

The most valuable follow-ups are narrower than another broad lever screen:

1. **Full-pipeline multimodal timing:** include image resize, PDF parsing or
   OCR, encoding, upload, and validation inside an application-workflow timer.
2. **Winner-only pressure test:** run the non-optimized and optimized
   configurations at representative concurrency or arrival rates and capture
   queueing, HTTP 429s, throughput, and cache behavior.
3. **Tail confirmation:** repeat release candidates with enough attempts across
   multiple time windows to support p95 or p99 objectives.
4. **Independent replication:** use held-out fixtures and another measurement
   window before treating effect sizes as durable.
5. **Tool-search diversity:** vary catalogue size, naming quality, ambiguity,
   and task mix rather than relying on one 50-tool catalogue.

The reusable experimental rules are captured in
[AI response performance testing guidelines](./ai-response-performance-guidelines.md).
Install the
[AI response performance skill](../.github/skills/ai-response-performance/SKILL.md)
to apply those rules from an application workspace to a scoped plan,
implementation, benchmark run, or evidence review.

### Adjacent performance tracks

Three important tracks remain deliberately outside this report:

- **Model performance and distillation:** the smaller off-the-shelf model was
  not consistently faster here. A dedicated study should compare task quality,
  latency, throughput, and cost, and can evaluate distillation for specialized
  tasks. See
  [Distillation: Turning Smaller Models into High-Performance, Cost-Effective Solutions](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/distillation-turning-smaller-models-into-high-performance-cost-effective-solutio/4355029).
- **Voice agents:** voice adds turn detection, speech processing, time to first
  audio, interruption, and session behavior. See
  [Choosing a real-time voice architecture on Microsoft Foundry: three enterprise patterns](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/choosing-a-real-time-voice-architecture-on-microsoft-foundry-three-enterprise-pa/4552676)
  for a measured architecture comparison.
- **RAG with Azure AI Search:** retrieval adds query planning, search,
  filtering, ranking, chunk selection, and context construction. Start with
  [Retrieval-augmented generation in Azure AI Search](https://learn.microsoft.com/azure/search/retrieval-augmented-generation-overview),
  then examine
  [metadata filters for RAG performance](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/boost-rag-performance-enhance-vector-search-with-metadata-filters-in-azure-ai-se/4208985)
  and
  [vector storage and processing optimization](https://learn.microsoft.com/azure/search/vector-search-how-to-configure-compression-storage).

These references suggest experiments; they do not extend the findings or
percentages measured in this lab.

## 13. Reproduction

The commands below reproduce the request profiles. Provisioning creates paid
Azure resources, and availability depends on subscription quota, model and
region support, permissions, and applicable data-residency requirements. Start
with smoke tests, then run larger measured profiles only when that environment
is intentional.

### 13.1 Prepare the local environment and Azure context

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
az login --use-device-code --tenant <tenant-id>
az account set --subscription <subscription-id>
$env:ARM_SUBSCRIPTION_ID = az account show --query id -o tsv
```

### 13.2 Deploy Azure resources

```powershell
Set-Location terraform
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
terraform apply -target azurerm_container_registry.this
$registry = terraform output -raw container_registry_login_server
az acr build --registry $registry.Split('.')[0] --image ai-perf:latest ..
terraform apply
```

Terraform provisions the baseline and smaller model deployments, the
deployment used for Priority Processing, the benchmark runtime, and artifact
storage. Review
[the infrastructure guide](../terraform/README.md) and `terraform.tfvars`
before applying.

### 13.3 Configure endpoints and Foundry toolbox

```powershell
$env:AZURE_OPENAI_ENDPOINT = terraform output -raw azure_openai_endpoint
$env:AZURE_OPENAI_DEPLOYMENT = terraform output -raw azure_openai_deployment
$env:AZURE_OPENAI_FAST_DEPLOYMENT = terraform output -raw azure_openai_fast_deployment
$env:AZURE_OPENAI_PRIORITY_DEPLOYMENT = terraform output -raw azure_openai_priority_deployment
$env:FOUNDRY_PROJECT_ENDPOINT = terraform output -raw foundry_project_endpoint
$env:AI_PERF_REMOTE_MCP_URL = terraform output -raw remote_mcp_url
$env:AI_PERF_TOOLBOX_ENDPOINT = terraform output -raw foundry_toolbox_endpoint
..\.venv\Scripts\ai-perf.exe provision-toolbox
Set-Location ..
```

The Toolbox provisioner creates or reuses the version containing the remote
synthetic MCP catalogue and tool search. The public MCP endpoint is appropriate
only for these read-only synthetic tools.

### 13.4 Run smoke and the one-lever confirmation

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile smoke `
  --warmups 1 `
  --repetitions 2

.\.venv\Scripts\ai-perf.exe run-suite `
  --profile screen `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904
```

### 13.5 Run the combined confirmation

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile bundle `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904
```

### 13.6 Inspect and validate

```powershell
.\.venv\Scripts\ai-perf.exe summarize results\raw\<result-file>.jsonl
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform validate
terraform -chdir=terraform plan
```

The completed implementation passed 46 automated tests, Ruff, Pylance source
diagnostics, Terraform validation, and a live zero-drift plan.

The Terraform-managed Container Apps job defaults to a functional integration
screen, not a publication-sized run. Follow the
[infrastructure guide](../terraform/README.md) for the cloud job path and use
an execution-only override when changing repetitions so the Terraform template
does not drift.

### 13.7 Clean up

After exporting any required private artifacts, remove the lab resources:

```powershell
terraform -chdir=terraform destroy
```

## 14. Execution and artifact record

| Scope | Container Apps execution | Blob prefix | Measurements |
|---|---|---|---:|
| 51-case preflight | `job-aiperf-6l2kni-zicg036` | `20260904T164428Z` | 51 |
| Text | `job-aiperf-6l2kni-nnc62o6` | `20260904T165156Z` | 270 |
| Image | `job-aiperf-6l2kni-iyrljso` | `20260904T170420Z` | 300 |
| File | `job-aiperf-6l2kni-nd92mw3` | `20260904T171753Z` | 330 |
| Tool catalogue | `job-aiperf-6l2kni-9xd9xfk` | `20260904T173143Z` | 450 |
| Tool integrations | `job-aiperf-6l2kni-l64rem0` | `20260904T181348Z` | 210 |
| Corrected client comparison | `job-aiperf-6l2kni-b6oe74l` | `20260904T183141Z` | 240 |
| Bundle preflight | `job-aiperf-6l2kni-o8k8z7g` | `20260904T203720Z` | 12 |
| Non-optimized Standard (PAYGO), Optimized Standard (PAYGO), and Optimized + Priority Processing confirmation | `job-aiperf-6l2kni-3rl9th4` | `20260904T203946Z` | 360 |

The bundle execution is marked failed by Container Apps because the CLI exits
nonzero after uploading artifacts when any observation fails. All 360
scheduled attempts were recorded; 359 completed successfully and correctly,
and all three artifacts were uploaded before that exit.

An earlier attempted bundle launch used an incorrectly shaped execution
override and reran the old screen profile. It is excluded from every count and
conclusion.

For image digests and the exact superseded-row audit, see
[Publication-oriented Azure benchmark results](./publication-results.md).
Raw cloud artifacts remain in private storage because they contain deployment
metadata; the linked ledger is the public numerical source of truth.

## 15. References

- [AI response performance testing guidelines](./ai-response-performance-guidelines.md)
- [AI response performance Copilot skill](../.github/skills/ai-response-performance/SKILL.md)
- [Benchmark plan](./benchmark-plan.md)
- [Publication result ledger](./publication-results.md)
- [Use the Azure OpenAI Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses)
- [Configure image detail level](https://learn.microsoft.com/azure/foundry/openai/how-to/gpt-with-vision#configure-image-detail-level)
- [Prompt caching](https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching)
- [Enable Priority Processing for Microsoft Foundry models](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing)
- [Compare Standard, Priority Processing, and Provisioned Throughput](https://learn.microsoft.com/azure/foundry/openai/concepts/provisioned-throughput#deployment-categories-compared)
- [Enable tool search in a toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search)
- [Announcing Priority Processing in Microsoft Foundry for Performance-Sensitive AI Workloads](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/announcing-priority-processing-in-microsoft-foundry-for-performance-sensitive-ai/4504788)
- [Distillation: Turning Smaller Models into High-Performance, Cost-Effective Solutions](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/distillation-turning-smaller-models-into-high-performance-cost-effective-solutio/4355029)
- [Choosing a real-time voice architecture on Microsoft Foundry: three enterprise patterns](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/choosing-a-real-time-voice-architecture-on-microsoft-foundry-three-enterprise-pa/4552676)
- [Retrieval-augmented generation in Azure AI Search](https://learn.microsoft.com/azure/search/retrieval-augmented-generation-overview)
- [Boost RAG Performance: Enhance Vector Search with Metadata Filters in Azure AI Search](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/boost-rag-performance-enhance-vector-search-with-metadata-filters-in-azure-ai-se/4208985)
- [Choose an approach for optimizing vector storage and processing](https://learn.microsoft.com/azure/search/vector-search-how-to-configure-compression-storage)

## 16. Conclusion

The dominant lesson is not "use one magic feature." It is to remove work from
the critical path while preserving correctness:

- generate less;
- avoid reprocessing stable input;
- choose task-appropriate multimodal representations;
- keep tool context focused;
- remove avoidable serial waits and model rounds;
- reuse expensive discovery state;
- buy a faster processing tier only after verifying that the request actually
  received it.

Those choices produced large median improvements in this lab, but the tails
and reliability events prevented a simplistic victory claim. The practical
engineering rule is therefore:

> Optimize the complete, correctly completed task--not the fastest isolated API
> response.

Use that performance evidence as one architecture input, then apply the
required quality, cost, data-residency, security, compliance, availability,
and operational gates for the production workload.
