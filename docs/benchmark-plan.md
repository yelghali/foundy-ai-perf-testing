# AI Response Performance Benchmark Plan

## Purpose

Determine which practical choices make AI applications respond faster across
different workloads without unacceptable losses in quality, reliability, or
cost.

The project asks:

> Which performance levers work consistently across text, images, files, and
> tool calling, and which are useful only for specific workloads?

The deliverables are working benchmark code, raw and summarized results,
evidence-based recommendations, and a later technical article based on measured
results.

The original vision-latency notes are hypotheses, not accepted conclusions.
Model-specific token calculations, cache controls, expected speedups, and API
parameters must be verified against the Azure model, deployment, API, and SDK
versions used by each run.

## Functional scenarios

1. **Text chat**: a realistic conversational response.
2. **Image understanding**: classification and structured document extraction.
3. **File processing**: extraction or summarization of multi-page documents.
4. **Tool calling and MCP**: tool selection, execution, and final response.

RAG is a later, separate track because it introduces embedding, search,
filtering, reranking, and context-construction latency.

## Shared performance levers

1. Select a faster model that still meets the quality target.
2. Reduce generated output.
3. Reduce unnecessary input and context.
4. Reuse clients and connections.
5. Reuse stable prompt prefixes through verified prompt caching.
6. Compare Standard (PAYGO) and Priority Processing.
7. Stream output where perceived latency matters.

Streaming is a user-experience lever. It can improve time to first token without
reducing completion time.

Input reduction has workload-specific implementations:

- text: trim or summarize conversation history;
- image: resize or reduce image detail;
- file: select relevant pages or extract relevant text;
- tools: expose fewer relevant tools and simplify definitions.

Results remain separate by scenario. Raw milliseconds must not be averaged
across unrelated workloads.

## Experiment strategy

### Avoid a Cartesian product

Each scenario has a fixed baseline. Change one lever at a time, measure it, and
restore the baseline before testing the next lever.

The implemented screen has 49 core configurations: shared single-lever cases
for all applicable scenarios plus focused image, file, tool, and MCP
experiments. When the remote MCP and Foundry Toolbox endpoints are configured,
the screen adds two controlled 50-tool cases for a total of 51:

- direct remote MCP, with all 50 tool definitions exposed to the model;
- Microsoft Foundry Toolbox Tool Search over that same remote MCP catalogue.

Using the same server, tool implementations, task, model, and region keeps the
comparison focused on full exposure versus managed tool discovery rather than
confounding it with different tool backends.

Every scenario/lever pair is classified as:

- applicable;
- applicable with conditions;
- not applicable.

Do not create artificial workloads merely to make a lever applicable. For
example, do not pad a short prompt to manufacture a cache test.

### Screen, confirm, combine

1. Run three unmeasured warm-ups.
2. Run ten measured requests for initial screening.
3. Advance only changes with meaningful latency improvement and acceptable
   quality, reliability, and cost.
4. Confirm with at least 30 measured randomized rounds. In each round, execute
   every case once in a seeded random order and use the same fixture index for
   each case in that scenario. This randomized complete-block design reduces
   time-of-run and fixture confounding while preserving paired comparisons.
5. Rotate through five deterministic fixtures per scenario rather than
   repeatedly measuring one prompt, receipt, document, or tool request.
6. Report bootstrap 95% confidence intervals for medians and paired p50
   changes. Treat an interval excluding zero as evidence of direction, not as
   a universal guarantee or a substitute for independent replication.
7. Retain failures in the attempted-request count. Compute latency percentiles
   only from successfully completed requests that pass the quality gate.
8. Combine winners into only two bundles:
   - a low-cost software bundle;
   - a maximum-performance bundle that also uses the best suitable model and
     Priority Processing.

Test baseline and winning bundles under concurrency after single-request
screening. Suggested levels are 1, 5, 10, and 20 concurrent requests where
quota permits. Persist the requested concurrency in each raw observation so
separate job executions remain comparable.

### Non-optimized-to-optimized confirmation

Keep every one-lever result as the evidence for what each individual change
contributed. Add a separate `bundle` profile to answer the deployment question:
how much faster is a workload after combining only compatible, strongly
supported findings?

Run three arms for each functional scenario:

1. `bundle-worst-standard`: an intentionally non-optimized but valid Standard
   (PAYGO) reference configuration;
2. `bundle-best-standard`: the compatible supported software improvements;
3. `bundle-best-priority`: the same optimized configuration with Priority
   Processing.

All three configurations use the same `gpt-4.1` model deployment used for
Priority Processing, model version, account, region, five fixtures, and
randomized round schedule. The first two explicitly request the `default`
service tier. The third requests `priority`. Use non-streaming Responses API
calls because Azure documents that the returned tier can be incorrect for
streaming Priority Processing responses. Reject a Priority Processing
conclusion unless every accepted Priority Processing observation reports
`service_tier = priority`.

The compatible bundle choices are:

| Scenario | Non-optimized Standard (PAYGO) | Optimized Standard (PAYGO) and Optimized + Priority Processing |
|---|---|---|
| Text | Cold long prefix, full history, normal output | Warm prefix cache and concise output |
| Image | Cold long prefix, high detail, normal output | Warm prefix cache, low detail, concise JSON |
| File | Native full PDF | Extracted text |
| Tools | 20 concise tools, one tool selection per model round | Five minimal tools, both tools selected in one model round and executed concurrently |

