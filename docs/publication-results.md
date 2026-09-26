# Publication-oriented Azure benchmark results

## Scope

This run tested every implemented performance lever with real Azure OpenAI
requests. It is designed to support evidence-based findings and a later blog,
not universal performance guarantees.

- 51 configured cases across text, image, file, native tools, MCP, and Foundry
  Toolbox Search.
- Five deterministic fixtures per scenario.
- Three unmeasured warm-ups per case.
- 30 measured randomized rounds per case.
- Seeded randomized complete-block schedule: `20260904`.
- 5,000-sample bootstrap 95% intervals.
- Paired comparisons by round when the treatment and control were in the same
  execution.
- Latency distributions include only successful, quality-passing requests.
  Correct-completion rates use every attempted request.

The one-lever analysis uses 1,680 measurements. Another 120 measurements from
the first new-client runs were discarded because client construction was
initially outside the corrected client-lifecycle timer. In total, 1,800
one-lever publication-run requests were executed. A later
non-optimized-to-optimized confirmation added 360 measurements, bringing the
final evidence set to 2,040 measurements and the total measured publication
executions to 2,160, plus cloud preflights.

For reused-client single-response cases, reported AI-path latency starts
immediately before the Responses API call. Deterministic image generation and
resize, PDF generation, and extracted-text preparation occur before that
timer. Composed page and tool workflows include their model and tool stages
after fixture preparation. These are not user-click-to-render measurements.

Intervals are not adjusted for testing many hypotheses. A result labelled
**faster** or **slower** has a bootstrap p50-effect interval that excludes zero,
but it should still be independently replicated before publication.
With 30 observations per case, p95 and p99 are descriptive; the paired p50
effect intervals are the inferential comparisons in this ledger.

## Executions and artifacts

| Scope | Job execution | Artifact prefix | Image | Measurements |
|---|---|---|---|---:|
| 51-case preflight | `job-aiperf-6l2kni-zicg036` | `20260904T164428Z` | `ch13` | 51 |
| Text | `job-aiperf-6l2kni-nnc62o6` | `20260904T165156Z` | `ch13` | 270 |
| Image | `job-aiperf-6l2kni-iyrljso` | `20260904T170420Z` | `ch13` | 300 |
| File | `job-aiperf-6l2kni-nd92mw3` | `20260904T171753Z` | `ch13` | 330 |
| Tool catalogue and prompts | `job-aiperf-6l2kni-9xd9xfk` | `20260904T173143Z` | `ch13` | 450 |
| Tool integrations and execution | `job-aiperf-6l2kni-l64rem0` | `20260904T181348Z` | `ch14` | 210 |
| Corrected client-reuse comparison | `job-aiperf-6l2kni-b6oe74l` | `20260904T183141Z` | `ch15` | 240 |
| Bundle preflight | `job-aiperf-6l2kni-o8k8z7g` | `20260904T203720Z` | `ch17` | 12 |
| Non-optimized Standard (PAYGO), Optimized Standard (PAYGO), and Optimized + Priority Processing confirmation | `job-aiperf-6l2kni-3rl9th4` | `20260904T203946Z` | `ch17` | 360 |

Images and digests:

- `ch13`: `sha256:b7745362737697a73f4911e61a33f210a1e13d0ca64ba5d654e8a0a77f6ab811`
- `ch14`: `sha256:55e76b6cf7a0ec6c5b64655a119255cafe8c24912aefa6669150fcb4c404b762`
- `ch15`: `sha256:d6495a774794b3d4cc7e7b22e83a998aae65ba48822e30e940a2f325b14bfafd`
- `ch17`: `sha256:48e72ee85244b681994ab1e634cb7e9beee5f84647720cfc043b9cae178e180d`
- `ch18`: `sha256:be043a8379e2e5b098df1e16a710680daf807852e4864b8024de8aa4207cea74`
- `ch19`: `sha256:0b8158943811eedabcb0f50891dd638ea0842f69693bdb9cf9b306a9d38ddb14`

The version changes are narrow:

- `ch14` accepts `2:30 PM` as semantically equivalent to `14:30`.
- `ch15` includes one-shot client construction in the corrected
  client-lifecycle latency.

