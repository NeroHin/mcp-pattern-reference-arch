"""Flat baseline: twenty tools, isolated entry point."""

from mcp.server.fastmcp import FastMCP

from mcp_pattern_demo.registry import CORE, DISTRACTORS, register


def build_server() -> FastMCP:
    server = FastMCP("flat", log_level="WARNING")
    register(server, CORE + DISTRACTORS)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