Do not include findings that were inconclusive or had worse tail behavior, such
as client recreation, smaller-model selection, image resizing, file/tool cache
reuse, or verbose tool descriptions. Run three warm-ups and 30 measured
randomized complete-block rounds. Report paired effects for Optimized Standard
(PAYGO) versus Non-optimized Standard (PAYGO), and for Priority Processing
versus Optimized Standard (PAYGO), per scenario. Never average raw milliseconds
across scenarios.

## Scenario design

### Text chat

Test model selection, concise output, history reduction, connection reuse,
verified caching for a realistic long stable prompt, Standard (PAYGO) versus
Priority Processing, and streaming.

### Image understanding

Use labelled examples for simple classification, document classification,
structured receipt or invoice extraction, and difficult small text. In
addition to shared levers, test resizing, low versus high detail, and a
low-detail-first cascade that escalates uncertain cases.

### File processing

Use controlled multi-page documents with expected outputs. Test full document
versus selected pages, native file input versus extracted text, and sequential
versus parallel page processing.

### Tool calling and MCP

Measure these stages independently:

```text
MCP connection and discovery
-> model tool selection
-> tool execution
-> final model generation
-> completed task
```

The primary release gates are correct-completion rate over all attempts and
completed-task latency conditional on a correct completion.

Use a 20-tool baseline with concise, distinctive descriptions, moderate
schemas, stable ordering, and a reused MCP session. Change one factor at a time:

- tool count: 5, 20, and 50;
- description style: minimal, concise/distinctive, and verbose;
- schema complexity: simple, many parameters, and nested schemas;
- tool ambiguity: distinct versus overlapping responsibilities;
- exposure: all tools versus a deterministic or lightweight selected subset;
- lifecycle: cold discovery versus a reused session and cached catalogue;
- integration: identical native function definitions versus MCP;
- discovery: all 50 remote MCP definitions versus Foundry Toolbox Tool Search;
- cache stability: stable versus reordered or modified definitions;
- orchestration: one tool selection per model round versus selecting
  independent tools in one round and executing them concurrently.

Do not assume fewer tools are always better. Tool-definition tokens, selection
accuracy, argument validity, retries, and total latency must be measured
together. A model-based tool router adds an inference call and must prove that
its selection benefit offsets its latency and cost.

The Foundry comparison records these stages separately:

```text
Toolbox connection and MCP discovery
-> model selects tool_search
-> Toolbox BM25 search
-> model selects the discovered tool
-> tool execution
-> final model generation
```

Tool Search initially exposes the `tool_search` and `call_tool` meta-tools
instead of the full catalogue. Correctness accepts either `call_tool` or direct
invocation of a discovered namespaced tool because both paths have been
observed and successfully executed by the managed Toolbox endpoint. Record the
actual call path and model-call count rather than assuming a fixed path.

Sequential and parallel tool execution use the same two-tool task. The
sequential control permits one tool call per model round; the parallel variant
permits both independent calls in one round. Do not compare a two-tool parallel
task with the one-tool native baseline. Record model-call count explicitly:
this comparison combines one fewer model-selection round with concurrent tool
execution and does not isolate backend parallelism.

## Measurements

Capture:

- connection or setup time where measurable;
- time to first byte;
- time to first token;
- time to first and complete tool call;
- tool execution duration;
- final generation duration;
- named request, AI-path, workflow, or user-journey latency with exact timer
  boundaries;
- output tokens per second;
- input, output, reasoning, and cached tokens;
- serialized tool-definition size and token estimate;
- model, deployment, region, processing tier, API, and SDK versions;
- streaming state, concurrency, retries, status, and estimated cost;
- task correctness and quality.

Report p50 plus descriptive p95 and p99 during a 30-round screen. Add p50
bootstrap intervals and baseline-relative paired effect intervals for
confirmation. Use a separate, adequately sampled run across time windows for
production p95 or p99 conclusions.
Retain raw JSONL observations, including the schedule seed, round, position,
fixture, actual service tier, errors, and quality failures.

For prompt-cache comparisons, place a per-request nonce before the otherwise
stable long prefix in the cold case. Verify zero observed cached tokens in the
cold cohort and positive cached tokens in the warm cohort. Compare warm cache
to that controlled cold case, not to the shorter scenario baseline.

## Quality gates

Define correctness per scenario:

- text: rubric and required facts;
- image/file extraction: field-level accuracy;
- classification: exact label accuracy;
- tools: correct tool, valid arguments, and correct final answer.

A faster result is not an optimization if it no longer completes the task.

## Milestones

1. Benchmark core, timing, JSONL output, summaries, and correctness hooks.
2. One stable baseline for text, image, file, native tools, and MCP.
3. Shared-lever screening across applicable scenarios.
4. Tool/MCP deep dive.
5. Winning bundles, confirmation samples, and controlled concurrency.
6. Separate RAG benchmarks for metadata filters, top-k, hybrid search,
   reranking, chunking, and caches.
7. Technical article covering successful, workload-specific, ineffective, and
   quality/cost-sensitive techniques.

Comparing existing large and small models is model selection, not distillation.
Distillation belongs in the article as future work unless this project actually
trains and evaluates a distilled model.
