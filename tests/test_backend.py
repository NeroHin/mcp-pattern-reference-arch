import json
from collections import defaultdict

import pytest

from mcp_pattern_demo import backend as b
from mcp_pattern_demo.evaluation import evaluate
from mcp_pattern_demo.registry import call_tool, get_tool_schema, search_tools

START = "2026-09-01T00:00:00+08:00"
END = "2026-10-01T00:00:00+08:00"


def test_raw_and_semantic_agree_with_independent_reference():
    payments = b.list_payments(START, END, "north")["data"]
    refunds = b.list_refunds(START, END, "north")["data"]
    paid = sum(r["amount_minor"] for r in payments if r["status"] == "succeeded")
    refunded = sum(r["amount_minor"] for r in refunds if r["status"] == "succeeded")
    assert paid == 7_000_000
    assert refunded == 850_000
    assert "P09" in {r["id"] for r in payments}
    assert "P10" not in {r["id"] for r in payments}
    assert "R07" in {r["id"] for r in refunds}  # Payment occurred in August.
    assert "R11" not in {r["id"] for r in refunds}  # Wrong region.
    assert any(r["status"] == "pending" for r in refunds)
    result = b.query_metrics("net_revenue", START, END, "north", "region")
    assert result["data"]["rows"] == [{"region": "north", "amount_minor": paid - refunded}]
    top = defaultdict(int)
    for row in refunds:
        if row["status"] == "succeeded":
            top[row["order_id"]] += row["amount_minor"]
    assert max(top, key=top.get) == "O02"
    assert top["O02"] == 500_000
    assert {
        r["order_id"]: r["amount_minor"]
        for r in b.query_metrics("refunded_amount", START, END, "north", "order_id")["data"]["rows"]
    } == dict(top)


@pytest.mark.parametrize(
    "args",
    [
        ("invalid", END, "north"),
        (START, START, "north"),
        ("2026-09-01", END, "north"),
        (START, END, "unknown"),
    ],
)
def test_invalid_queries_are_not_empty_success(args):
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        b.list_payments(*args)


def test_progressive_preserves_evidence_without_leaking_note_body():
    ids = b.search_records("case_note", order_id="O02")["source_ids"]
    assert ids == ["N02a", "N02b"]
    metadata = b.get_metadata(ids)
    assert all("body" not in row and "amount_minor" not in row for row in metadata["data"])
    assert b.get_content(ids) == b.get_case_notes("O02")
    with pytest.raises(ValueError, match="NOT_FOUND"):
        b.get_content(["../expected.json"])


def test_progressive_metadata_is_smaller_for_the_aggregation_records():
    ids = (
        b.search_records("payment", START, END, "north")["source_ids"]
        + b.search_records("refund", START, END, "north")["source_ids"]
    )
    metadata, content = b.get_metadata(ids), b.get_content(ids)
    assert metadata["source_ids"] == content["source_ids"] == ids
    assert len(json.dumps(metadata, ensure_ascii=False)) < len(
        json.dumps(content, ensure_ascii=False)
    )
    assert all("amount_minor" not in row and "status" not in row for row in metadata["data"])


def test_discovery_dispatch_is_equivalent_and_validates_arguments():
    found = search_tools("refund 退款")["data"]
    assert "list_refunds" in {r["operation_id"] for r in found}
    args = {"start": START, "end": END, "region": "north"}
    assert get_tool_schema("list_refunds")["data"]["input_schema"]["required"]
    assert call_tool("list_refunds", args) == b.list_refunds(**args)
    for bad in [{**args, "unexpected": True}, {"region": "north"}, {**args, "region": 1}]:
        with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
            call_tool("list_refunds", bad)
    with pytest.raises(ValueError, match="NOT_FOUND"):
        call_tool("__import__", {})


def test_metric_contract_rejects_undefined_metrics_and_dimensions():
    with pytest.raises(ValueError, match="UNSUPPORTED_METRIC"):
        b.query_metrics("profit", START, END, "north", "region")
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        b.query_metrics("net_revenue", START, END, "north", "order_id")


def test_evaluation_requires_sources_and_correct_cents():
    answer = {
        "net_revenue_twd": 61500,
        "top_refund_order_id": "O02",
        "top_refund_twd": 5000,
        "refund_reasons": ["螢幕閃爍", "配件缺漏"],
        "source_ids": ["N02a", "N02b"],
    }
    assert evaluate(answer)["automated_pass"]
    assert not evaluate({**answer, "source_ids": ["N02a"]})["automated_pass"]
    assert not evaluate({**answer, "net_revenue_twd": 61500.001})["automated_pass"]
    assert evaluate(answer)["manual_reason_review"] == "not_reviewed"
