from mcp_pattern_demo.servers.domain import server


async def test_standalone_domain_does_not_require_runner_private_environment(monkeypatch):
    for key in ("DEMO_RUN_ID", "DEMO_BATCH_ID", "DEMO_INNER_RESULTS", "DEMO_DEADLINE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(server, "load_settings", lambda: None)
    calls = []

    async def run_agent(pattern, run_id, batch_id, deadline, **kwargs):
        calls.append((pattern, run_id, batch_id, kwargs))
        return {"status": "completed", "answer": {"source_ids": ["N02a"]}}

    monkeypatch.setattr(server, "run_agent", run_agent)
    result = await server.analyze_sales_case("Investigate this order")
    assert result["source_ids"] == ["N02a"]
    assert calls[0][0] == "scoped"
    assert calls[0][1].startswith("domain-")
    assert calls[0][2] == "standalone"
    assert calls[0][3]["role"] == "inner"
