# Azure cloud screening results

## Status and scope

These results are an initial performance screen, not publication-ready proof.
They identify candidates for larger, randomized confirmation runs.

The completed randomized 30-round follow-up is documented in
[publication-results.md](publication-results.md) and supersedes this initial
screen for performance findings.

The core screen covered 48 one-lever-at-a-time configurations across text
chat, image understanding, file processing, native tools, and MCP. A later
targeted screen compared direct remote MCP with Microsoft Foundry Toolbox Tool
Search over the same 50-tool catalogue. RAG was intentionally excluded. Every
measured request in the runs documented below completed successfully and
passed its scenario correctness check.

## Deployed environment

The benchmark ran in Azure Container Apps against Azure OpenAI in `eastus2`.

| Component | Deployed value |
|---|---|
| Resource group | `rg-aiperf-6l2kni` |
| Azure OpenAI account | `oai-aiperf-6l2kni` |
| Baseline model | `gpt-4.1-mini`, version `2025-04-14` |
| Comparison model | `gpt-4.1-nano`, version `2025-04-14` |
| Deployment SKU | `GlobalStandard` |
| Model capacity | 100K TPM per deployment |
| Container Apps job | `job-aiperf-6l2kni` |
| Foundry account/project | `foundry-aiperf-6l2kni` / `tools` |
| Toolbox | `ai-perf-tools`, version 1 |
| Remote MCP app | `mcp-aiperf-6l2kni`, 50 synthetic tools |
| Results storage | Private `benchmark-results` blob container |
| Authentication | Managed identity; OpenAI keys and storage shared keys disabled |
| Runtime | Python `3.12.14`, OpenAI SDK `2.54.0`, Responses API |

The final throughput runs used image tag `ai-perf:ch10`. At execution time,
`ch10` and `latest` both resolved to digest
`sha256:80167b2099501031a39bd1f6f25d7449ce8799a1991ef82869e9fbd73daa8a89`.
The uploaded concurrency-20 JSONL was read back through the private network and
confirmed `concurrency: 20` and the `ch10` image reference in its raw metadata.
The Toolbox comparison used image tag `ai-perf:ch12`, digest
`sha256:b91b2f6c9e90e0b11287031e0ed17b925257f1cf816c4e0a2daf95d86f875003`.

## Full 48-case screen

- Job execution: `job-aiperf-6l2kni-js0dq61`
- Artifact prefix: `20260904T143733Z`
- Warm-ups: 3 per case
- Measurements: 10 per case
- Total measured observations: 480
- Errors: 0
- Quality failures: 0

The tables show rounded values from the uploaded JSON summary. A negative
change means a lower median than the scenario baseline.

### Text chat

| Variant | p50 | p95 | p50 change |
|---|---:|---:|---:|
| Baseline | 3294 ms | 4097 ms | - |
| Concise output | 1735 ms | 2360 ms | -47% |
| Warm prompt cache | 1923 ms | 2935 ms | -42% |
| Smaller model | 1992 ms | 6002 ms | -40% |
| Reduced input | 2287 ms | 3569 ms | -31% |

Concise output was the strongest text median and tail result in this screen.
Warm caching was also promising: 9 of 10 requests reported cached tokens, with
an average of 3,456 cached tokens. The smaller model improved the median but
had a worse p95 than the baseline, so it is not yet a robust winner.

### File processing

| Variant | p50 | p95 | p50 change |
|---|---:|---:|---:|
| Baseline | 1790 ms | 7563 ms | - |
| Concise output | 1113 ms | 4318 ms | -38% |
| Parallel pages | 1148 ms | 2239 ms | -36% vs baseline |
| Smaller model | 1274 ms | 3671 ms | -29% |
| Reduced input | 1322 ms | 5294 ms | -26% |
| Extracted text | 1364 ms | 3364 ms | -24% |
| Sequential pages | 3116 ms | 8344 ms | +74% vs baseline |

Parallel page processing reduced p50 by 63% relative to sequential page
processing and substantially reduced its p95. It made three model calls,
however, so this is a latency-for-cost trade-off rather than a free
optimization.

### Image understanding

| Variant | p50 | p95 | p50 change |
|---|---:|---:|---:|
| Baseline | 1725 ms | 5010 ms | - |
| Concise output | 1512 ms | 3012 ms | -12% |
| Warm prompt cache | 1616 ms | 4269 ms | -6% |
| Low detail | 1636 ms | 7702 ms | -5% |
| Low-detail-first cascade | 1816 ms | 8974 ms | +5% |
| Reduced image input | 2067 ms | 5925 ms | +20% |
| Smaller model | 2189 ms | 7725 ms | +27% |

