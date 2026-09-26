from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AzureOpenAISettings:
    endpoint: str
    deployment: str
    fast_deployment: str | None = None
    priority_deployment: str | None = None
    foundry_project_endpoint: str | None = None
    foundry_toolbox_name: str = "ai-perf-tools"
    foundry_toolbox_endpoint: str | None = None
    remote_mcp_url: str | None = None
    results_dir: Path = Path("results/raw")
    token_scope: str = "https://cognitiveservices.azure.com/.default"
    foundry_token_scope: str = "https://ai.azure.com/.default"
    storage_account_url: str | None = None
    storage_container: str = "benchmark-results"
    managed_identity_client_id: str | None = None
    azure_region: str | None = None
    benchmark_image: str | None = None

    @classmethod
    def from_env(cls) -> AzureOpenAISettings:
        missing = [
            name
            for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT")
            if not os.getenv(name)
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {joined}")

        return cls(
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            fast_deployment=os.getenv("AZURE_OPENAI_FAST_DEPLOYMENT"),
            priority_deployment=os.getenv("AZURE_OPENAI_PRIORITY_DEPLOYMENT"),
            foundry_project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
            foundry_toolbox_name=os.getenv("AI_PERF_TOOLBOX_NAME", "ai-perf-tools"),
            foundry_toolbox_endpoint=os.getenv("AI_PERF_TOOLBOX_ENDPOINT"),
            remote_mcp_url=os.getenv("AI_PERF_REMOTE_MCP_URL"),
            results_dir=Path(os.getenv("AI_PERF_RESULTS_DIR", "results/raw")),
            storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
            storage_container=os.getenv("AI_PERF_STORAGE_CONTAINER", "benchmark-results"),
            managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"),
            azure_region=os.getenv("AI_PERF_AZURE_REGION"),
            benchmark_image=os.getenv("AI_PERF_BENCHMARK_IMAGE"),
        )

    @property
    def base_url(self) -> str:
        endpoint = self.endpoint.rstrip("/")
        if endpoint.endswith("/openai/v1"):
            return f"{endpoint}/"
        return f"{endpoint}/openai/v1/"

    @property
    def has_toolbox_comparison(self) -> bool:
        return self.remote_mcp_url is not None and self.foundry_toolbox_endpoint is not None

    @property
    def has_priority_deployment(self) -> bool:
        return self.priority_deployment is not None
