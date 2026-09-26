from pathlib import Path

import pytest

from ai_perf.config import AzureOpenAISettings


def test_base_url_is_normalized() -> None:
    settings = AzureOpenAISettings(
        endpoint="https://example.openai.azure.com/",
        deployment="test",
    )

    assert settings.base_url == "https://example.openai.azure.com/openai/v1/"


def test_existing_v1_base_url_is_not_duplicated() -> None:
    settings = AzureOpenAISettings(
        endpoint="https://example.openai.azure.com/openai/v1",
        deployment="test",
        results_dir=Path("results"),
    )

    assert settings.base_url == "https://example.openai.azure.com/openai/v1/"


def test_missing_environment_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT"):
        AzureOpenAISettings.from_env()


def test_toolbox_comparison_requires_both_endpoints() -> None:
    settings = AzureOpenAISettings(
        endpoint="https://example.openai.azure.com/",
        deployment="test",
        remote_mcp_url="https://mcp.example.com/mcp",
        foundry_toolbox_endpoint="https://foundry.example.com/toolbox/mcp",
    )

    assert settings.has_toolbox_comparison is True


def test_priority_deployment_is_read_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "baseline")
    monkeypatch.setenv("AZURE_OPENAI_PRIORITY_DEPLOYMENT", "priority-supported")

    settings = AzureOpenAISettings.from_env()

    assert settings.priority_deployment == "priority-supported"
    assert settings.has_priority_deployment is True
