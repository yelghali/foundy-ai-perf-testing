import pytest
from azure.core.credentials import AccessToken

from ai_perf.client import CachingTokenProvider


class FakeCredential:
    def __init__(self) -> None:
        self.calls = 0

    async def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        self.calls += 1
        return AccessToken("token", 4_102_444_800)


@pytest.mark.asyncio
async def test_token_provider_caches_valid_token() -> None:
    credential = FakeCredential()
    provider = CachingTokenProvider(credential, "scope")

    assert await provider() == "token"
    assert await provider() == "token"
    assert credential.calls == 1
