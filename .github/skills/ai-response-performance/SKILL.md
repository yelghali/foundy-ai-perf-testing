---
name: ai-response-performance
description: Design, implement, run, or review evidence-based AI response performance experiments across text, image, file, RAG, function tools, MCP, and Microsoft Foundry toolboxes. Use when asked to benchmark or reduce AI latency, compare prompts, caching, models, reasoning effort, processing tiers or infrastructure, or tool configurations, investigate p50 or tail latency, or produce a performance report. Do not use for generic code performance unrelated to AI workflows.
---

# AI response performance

Optimize the latency of correctly completed user tasks, not isolated fast API
calls.

## Use this skill in an application repository

This skill is designed for real application workspaces as well as this
benchmark repository. GitHub Copilot supports project skills under
`.github/skills` and personal skills under `~/.copilot/skills`; it loads a
skill when the request matches its description.

For a project installation with GitHub CLI 2.90.0 or later, inspect and install
the skill:

```shell
gh skill preview yelghali/foundy-ai-perf-testing ai-response-performance
gh skill install yelghali/foundy-ai-perf-testing ai-response-performance
```

Alternatively, copy this `ai-response-performance` directory into the target
repository's `.github/skills` directory, or into
`~/.copilot/skills` for personal use across repositories.

When used in an application repository:

1. inspect its actual AI entry points, SDKs, prompts, models, tools, telemetry,
   deployment configuration, tests, and performance requirements;
2. choose one production-shaped user task and define correctness before
   proposing optimizations;
3. adapt the application's existing test and observability patterns rather
   than assuming the `ai-perf` CLI or this lab's Terraform is present;
4. implement the smallest one-lever experiment that targets the measured slow
   stage;
5. validate the change with the application's existing tests plus the scoped
   performance comparison; and
6. request explicit approval before running paid cloud experiments or changing
   infrastructure.

When working in this repository, read
`docs/ai-response-performance-guidelines.md` and reuse the existing `ai-perf`
CLI, fixtures, scorers, reporting, and Terraform. Do not duplicate benchmark
logic in this skill.

When working elsewhere, use the published testing guideline linked under
References and keep the benchmark implementation local to that application's
architecture and conventions.

## Workflow

1. **Define the decision.**
   - Identify the user task, target SLO, expected traffic, and deployment
     environment.
   - Establish whether the goal concerns perceived response time, completed
     workflow time, throughput, tail latency, cost, or a combination.

2. **Name the timing boundary.**
   - State the exact timer start and stop.
   - List included and excluded preprocessing, retrieval, model, MCP, tool,
     validation, retry, network, and rendering stages.
   - Do not call a model-request measurement "end-to-end."

3. **Create a correctness contract.**
   - Prefer deterministic field, fact, classification, tool-selection, and
     argument checks.
   - Use at least five representative fixtures for an exploratory comparison.
   - Keep failures and incorrect answers in reliability counts.
   - Exclude failed or incorrect attempts from successful-task latency
     percentiles.

4. **Instrument before changing behavior.**
   - Persist scenario, variant, fixture, round, randomized position, model,
     version, region, deployment, requested and returned tier, token usage,
     retry information, and benchmark version.
   - Capture relevant stages such as input preparation, time to first token,
     model completion, MCP discovery, tool selection, tool execution, final
     generation, and validation.

5. **Run a one-lever screen.**
   - Keep a valid reference control.
   - Change one factor per treatment.
   - Warm up the path, rotate fixtures, and randomize treatment order inside
     paired rounds.
   - Keep concurrency at one for attribution.
   - Reuse existing project commands and test infrastructure.

6. **Interpret conservatively.**
   - Label an effect supported only when its paired interval excludes zero and
     correctness passes.
   - Label intervals crossing zero inconclusive.
   - Treat p95 and p99 from 30 observations as descriptive.
   - Identify confounding before recommending a treatment.
   - Never add percentages from isolated experiments.

7. **Confirm compatible winners.**
   - Compare a non-optimized but valid reference configuration with the
     optimized software configuration.
   - Isolate any paid processing tier in a third otherwise-identical arm.
   - If the model, version, or region changed, state that the confirmation
     validates the bundle only, not transfer of each individual effect.

8. **Evaluate production pressure separately when requested.**
   - Run a manual concurrency or arrival-rate sweep after attribution.
   - Record throughput, queueing, rate limits, errors, p50, adequately sampled
     tails, cache behavior, and cost per correct completion.
   - Do not add a recurring workflow or automatically run paid cloud
     benchmarks unless the user explicitly requests it.

9. **Report the evidence.**
   - Separate supported, inconclusive, adverse, and confounded findings.
   - Include correctness, reliability, p50, tail-sample caveats, token and
     tier data, cost inputs, timing boundaries, threats to validity, and exact
     reproduction commands.
   - Present synthetic results as workload-specific hypotheses, never as
     service guarantees.

## Decision sequence

Use measured stage data rather than applying every lever. A useful order is:

1. **Remove unnecessary work:** constrain output, remove irrelevant input,
   and avoid image or document processing the task does not need.
2. **Reuse prior work:** verify prompt-cache hits and reuse app-managed MCP
   connections and discovered tool lists when safe.
3. **Remove serial waits and model rounds:** overlap independent requests and
   let one model response request multiple required functions when correct.
