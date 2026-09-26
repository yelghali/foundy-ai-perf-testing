# AI response performance testing guidelines

Use this guide to design evidence-based latency experiments for AI
applications. It applies to text, image, file, retrieval, function-tool,
Model Context Protocol (MCP), and managed-tool workflows.

The goal is not to find the fastest isolated API response. The goal is to
reduce the time required to complete a user task correctly, reliably, and at
an acceptable cost.

## 1. Non-negotiable principles

1. **Define correctness before measuring speed.**
2. **Name the timing boundary.** Do not use "end-to-end" without saying where
   the timer starts and stops.
3. **Change one lever at a time before combining winners.**
4. **Pair treatment and control on the same fixture and time block.**
5. **Retain failures and incorrect answers in reliability counts.**
6. **Use latency percentiles only for successfully completed, correct tasks.**
7. **Treat p50, p95, cost, and reliability as separate release gates.**
8. **Verify observed behavior, such as cached tokens or returned service tier.**
9. **Do not add percentage improvements from separate experiments.**
10. **Present results as workload-specific until independently replicated.**

## 2. Select and label the timing boundary

An application can have several valid timers. Record all that matter, but do
not mix them.

| Boundary | Start | Stop | Typical use |
|---|---|---|---|
| User journey | User submits input | Useful result is rendered or spoken | Product experience and SLO |
| Application workflow | Application accepts input | Validated result is ready | Architecture and orchestration |
| AI path | Prepared request or composed AI loop starts | Final model result is validated | Prompt, model, tier, and tool experiments |
| Model request | SDK sends one request | Complete response arrives | Provider and request-shape comparison |
| Stage | One named operation starts | That operation completes | Diagnosis |

For every reported number, state whether the following work is inside or
outside the timer:

- authentication and client creation;
- image resize, encoding, or compression;
- PDF rendering, parsing, or OCR;
- retrieval, reranking, and context construction;
- MCP connection and tool discovery;
- model tool selection and final generation;
- tool execution;
- retries, backoff, and validation;
- network travel between the user, application, model, and tools;
- client rendering or audio playback.

If preprocessing is outside the timer, use a narrow claim. For example:

> With text already extracted, the AI request was 17% faster than native PDF
> input.

Do not convert that into a full-pipeline claim until parser or OCR time is also
measured.

## 3. Define a scenario contract

Each scenario needs a reproducible contract:

| Field | Required definition |
|---|---|
| User task | What the user is trying to complete |
| Input fixture | Prompt, image, file, conversation, or tool request |
| Expected result | Exact fields, facts, tool calls, or semantic requirements |
| Correctness scorer | Deterministic validation whenever possible |
| Failure policy | Which API, parsing, timeout, and quality failures are retained |
| Timing boundary | Named start, stop, included stages, and excluded stages |
| Cost inputs | Model usage, tool/service meters, and preprocessing cost |
| Sensitive-data policy | Synthetic or approved data and redaction requirements |

Use at least five fixtures for an exploratory comparison. Include different
input sizes and difficulty levels when the production workload varies.

Prefer deterministic scorers for structured extraction, classification, tool
selection, and exact factual tasks. If human or model-based grading is needed,
run it after the measured workflow so grader latency does not contaminate the
result.

## 4. Instrument before optimizing

Record a total plus the stages that could explain it:

```text
input preparation
-> retrieval or cache lookup
-> model first token
-> model completion or tool selection
-> tool discovery
-> tool execution
-> final model generation
-> validation
-> rendering
```

At minimum, persist:

- scenario, variant, fixture, round, and randomized position;
- model, version, deployment, region, and API or SDK version;
- requested and returned processing tier;
- success, correctness score, and failure reason;
- total latency and relevant stage latencies;
- input, output, reasoning, and cached tokens;
- retry count and rate-limit metadata;
- concurrency and configured quota;
- a benchmark code or image identifier.

Raw observations should be immutable. Derived summaries can be regenerated
when the analysis changes.

## 5. Choose metrics that support a decision

### Correctness and reliability

```text
correct-completion rate = correct completed attempts / all attempts
request success rate = successful requests / all attempts
```

Do not silently retry failed observations. If the production application
retries, model the retry policy as a separate, explicit workflow and include
its latency and cost.

### Latency

- **p50** answers what a typical successful task experiences.
- **p95** and **p99** describe tail behavior and need substantially more data.
- **Time to first token** measures perceived responsiveness for streaming.
- **Total latency** measures when the task is actually complete.