The earlier fully validated source was published as `ch16`, digest
`sha256:65212b2feb6d42df00f782a5e8f6645e73679ad08e837817bfe4bf959d4b29db`.
It differs from `ch15` only by suppressing bootstrap inference for cohorts
smaller than ten observations. This does not alter the final result tables,
whose cohorts each contain 30 observations.

`ch17` adds the bundle profile and is the image used for the confirmation
measurements. `ch18` adds the direct Optimized + Priority Processing versus
non-optimized Standard (PAYGO) paired interval. `ch19`, currently tagged
`latest`, also exposes that interval in HTML reports. These reporting changes
made no model calls; the additional statistic was recomputed from the immutable
`ch17` raw JSONL.

## Text chat

| Variant | Control | Correct | p50 | p95 | p50 change [95% CI] | Finding |
|---|---|---:|---:|---:|---:|---|
| Baseline | - | 100% | 2078 ms | 4715 ms | - | Control |
| Concise output | Baseline | 96.7% | 1537 ms | 2204 ms | -26.0% [-36.1%, -13.4%] | Faster; one incomplete stream |
| Reduced history | Baseline | 100% | 1813 ms | 4203 ms | -12.7% [-25.5%, +2.2%] | Inconclusive |
| New client per request | Paired baseline | 100% | 2213 ms | 3280 ms | -1.9% [-13.4%, +5.6%] | Inconclusive |
| Cache cold | - | 100% | 1935 ms | 5120 ms | - | Cache control |
| Cache warm | Cache cold | 100% | 1647 ms | 2129 ms | -14.9% [-25.2%, -6.9%] | Faster |
| Priority Processing requested | Baseline | 100% | 1960 ms | 4042 ms | -5.7% [-18.2%, +5.0%] | Invalid: served as default |
| Smaller model | Baseline | 100% | 1869 ms | 3424 ms | -10.1% [-22.2%, +14.5%] | Inconclusive |
| Non-streaming | Streaming baseline | 100% | 2349 ms | 4210 ms | +13.0% [-6.4%, +34.1%] | Total latency inconclusive |

The streaming baseline delivered its first token in 912 ms on average, versus
a 2078 ms total-latency median. Warm caching lowered average first-token
latency from 991 ms in the controlled cold case to 602 ms.

## Image understanding

| Variant | Control | Correct | p50 | p95 | p50 change [95% CI] | Finding |
|---|---|---:|---:|---:|---:|---|
| Baseline | - | 100% | 1646 ms | 5087 ms | - | Control |
| Concise JSON | Baseline | 100% | 1237 ms | 4751 ms | -24.9% [-32.3%, -16.2%] | Faster |
| Resized image | Baseline | 100% | 1435 ms | 8802 ms | -12.8% [-21.9%, -3.4%] | Faster median, worse tail |
| New client per request | Paired baseline | 100% | 1715 ms | 4142 ms | +1.3% [-10.7%, +17.0%] | Inconclusive |
| Cache cold | - | 100% | 1897 ms | 8040 ms | - | Cache control |
| Cache warm | Cache cold | 100% | 1449 ms | 4210 ms | -23.6% [-42.0%, -7.8%] | Faster |
| Priority Processing requested | Baseline | 100% | 1669 ms | 6352 ms | +1.4% [-10.6%, +25.6%] | Invalid: served as default |
| Smaller model | Baseline | 100% | 2058 ms | 5416 ms | +25.0% [+16.3%, +61.4%] | Slower |
| Low detail | Baseline | 100% | 1352 ms | 3846 ms | -17.8% [-24.6%, -2.5%] | Faster |
| Low-detail cascade | Baseline | 100% | 1476 ms | 4714 ms | -10.3% [-18.7%, -2.5%] | Faster |

Resizing reduced median latency, but p95 increased from 5.1 to 8.8 seconds and
p99 increased from 7.6 to 10.4 seconds. It is therefore not a robust general
recommendation from this data.

## File processing

