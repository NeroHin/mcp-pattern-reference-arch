"""Sales-case capability scope: four unchanged core tools."""

from mcp.server.fastmcp import FastMCP

from mcp_pattern_demo.registry import CORE, register


def build_server() -> FastMCP:
    server = FastMCP("scoped", log_level="WARNING")
    register(server, CORE)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
