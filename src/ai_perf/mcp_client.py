from __future__ import annotations

import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from azure.identity.aio import DefaultAzureCredential
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, Tool

from ai_perf.tool_catalogue import DescriptionStyle


@dataclass
class MCPConnection:
    session: ClientSession
    tools: list[dict[str, Any]]
    discovery_ms: float

    async def call_tool_result(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> CallToolResult:
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            raise RuntimeError(f"MCP tool {name} returned an error: {result.content}")
        return result

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self.call_tool_result(name, arguments)
        structured = result.structuredContent
        if not isinstance(structured, dict):
            raise TypeError(f"MCP tool {name} did not return structured content")
        return structured


def _as_openai_tool(tool: Tool, *, strict: bool) -> dict[str, Any]:
    schema = dict(tool.inputSchema)
    if strict:
        schema["additionalProperties"] = False
    converted: dict[str, Any] = {
        "type": "function",
        "name": tool.name,
        "description": tool.description or "",
        "parameters": schema,
    }
    if strict:
        converted["strict"] = True
    return converted


@asynccontextmanager
async def open_mcp_connection(
    tool_count: int,
    description_style: DescriptionStyle,
) -> AsyncGenerator[MCPConnection]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "ai_perf.mcp_server",
            "--tool-count",
            str(tool_count),
            "--description-style",
            description_style,
        ],
    )
    started = time.perf_counter()
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        listed = await session.list_tools()
        discovery_ms = (time.perf_counter() - started) * 1000
        tools = [_as_openai_tool(tool, strict=True) for tool in listed.tools]
        yield MCPConnection(session=session, tools=tools, discovery_ms=discovery_ms)


@asynccontextmanager
async def open_remote_mcp_connection(
    url: str,
) -> AsyncGenerator[MCPConnection]:
    async with httpx.AsyncClient(timeout=60) as http_client:
        started = time.perf_counter()
        async with (
            streamable_http_client(url, http_client=http_client) as (
                read_stream,
                write_stream,
                _,
            ),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            discovery_ms = (time.perf_counter() - started) * 1000
            tools = [_as_openai_tool(tool, strict=True) for tool in listed.tools]
            yield MCPConnection(session=session, tools=tools, discovery_ms=discovery_ms)


@asynccontextmanager
async def open_foundry_toolbox_connection(
    endpoint: str,
    *,
    managed_identity_client_id: str | None,
    token_scope: str,
) -> AsyncGenerator[MCPConnection]:
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        managed_identity_client_id=managed_identity_client_id,
    )
    try:
        token = await credential.get_token(token_scope)
        headers = {"Authorization": f"Bearer {token.token}"}
        async with httpx.AsyncClient(headers=headers, timeout=60) as http_client:
            started = time.perf_counter()
            async with (
                streamable_http_client(endpoint, http_client=http_client) as (
                    read_stream,
                    write_stream,
                    _,
                ),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()
                listed = await session.list_tools()
                discovery_ms = (time.perf_counter() - started) * 1000
                tools = [_as_openai_tool(tool, strict=False) for tool in listed.tools]
                yield MCPConnection(session=session, tools=tools, discovery_ms=discovery_ms)
    finally:
        await credential.close()
