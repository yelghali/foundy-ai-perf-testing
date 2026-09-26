# How to make AI responses faster on Microsoft Foundry: lessons from 2,040 measurements

![Grouped bars compare median AI-path latency for non-optimized Standard pay-as-you-go, optimized Standard pay-as-you-go, and optimized with Priority Processing across text, image, file, and function tool workloads; total reductions range from 23% to 50%.](./images/ai-response-latency-hero.png)

A faster model does not always make an AI application faster.

Latency also comes from output length, repeated prompt content, image and document processing, tool selection, connection setup, serial waits, and extra model requests.

Comparing complete configurations, optimized software plus verified Priority Processing reduced median AI-path latency by **23% to 50%**, depending on the workload, versus non-optimized Standard pay-as-you-go. This result does **not** isolate the effect of Priority Processing.

> **Want the short version?**
>
> - Remove unnecessary output, visual processing, and tool definitions.
> - Reuse stable prompt prefixes and app-managed MCP sessions.
> - Remove serial waits and model rounds, then test Priority Processing on the work that remains.
>
> Measure correctness and reliability with latency. A fast wrong answer is not a performance improvement.

[Jump to the decision guide](#a-practical-decision-guide).

## What we measured

Each measurement represents one execution of a specific scenario, variant, and fixture. Each case produced 30 measured observations across five deterministic fixtures in a seeded randomized schedule. Treatment and control were paired when they ran against the same fixture and round in one execution.

The analyzed dataset contains **2,040 measurements**. The audit trail contains 2,160 benchmark executions recorded during the publication campaign, excluding cloud preflight checks; 120 earlier client-lifecycle runs were excluded after we corrected the timing boundary.

Automated deterministic scorers checked required fields, facts, tool calls, and arguments. Failed and incorrect runs remain in reliability counts; we calculate latency percentiles only from correct completions and do not silently retry failures.

**AI-path latency** starts immediately before a model request or an orchestrated model-and-tool workflow and stops when that response or workflow completes. Validation determines whether the result enters the latency analysis, but validation time is outside the primary timer. User-to-application networking, UI rendering, and preprocessing such as image resizing, PDF generation, text extraction, or OCR are also excluded.

The benchmark ran on **4 September 2026** using one Azure account with resources in East US 2. Runs executed one benchmark case at a time, except where a treatment explicitly tested internal request or tool fan-out. The combined benchmark used a Global Standard deployment, so East US 2 identifies the resource region, not a guarantee that inference processing remained there. The individual-optimization tests used `gpt-4.1-mini`; the combined benchmark used `gpt-4.1`, version `2025-04-14`. This was not a load test, and percentages from the two result sets should not be combined.

The fixtures were synthetic and deterministic. The combined benchmark reused the same fixture families, so it was not an independent replication on held-out production inputs. We used 5,000-sample bootstrap intervals for median effects; intervals were not adjusted for multiple comparisons, and p95 from 30 observations is descriptive. The [lab report](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/lab-report.md) documents the protocol and limitations; the [result ledger](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/publication-results.md) contains execution IDs, artifact versions, intervals, and reliability events.

## Results at a glance

The table below summarizes the most decision-relevant one-lever results.

| Change tested | Workload | Observed median result | Important qualification |
|---|---|---:|---|
| Generate a concise text answer | Text | **26.0% faster** | 29/30 correct; one stream ended before completion |
| Generate concise JSON | Image | **24.9% faster** | 30/30 correct |
| Reuse a cacheable prompt prefix | Text / image | **14.9% / 23.6% faster** | Requests had to report cached tokens |
| Use low image detail | Image | **17.8% faster** | Fine text and visual evidence must remain accurate |
| Send already-extracted text instead of a PDF | File | **17.2% faster AI path** | Extraction or OCR time was outside the timer |
| Process three independent pages concurrently | File | **56.8% faster** | Same three model requests; only scheduling changed |
| Request two required functions in one model response | Function tools | **28.2% faster** | Mainly one fewer model request, not just parallel handlers |
| Expose five tools instead of 20 | Function tools | **16.8% faster** | The required tool must remain available |
| Use minimal tool descriptions | Function tools | **14.4% faster** | Selection and arguments must stay correct |
| Reuse an app-managed MCP session | MCP | A cold session was **34.1% slower** | Requires safe lifecycle and recovery handling |
| Add tool search to a 50-tool Toolbox | Toolbox / MCP | **43.0% slower p50** | Input tokens fell 26%; 30/30 vs 29/30 correct, with a lower descriptive p95 |

These are workload-specific findings, not service guarantees. A result was labelled faster only when its paired 95% interval for the median effect excluded zero.

## 1. Remove work the task does not need

### Generate only the required output

The clearest supported text optimization was shortening the output contract.

For text, requesting a compact answer reduced median latency from **2,078 ms to 1,537 ms**, a **26.0%** improvement among correct completions.

For image extraction, concise JSON reduced the median from **1,646 ms to 1,237 ms**, a **24.9%** improvement with 30/30 correct completions.

This does not mean every answer should be terse. It means the model should not generate content that the next application step discards.

A UI card may require five fields. A routing step may require one enum. A tool planner may need only validated arguments. Define that contract explicitly, then verify that the shorter response still satisfies the product requirement.

Reducing input is different. Removing 12 irrelevant history turns lowered the observed text median by 12.7%, but the paired 95% confidence interval included zero. That result was inconclusive for this small test. Removing irrelevant context can still reduce input-token cost, but this lab does not claim a proven latency improvement for that treatment.

### Use only the visual representation the task requires

Low image detail was **17.8% faster** than high detail for extracting invoice ID, total, and status.

Low detail is not the same as resizing the source file. The full image is still sent, but `detail: "low"` asks the service to analyze a **512 x 512 representation** instead of using high-resolution tiled inspection. See [Configure image detail level](https://learn.microsoft.com/azure/foundry/openai/how-to/gpt-with-vision#configure-image-detail-level).

This can work well for large, clearly printed fields, but it can miss small text, handwriting, charts, or spatial evidence. Start low only when deterministic validation confirms that every required field remains accurate.

Image resizing also lowered the median by 12.8%, but descriptive p95 increased from **5.1 seconds to 8.8 seconds**. That does not invalidate the median result, but the slower tail-latency observations require further investigation. Local resize time was also outside the AI-path timer.

For files, sending already-extracted text was **17.2% faster** than native PDF input. The claim is intentionally narrow: extraction or OCR happened before the timer.

Use text when the task depends only on textual facts. Keep native document processing when layout, signatures, charts, handwriting, or other visual evidence matters. A full-pipeline decision must include extraction cost and reliability.

## 2. Reuse work and connections

### Put repeated prompt content first

Prompt caching does not store the model's answer. It temporarily reuses work the service already performed on the **beginning of a long input**. The first request is processed normally; later requests can reuse the matching prefix.

For the `gpt-4.1` models in this lab, an eligible request required at least 1,024 input tokens. The first 1,024 tokens had to match a recent request.

The service does not cache request fields independently. It starts at the beginning and reuses matching content only until the first change. That is why request order matters.

Here is a simplified Responses API request:

```json
{
  "model": "<deployment-name>",
  "instructions": "[REUSABLE] Stable system instructions, examples, and output rules",
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "[REUSABLE] Reference content shared by many requests"
        },
        {
          "type": "input_text",
          "text": "[CHANGES] The current user's question"
        }
      ]
    }
  ]
}
```

The reusable beginning can contain system instructions, examples, output rules, tool definitions, or shared reference text. Keep it identical and put it first. Put the current question, request ID, image, document, or other changing content afterward.

If a timestamp or request ID appears at the beginning, requests differ immediately and the stable instructions that follow cannot form one long matching prefix.

Warm-prefix caching reduced text median latency by **14.9%** and image median latency by **23.6%**. Average text time to first token fell from 991 ms to 602 ms.

We verified the mechanism instead of assuming it worked. Roughly 93-100% of repeated requests reported a cache hit. Control requests changed a value at the beginning and reported no cached tokens.

> Put shared content first, put request-specific content last, and check `cached_tokens` in the response.

Caching did not produce a clear median improvement for file or function-tool tasks in this run. Reusing prompt work matters less when document processing, tool selection, or another stage dominates.

See [Prompt caching](https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching) for current eligibility and retention details.

### Avoid reconnecting to MCP for every task

When the application is the MCP client, connection setup and tool discovery can be a meaningful part of the critical path.

A reused session completed in **2,283 ms** at p50. Opening a new session and discovering tools for every task raised p50 to **3,061 ms**: the cold path was **34.1% slower than the reused path**. Setup and discovery averaged 1,016 ms; the local tool itself remained below 5 ms.

This is an application-lifecycle optimization, not a model optimization, and the result does not automatically apply to service-managed MCP.

Reuse a compatible session and its discovered tool catalog across tasks, or use a bounded pool when one session cannot safely serve the expected concurrency. Scope reuse by identity and tenant, and design for expiry, reconnect, credential rotation, catalog refresh, health checks, and failure isolation.

The repository includes the [complete MCP connection helper](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/src/ai_perf/mcp_client.py#L51-L96).

## 3. Remove serial waits and unnecessary model requests

### Run independent page requests concurrently

The largest supported one-lever effect came from processing three independent document pages concurrently.

Both configurations made the same three model requests. The sequential version waited for one response before starting the next. The concurrent version started all three before waiting for their results.

Median latency fell from **2,811 ms to 1,216 ms**, a **56.8%** improvement.

This is a scheduling result. It applies only when requests are independent and model quota can support the burst. Production code still needs bounded concurrency, timeouts, and partial-failure handling.

### Remove an avoidable model round from function workflows

The function-tool task needed both weather and local time:

```text
Slower: model -> weather -> model -> time -> model -> final answer
Faster: model -> weather + time -> model -> final answer
```

The faster design allowed one model response to request both functions. It reduced the workflow from three model requests to two and lowered p50 from **3,646 ms to 2,617 ms**, a **28.2%** improvement.

The synthetic handlers completed in under 5 ms, so most of the benefit came from removing a model request. Running the handlers concurrently is a separate mechanism.

For app-run functions:

- allow the model to request multiple calls;
- validate tool names and arguments;
- confirm that calls are independent and safe to overlap;
- run asynchronous I/O together;
- return one output for every original call ID;
- ask the model for the final answer after all required results arrive.

`parallel_tool_calls=True` permits multiple calls but does not guarantee that the model selects every required tool. `asyncio.gather` overlaps asynchronous I/O; it does not make blocking synchronous code parallel.

The 28.2% result applies to app-executed function tools. It should not be transferred to service-managed MCP or Foundry Agent Service without a separate benchmark and traces showing actual execution behavior.

## 4. Limit the tools available to each request

Tool definitions are part of the model input. Even when the actual function runs in milliseconds, selection and final generation can take seconds.

Reducing the active catalogue from 20 function tools to five lowered p50 by **16.8%**. Using minimal descriptions lowered p50 by **14.4%**.

The useful design pattern is:

1. route the request to a domain;
2. expose only that domain's relevant tools;
3. keep names, descriptions, and schemas concise but discriminative;
4. validate selection and arguments, not token count alone.

Other tool-schema treatments were inconclusive at this sample size. Exposing 50 tools, adding complex schemas, making descriptions ambiguous, and reordering definitions did not produce a statistically supported change in median latency. Some descriptive p95 values were slower, but 30 attempts are not enough to conclude that those treatments consistently damage tail latency.

### Toolbox can improve selection, but adds a search round

Microsoft Foundry Toolbox tool search keeps a large tool catalog out of the initial prompt and discovers relevant tools when needed.

In this synthetic 50-tool test, it reduced average input tokens by **26%** and completed correctly **30/30** times versus **29/30** for direct MCP. However, the extra search round increased p50 from **2,528 ms to 3,614 ms** - a **43.0% increase**.

This single test does not prove that Toolbox generally improves accuracy. It shows the trade-off: use tool search when catalog size, context pressure, or tool selection is the main problem. If first-response latency matters most and the application already knows the relevant subset, exposing that smaller subset directly can be faster.

See [Tool search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search) and the [Toolbox overview](https://learn.microsoft.com/azure/foundry/agents/concepts/toolbox-overview).

## 5. Test Priority Processing after software optimization

Our first Priority Processing-labelled requests taught an important validation lesson: the selected model did not support the requested tier, and every response reported `service_tier=default`.

We kept those observations in the audit trail but excluded them as Priority Processing evidence.

Unlike the individual-optimization tests on `gpt-4.1-mini`, the combined benchmark used a supported `gpt-4.1` deployment. Every successful Priority Processing response reported `service_tier=priority`.

We compared:

1. non-optimized Standard pay-as-you-go;
2. optimized Standard pay-as-you-go;
3. the same optimized setup with Priority Processing.

| Workload | Non-optimized Standard | Optimized Standard | Optimized + Priority Processing | Combined improvement |
|---|---:|---:|---:|---:|
| Text | 2,070 ms | 2,125 ms | 1,222 ms | **41.0% faster** |
| Image | 2,872 ms | 2,234 ms | 1,448 ms | **49.6% faster** |
| File | 1,512 ms | 1,245 ms | 1,165 ms | **23.0% faster** |
| Function tools | 3,817 ms | 2,824 ms | 2,393 ms | **37.3% faster** |

Every value is median AI-path latency. The combined improvement compares optimized software plus Priority Processing with non-optimized Standard.

Software alone clearly improved the image, file, and function-tool workloads. The optimized text configuration produced an inconclusive result on `gpt-4.1`.

Adding Priority Processing to the optimized setup lowered observed p50 in all four workloads. The paired interval excluded zero for text and image, but crossed zero for file and function tools; the incremental effect was therefore inconclusive for those two workloads.

Standard completed correctly 240/240 times. Priority Processing completed correctly 119/120 times, with one function-tool failure. For file and function-tool workloads, descriptive p95 was slower under Priority Processing than under optimized Standard in this run. With 30 attempts per arm, that is a reason to gather more tail observations before setting an SLO, not a firm tail-latency conclusion.

Priority Processing is pay-as-you-go at its own rate. Provisioned Throughput reserves dedicated capacity measured in PTUs; it was outside this comparison. We did not calculate currency cost, so evaluate current regional pricing separately. Review the current [deployment categories](https://learn.microsoft.com/azure/foundry/openai/concepts/provisioned-throughput#deployment-categories-compared) and [Priority Processing documentation](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing) before selecting a processing option.

## What did not produce a clear median improvement

Negative and inconclusive findings are part of the result:

- `gpt-4.1-nano` was not consistently faster than `gpt-4.1-mini`; it was **25.0% slower** for the tested image task;
- removing 12 irrelevant text-history turns was inconclusive for latency;
- recreating the SDK client was inconclusive;
- selecting one PDF page instead of three was inconclusive;
- prompt caching was inconclusive for the tested file and function-tool tasks;
- many-parameter and nested schemas, ambiguous descriptions, and reordered tool definitions were inconclusive.

These findings do not prove that the changes never help. They show that model names, token counts, and architectural intuition are not performance evidence. Test the real task, score correctness, retain failures, and identify which stage actually dominates.

## A practical decision guide

| Likely source of delay | What to test | What must remain true |
|---|---|---|
| Long generated responses | Request only the required output | The answer remains complete and correct |
| Repeated long prompt content | Move stable content first and keep it identical | Responses report cached tokens |
| Image processing | Try low detail | Fine text and required visual evidence remain accurate |
| Document representation | Compare native PDF with extracted text | Extraction time is included and visual evidence is preserved when needed |
| Independent page requests | Run them concurrently | Requests are independent and quota supports the burst |
| Extra model rounds between tools | Request required functions in one model response | The same functions and arguments are selected |
| Slow independent app-run functions | Overlap asynchronous I/O | Side effects, quotas, timeouts, and failures are safe |
| Large static tool surface | Route to a smaller relevant catalogue | The correct tool remains available |
| Large dynamic catalogue | Test Toolbox tool search | Token and selection benefits justify the search round |
| Repeated MCP setup | Reuse the app-managed session | Authentication, expiry, reconnect, and isolation remain safe |
| Provider processing time | Test Priority Processing | Returned tier, p50, p95, reliability, quality, cost, and residency meet the goal |

Use the following sequence for each experiment:

1. define what a correct answer must contain;
2. name the timer's exact start and stop;
3. pair control and treatment on representative fixtures;
4. randomize which one runs first;
5. retain failures in the reliability result;
6. calculate latency only from correct completions;
7. test compatible winners together instead of adding isolated percentages.

## Reproduce or inspect the lab

The [AI response performance benchmark repository](https://github.com/yelghali/foundy-ai-perf-testing) contains the benchmark implementation, Terraform environment, deterministic fixtures, raw-result processing, and reports. The linked URL retains the project's original `foundy-ai-perf-testing` slug.

Follow the repository README to configure the Azure environment and run the included smoke, one-lever, and combined benchmark profiles. Start with the smoke profile before paid benchmark rounds. Use synthetic or approved data, confirm quota and expected cost, and replace the included fixtures with examples that represent the production workload.

The repository also includes:

- an [AI response performance testing guide](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/ai-response-performance-guidelines.md);
- the full [lab report](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/lab-report.md);
- the auditable [publication result ledger](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/publication-results.md);
- an [AI response performance Copilot skill](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/.github/skills/ai-response-performance/SKILL.md) for applying the method to another repository.

Start with the real task: define correctness, measure each stage, remove avoidable work, and then test the platform options that target the time still left in the critical path.
