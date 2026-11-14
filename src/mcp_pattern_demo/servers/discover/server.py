"""Fixed discovery/dispatch surface. Underlying operations are not registered tools."""

from mcp.server.fastmcp import FastMCP

from mcp_pattern_demo.registry import call_tool, get_tool_schema, search_tools


def build_server() -> FastMCP:
    server = FastMCP("discover", log_level="WARNING")
    for operation in (search_tools, get_tool_schema, call_tool):
        server.add_tool(operation)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
