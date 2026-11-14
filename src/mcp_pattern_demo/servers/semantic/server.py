"""Governed metric definitions plus original support evidence."""

from mcp.server.fastmcp import FastMCP

from mcp_pattern_demo.backend import (
    get_case_notes,
    get_dimensions,
    get_order,
    list_metrics,
    query_metrics,
)


def build_server() -> FastMCP:
    server = FastMCP("semantic", log_level="WARNING")
    for operation in (list_metrics, get_dimensions, query_metrics, get_order, get_case_notes):
        server.add_tool(operation)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
