# Terraform infrastructure

This configuration creates:

- one resource group;
- one Azure OpenAI cognitive account with local API-key authentication disabled;
- baseline and smaller comparison deployments, plus the model deployment used
  for Priority Processing;
- one Microsoft Foundry account and project;
- a private Azure Container Registry;
- private blob storage for benchmark artifacts;
- a public, one-replica Container App serving 50 deterministic synthetic MCP
  tools over streamable HTTP;
- an Azure Container Apps manual job with a user-assigned managed identity;
- a VNet-integrated Container Apps environment and blob private endpoint;
- least-privilege roles for model access, image pull, and result upload;
- a `Cognitive Services OpenAI User` assignment for the deployment identity;
- `Foundry User` assignments for the deployment and benchmark identities;
- Blob and Queue data-plane roles for the deployment identity so the AzureRM
  provider can manage policy-locked storage without a shared key.

## Prepare

Authenticate with Azure CLI and select the intended subscription:

```powershell
az login --use-device-code --tenant <tenant-id>
az account set --subscription <subscription-id>
$env:ARM_SUBSCRIPTION_ID = az account show --query id -o tsv
```

Confirm that the selected model/version, SKU, capacity, and region are available
to the subscription before applying. The deployment identity must be allowed
to create role assignments at the target scope.

```powershell
Set-Location terraform
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
terraform apply -target azurerm_container_registry.this
```

Build the image with ACR Tasks, then apply the complete configuration:

```powershell
$registry = terraform output -raw container_registry_login_server
az acr build --registry $registry.Split('.')[0] --image ai-perf:latest ..
terraform apply
```

Terraform creates the Foundry resources and remote MCP host, while the Python
SDK creates the preview Toolbox version. Use the outputs to configure a local
runner and provision the Toolbox:

```powershell
$env:AZURE_OPENAI_ENDPOINT = terraform output -raw azure_openai_endpoint
$env:AZURE_OPENAI_DEPLOYMENT = terraform output -raw azure_openai_deployment
$env:AZURE_OPENAI_FAST_DEPLOYMENT = terraform output -raw azure_openai_fast_deployment
$env:AZURE_OPENAI_PRIORITY_DEPLOYMENT = terraform output -raw azure_openai_priority_deployment
$env:FOUNDRY_PROJECT_ENDPOINT = terraform output -raw foundry_project_endpoint
$env:AI_PERF_REMOTE_MCP_URL = terraform output -raw remote_mcp_url
$env:AI_PERF_TOOLBOX_ENDPOINT = terraform output -raw foundry_toolbox_endpoint
..\.venv\Scripts\ai-perf.exe provision-toolbox
```

The command creates an `ai-perf-tools` Toolbox version containing the remote
MCP server and Foundry Tool Search, or reuses the existing Toolbox. The Toolbox
consumer authenticates with an Entra token scoped to
`https://ai.azure.com/.default`; both the local deployment identity and job
managed identity have the project-level `Foundry User` role.

The Foundry service must be able to reach the MCP server. This benchmark
therefore exposes a public anonymous endpoint that contains only deterministic,
read-only synthetic tools and no secrets. Production MCP deployments need
supported authentication or private connectivity instead.

Start the cloud integration screen:

```powershell
az containerapp job start `
  --name (terraform output -raw benchmark_job_name) `
  --resource-group (terraform output -raw resource_group_name)
```

The job uploads JSONL, JSON, and HTML artifacts to the private
`benchmark-results` container. The storage account disables public network and
shared-key access. Access it from an approved private-network path, or inspect
the JSON summary printed in Container Apps job logs.

The default job runs all 49 core cases plus the two Toolbox comparison cases
with one warm-up and two measurements. This is an integration screen, not a
statistically meaningful comparison. Start an execution with a YAML template
override to use the plan's three warm-ups and ten screening measurements
without introducing Terraform drift.

Tool Search is a preview feature. It initially hides the 50 MCP definitions
behind the `tool_search` and `call_tool` meta-tools, with BM25 discovery over
the tool metadata. The benchmark records search, selection, execution, and
final-generation time separately.

The bundle profile uses `gpt-4.1` version `2025-04-14` on a Global Standard
deployment, which supports Priority Processing in `eastus2`. The Standard
(PAYGO) and Priority Processing configurations use the same deployment and
select the tier per request. This avoids a model or deployment confound. The
response's actual service tier and any rejection are preserved in results.
