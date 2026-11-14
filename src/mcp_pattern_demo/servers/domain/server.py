"""Delegate through MCP to a real, separately traced SDK Agent."""

import os
import time
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_pattern_demo.runtime import load_settings, run_agent, write_json


async def analyze_sales_case(question: str) -> dict[str, Any]:
    """Delegate a sales investigation to a domain Agent; returns its answer and source evidence."""
    load_settings()
    deadline = float(os.environ.get("DEMO_DEADLINE", time.monotonic() + 120))
    run_id = os.environ.get("DEMO_RUN_ID") or f"domain-{uuid.uuid4().hex}"
    batch_id = os.environ.get("DEMO_BATCH_ID", "standalone")
    result = await run_agent(
        "scoped",
        run_id,
        batch_id,
        deadline,
        question=question,
        role="inner",
    )
    output_path = os.environ.get("DEMO_INNER_RESULTS")
    if output_path:
        import json

        path = Path(output_path)
        stored = json.loads(path.read_text()) if path.exists() else {"runs": []}
        stored["runs"].append(result)
        write_json(path, stored)
    if result["status"] != "completed":
        raise ValueError(f"DOMAIN_FAILED: {result['error']}")
    return {
        "status": "ok",
        "data": result["answer"],
        "source_ids": result["answer"]["source_ids"],
        "fixture_version": "sales-demo-v1",
    }


def build_server() -> FastMCP:
    server = FastMCP("domain", log_level="WARNING")
    server.add_tool(analyze_sales_case)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