| Variant | Control | Correct | p50 | p95 | p50 change [95% CI] | Finding |
|---|---|---:|---:|---:|---:|---|
| Baseline PDF | - | 100% | 1445 ms | 3004 ms | - | Control |
| Concise JSON | Baseline | 100% | 1215 ms | 5566 ms | -15.9% [-30.8%, +6.6%] | Inconclusive; worse tail |
| Relevant page only | Baseline | 100% | 1465 ms | 2857 ms | +1.4% [-6.5%, +21.6%] | Inconclusive |
| New client per request | Paired baseline | 100% | 1423 ms | 5061 ms | -4.8% [-19.2%, +8.2%] | Inconclusive |
| Cache cold | - | 100% | 1544 ms | 7601 ms | - | Cache control |
| Cache warm | Cache cold | 100% | 1776 ms | 2954 ms | +15.0% [-16.4%, +34.7%] | Inconclusive |
| Priority Processing requested | Baseline | 100% | 1487 ms | 8020 ms | +2.9% [-6.3%, +24.6%] | Invalid: served as default |
| Smaller model | Baseline | 100% | 1329 ms | 4917 ms | -8.0% [-24.5%, +16.0%] | Inconclusive |
| Extracted text | Baseline PDF | 100% | 1197 ms | 1752 ms | -17.2% [-22.1%, -3.2%] | Faster |
| Sequential pages | - | 100% | 2811 ms | 6517 ms | - | Page control |
| Parallel pages | Sequential pages | 100% | 1216 ms | 3784 ms | -56.8% [-63.2%, -45.1%] | Faster |

Sequential and parallel page cases both make three model calls, so the
parallel result isolates scheduling rather than a different call count.

## Tool catalogue and prompt design

| Variant | Control | Correct | p50 | p95 | p50 change [95% CI] | Finding |
|---|---|---:|---:|---:|---:|---|
| Native 20-tool baseline | - | 100% | 2289 ms | 4488 ms | - | Control |
| Concise output | Baseline | 100% | 2350 ms | 8077 ms | +2.7% [-20.7%, +20.8%] | Inconclusive |
| Five exposed tools | Baseline | 100% | 1904 ms | 4005 ms | -16.8% [-34.3%, -9.9%] | Faster |
| New client per request | Paired baseline | 100% | 2173 ms | 3605 ms | +2.7% [-8.7%, +20.5%] | Inconclusive |
| Cache cold | - | 100% | 2294 ms | 2883 ms | - | Cache control |
| Cache warm | Cache cold | 100% | 2226 ms | 5374 ms | -3.0% [-12.0%, +18.3%] | Inconclusive |
| Priority Processing requested | Baseline | 100% | 2100 ms | 5639 ms | -8.2% [-25.4%, +1.0%] | Invalid: served as default |
| Smaller model | Baseline | 100% | 2187 ms | 4721 ms | -4.4% [-22.3%, +5.8%] | Inconclusive |
| Fifty tools | Baseline | 100% | 2492 ms | 4288 ms | +8.9% [-16.9%, +15.1%] | Inconclusive |
| Minimal descriptions | Baseline | 100% | 1959 ms | 4185 ms | -14.4% [-31.8%, -4.4%] | Faster |
| Verbose descriptions | Baseline | 100% | 1954 ms | 3863 ms | -14.6% [-31.7%, -8.5%] | Cache-confounded |
| Many-parameter schema | Baseline | 100% | 2443 ms | 7818 ms | +6.7% [-15.5%, +32.6%] | Inconclusive; worse tail |
| Nested schema | Baseline | 100% | 2309 ms | 4340 ms | +0.9% [-19.8%, +9.7%] | Inconclusive |
| Ambiguous descriptions | Baseline | 100% | 2502 ms | 3480 ms | +9.3% [-13.3%, +17.6%] | Inconclusive |
| Reordered definitions | Cache warm | 100% | 2655 ms | 6583 ms | +19.3% [-4.6%, +52.4%] | Inconclusive |

The verbose-description row had a 90% prompt-cache hit rate while the native
baseline had none, so its apparent improvement cannot be attributed to
description length. Minimal descriptions had no cache hits and remain the
cleaner finding.

## Tool integrations and execution

| Variant | Control | Correct | p50 | p95 | p50 change [95% CI] | Finding |
|---|---|---:|---:|---:|---:|---|
| Native baseline | - | 100% | 2057 ms | 5645 ms | - | Integration control |
| Warm local MCP | Native baseline | 100% | 2283 ms | 4353 ms | +11.0% [-7.1%, +22.6%] | Inconclusive |
| Cold local MCP | Warm MCP | 100% | 3061 ms | 3704 ms | +34.1% [+20.9%, +58.0%] | Slower |
| Direct remote MCP, 50 tools | - | 96.7% | 2528 ms | 7797 ms | - | Toolbox control |
| Foundry Toolbox Search | Direct remote MCP | 100% | 3614 ms | 4751 ms | +43.0% [+26.1%, +76.4%] | Slower median |
| Sequential two-tool orchestration | - | 100% | 3646 ms | 8688 ms | - | Orchestration control |
| Single-round two-tool orchestration | Sequential tools | 100% | 2617 ms | 4761 ms | -28.2% [-36.5%, -9.3%] | Faster |

