"""Locate records and load selected content incrementally."""

from mcp.server.fastmcp import FastMCP

from mcp_pattern_demo.backend import get_content, get_metadata, search_records


def build_server() -> FastMCP:
    server = FastMCP("progressive", log_level="WARNING")
    for operation in (search_records, get_metadata, get_content):
        server.add_tool(operation)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