4. **Reduce the tool surface:** first try a smaller static catalogue and
   concise definitions; test dynamic tool search separately because it adds a
   discovery round.
5. **Tune model computation:** compare supported models and reasoning-effort
   levels against the same quality contract.
6. **Test provider infrastructure:** after fixing the software configuration,
   isolate Priority Processing or provisioned capacity in a separate arm.

Priority Processing belongs in this skill because provider processing can
dominate the remaining latency. It does not replace prompt, orchestration, or
tool optimization, and it must not be credited for improvements already made
in the software configuration.

## Lever-selection guide

Choose a small set based on the dominant measured stage:

| Dominant stage | Candidate experiments |
|---|---|
| Input processing | Stable prefix, prompt cache, context reduction |
| Output generation | Smaller response contract, output cap, streaming |
| Image processing | Detail level, crop, compression, resize |
| File processing | Native document versus prepared text, page scheduling |
| Tool selection and orchestration | Relevant-tool routing, descriptions, schema, tool search, independent multi-tool selection in one model round |
| MCP setup | Connection and discovery reuse |
| Tool execution | Concurrent backend invocations, batching, backend latency |
| Reasoning-model generation | Supported `reasoning_effort` levels and output limits |
| Provider processing | Supported model, deployment, Priority Processing, provisioned capacity |

## Required controls

### Caching

Verify cached tokens. Use a genuinely unique prefix for the cold control and
an identical reusable prefix for the warm treatment.

### Input reduction

Measure latency and input-token cost separately. Preserve all evidence needed
for correctness. Do not generalize a small-context result to long
conversations or corpus-backed retrieval workloads.

### Reasoning effort

Use a model that supports `reasoning_effort`, set the level explicitly, and
keep the model, prompt, output limit, processing tier, fixtures, and schedule
constant. Record reasoning tokens, incomplete responses, latency, quality, and
cost. Treat lower effort as a win only when the task still passes its
correctness and quality contract.

### Priority Processing

Treat Priority Processing as a provider-infrastructure experiment after the
software request is fixed. Keep model, version, deployment, region, prompt,
fixtures, and schedule identical to an optimized Standard control. Record both
requested and returned service tier for every observation, and reject the
claim when accepted responses do not report Priority Processing. Compare p50,
tails, reliability, cost, and data-residency requirements.

### Multimodal preprocessing

Include local resize, compression, extraction, parsing, or OCR in a separate
full-pipeline timer before making a full-pipeline recommendation.

### Tools and MCP

Hold the underlying task and tool behavior constant. Separate discovery,
selection, execution, and final generation. Sequential and parallel arms must
perform the same tool calls. Record model-call count; when a treatment both
removes a model-selection round and executes tools concurrently, report an
orchestration effect rather than attributing it to backend parallelism alone.

Keep these experiments distinct:

- static tool pruning or shorter descriptions change the definitions sent to
  the model;
- dynamic tool search reduces the initial tool surface but adds a discovery
  round;
- app-managed MCP connection reuse changes connection and discovery lifecycle;
- concurrent app-run functions do not prove concurrent service-managed MCP or
  agent execution.

## Guardrails

- Do not silently retry away failures.
- Do not use a fast wrong answer as latency evidence.
- Do not infer p99 from a 30-run screen.
- Do not recommend a smaller model without task-specific evidence.
- Do not recommend lower reasoning effort without task-quality and
  completeness evidence.
- Do not infer cache use or Priority Processing service from configuration
  alone.
- Do not present unmeasured guidance as a benchmark finding.
- Do not describe a deliberately non-optimized reference configuration as the
  absolute worst.
- Do not claim lower AI-request latency when excluded preprocessing may reverse
  the full-pipeline result.
- Do not expose credentials, private prompts, customer data, or private result
  artifacts in reports.
- Do not run paid Azure experiments without a defined scope and user-approved
  environment.

## Completion criteria

The task is complete only when:

- the measurement boundary and correctness contract are documented;
- raw observations are retained;
- the relevant focused tests pass;
- every recommendation is supported by the measured workload;
- inconclusive and adverse results remain visible;
- the combined configuration is verified separately when one is proposed;
- limitations and reproduction steps are reported.

## References

### Project method and evidence

- [AI response performance testing guidelines](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/ai-response-performance-guidelines.md)
- [Completed lab report](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/lab-report.md)
- [Publication result ledger](https://github.com/yelghali/foundy-ai-perf-testing/blob/main/docs/publication-results.md)

### Agent Skills

- [About agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
- [Add agent skills to GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)

### Microsoft Foundry performance controls

- [Use the Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses)
- [Prompt caching](https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching)
- [Reasoning effort](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning#reasoning-effort)
- [Configure image detail](https://learn.microsoft.com/azure/foundry/openai/how-to/gpt-with-vision#configure-image-detail-level)
- [Parallel function calling](https://learn.microsoft.com/azure/foundry/openai/how-to/function-calling#parallel-function-calling-with-multiple-functions)
- [Remote MCP with the Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses#using-remote-mcp-servers)
- [Foundry Toolbox](https://learn.microsoft.com/azure/foundry/agents/concepts/toolbox-overview)
- [Toolbox tool search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search)
- [Priority Processing](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing)
- [Compare Standard, Priority Processing, and Provisioned Throughput](https://learn.microsoft.com/azure/foundry/openai/concepts/provisioned-throughput#deployment-categories-compared)