Concise output is the only image candidate that improved both p50 and p95 in
this sample. The smaller model was faster for text and files but slower for
this image workload, demonstrating that model selection is workload-specific.
Low detail slightly improved the median but materially worsened the tail.

### Native tools and MCP

| Variant | p50 | p95 | p50 change vs native baseline |
|---|---:|---:|---:|
| Native 20-tool baseline | 2651 ms | 15117 ms | - |
| Five-tool exposure | 1738 ms | 4956 ms | -34% |
| Minimal descriptions | 1890 ms | 4186 ms | -29% |
| Warm prompt cache | 1908 ms | 2629 ms | -28% |
| MCP warm session | 2122 ms | 3764 ms | -20% |
| Fifty tools | 2427 ms | 6190 ms | -8% |
| Reordered definitions | 2564 ms | 8937 ms | -3% |
| Many-parameter schema | 3025 ms | 4462 ms | +14% |
| MCP cold session | 3269 ms | 7493 ms | +23% |

The native baseline had a 15.1-second p95, so its apparent p50 improvements
need a larger confirmation sample. Stage timings nevertheless show useful
mechanisms:

- the MCP tool execution itself averaged about 4-5 ms;
- cold MCP startup and discovery averaged 971 ms;
- reusing the MCP session removed that discovery cost;
- the many-parameter schema increased average model tool-selection time to
  about 2,206 ms;
- stable warm tool definitions reported a 100% cache-hit rate, while reordered
  definitions reported 0%.

The ambiguous-description case still had 100% correctness. The current task is
therefore too simple to support a claim that ambiguity harms selection
accuracy.

## Remote MCP versus Foundry Toolbox Tool Search

This targeted screen used the same public, deterministic 50-tool MCP server,
weather task, `gpt-4.1-mini` deployment, region, and benchmark host for both
variants:

- direct MCP exposed all 50 definitions to the model;
- Toolbox initially exposed `tool_search` and `call_tool`, used BM25 to
  discover matching definitions, and then executed the same remote MCP tool.

- Job execution: `job-aiperf-6l2kni-0xn7lmm`
- Artifact prefix: `20260904T161351Z`
- Warm-ups: 3 per case
- Measurements: 10 per case
- Total measured observations: 20
- Errors: 0
- Quality failures: 0

| Variant | Model calls | p50 | p95 | Mean | Avg input tokens |
|---|---:|---:|---:|---:|---:|
| Direct remote MCP, 50 tools | 2 | 2382 ms | 5197 ms | 2709 ms | 1938.0 |
| Foundry Toolbox Search, 50 tools | 3 | 4107 ms | 8369 ms | 4950 ms | 1253.1 |

Toolbox reduced average input tokens by 35%, but its p50 was 72% higher, its
p95 was 61% higher, and its mean was 83% higher in this small screen. The
additional model round trip dominated the trade-off.

| Average stage | Direct remote MCP | Foundry Toolbox Search |
|---|---:|---:|
| Tool-search model selection | - | 1629 ms |
| BM25 tool-search execution | - | 114 ms |
| Discovered-tool model selection | 1668 ms | 1891 ms |
| Tool execution | 34 ms | 161 ms |
| Final generation | 1007 ms | 1154 ms |

All ten Toolbox observations used `tool_search` and returned the correct 21°C
answer. Seven followed the documented `tool_search -> call_tool` path. Three
successfully invoked the discovered `benchmark___lookup_weather` tool directly.
The scorer accepts and records both valid paths.

This result does not show that Tool Search is generally slower or less useful.
It shows that, for one simple task and 50 concise tools, the token reduction
did not repay an extra model call. Direct MCP also received a 100% prompt-cache
hit rate with 1,792 average cached tokens, while Toolbox received no reported
cache hits, so caching favored the direct path. Larger or more ambiguous
catalogues, multi-step tasks, and different cache conditions may change the
result and need confirmation runs.

Foundry Toolbox Tool Search is a preview feature. The public anonymous MCP
endpoint is benchmark-only: it exposes deterministic read-only tools and no
secrets or production data. A production deployment requires supported
authentication or private connectivity.

