# AI Response Performance Lab

Reproducible benchmarks for techniques that can improve AI application response
time across text, image, file, and tool-calling workloads.

The project measures latency together with quality, reliability, token usage,
and cost inputs. It does not assume that a technique that helps one workload
helps all workloads.

## Read the findings

- [Detailed lab report](docs/lab-report.md) — architecture, methodology, every
  result table, reliability events, limitations, and reproduction steps.
- [Microsoft Tech Community blog draft](docs/tech-community-blog-draft.md) —
  the decision-oriented publication narrative and recommendations.
- [Publication result ledger](docs/publication-results.md) — execution IDs,
  artifact prefixes, image digests, and the numerical source of truth.
- [Performance testing guidelines](docs/ai-response-performance-guidelines.md)
  — a reusable method for defining timing, quality, sample, cost, and reporting
  controls.
- [Copilot skill](.github/skills/ai-response-performance/SKILL.md) — apply the
  method from a real application workspace.

## Use the Copilot skill in your application

[Agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
work in agent mode in Visual Studio Code. Install this skill in a target
application repository with GitHub CLI 2.90.0 or later:

```powershell
gh skill preview yelghali/foundy-ai-perf-testing ai-response-performance
gh skill install yelghali/foundy-ai-perf-testing ai-response-performance
```

GitHub CLI installs project skills under `.github/skills` by default. You can
also copy `.github/skills/ai-response-performance` into another repository, or
into `~/.copilot/skills` to make it available across projects.

Open the application in VS Code agent mode and ask Copilot to use the AI
response performance skill for a specific workflow. Include the task, latency
goal, deployment environment, and whether paid cloud tests are allowed. For
example:

> Use the AI response performance skill to design a one-lever-at-a-time
> latency benchmark for our support chat. Optimize time to a correct final
> answer, preserve answer quality, and do not run paid cloud tests without my
> approval.

## Project status

The implementation includes:

- the benchmark methodology in [docs/benchmark-plan.md](docs/benchmark-plan.md);
- Terraform for keyless Azure OpenAI deployments and an Azure Container Apps
  benchmark job;
- text, generated-image, generated-PDF, native-tool, and MCP scenarios;
- model, output, input, connection, cache, Priority Processing, and streaming
  variants;
- separate image resize/detail/cascade, PDF/extracted-text/page-parallelism,
  and tool count/description/schema/ambiguity/order/lifecycle experiments;
- correctness scoring, concurrency, JSONL observations, JSON summaries, and
  HTML reports;
- seeded randomized complete-block runs over five fixtures per scenario, with
  descriptive p95/p99 and bootstrap p50 95% confidence intervals;
- an optional controlled comparison between direct remote MCP and Microsoft
  Foundry Toolbox Tool Search over the same 50-tool synthetic catalogue;
- a three-way confirmation covering Non-optimized Standard (PAYGO), Optimized
  Standard (PAYGO), and Optimized + Priority Processing on one supported model
  deployment;
- private blob artifact upload through managed identity and a private endpoint.

RAG remains a separate later track, as described in the benchmark plan.
The first Azure screen and controlled-concurrency measurements are documented
in [docs/cloud-screen-results.md](docs/cloud-screen-results.md).

## Prerequisites

- Python 3.11 or later
- Terraform 1.7 or later
- Azure CLI
- an Azure subscription with Azure OpenAI access and model quota

## Local setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT`, then authenticate:

```powershell
az login --use-device-code --tenant <tenant-id>
```

Run the text benchmark:

```powershell
.\.venv\Scripts\ai-perf.exe run-text --repetitions 10 --warmups 3
```

Run all functional smoke scenarios:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile smoke --warmups 1 --repetitions 2
```

Run the complete one-lever-at-a-time screen:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile screen --warmups 3 --repetitions 10
```

The screen contains 49 core cases. It contains 51 when
`AI_PERF_REMOTE_MCP_URL` and `AI_PERF_TOOLBOX_ENDPOINT` are both configured,
adding direct remote MCP and Foundry Toolbox Tool Search cases. Use
`--concurrency` to measure the same case group under controlled load; the
requested level is stored in every raw observation.

Use `--scenario` and `--variant` to isolate a case:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile screen `
  --scenario tool_calling `
  --variant verbose-descriptions
```

Run only the controlled remote MCP comparison:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile screen `
  --warmups 3 `
  --repetitions 10 `
  --scenario tool_calling `
  --variant mcp-remote-50 `
  --variant foundry-toolbox-search-50
```

Run a publication-oriented confirmation with 30 randomized rounds:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile screen `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904
```

Interleaved mode requires concurrency 1. Every case runs once per round in a
seeded random order against the same rotating fixture. The report includes
correct-completion rate, p50, descriptive p95/p99, bootstrap p50 intervals,
and paired baseline-relative p50 effect intervals. See
[docs/publication-results.md](docs/publication-results.md) for the completed
Azure one-lever and non-optimized-to-optimized confirmation runs.

Run the 12-case bundle confirmation with 30 randomized rounds:

```powershell
.\.venv\Scripts\ai-perf.exe run-suite `
  --profile bundle `
  --warmups 3 `
  --repetitions 30 `
  --schedule interleaved `
  --seed 20260904
```

The bundle profile requires `AZURE_OPENAI_PRIORITY_DEPLOYMENT`. It compares the
combined supported software changes in a Non-optimized Standard (PAYGO) and
Optimized Standard (PAYGO) configuration, then applies Priority Processing to
the identical optimized configuration.

Summarize an existing JSONL result:

```powershell
.\.venv\Scripts\ai-perf.exe summarize results\raw\<result-file>.jsonl
```

## Infrastructure

Review [terraform/README.md](terraform/README.md). Terraform creates the Azure
OpenAI deployments, Foundry account and project, private registry and result
storage, managed identity, private network, Container Apps manual job, and a
public Container App serving the deterministic 50-tool MCP catalogue. The
benchmark receives no API keys or storage keys.

After `terraform apply`, configure the Toolbox developer settings from the
outputs and create its first version:

```powershell
$env:FOUNDRY_PROJECT_ENDPOINT = terraform -chdir=terraform output -raw foundry_project_endpoint
$env:AI_PERF_REMOTE_MCP_URL = terraform -chdir=terraform output -raw remote_mcp_url
$env:AI_PERF_TOOLBOX_ENDPOINT = terraform -chdir=terraform output -raw foundry_toolbox_endpoint
.\.venv\Scripts\ai-perf.exe provision-toolbox
```

Provisioning is idempotent: it creates version 1 only when the named Toolbox
does not already exist. Tool Search is a preview feature. It uses BM25 over
tool names, descriptions, and parameters, and initially exposes `tool_search`
and `call_tool` rather than all underlying definitions. See the official
[Tool Search documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search)
and [Toolbox documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox).

The remote MCP endpoint is intentionally anonymous and public so the managed
Foundry service can reach it. It contains only deterministic, read-only
synthetic benchmark tools and no secrets or production data. Do not reuse this
deployment pattern for production without supported authentication or private
connectivity.

After applying Terraform and publishing the image, start the cloud integration
screen with:

```powershell
az containerapp job start `
  --name (terraform -chdir=terraform output -raw benchmark_job_name) `
  --resource-group (terraform -chdir=terraform output -raw resource_group_name)
```

The checked-in job template uses one warm-up and two measurements per case to
validate the integration. Use an execution-only YAML override with three
warm-ups and ten measurements for initial performance screening; this does not
change the Terraform-managed job.

## Result interpretation

Raw observations are written under `results/raw/`. Reports include only
successful calls in latency percentiles while retaining quality failures and
errors as explicit fields. They also report time to first token, token rates,
input/output/reasoning/cache tokens, requested and actual service tiers,
stage timings, concurrency, batch elapsed time, and achieved throughput. A
faster result is not considered an optimization unless it passes the
scenario's correctness check.

The `smoke` profile proves integration. Its sample count is intentionally too
small for performance conclusions. Use the screening and confirmation sample
sizes in the benchmark plan before publishing comparisons.

See [docs/cloud-screen-results.md](docs/cloud-screen-results.md) for the first
48-case Azure screen, the targeted remote MCP versus Toolbox comparison, its
limitations, and the measured concurrency 5/10/20 results. The later
[publication-oriented results](docs/publication-results.md) supersede that
initial screen for performance findings.
