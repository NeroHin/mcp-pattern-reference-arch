import sys

import pytest
from agents.mcp import MCPServerStdio

from mcp_pattern_demo.registry import CORE

EXPECTED = {
    "flat": 20,
    "scoped": 4,
    "progressive": 3,
    "discover": 3,
    "semantic": 5,
    "domain": 1,
}


@pytest.mark.parametrize("pattern", EXPECTED)
async def test_independent_stdio_server_namespaces(pattern):
    async with MCPServerStdio(
        params={
            "command": sys.executable,
            "args": ["-m", f"mcp_pattern_demo.servers.{pattern}.server"],
        },
    ) as server:
        tools = await server.list_tools()
        assert len(tools) == EXPECTED[pattern]
        names = {tool.name for tool in tools}
        if pattern == "scoped":
            assert names == set(CORE)
        if pattern == "discover":
            assert not (names & set(CORE))
            result = await server.call_tool(
                "call_tool",
                {
                    "operation_id": "get_case_notes",
                    "arguments": {"order_id": "O02"},
                },
            )
            assert not result.isError
            assert "N02b" in str(result)


async def test_flat_and_scoped_core_schemas_are_identical():
    schemas = []
    for pattern in ("flat", "scoped"):
        async with MCPServerStdio(
            params={
                "command": sys.executable,
                "args": ["-m", f"mcp_pattern_demo.servers.{pattern}.server"],
            },
        ) as server:
            schemas.append(
                {
                    t.name: (t.inputSchema, t.description)
                    for t in await server.list_tools()
                    if t.name in CORE
                }
            )
    assert schemas[0] == schemas[1]
