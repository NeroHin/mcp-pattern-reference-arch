from types import SimpleNamespace as NS

from mcp_pattern_demo.verification import read_trace


def client_with(rows):
    return NS(
        api=NS(observations=NS(get_many=lambda **_: NS(data=rows, meta=NS(cursor=None)))),
        get_trace_url=lambda **_: "https://example.test/trace",
    )


def test_langfuse_exclusive_buckets_match_inclusive_sdk_usage():
    rows = [
        NS(
            type="GENERATION",
            end_time="finished",
            usage_details={
                "input": 3,
                "input_cached_tokens": 2522,
                "input_cache_creation": 287,
                "output": 160,
                "output_reasoning_tokens": 281,
                "total": 3253,
            },
        ),
        NS(type="TOOL"),
    ]
    expected = {"model_requests": 1, "mcp_calls": 1, "input_tokens": 2812, "output_tokens": 441}
    result = read_trace(client_with(rows), "id", expected)
    assert result["status"] == "verified"
    assert result["input_tokens"] == 2812
    assert result["output_tokens"] == 441


def test_unfinished_or_missing_usage_is_not_success():
    rows = [NS(type="GENERATION", end_time=None, usage_details=None)]
    expected = {"model_requests": 1, "mcp_calls": 0, "input_tokens": 0, "output_tokens": 0}
    assert read_trace(client_with(rows), "id", expected)["status"] != "verified"