## Priority Processing limitation

The benchmark retained both the requested and actual service tier. All 40
requests in the four Priority Processing variants were reported by the service as
`default`, not `priority`.

The measured Priority Processing rows must not be interpreted as Priority
Processing performance. They only show the behavior observed after the
requests were served at the default tier. A future Priority Processing test
must first verify that the actual response tier is `priority`.

## Controlled concurrency

Each load execution ran the four baseline scenarios with three warm-ups and 20
measured requests per scenario. Each row therefore summarizes 20 requests.
All 240 measured load requests succeeded and passed quality.

| Concurrency | Scenario | p50 | p95 | Batch elapsed | Throughput |
|---:|---|---:|---:|---:|---:|
| 5 | File | 1419 ms | 5570 ms | 9.84 s | 2.03 req/s |
| 5 | Image | 1950 ms | 5996 ms | 14.83 s | 1.35 req/s |
| 5 | Text | 2419 ms | 5079 ms | 15.32 s | 1.31 req/s |
| 5 | Native tools | 1870 ms | 2569 ms | 11.64 s | 1.72 req/s |
| 10 | File | 1459 ms | 2374 ms | 10.57 s | 1.89 req/s |
| 10 | Image | 2206 ms | 7486 ms | 10.67 s | 1.87 req/s |
| 10 | Text | 2066 ms | 2718 ms | 5.23 s | 3.83 req/s |
| 10 | Native tools | 2141 ms | 5045 ms | 9.37 s | 2.13 req/s |
| 20 | File | 1528 ms | 4506 ms | 5.20 s | 3.85 req/s |
| 20 | Image | 2619 ms | 4605 ms | 7.36 s | 2.72 req/s |
| 20 | Text | 3132 ms | 4644 ms | 5.25 s | 3.81 req/s |
| 20 | Native tools | 2232 ms | 3124 ms | 6.02 s | 3.32 req/s |

Execution and artifact identifiers:

| Concurrency | Job execution | Artifact prefix |
|---:|---|---|
| 5 | `job-aiperf-6l2kni-638pcbj` | `20260904T152035Z` |
| 10 | `job-aiperf-6l2kni-h10rbc4` | `20260904T152320Z` |
| 20 | `job-aiperf-6l2kni-z4rz62t` | `20260904T152610Z` |

Concurrency improved throughput, but not uniformly. From concurrency 5 to 20,
file, image, and native-tool throughput increased by roughly 89%, 102%, and
93%, respectively. Text reached about 3.8 req/s at concurrency 10 and did not
improve at 20; its p50 rose from 2066 ms to 3132 ms. For this deployment and
request shape, concurrency 10 is the better text operating point of the tested
levels.

The non-monotonic p50 and p95 values also show why a single short load run
cannot establish capacity limits. A proper saturation test should run each
level for a fixed duration, repeat the levels in randomized order, and record
throttling and retry data.

## Cache confounding

Azure OpenAI automatically cached repeated large prefixes. This occurred even
in cases intended as baselines or cold-cache comparisons:

- the image baseline reported cached tokens in 9 of 10 requests;
- the image load baselines reported high cache-hit rates;
- the nominally cold text, image, file, and tool cases sometimes reported
  cached tokens;
- larger tool-definition variants also received cache hits.

A unique prompt cache key did not guarantee zero cached tokens. Results must
therefore be interpreted using observed `cached_tokens`, not the variant name.
Future confirmation runs should either embrace a realistic warm-cache workload
or vary eligible prefixes enough to produce a verified uncached cohort.

## What can be concluded now

The screen provides evidence worth confirming for:

1. concise outputs, especially for text and file workloads;
2. warm stable prompt prefixes for repeated text workloads;
3. parallel page processing when lower latency justifies extra calls;
4. exposing a smaller relevant tool subset;
5. reusing an MCP process and discovered catalogue;
6. keeping tool definitions stable and avoiding unnecessary schema
   complexity;
7. selecting models per workload rather than assuming the smaller model is
   always faster;
8. treating tool discovery as a token/latency trade-off: Toolbox Search reduced
   context size, but did not improve latency for the tested 50-tool task.

It does not yet justify universal percentage claims, a Priority Processing
claim, or a blog conclusion. Before publication, selected candidates should be
confirmed with 30-50 or more observations, randomized or interleaved execution,
more diverse fixtures, confidence intervals, and the same correctness and
cost gates.
