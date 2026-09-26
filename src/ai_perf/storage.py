from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from ai_perf.config import AzureOpenAISettings


async def upload_artifacts(
    settings: AzureOpenAISettings,
    paths: Sequence[Path],
    *,
    prefix: str,
) -> list[str]:
    if settings.storage_account_url is None:
        raise ValueError("AZURE_STORAGE_ACCOUNT_URL is required when --upload is used")

    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        managed_identity_client_id=settings.managed_identity_client_id,
    )
    service = BlobServiceClient(settings.storage_account_url, credential=credential)
    uploaded: list[str] = []
    try:
        container = service.get_container_client(settings.storage_container)
        for path in paths:
            blob_name = f"{prefix}/{path.name}"
            blob = container.get_blob_client(blob_name)
            with path.open("rb") as source:
                await blob.upload_blob(source, overwrite=True)
            uploaded.append(blob.url)
    finally:
        await service.close()
        await credential.close()
    return uploaded
