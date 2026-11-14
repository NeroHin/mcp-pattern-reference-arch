"""Pure, shared business operations. No model calls and no access to expected.json."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal

Region = Literal["north", "south", "east"]
Kind = Literal["payment", "refund", "case_note"]
COLLECTIONS = {"payment": "payments", "refund": "refunds", "case_note": "case_notes"}
DATES = {"payment": "paid_at", "refund": "refunded_at", "case_note": "created_at"}


@lru_cache(maxsize=1)
def fixture() -> dict[str, Any]:
    return json.loads(files("mcp_pattern_demo").joinpath("fixtures.json").read_text())


def envelope(data: Any, source_ids: list[str]) -> dict[str, Any]:
    return {
        "status": "ok",
        "data": data,
        "source_ids": list(dict.fromkeys(source_ids)),
        "fixture_version": fixture()["version"],
    }


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("INVALID_ARGUMENT: timestamp must be ISO 8601") from exc
    if result.tzinfo is None:
        raise ValueError("INVALID_ARGUMENT: timestamp requires timezone")
    return result


def period(start: str, end: str) -> tuple[datetime, datetime]:
    lower, upper = timestamp(start), timestamp(end)
    if lower >= upper:
        raise ValueError("INVALID_ARGUMENT: start must precede end")
    return lower, upper


def check_region(region: str) -> None:
    if region not in ("north", "south", "east"):
        raise ValueError("INVALID_ARGUMENT: unsupported region")


def records(
    kind: Kind,
    start: str | None = None,
    end: str | None = None,
    region: Region | None = None,
    order_id: str | None = None,
) -> list[dict[str, Any]]:
    if kind not in COLLECTIONS:
        raise ValueError("INVALID_ARGUMENT: unsupported record kind")
    if (start is None) != (end is None):
        raise ValueError("INVALID_ARGUMENT: start and end must be supplied together")
    bounds = period(start, end) if start is not None and end is not None else None
    if region is not None:
        check_region(region)
    orders = {row["id"]: row for row in fixture()["orders"]}
    return [
        dict(row)
        for row in fixture()[COLLECTIONS[kind]]
        if (region is None or orders[row["order_id"]]["region"] == region)
        and (order_id is None or row["order_id"] == order_id)
        and (bounds is None or bounds[0] <= timestamp(row[DATES[kind]]) < bounds[1])
    ]


def list_payments(start: str, end: str, region: Region) -> dict[str, Any]:
    """List payments for a region and [start,end). Amounts are integer TWD cents; inspect status."""
    rows = records("payment", start, end, region)
    return envelope(rows, [row["id"] for row in rows])


def list_refunds(start: str, end: str, region: Region) -> dict[str, Any]:
    """List refunds by refunded_at and region, including pending; amounts are integer TWD cents."""
    rows = records("refund", start, end, region)
    return envelope(rows, [row["id"] for row in rows])


def get_order(order_id: str) -> dict[str, Any]:
    """Retrieve a single order by its stable ID, including its region."""
    for row in fixture()["orders"]:
        if row["id"] == order_id:
            return envelope(dict(row), [order_id])
    raise ValueError("NOT_FOUND: order")


def get_case_notes(order_id: str) -> dict[str, Any]:
    """Read customer support notes for an order, including refund reasons and source IDs."""
    get_order(order_id)
    rows = records("case_note", order_id=order_id)
    return envelope(rows, [row["id"] for row in rows])


def record_index() -> dict[str, tuple[str, dict[str, Any]]]:
    return {
        row["id"]: (kind, row)
        for kind, collection in COLLECTIONS.items()
        for row in fixture()[collection]
    }


def search_records(
    kind: Kind,
    start: str | None = None,
    end: str | None = None,
    region: Region | None = None,
    order_id: str | None = None,
) -> dict[str, Any]:
    """Find payment/refund/support record IDs. Then inspect metadata or fetch selected contents."""
    rows = records(kind, start, end, region, order_id)
    return envelope(
        [{"id": row["id"], "title": f"{row['order_id']} {kind} record"} for row in rows],
        [row["id"] for row in rows],
    )


def selected(ids: list[str]) -> list[tuple[str, dict[str, Any]]]:
    index = record_index()
    if not ids or len(ids) > 100:
        raise ValueError("INVALID_ARGUMENT: supply 1 to 100 record IDs")
    if any(key not in index for key in ids):
        raise ValueError("NOT_FOUND: one or more record IDs")
    return [index[key] for key in dict.fromkeys(ids)]


def get_metadata(ids: list[str]) -> dict[str, Any]:
    """Inspect record types, timestamps and order IDs without amounts or full note contents."""
    rows = [
        {
            "id": row["id"],
            "kind": kind,
            "order_id": row["order_id"],
            "timestamp": row[DATES[kind]],
        }
        for kind, row in selected(ids)
    ]
    return envelope(rows, [row["id"] for row in rows])


def get_content(ids: list[str]) -> dict[str, Any]:
    """Fetch complete original records for selected stable IDs. Amounts are integer TWD cents."""
    rows = [dict(row) for _, row in selected(ids)]
    return envelope(rows, [row["id"] for row in rows])


METRICS = {
    "net_revenue": {
        "description": "Successful payments by paid_at minus successful refunds by refunded_at.",
        "dimensions": ["region"],
        "unit": "TWD_cent",
    },
    "refunded_amount": {
        "description": "Sum of successful refunds by refunded_at; group by order to compare.",
        "dimensions": ["region", "order_id"],
        "unit": "TWD_cent",
    },
}


def metric_definition(metric_id: str) -> dict[str, Any]:
    if metric_id not in METRICS:
        raise ValueError("UNSUPPORTED_METRIC: unknown metric_id")
    return METRICS[metric_id]


def list_metrics() -> dict[str, Any]:
    """Discover governed business metrics, their formulas, units and definition version."""
    return envelope(
        [{"id": key, **value, "definition_version": "v1"} for key, value in METRICS.items()], []
    )


def get_dimensions(metric_id: str) -> dict[str, Any]:
    """Return supported group_by dimensions for a metric."""
    return envelope(
        {"metric_id": metric_id, "dimensions": metric_definition(metric_id)["dimensions"]}, []
    )


def query_metrics(
    metric_id: str,
    start: str,
    end: str,
    region: Region,
    group_by: str,
) -> dict[str, Any]:
    """Compute a governed metric for [start,end), with integer TWD cents and sources."""
    definition = metric_definition(metric_id)
    if group_by not in definition["dimensions"]:
        raise ValueError("INVALID_ARGUMENT: unsupported group_by for metric")
    check_region(region)
    period(start, end)
    totals: defaultdict[str, int] = defaultdict(int)
    sources: list[str] = []
    if group_by == "region":
        totals[region] = 0
    operations = [("refund", -1), ("payment", 1)] if metric_id == "net_revenue" else [("refund", 1)]
    for kind, sign in operations:
        for row in records(kind, start, end, region):
            if row["status"] != "succeeded":
                continue
            key = region if group_by == "region" else row["order_id"]
            totals[key] += sign * row["amount_minor"]
            sources.append(row["id"])
    rows = [{group_by: key, "amount_minor": value} for key, value in sorted(totals.items())]
    return envelope(
        {"metric_id": metric_id, "definition_version": "v1", "unit": "TWD_cent", "rows": rows},
        sources,
    )