Cold MCP discovery averaged 1016 ms and accounted for most of the cold-session
penalty. The tool itself averaged under 5 ms locally.

The two-tool treatment keeps the same user task and tool invocations, but it
does not keep model-call count constant. The sequential arm selects one tool
per model round; the parallel arm permits both calls in one selection response
and executes them concurrently. Its 28.2% effect is therefore an orchestration
result that combines one fewer model-selection round with concurrent tool
execution, not a pure backend parallelism effect.

Toolbox Search used 1,431 average input tokens versus 1,941 for direct remote
MCP, a 26% reduction. It nevertheless added a model search round and increased
p50. Its p95 was lower than direct MCP in this run, and it achieved 100%
correctness while direct MCP omitted the requested temperature once. The
finding is therefore a latency/token/reliability trade-off, not a blanket
rejection of Toolbox Search.

## Combined non-optimized-to-optimized confirmation

This confirmation keeps the one-lever tables above; it does not replace them.
It asks how much is gained when compatible supported findings are combined.
Each scenario ran three non-streaming arms on the same `gpt-4.1` version
`2025-04-14` Global Standard deployment in `eastus2`:

1. a non-optimized but valid Standard (PAYGO) configuration;
2. the best supported software bundle on Standard (PAYGO);
3. the identical best bundle with request-level Priority Processing.

| Scenario | Non-optimized Standard (PAYGO) | Optimized Standard (PAYGO) and Optimized + Priority Processing |
|---|---|---|
| Text | Cold long prefix, full history, normal output | Warm prefix cache, concise output |
| Image | Cold long prefix, high detail, normal output | Warm prefix cache, low detail, concise JSON |
| File | Native full PDF | Extracted text |
| Tools | 20 concise tools, sequential two-tool execution | Five minimal tools, parallel two-tool execution |

