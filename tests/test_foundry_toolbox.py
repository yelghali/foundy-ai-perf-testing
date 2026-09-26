import pytest

from ai_perf.config import AzureOpenAISettings
from ai_perf.foundry_toolbox import provision_toolbox


def test_provisioning_requires_foundry_project_endpoint() -> None:
    settings = AzureOpenAISettings(
        endpoint="https://example.openai.azure.com",
        deployment="test",
        remote_mcp_url="https://mcp.example.com/mcp",
    )

    with pytest.raises(ValueError, match="FOUNDRY_PROJECT_ENDPOINT"):
        provision_toolbox(settings)


def test_provisioning_requires_remote_mcp_url() -> None:
    settings = AzureOpenAISettings(
        endpoint="https://example.openai.azure.com",
        deployment="test",
        foundry_project_endpoint="https://foundry.example.com/api/projects/test",
    )

    with pytest.raises(ValueError, match="AI_PERF_REMOTE_MCP_URL"):
        provision_toolbox(settings)