Suggested sample floors are decision aids, not statistical guarantees:

| Purpose | Suggested measured attempts per arm | Interpretation |
|---|---:|---|
| Smoke test | 3-5 | Functional only |
| Exploratory p50 | 30 paired rounds | Directional median evidence |
| p95 release gate | 200 or more across time windows | At least several tail observations |
| p99 release gate | 1,000 or more across time windows | Do not infer from a 30-run screen |

With 30 observations, p95 and p99 should be labelled **descriptive**. Do not
claim a tail-latency SLO from that sample.

### Cost

Where pricing inputs are available, report:

```text
cost per correct completion =
  total model + platform + tool + preprocessing cost
  / correct completed attempts
```

If actual currency cost is not calculated, report the contributing meters and
say that cost remains unresolved.

## 6. Run a one-lever screen

Start from one valid reference configuration for each scenario. Change one
factor at a time:

1. run unmeasured warm-ups;
2. rotate fixtures;
3. execute the control and every treatment once per round;
4. randomize order inside each round with a recorded seed;
5. keep concurrency at one for attribution;
6. pair treatment and control by round;
7. calculate p50 effect intervals;
8. classify the result as supported, inconclusive, adverse, or confounded.

For a 30-round exploratory screen, bootstrap intervals can support directional
p50 conclusions. Do not treat an interval crossing zero as "probably faster."

Intervals from many tested hypotheses are exploratory unless the study
pre-registers primary comparisons or applies an appropriate multiplicity
strategy.

## 7. Select levers from the dominant stage

Do not run every possible combination. Use stage evidence to choose the next
small set of experiments.

| Dominant stage | Candidate levers |
|---|---|
| Input processing | Stable prefixes, prompt caching, context reduction |
| Output generation | Smaller response contract, lower output cap, streaming |
| Image processing | Detail level, task-specific crop, compression or resize |
| File processing | Native document versus prepared text, page scheduling |
| Tool selection and orchestration | Relevant-tool routing, descriptions, schemas, tool search, independent multi-tool selection in one model round |
| MCP setup | Session reuse, discovery caching, connection placement |
| Tool execution | Concurrent backend invocations, batching, faster backend |
| Reasoning-model generation | Supported `reasoning_effort` levels and output limits |
| Provider queue or generation | Supported model/deployment options, Priority Processing, provisioned capacity |

Treat results from this repository as hypotheses to test, not defaults to
apply blindly.

## 8. Apply special controls

### Prompt caching

- Keep the reusable prefix identical.
- Put variable content after the reusable prefix.
- Make the cold control genuinely unique before the cacheable region.
- Verify cached-token counts in every cohort.
- Separate cache-hit benefit from cache-write and miss behavior.

### Reasoning effort

No reasoning-effort result is currently included in this repository's
evidence set. For a supported reasoning model:

- set `reasoning_effort` explicitly because supported values and defaults vary
  by model;
- keep the model, version, deployment, prompt, output limit, processing tier,
  fixtures, and schedule identical between levels;
- record correctness, p50, tails, reasoning tokens, incomplete responses, and
  cost per correct completion;
- set an output limit that leaves enough room for both hidden reasoning tokens
  and the visible answer; and
- select the lowest effort that meets the task's evaluated quality bar, rather
  than assuming that less reasoning is always better.

