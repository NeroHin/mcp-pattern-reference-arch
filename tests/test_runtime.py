from types import SimpleNamespace as NS

from agents.usage import Usage

from mcp_pattern_demo.runtime import RunSummary, safe_error


async def test_failed_model_attempt_is_counted_and_marks_usage_incomplete():
    summary = RunSummary()
    await summary.on_llm_start(None, None, None, [])
    await summary.on_llm_end(
        None,
        None,
        NS(
            response_id="ok",
            usage=Usage(input_tokens=10, output_tokens=3, total_tokens=13),
        ),
    )
    assert summary.usage()["usage_complete"]
    await summary.on_llm_start(None, None, None, [])
    assert summary.usage()["model_requests"] == 2
    assert not summary.usage()["usage_complete"]
    assert summary.usage()["input_tokens"] == 10


def test_error_summary_redacts_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-value")
    assert "test-secret-value" not in safe_error(ValueError("test-secret-value was rejected"))


async def test_real_sdk_loop_invokes_usage_hooks_without_external_api():
    import httpx
    from agents import Agent, RunConfig, Runner
    from agents.models.openai_responses import OpenAIResponsesModel
    from openai import AsyncOpenAI

    def respond(request):
        return httpx.Response(
            200,
            json={
                "id": "resp-test",
                "object": "response",
                "created_at": 1,
                "model": "test-model",
                "status": "completed",
                "output": [
                    {
                        "id": "msg-test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": "OK", "annotations": []},
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 3,
                    "total_tokens": 13,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = AsyncOpenAI(api_key="offline-test", http_client=http)
        model = OpenAIResponsesModel(model="test-model", openai_client=client)
        summary = RunSummary()
        result = await Runner.run(
            Agent(name="test", model=model),
            "test",
            hooks=summary,
            run_config=RunConfig(tracing_disabled=True),
        )
    assert result.final_output == "OK"
    assert summary.usage()["model_requests"] == 1
    assert summary.usage()["usage_complete"]
    assert summary.usage()["input_tokens"] == result.context_wrapper.usage.input_tokens == 10
