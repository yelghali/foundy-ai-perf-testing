from __future__ import annotations

from dataclasses import dataclass

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPToolboxTool, ToolboxSearchPreviewToolboxTool
from azure.identity import DefaultAzureCredential

from ai_perf.config import AzureOpenAISettings


@dataclass(frozen=True)
class ToolboxProvisioningResult:
    name: str
    version: str
    endpoint: str
    created: bool


def provision_toolbox(settings: AzureOpenAISettings) -> ToolboxProvisioningResult:
    if settings.foundry_project_endpoint is None:
        raise ValueError("FOUNDRY_PROJECT_ENDPOINT is required to provision the toolbox")
    if settings.remote_mcp_url is None:
        raise ValueError("AI_PERF_REMOTE_MCP_URL is required to provision the toolbox")

    endpoint = settings.foundry_project_endpoint.rstrip("/")
    toolbox_endpoint = (
        f"{endpoint}/toolboxes/{settings.foundry_toolbox_name}/mcp?api-version=v1"
    )
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        managed_identity_client_id=settings.managed_identity_client_id,
    )
    try:
        with AIProjectClient(
            endpoint=endpoint,
            credential=credential,
            allow_preview=True,
        ) as project:
            existing = next(
                (
                    toolbox
                    for toolbox in project.toolboxes.list()
                    if toolbox.name == settings.foundry_toolbox_name
                ),
                None,
            )
            if existing is not None:
                versions = list(
                    project.toolboxes.list_versions(name=settings.foundry_toolbox_name)
                )
                if not versions:
                    raise RuntimeError(
                        f"Toolbox {settings.foundry_toolbox_name} has no versions"
                    )
                return ToolboxProvisioningResult(
                    name=settings.foundry_toolbox_name,
                    version=str(versions[0].version),
                    endpoint=toolbox_endpoint,
                    created=False,
                )

            created = project.toolboxes.create_version(
                name=settings.foundry_toolbox_name,
                description=(
                    "AI response performance catalogue with Foundry BM25 tool search."
                ),
                tools=[
                    MCPToolboxTool(
                        server_label="benchmark",
                        server_url=settings.remote_mcp_url,
                        require_approval="never",
                    ),
                    ToolboxSearchPreviewToolboxTool(),
                ],
            )
            return ToolboxProvisioningResult(
                name=str(created.name),
                version=str(created.version),
                endpoint=toolbox_endpoint,
                created=True,
            )
    finally:
        credential.close()
