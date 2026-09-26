from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from ai_perf.tool_catalogue import DescriptionStyle, build_tool_specs, execute_tool


def _handler_for(name: str) -> Callable[[str], dict[str, Any]]:
    def handler(query: str) -> dict[str, Any]:
        return execute_tool(name, {"query": query})

    handler.__name__ = name
    return handler


def create_server(
    tool_count: int,
    description_style: DescriptionStyle,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> FastMCP:
    server = FastMCP(
        "AI Response Performance Tools",
        host=host,
        port=port,
        stateless_http=True,
    )
    for spec in build_tool_specs(tool_count, description_style):
        server.tool(
            name=spec.name,
            description=spec.description,
            structured_output=True,
        )(_handler_for(spec.name))
    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-count", type=int, default=20)
    parser.add_argument(
        "--description-style",
        choices=("minimal", "concise", "verbose"),
        default="concise",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    create_server(
        args.tool_count,
        args.description_style,
        host=args.host,
        port=args.port,
    ).run(transport=args.transport)


if __name__ == "__main__":
    main()
