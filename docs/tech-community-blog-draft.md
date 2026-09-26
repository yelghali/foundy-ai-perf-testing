# How to make AI responses faster on Microsoft Foundry: lessons from more than 2,000 benchmark runs

![Grouped bars compare median AI-path latency for non-optimized Standard
pay-as-you-go, optimized Standard pay-as-you-go, and optimized with Priority
Processing across text, image, file, and function tool workloads;
total reductions range from 23% to 50%.](./images/ai-response-latency-hero.png)

**More than 2,000 measured Azure benchmark runs show where AI latency hides,
which changes helped, and which common "optimizations" did not.**

A faster model does not always produce a faster AI application. Time can
disappear into long outputs, repeated prompt content, image processing,
document rendering, tool selection, connection setup, or an extra model
request.

We built a reproducible performance lab on Microsoft Foundry to isolate those
stages. We tested text, images, files, function tools, Model Context Protocol
(MCP), and Microsoft Foundry Toolbox, changing one lever at a time and checking
every answer. We then tested the strongest compatible changes together.

Function tools and MCP are both ways to use tools, but the execution paths
differ. In this lab, our application ran the function handlers and acted as
the MCP client, including when it connected to the Toolbox MCP endpoint. We did
not benchmark a prompt or hosted agent in Foundry Agent Service.

We compare two latency measurements. **p50, or the median, represents a
typical task attempt:** half of the attempts were faster and half were slower.
**p95 highlights occasional slow task attempts:** about 95 of 100 attempts
finished within that time, while about five took longer. The opening chart
shows p50; the analysis also checks p95 and correctness.

We compared three configurations: non-optimized Standard pay-as-you-go
(PAYGO), optimized Standard (PAYGO), and the same optimized configuration
with verified Priority Processing. **Depending on the workload, combining
software optimization with Priority Processing cut median latency in the
measured AI path by 23% to 50%.**

That is a combined result, not the effect of Priority Processing alone. The
route to the result--and the changes that did not help--is the useful part.

Three Microsoft Foundry processing options are relevant:

- **Standard (PAYGO)** uses shared capacity and pay-per-token billing. Both
  Standard configurations in this lab used this processing mode.
- **Priority Processing** is also pay-as-you-go, at the Priority Processing
  rate. It targets more consistent low latency for supported models without
  reserving capacity in advance.
- **Provisioned Throughput** reserves dedicated capacity measured in
  Provisioned Throughput Units (PTUs). We did not compare PTU in this lab.

