"""Read back Langfuse generations and compare them to actual SDK usage."""

from typing import Any

from .runtime import safe_error


def read_trace(client: Any, trace_id: str, expected: dict[str, Any]) -> dict[str, Any]:
    try:
        rows = []
        cursor = None
        seen = set()
        while True:
            page = client.api.observations.get_many(
                trace_id=trace_id,
                fields="core,basic,usage",
                limit=100,
                cursor=cursor,
            )
            rows.extend(page.data)
            cursor = page.meta.cursor
            if not cursor:
                break
            if cursor in seen:
                raise ValueError("Langfuse returned a repeated pagination cursor")
            seen.add(cursor)
        generations = [row for row in rows if row.type == "GENERATION"]
        tools = [row for row in rows if row.type == "TOOL"]
        details = [row.usage_details or {} for row in generations]
        have_usage = bool(details) and all(
            "input" in u and "output" in u and row.end_time is not None
            for row, u in zip(generations, details, strict=True)
        )
        # Langfuse stores exclusive buckets: cached inputs/reasoning outputs are
        # subtracted from the base bucket. Recombine them to compare to SDK totals.
        inputs = sum(
            v for u in details for k, v in u.items() if k == "input" or k.startswith("input_")
        )
        outputs = sum(
            v for u in details for k, v in u.items() if k == "output" or k.startswith("output_")
        )
        matched = (
            have_usage
            and len(generations) == expected["model_requests"]
            and inputs == expected["input_tokens"]
            and outputs == expected["output_tokens"]
        )
        return {
            "status": "verified"
            if matched and len(tools) >= expected["mcp_calls"]
            else "pending_or_mismatch",
            "observations": len(rows),
            "generations": len(generations),
            "tools": len(tools),
            "input_tokens": inputs if have_usage else None,
            "output_tokens": outputs if have_usage else None,
            "usage_matches_sdk": matched,
            "trace_url": client.get_trace_url(trace_id=trace_id),
        }
    except Exception as exc:
        return {"status": "readback_failed", "error": safe_error(exc)}
