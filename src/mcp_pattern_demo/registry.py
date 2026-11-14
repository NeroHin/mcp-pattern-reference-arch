"""One operation catalog shared by Flat, Scoped and Discover."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools.base import Tool

from . import backend


@dataclass(frozen=True)
class Operation:
    tool: Tool
    aliases: str


CORE = ("list_payments", "list_refunds", "get_order", "get_case_notes")
DISTRACTORS = (
    "list_products",
    "get_product",
    "list_shipments",
    "get_shipment",
    "list_warehouses",
    "get_warehouse_stock",
    "list_suppliers",
    "get_supplier",
    "list_campaigns",
    "get_campaign",
    "list_coupons",
    "get_coupon",
    "list_inventory_events",
    "get_inventory_item",
    "list_delivery_zones",
    "get_delivery_zone",
)


def distractor(name: str) -> Callable[..., dict[str, Any]]:
    if name.startswith("list_"):

        def operation() -> dict[str, Any]:
            return backend.envelope([{"id": f"{name}-01", "name": "Mock catalog entry"}], [])
    else:

        def operation(item_id: str) -> dict[str, Any]:
            return backend.envelope({"id": item_id, "operation": name, "status": "available"}, [])

    operation.__name__ = name
    operation.__doc__ = f"Read mock {name.removeprefix('list_').removeprefix('get_')} catalog data."
    return operation


def catalog() -> dict[str, Operation]:
    aliases = {
        "list_payments": "payment paid revenue 付款 營收 收入",
        "list_refunds": "refund refunded 退款 退費",
        "get_order": "order region 訂單 區域",
        "get_case_notes": "support notes reason customer 客服 原因 紀錄",
    }
    functions = [getattr(backend, name) for name in CORE] + [distractor(n) for n in DISTRACTORS]
    return {
        fn.__name__: Operation(Tool.from_function(fn), aliases.get(fn.__name__, ""))
        for fn in functions
    }


def register(server: FastMCP, names: tuple[str, ...]) -> None:
    operations = catalog()
    for name in names:
        server.add_tool(operations[name].tool.fn, name=name)


def search_tools(query: str) -> dict[str, Any]:
    """Search operation descriptions by keywords. Fetch schemas before calling discovered tools."""
    terms = re.findall(r"[\w]+", query.lower())
    scored = []
    for name, entry in catalog().items():
        text = f"{name} {entry.tool.description} {entry.aliases}".lower()
        score = sum(term in text for term in terms)
        if score:
            scored.append((score, name, entry.tool.description))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return backend.envelope(
        [{"operation_id": name, "description": description} for _, name, description in scored[:8]],
        [],
    )


def get_tool_schema(operation_id: str) -> dict[str, Any]:
    """Get the full parameter JSON schema for a stable operation ID."""
    entry = catalog().get(operation_id)
    if entry is None:
        raise ValueError("NOT_FOUND: operation")
    return backend.envelope(
        {
            "operation_id": operation_id,
            "description": entry.tool.description,
            "input_schema": {**entry.tool.parameters, "additionalProperties": False},
        },
        [],
    )


def call_tool(operation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a discovered operation with arguments matching its fetched JSON schema."""
    entry = catalog().get(operation_id)
    if entry is None:
        raise ValueError("NOT_FOUND: operation")
    schema = {**entry.tool.parameters, "additionalProperties": False}
    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as exc:
        raise ValueError(f"INVALID_ARGUMENT: {exc.message}") from exc
    return entry.tool.fn(**arguments)