See the official
[deployment-category comparison](https://learn.microsoft.com/azure/foundry/openai/concepts/provisioned-throughput#deployment-categories-compared)
and [Priority Processing documentation](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing).

> **Want the short version?**
>
> 1. Remove work the task does not need.
> 2. Reuse cacheable prompt prefixes and MCP sessions you manage.
> 3. Remove serial waits and unnecessary model requests.
> 4. Use Priority Processing for supported, latency-sensitive workloads.
>
> Check correctness at every step, and test the final combination instead of
> adding isolated percentages.

[Jump to the practical decision guide](#a-practical-decision-guide). You can
also apply the same method to your workload by installing the repository's
[AI response performance skill](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/.github/skills/ai-response-performance/SKILL.md)
as a project or personal Copilot skill. Agent skills work in VS Code agent
mode and load when relevant.

## The result at a glance

Using five deterministic fixtures and 30 randomized paired rounds, we changed
one lever at a time, labelled a result faster only when the paired 95% range
for its median change excluded zero, and treated p95 as descriptive; the
[detailed lab report](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/lab-report.md)
documents the full protocol, 2,160 task attempts, audit trail, and limitations.

| Change tested | Scenario | Observed result | What to verify before shipping |
|---|---|---:|---|
| Concise text output | Text | 26.0% faster; 29/30 correct | Completion rate meets the product objective |
| Concise JSON output | Image | 24.9% faster; 30/30 correct | Required fields remain accurate |
| Remove 12 irrelevant history turns | Text | 12.7% lower observed p50; inconclusive | Required context remains; repeat the test on real conversations |
| Warm prompt cache | Text / image | 14.9% / 23.6% faster | Cached tokens are actually reported |
| Low image detail | Image | 17.8% faster | Small text and fine visual evidence remain accurate |
| Already-extracted text | File | 17.2% faster AI path | Extraction cost and visual evidence are accounted for |
| Process independent pages at the same time | File | 56.8% faster | Pages are independent and limits allow concurrency |
| Request both functions in one model response | Function tools (app-run) | 28.2% faster, mainly from one fewer model request | The same functions are selected; model requests and tool execution are measured separately |
| Five function tools instead of 20 | Function tools (app-run) | 16.8% faster | The correct tool remains available |
| Shorter function tool descriptions | Function tools (app-run) | 14.4% faster | Selection accuracy does not fall |
| Add tool search to a 50-tool Toolbox | Foundry Toolbox (app-managed MCP) | 43.0% slower p50; 26% fewer input tokens | Smaller context or better selection justifies the extra search round |
| Reuse the MCP session | MCP (app-managed) | Avoided a 34.1% cold penalty | Session lifetime and failure recovery are safe |
| Combine optimized software with Priority Processing | Text / image / file / function tools | 23% to 50% faster than non-optimized Standard | Responses report `priority`; p50, p95, reliability, quality, cost, and data residency meet the goal |

These workload-specific findings are not service guarantees. Unless noted,
percentages are p50 AI-path changes among correct completions. The combined
23% to 50% result compares complete configurations, not Priority Processing
alone. The Toolbox result used an app-run model loop; the 28.2% function result
mainly reflects one fewer model request; and the MCP result covers setup reuse,
not parallel execution.

The pattern is: **remove unnecessary work, reuse prior work, remove serial
waits and model requests, then test Priority Processing for the provider time
that remains.** Production decisions must also account for quality, cost,
residency, security, compliance, availability, and operations.

## Measure a correct task, not just a fast request

A fast wrong answer is not a performance win. We kept failed and incorrect
attempts in the completion-rate calculation, but calculated p50 and p95 only
from correct completions.

The reported **AI-path latency** starts immediately before a model request or
model-and-tool loop, after local input preparation, and stops when the result
has been validated. It includes the measured model and tool stages, but
excludes user-to-application networking, UI rendering, image resizing, PDF
generation, and text extraction. It is not click-to-render latency.

One task attempt can contain several model requests and tool calls; an agent
invocation can too. This lab used direct Responses API workflows, not Foundry
Agent Service invocations.

## Finding 1: Generate only the output the application needs

The simplest latency lever was shortening the output contract.

For text, a compact answer reduced p50 from **2,078 ms to 1,537 ms**, or
**26.0%** among correct completions. One of the 30 streams ended before
`response.completed`, so this treatment completed correctly 29/30 times.

For images, concise JSON reduced p50 from **1,646 ms to 1,237 ms**, or
**24.9%**, with 30/30 correct completions.

This finding is specifically about output length. We also tested shorter text
input by removing 12 irrelevant history turns. The observed p50 fell from
2,078 ms to 1,813 ms, or 12.7%, but the paired interval crossed zero. The
latency effect was therefore inconclusive for this small text-history test.

We did not test very long conversations or retrieval from a large document
corpus; RAG remains a separate performance track with additional stages.
Removing irrelevant content is still sound cost and context hygiene because
it reduces the number of input tokens sent, provided the evidence needed for a
correct answer remains. That is a cost principle, not a measured latency
finding from this lab.

This is not "make every answer terse." It is "do not generate prose that the
next application step discards." A UI card may need five fields. A routing
decision may need one enum. A tool planner may need only valid arguments.
Asking for only that output reduces generation work and usually simplifies
validation. Before shipping, verify that answers are still complete.

## Finding 2: Put repeated prompt content first

Prompt caching does not store the model's answer. It temporarily reuses work
the service already did on the **beginning of a long input**. The first request
is processed normally; later requests can reuse the matching beginning. For
the `gpt-4.1` models in this lab, matching was automatic. An eligible request
needed at least 1,024 tokens, and its first 1,024 tokens had to be identical to
an earlier request.

The service does not cache request fields independently. It starts at the
beginning and reuses matching content only until it reaches the first change.
That is why request order matters.

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

The reusable beginning can contain system instructions, examples, output
rules, tool definitions, or shared reference text. Keep it identical and put
it first. The current question, request ID, image, or document usually changes,
so put it afterward; that changing part is processed normally.

If a timestamp or request ID appears first, the requests differ immediately.
The shared instructions that follow can no longer form one long matching
beginning.

In this lab, prompt caching reduced text p50 by **14.9%** and image p50 by
**23.6%**. It also reduced average text time-to-first-token from 991 ms to
602 ms.

We verified the cause rather than assuming the cache worked. Repeated requests
kept their beginning identical, and roughly 93-100% of them reported a cache
hit. Comparison requests changed a value at the very beginning and reported
no cache hits.

> Put shared content first, put request-specific content last, and check
> `cached_tokens` in the response.

See the Microsoft documentation for eligibility and retention details:
[Prompt caching](https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching).

Caching did not produce a clear p50 improvement for the file or function tool
tasks in this run. Reusing part of a prompt may have little effect when most of
the time is spent on document processing, tool selection, or another stage.

## Finding 3: Multimodal representation can dominate model time

### Use only the image detail the task requires

Low image detail was **17.8% faster** than high detail for extracting invoice
ID, total, and status. A low-detail-first cascade was 10.3% faster.

Low detail is not the same as resizing the source file. The full image is
still sent to the API, but the service analyzes a **512 x 512 representation**
instead of activating high-resolution tiled inspection. This reduces visual
work, but it can miss small print or fine evidence. See
[Configure image detail level](https://learn.microsoft.com/azure/foundry/openai/how-to/gpt-with-vision#configure-image-detail-level).

The cascade starts with low detail and sends a second high-detail request only
when validation fails. Start low only when the exact fields required by the
product continue to pass; charts, handwriting, spatial reasoning, and small
text may require high detail.

Image resizing produced a supported p50 improvement of 12.8%, while the
descriptive p95 rose from **5.1 seconds to 8.8 seconds**. This remains a
relevant candidate, not a rejected lever. Before using it, run more attempts
to see whether the occasional very slow responses happen consistently, and
include local resize time in the measurement.

### Avoid rendering a PDF when text is enough

With text already extracted, the AI request was **17.2% faster** than native
PDF input. Extraction or OCR time was outside the timer. That does not mean
"never send PDFs." Native PDF processing is useful when charts, page layout,
signatures, or other visual evidence matter. When the task is plain fact
extraction, rendering those pages is extra model-path work. Measure the parser
or OCR stage before making a full-pipeline decision.

Selecting only the relevant page did not produce a conclusive improvement.
The representation change--from rendered document to text--mattered more than
the page-count change in this workload.

## Finding 4: Remove serial waits, but distinguish the mechanism

Two changes produced large improvements, but for different reasons.

### Process independent pages at the same time

The largest one-lever effect came from processing three independent document
pages at the same time. Both versions made the same three model requests. Only
their scheduling changed: the sequential version waited for each response
before starting the next request, while the parallel version started all three
before waiting for their results.

p50 fell from **2,811 ms to 1,216 ms**, or **56.8%**.

### Function tools: remove an extra model request

The second test used function tools run by the app--not MCP and not Foundry
Agent Service. The task needed both weather and local time.

```text
Slower: model request -> weather function -> model request -> time function
        -> model request -> final answer
Faster: model request -> weather + time functions together
        -> model request -> final answer
```

Both versions executed the same two handlers. The faster design let one model
response request both, reducing the workflow from three model requests to two.
p50 fell from **3,646 ms to 2,617 ms**, or **28.2%**. Because the synthetic
handlers finished in under 5 ms, most of that improvement came from removing a
model request, not from overlapping function execution.

> One model response requesting several functions can remove a model round.
> Running those functions at the same time is a separate optimization that
> overlaps the work inside the tools.

### Run function tools in the application

For custom function tools, the application receives the names, arguments, and
call IDs, then runs the handlers. With a configured `AsyncOpenAI` client, tool
definitions, and an allow-listed handler map, the core flow is:

```python
import asyncio
import json

first_response = await client.responses.create(
    model=deployment_name,
    input="Give me the weather and local time in Paris.",
    tools=tools,
    parallel_tool_calls=True,
)

calls = [
    item
    for item in first_response.output
    if item.type == "function_call"
]

async def execute(call):
    arguments = json.loads(call.arguments)
    handler = tool_handlers[call.name]
    result = await handler(**arguments)
    return {
        "type": "function_call_output",
        "call_id": call.call_id,
        "output": json.dumps(result),
    }

outputs = await asyncio.gather(*(execute(call) for call in calls))

final_response = await client.responses.create(
    model=deployment_name,
    previous_response_id=first_response.id,
    input=outputs,
)
```

`parallel_tool_calls=True` permits several calls but does not guarantee that
the model will choose them. Validate names, arguments, and independence before
execution. `asyncio.gather` overlaps async I/O, not blocking synchronous code.
Only overlap independent, side-effect-safe work, and enforce downstream
timeouts and quotas.

See Microsoft's
[parallel function-calling guide for Chat Completions](https://learn.microsoft.com/azure/foundry/openai/how-to/function-calling#parallel-function-calling-with-multiple-functions),
the [Responses API guide](https://learn.microsoft.com/azure/foundry/openai/how-to/responses),
and the
[working implementation used by this lab](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/src/ai_perf/scenarios.py#L1093-L1169).

### MCP and Foundry agents: who controls execution?

- **App-managed function tools or MCP:** the application schedules calls,
  including when it consumes a Toolbox endpoint directly. Concurrency still
  depends on the client, server, and tools. This lab tested warm versus cold
  MCP setup, not parallel MCP calls.
- **Responses API remote MCP or a Foundry prompt agent:** the service owns the
  MCP loop. Current guidance does not promise parallel execution, so verify it
  with traces and server logs.
- **Code in a Foundry Hosted Agent:** your implementation controls scheduling;
  hosting alone does not enable concurrency.

In .NET Agent Framework code, `FunctionInvokingChatClient` invokes a batch of
model-requested functions serially by default. Set
`AllowConcurrentInvocation` to `true` for independent functions:

```csharp
var invokingClient = new FunctionInvokingChatClient(innerClient)
{
    AllowConcurrentInvocation = true
};
```

This applies to application-executed functions, not service-managed MCP. See
the
[`AllowConcurrentInvocation` reference](https://learn.microsoft.com/dotnet/api/microsoft.extensions.ai.functioninvokingchatclient.allowconcurrentinvocation)
and
[`FoundryAgent` integration behavior](https://learn.microsoft.com/agent-framework/integrations/by-component/agent-services/foundry#what-works-and-what-doesnt-with-foundryagent).
The 28.2% result therefore remains an app-run function-tool result; parallel
MCP or agent execution needs a separate controlled benchmark.

## Finding 5: Treat function definitions as prompt content

The catalogue, description, schema, ambiguity, and ordering experiments in
this section used function tools run by the app. Their workflow has more than
one latency stage:

```text
function definitions sent with the request
-> model selects the needed function or functions
-> application runs them
-> model produces the final answer
-> application validates the answer
```

The actual synthetic function executed in under 5 ms, yet the composed
function tool workflow took roughly 2-4 seconds. The dominant costs were model
requests, not function execution.

Reducing the active catalogue from 20 function tools to five lowered p50 by
**16.8%**. Using minimal descriptions lowered it by **14.4%**. In contrast,
exposing 50 function tools, adding complex schemas, making descriptions
ambiguous, and reordering definitions did not produce conclusive median
changes at this sample size. Some had slower p95 values, but 30 attempts are
not enough to conclude that they consistently cause occasional slow
responses.

That suggests a better design than handing every capability to every turn:

1. route the request to a domain;
2. expose only that domain's relevant tools;
3. keep names, descriptions, and schemas discriminative but economical;
4. validate selection and arguments, not token count alone.

## Finding 6: Foundry tool search trades latency for a smaller tool surface

Finding 5 reduced a static tool-definition payload by exposing fewer tools or
shortening their descriptions. Toolbox tool search instead reduces the initial
tool surface dynamically; it does not make each description shorter.

This app-managed comparison used the same 50-tool catalogue and direct model
loop in two ways:

- **direct remote MCP:** the application connected straight to the MCP server
  and exposed all tool definitions to the model;
- **Microsoft Foundry Toolbox with tool search:** the application connected to
  the Toolbox MCP endpoint, which initially exposed only `tool_search` and
  `call_tool`, then returned matching definitions.

Tool search reduced average input from **1,941 to 1,431 tokens**, about 26%.
It also achieved 100% correctness and a better p95 in this run. But the extra
search round raised p50 from **2,528 ms to 3,614 ms**, a **43.0% median
penalty**. Direct MCP completed correctly 96.7% of the time because one answer
omitted the requested value.

This is not a verdict against tool search. It is the trade-off tool search is
designed to make: keep a large catalogue out of the initial context, discover
relevant capabilities on demand, and potentially improve selection as the
catalogue grows.

Foundry ranks tool names, descriptions, and parameters with BM25 for this
flow. Toolbox exposes an MCP-compatible endpoint and is not limited to Agent
Service. See [tool search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search)
and the [Toolbox overview](https://learn.microsoft.com/azure/foundry/agents/concepts/toolbox-overview).

Use it when context size, catalogue scale, or selection quality is the main
problem. If first-turn latency matters most and a small relevant subset is
already known, direct exposure can be faster.

## Finding 7: Reuse app-managed MCP connections when the workflow allows it

A warm local MCP task completed in 2,283 ms at p50. Creating a cold session for
every task raised p50 to 3,061 ms--**34.1% slower**. Connection and discovery
averaged 1,016 ms; the local tool itself remained below 5 ms.

For this comparison, the benchmark application was the MCP client. MCP session
reuse is therefore an application lifecycle decision, not a model
optimization. Production implementations still need expiry, reconnect,
catalogue refresh, credential rotation, and failure isolation.

The code change is mainly where the application owns the connection. Assume
`connect_mcp()` opens the transport, initializes the MCP session, discovers
the tools once, and closes everything on exit.

For a batch or worker, open the connection outside the task loop:

```python
async with connect_mcp(MCP_URL) as mcp:
    for task in tasks:
        await handle_task(task, mcp)
```

For a FastAPI service, own it for the application lifespan instead of opening
it inside each request handler:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with connect_mcp(MCP_URL) as mcp:
        app.state.mcp = mcp
        yield

app = FastAPI(lifespan=lifespan)
```

Request handlers can then use `app.state.mcp`. Scope sessions by credential or
tenant boundary, and add health checks, reconnect, and catalogue refresh for a
long-lived service. If one session cannot safely serve the expected
concurrency, use a bounded pool rather than creating a connection per request.
See the lab's
[complete MCP connection helper](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/src/ai_perf/mcp_client.py#L51-L96).

## Finding 8: Use Priority Processing after software optimization

Our first requests labelled for Priority Processing taught an important
validation lesson. They used `gpt-4.1-mini`, and every response reported the
Standard tier. We retained the rows for the audit trail but excluded them from
Priority Processing evidence.

The final confirmation used `gpt-4.1`, version `2025-04-14`, on one Global
Standard deployment in East US 2. Standard configurations completed correctly
240/240 times; Priority Processing completed correctly 119/120 times, with one
function-tool failure. Every successful Priority Processing response reported
`service_tier=priority`.

The optimized software arm used warm-prefix caching with concise text output;
warm-prefix caching, low image detail, and concise JSON for images; extracted
text for files; and five minimally described tools with single-round two-tool
orchestration.

The one-lever screen used `gpt-4.1-mini`; this confirmation used `gpt-4.1`.
The table validates the complete configurations, not the independent transfer
of every isolated effect.

### The combined result

Every value below is median (p50) AI-path latency.

| Scenario | Non-optimized Standard (PAYGO) | Optimized Standard (PAYGO) | Optimized + Priority Processing | Improvement versus non-optimized Standard (PAYGO) |
|---|---:|---:|---:|---:|
| Text | 2,070 ms | 2,125 ms | 1,222 ms | **41.0% faster** [34.8%, 47.3%] |
| Image | 2,872 ms | 2,234 ms | 1,448 ms | **49.6% faster** [39.9%, 57.0%] |
| File | 1,512 ms | 1,245 ms | 1,165 ms | **23.0% faster** [13.7%, 33.2%] |
| Function tools | 3,817 ms | 2,824 ms | 2,393 ms | **37.3% faster** [25.2%, 48.9%] |

Each bracket is the paired 95% confidence interval for the p50 reduction.
The latency values include only correctly completed attempts; the completion
counts above retain the failed Priority Processing request.

Software alone clearly improved image, file, and function tool workloads. The
optimized text arm was inconclusive on `gpt-4.1`. Adding Priority Processing
to the optimized setup lowered the observed p50 in all four workloads:
**42.5% for text, 35.2% for image, 6.5% for file, and 15.3% for function
tools**. The evidence was clear for text and image. The file and function tool
results varied too much to confirm the size of their additional improvement.

Some file and function tool p95 values were slower, but 30 attempts are not
enough to draw a firm conclusion about occasional slow responses. That is a
reason to validate with more attempts, not evidence that Priority Processing
is ineffective.

> **Recommendation:** After removing avoidable application work, use Priority
> Processing for supported, latency-sensitive workloads. Verify that responses
> report `service_tier=priority`, then confirm that p50, p95, and reliability
> meet your workload's goals. This lab provides the strongest support for text
> and image workloads; file and function tool workloads need more data.

Also assess answer quality, cost, and data-residency requirements separately.
See
[Enable Priority Processing for Microsoft Foundry models](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing).

## How to read mixed and inconclusive results

p50 and p95 describe different parts of the same set of task attempts. They
can move in opposite directions when most attempts become faster but a few
slow outliers become much slower.

Image resizing produced exactly that pattern:

| Metric | Original image | Resized image | What changed |
|---|---:|---:|---|
| p50 | 1.65 seconds | 1.44 seconds | The typical call was 12.8% faster |
| p95 | 5.09 seconds | 8.80 seconds | A few of the slowest calls took longer |

This is not a contradiction. A typical resized-image attempt was faster, but
a few attempts took much longer. With only 30 attempts, p95 is determined by
roughly one or two of the slowest attempts. Treat it as a reason to test more,
not as proof that resizing always makes slow requests worse. Local resize time
was also outside the timer.

The p50 improvement was consistent enough across the paired runs to count as
a real finding in this lab. The p95 result says **investigate the occasional
slow attempts before shipping**; it does not erase the p50 improvement.

Test resizing again with more calls and include local resize time. The final
optimized configuration used the better-supported low-detail lever instead.

### No conclusive p50 improvement

- `gpt-4.1-nano` was not consistently faster than `gpt-4.1-mini`; it was
  **25.0% slower** for the tested image task;
- removing 12 irrelevant text-history turns, recreating the SDK client, and
  selecting one PDF page instead of three were inconclusive;
- file and function tool prompt-cache treatments were inconclusive;
- many-parameter and nested schemas, ambiguous descriptions, and reordered
  function tool definitions all had inconclusive p50 effects. Their
  descriptive p95 values varied in both directions, so this lab does not claim
  that they consistently help or hurt occasional slow requests.

This is why model labels, token counts, and architecture diagrams are not
performance evidence. Run the real task, score it, and retain the failures.

## A practical decision guide

Start with simple software changes. Test paid or architectural options only
after measuring what is still slow.

To turn the table below into a scoped experiment for your application, install
the repository's
[AI response performance skill](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/.github/skills/ai-response-performance/SKILL.md),
then ask Copilot in VS Code agent mode to apply it to a specific workflow.

| Likely source of delay | Scenario | What to try | What to verify before shipping |
|---|---|---|---|
| Long responses | Text / image | Ask only for the needed content | The answer remains complete and correct |
| Irrelevant conversation history | Text chat | Remove only context the task does not need | Required context remains; compare latency and input-token cost on larger real inputs |
| Repeated prompt content | Text / image | Put shared content first and keep it unchanged | Requests actually report cached tokens |
| Reasoning-model processing (not tested here) | Text / image / tools (model-dependent) | Compare supported `reasoning_effort` levels and choose the lowest that passes the quality bar | Correctness, p50, p95, reasoning tokens, incomplete responses, and cost |
| Image processing | Image | Try low detail | Small text and important details remain accurate |
| Document input | File | Compare PDF input with extracted text | Extraction or OCR time is included; needed visual information is preserved |
| Serial requests for independent pages | File | Send the same model requests at the same time | The pages are independent and model quota allows the burst |
| Extra model requests between required functions | Function tools (app-run) | Let the model request the functions in one response | The same functions are selected and the model-request count actually falls |
| Slow independent functions run by the app | Function tools (app-run) | Run their asynchronous I/O at the same time | The calls are independent; quotas, timeouts, and side effects remain safe |
| Function definition overhead | Function tools (app-run) | Expose only relevant tools and keep definitions concise and distinct | The correct tool and arguments remain accurate |
| Large dynamic tool catalogue | Toolbox / MCP | Test Foundry Toolbox tool search | The correct tool is found; the smaller context justifies the extra search round |
| MCP connection and discovery setup | MCP (app-managed) | Reuse the app-managed session and discovered tool list | Expiry, reconnect, authentication, catalogue refresh, and recovery still work |
| Service-managed MCP or Foundry Agent Service | MCP / agents | Time from the user's request to the final answer | Logs or traces show how long each model request, tool call, and approval step takes |
| Provider model processing | Text / image / file / function tools | Test Priority Processing after software optimization | The returned tier is `priority`; p50, p95, reliability, quality, cost, and data residency meet the goal |

The concurrency and managed-agent rows are next experiments: this lab did not
isolate parallel handler execution or benchmark service-managed MCP or Agent
Service.

Reasoning effort was not varied in this lab. Microsoft documents that higher
effort takes longer and generally produces more reasoning tokens, which are
billed as output tokens. Supported values and defaults vary by model. See
[Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning#reasoning-effort).

Count every model request in a direct Responses workflow. For a managed agent,
time from user request to final answer and use traces to attribute model, tool,
and approval stages; one invocation can contain several model requests. See
[Agents in Microsoft Foundry](https://learn.microsoft.com/azure/foundry/agents/overview).

### How to test each change

1. Define what a correct answer must include.
2. Pair both setups across at least five representative examples and vary
   which runs first.
3. Keep failures in reliability; calculate latency only from correct
   completions.
4. Compare p50 and p95, treating p95 from a small sample as descriptive.
5. Test compatible changes together; do not add separate percentages.

## Try it and inspect it

### Try the lab

Deploy the
[foundy-ai-perf-testing repository](https://github.com/yelghali/foundy-ai-perf-testing),
replace its fixtures with a safe workload sample, and use the
[testing guideline](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/ai-response-performance-guidelines.md)
to define timing, correctness, and the comparison before paid requests.

After configuring the documented Azure environment variables, run the smoke
profile first. Then run the one-lever screen and combined confirmation:

```powershell
ai-perf run-suite `
  --profile smoke `
  --warmups 1 `
  --repetitions 2

ai-perf run-suite `
  --profile screen `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904

ai-perf run-suite `
  --profile bundle `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904
```

### Inspect the lab

The
[lab report](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/lab-report.md)
contains the architecture, methods, full results, limitations, and reproduction
details. The
[result ledger](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/publication-results.md)
contains execution IDs, artifact versions, intervals, and reliability events.

## Explore the next performance track

This lab intentionally kept service-managed MCP, Foundry Agent Service, model
specialization, voice agents, and RAG outside the main comparison. Each needs
a clear definition of success, a clear start and end point for timing, and a
separate experiment.

### Managed MCP and Foundry Agent Service

Compare the same task and tools through app-managed MCP, Responses API remote
MCP, and a Foundry agent using MCP or Toolbox. Measure complete task latency,
then use traces and server logs to count model requests, discovery, approvals,
tool calls, and actual overlap before transferring the function-tool result.

### Voice agents

Voice performance has a different critical path: turn detection, speech
processing, model inference, tool calls, and time to first audio all affect
responsiveness. Architecture can matter as much as the model.

For a comparison of Realtime API direct, Voice Live with a deployment in your
Foundry environment, and Voice Live with a prompt agent, see
[Choosing a real-time voice architecture on Microsoft Foundry: three enterprise patterns](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/choosing-a-real-time-voice-architecture-on-microsoft-foundry-three-enterprise-pa/4552676).

### RAG with Azure AI Search

RAG adds retrieval stages that this lab deliberately excluded: query planning,
vector and keyword search, filtering, semantic ranking, chunk selection, and
context construction. Optimize retrieval latency together with recall and
answer quality; a faster search that removes the required evidence is not a
successful result.

Explore
[Retrieval-augmented generation in Azure AI Search](https://learn.microsoft.com/azure/search/retrieval-augmented-generation-overview)
for classic and agentic retrieval performance considerations, and
[Boost RAG Performance: Enhance Vector Search with Metadata Filters in Azure AI Search](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/boost-rag-performance-enhance-vector-search-with-metadata-filters-in-azure-ai-se/4208985)
for a focused metadata-filtering approach. For vector index size and query
processing options, see
[Choose an approach for optimizing vector storage and processing](https://learn.microsoft.com/azure/search/vector-search-how-to-configure-compression-storage).

### Model performance and distillation

The smaller off-the-shelf model was not consistently faster in this lab. A
useful model-performance track should compare task quality, latency,
throughput, and cost on the same fixtures. For a specialized workload,
distillation is another option to explore: a smaller model learns from a more
capable teacher so it can target a narrower task rather than merely being
swapped into the same prompt.

Start with
[Distillation: Turning Smaller Models into High-Performance, Cost-Effective Solutions](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/distillation-turning-smaller-models-into-high-performance-cost-effective-solutio/4355029).
For the broader path from distillation to reinforcement fine-tuning, see
[From Distillation to Reinforcement Fine-Tuning: Hill-Climbing in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/from-distillation-to-reinforcement-fine-tuning-hill-climbing-in-microsoft-foundr/4543260).
Treat model specialization as a hypothesis to benchmark, not a guaranteed
latency win.

If you run the lab against a different model, region, or production-shaped
scenario, share which lever moved p50, which moved p95, and which looked faster
until correctness was included. That comparison is more useful than another
universal latency rule.
