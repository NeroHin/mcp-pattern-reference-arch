"""Evaluator-only reference answers; never imported by a server or agent runtime."""

import json
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from typing import Any

from .backend import fixture, record_index


def evaluate(answer: dict[str, Any] | None) -> dict[str, Any]:
    expected = json.loads(files("mcp_pattern_demo").joinpath("expected.json").read_text())
    if answer is None:
        return {"automated_pass": False, "checks": {}, "manual_reason_review": "not_reviewed"}

    def minor(key: str) -> Decimal | None:
        try:
            value = Decimal(str(answer.get(key))) * 100
            return value if value.is_finite() and value == value.to_integral_value() else None
        except (InvalidOperation, ValueError, TypeError):
            return None

    refs = set(answer.get("source_ids", []))
    known_ids = set(record_index()) | {row["id"] for row in fixture()["orders"]}
    reasons = " ".join(answer.get("refund_reasons", []))
    checks = {
        "net_revenue": minor("net_revenue_twd") == expected["net_revenue_minor"],
        "top_order": answer.get("top_refund_order_id") == expected["top_refund_order_id"],
        "top_refund": minor("top_refund_twd") == expected["top_refund_minor"],
        "required_note_ids": set(expected["required_note_ids"]) <= refs,
        "all_sources_exist": refs <= known_ids,
        "reason_keyword_proxy": all(term in reasons for term in expected["reason_terms"]),
    }
    return {
        "automated_pass": all(checks.values()),
        "checks": checks,
        "manual_reason_review": "not_reviewed",
    }
