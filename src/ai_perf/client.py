from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential
from openai import AsyncOpenAI

from ai_perf.config import AzureOpenAISettings


class CachingTokenProvider:
    def __init__(
        self,
        credential: AsyncTokenCredential,
        scope: str,
        *,
        refresh_margin_seconds: int = 300,
    ) -> None:
        self._credential = credential
        self._scope = scope
        self._refresh_margin_seconds = refresh_margin_seconds
        self._token: AccessToken | None = None
        self._lock = asyncio.Lock()

    def _is_valid(self) -> bool:
        return (
            self._token is not None
            and self._token.expires_on - time.time() > self._refresh_margin_seconds
        )

    async def __call__(self) -> str:
        if self._is_valid():
            return self._token.token
        async with self._lock:
            if not self._is_valid():
                self._token = await self._credential.get_token(self._scope)
            return self._token.token


@asynccontextmanager
async def create_client(settings: AzureOpenAISettings) -> AsyncGenerator[AsyncOpenAI]:
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        managed_identity_client_id=settings.managed_identity_client_id,
    )
    token_provider = CachingTokenProvider(credential, settings.token_scope)
    client = AsyncOpenAI(base_url=settings.base_url, api_key=token_provider)
    try:
        yield client
    finally:
        await client.close()
        await credential.close()
