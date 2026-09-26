import pytest

from ai_perf.mcp_client import open_mcp_connection


@pytest.mark.asyncio
async def test_mcp_server_lists_and_executes_tools() -> None:
    async with open_mcp_connection(5, "concise") as connection:
        result = await connection.call_tool("lookup_weather", {"query": "Paris"})

    assert len(connection.tools) == 5
    assert connection.tools[0]["parameters"]["additionalProperties"] is False
    assert result["temperature_c"] == 21