Microsoft documents that higher effort takes longer and generally produces
more reasoning tokens. Reasoning tokens are billed as output tokens. See
[Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning#reasoning-effort).

### Priority Processing

- Verify that the exact model, version, deployment type, and region support it.
- Keep model, deployment, request, fixture, and schedule identical between
  Standard (PAYGO) and Priority Processing configurations.
- Record requested and returned tier for every observation.
- Reject a Priority Processing conclusion when accepted responses are not
  served with Priority Processing.
- Compare tails, reliability, and cost in addition to p50.

### Images and files

- Score the fields or visual reasoning the product actually requires.
- Include local resize, compression, extraction, parsing, or OCR in a separate
  full-pipeline timer.
- Do not recommend prepared text when layout, handwriting, signatures, charts,
  or visual evidence are required.

### Tools and MCP

- Hold the underlying task and tool implementation constant.
- Separate discovery, selection, execution, and final generation.
- Record model-call count as well as tool-call count.
- Compare tool-count changes only when the required tool remains available.
- Keep description variants equally cacheable.
- For sequential versus parallel tests, make the same calls in both arms.
- If the parallel arm also selects multiple tools in one model round, report
  the result as an orchestration effect rather than pure backend parallelism.
- Test cold and reused sessions separately.

For a practical Responses API implementation:

1. enable multiple tool requests with `parallel_tool_calls=True`;
2. collect the returned `function_call` items;
3. validate that the calls are independent and safe to overlap;
4. execute async I/O handlers together, such as with `asyncio.gather`;
5. return one `function_call_output` for each call using its original
   `call_id`; and
6. ask the model for the final response after every required result is
   available.

The model requests custom function calls; the application executes them.
Enabling parallel tool calls does not guarantee that the model selects every
required tool, and `asyncio.gather` does not make blocking synchronous
functions parallel. Validate tool selection, arguments, final-answer
correctness, downstream capacity, and partial-failure behavior.

### Managed tool search

- Use the same underlying catalogue in direct and search-mediated arms.
- Report context tokens, discovery rounds, selection quality, p50, and tails.
- Treat lower tokens, higher correctness, and higher latency as a trade-off,
  not a contradiction.

## 9. Confirm the combined configuration

Do not add one-lever percentages. Create a separate confirmation with:

1. a **non-optimized but valid reference configuration**;
2. an **optimized software configuration** using compatible supported
   findings;
3. an optional **optimized paid-tier configuration** with the same software
   request.

Run the same fixtures and randomized schedule across all arms. Compare the
optimized arm directly with the reference control and also isolate the
incremental paid-tier effect.

When one-lever findings came from a different model, version, or region, the
confirmation validates only the combined configuration in the new
environment. It does not prove that every individual lever transferred
independently.

## 10. Test production pressure separately

Attribution runs and load runs answer different questions. Keep them separate.

After selecting a winning configuration, run a manual concurrency or arrival
rate sweep that reflects expected traffic. Record:

- p50, p95, p99, throughput, and queue time;
- correct-completion and request-success rates;
- HTTP 429 and timeout rates;
- RPM, TPM, connection, and downstream-tool saturation;
- cache-hit behavior under distributed keys;
- cost per correct completion.

Run important release comparisons in more than one time window. Add another
region only when making a region-independent claim.

## 11. Report without overclaiming

Use four result classes:

- **Supported:** the effect interval excludes zero and quality passes.
- **Inconclusive:** the interval crosses zero.
- **Adverse:** the interval excludes zero in the wrong direction or violates
  another release gate.
- **Confounded:** the treatment changed another important factor.

Every report should include:

1. research question and workload;
2. exact timing boundary;
3. environment and model versions;
4. fixtures, warm-ups, rounds, schedule, and seed;
5. correctness and failure policy;
6. p50 plus descriptive or adequately sampled tails;
7. token, tier, and cost inputs;
8. supported, inconclusive, adverse, and confounded findings;
9. combined confirmation;
10. threats to validity and reproduction commands.

Avoid these claims:

- "Model X is always faster."
- "Priority Processing improves every request."
- "Fewer tokens necessarily means lower latency."
- "The percentages add up."
- "This synthetic result is a service guarantee."

## 12. Repository workflow

Run the one-lever screen:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile screen `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904
```

Run the combined confirmation:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile bundle `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904
```

Use [the benchmark plan](./benchmark-plan.md) for the implemented scenario
matrix and [the lab report](./lab-report.md) for a completed example.
Install the
[AI response performance skill](../.github/skills/ai-response-performance/SKILL.md)
as a project or personal GitHub Copilot skill to apply these guidelines from
an application workspace.

## 13. Release checklist

- [ ] The user task and correctness contract are explicit.
- [ ] The timing boundary names included and excluded work.
- [ ] Fixtures represent multiple inputs and difficulty levels.
- [ ] Control and treatment run against the same fixture per round.
- [ ] Warm-ups, randomization seed, and environment metadata are recorded.
- [ ] Failures and wrong answers remain in reliability counts.
- [ ] Cache and service-tier claims use observed response metadata.
- [ ] Thirty-run p95 and p99 values are labelled descriptive.
- [ ] Preprocessing is included before making full-pipeline claims.
- [ ] One-lever percentages are not added.
- [ ] The combined configuration has its own confirmation.
- [ ] Paid-tier decisions include cost inputs.
- [ ] Production SLO claims use a separate, adequately sampled load run.