The model was changed from the original `gpt-4.1-mini` screen because current
[Microsoft Priority Processing documentation](https://learn.microsoft.com/azure/foundry/openai/concepts/priority-processing)
lists `gpt-4.1` but not `gpt-4.1-mini` as supported. The deployment is
`gpt-4.1-priority-benchmark`, at 100K TPM. Every successful request reported
the explicitly requested tier.

The confirmation validates the complete configurations on `gpt-4.1`; it does
not prove that every one-lever effect measured on `gpt-4.1-mini` transferred
independently.

| Scenario | Non-optimized Standard (PAYGO) p50 / p95 | Optimized Standard (PAYGO) p50 / p95 | Software p50 change [95% CI] | Optimized + Priority Processing p50 / p95 | Priority Processing over Optimized Standard (PAYGO) [95% CI] | Optimized + Priority Processing over non-optimized Standard (PAYGO) [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| Text | 2070 / 4859 ms | 2125 / 4636 ms | +2.7% [-10.4%, +13.3%] | 1222 / 2009 ms | -42.5% [-46.7%, -37.5%] | **-41.0% [-47.3%, -34.8%]** |
| Image | 2872 / 6211 ms | 2234 / 5722 ms | -22.2% [-33.7%, -16.5%] | 1448 / 4963 ms | -35.2% [-42.3%, -22.5%] | **-49.6% [-57.0%, -39.9%]** |
| File | 1512 / 4824 ms | 1245 / 2895 ms | -17.7% [-27.0%, -5.7%] | 1165 / 4949 ms | -6.5% [-17.9%, +0.3%] | **-23.0% [-33.2%, -13.7%]** |
| Tools | 3817 / 8098 ms | 2824 / 4026 ms | -26.0% [-35.7%, -19.1%] | 2393 / 8023 ms | -15.3% [-25.2%, +3.9%] | **-37.3% [-48.9%, -25.2%]** |

The bold direct comparison is the main confirmation answer: the Optimized +
Priority Processing configuration had a significantly lower p50 than the
Non-optimized Standard (PAYGO) configuration in all four scenarios. As a
descriptive cross-scenario summary, the geometric mean of the four p50 ratios
was 16.5% lower for Optimized Standard (PAYGO) and 38.4% lower for Optimized +
Priority Processing versus Non-optimized Standard (PAYGO). This normalized
summary is not a pooled latency metric and has no aggregate confidence
interval; scenario-level paired intervals remain the primary evidence.

The contribution was not simply additive:

- The software bundle alone clearly helped image, file, and tool workloads,
  but not text on `gpt-4.1`.
- Priority Processing clearly improved text and image p50. Its incremental
  file and tool p50 intervals crossed zero.
- File and tool Priority Processing p95 were worse than Optimized Standard
  (PAYGO) in this run, so Priority Processing is not a universal tail-latency
  win from these samples.
- Text and image warm arms observed 97-100% cache-hit rates; their cold
  controls observed zero.
- Standard (PAYGO) configurations completed correctly 240/240 times. The
  Priority Processing configuration completed correctly 119/120 times. One
  Priority Processing tool request returned HTTP 400: `No tool call found for
  function call output`. It was retained as a reliability failure and excluded
  only from latency percentiles.

The execution is marked failed by Container Apps because the CLI deliberately
returns a nonzero exit after uploading artifacts when any observation fails.
All 360 attempts completed and the JSONL, JSON, and HTML artifacts were
uploaded under private blob prefix `20260904T203946Z`.

An earlier launch, `job-aiperf-6l2kni-xtiunsq`, ignored an incorrectly shaped
execution override and reran the existing screen profile. It is excluded from
all bundle counts and conclusions. The corrected preflight and publication
execution templates were verified from their Azure execution records before
their results were accepted.

## Cross-cutting findings

### Supported by these runs

1. **Reduce output when the output contract permits it.** This clearly helped
   text and image workloads, but not file or tool workloads.
2. **Use verified prompt caching for repeated long prefixes.** It improved text
   and image medians. File and tool cache effects were inconclusive.
3. **Choose image settings empirically.** Low detail helped this extraction
   workload. The smaller model was 25% slower at p50.
4. **Prefer extracted text when PDF rendering is unnecessary.** It improved
   both median and tail latency for the tested file task.
5. **Remove avoidable serial waits.** Parallel pages reduced p50 by 57% with
   the same three model calls. Single-round two-tool orchestration reduced p50
   by 28% by removing a model-selection round and executing both tools
   together.
6. **Limit the exposed tool set and keep descriptions economical.** Five tools
   and minimal descriptions produced clean median improvements.
7. **Reuse MCP sessions.** Cold connection and discovery added a clear 34%
   p50 penalty over a warm session.

### Not supported or invalid

- Recreating the SDK client had no detectable p50 effect in any scenario; mean
  measured client setup was only 7-69 ms in this environment.
- The smaller model was not a consistent latency win and was significantly
  slower for images.
- Schema complexity, ambiguity, fifty-tool exposure, reordered definitions,
  file page selection, and file/tool cache reuse were inconclusive at p50.
- Every Priority Processing request in the original `gpt-4.1-mini` one-lever
  screen was actually served at the `default` tier, so those rows remain
  invalid. Verified Priority Processing results are reported only in the later
  `gpt-4.1` bundle.

## Reliability and limitations

- One of 30 concise text streams ended without a `response.completed` event.
  That variant's correct-completion rate was 96.7%.
- One of 30 direct remote MCP responses selected and executed the correct
  weather tool but omitted the requested temperature in its final answer.
  Its correct-completion rate was 96.7%.
- One of 120 bundle Priority Processing requests failed with a tool-response
  API error. The other 119 successful Priority Processing requests all
  reported the `priority` tier.
- All other final-result rows achieved 100% correct completion.
- The fixtures are synthetic and deterministic. They improve repeatability but
  do not represent every production prompt, image, document, or tool catalogue.
- Azure latency has heavy tails. The 30-run p95 and p99 values are descriptive
  warnings, not production-tail estimates, even when the median interval
  indicates an improvement.
- Cache behavior must be interpreted from observed cached tokens. The cold
  cache cases reported zero hits; warm hit rates ranged from 93% to 100%.
- The confidence intervals cover sampling uncertainty in these runs, not model
  upgrades, regional changes, quota contention, or future service behavior.
- Independent replication and a separate winning-bundle load test remain
  appropriate before making broad production recommendations.
