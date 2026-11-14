"""SDK execution and a small summary around the existing Langfuse integration."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agents import (
    Agent,
    ModelSettings,
    RunConfig,
    RunContextWrapper,
    RunHooks,
    Runner,
    set_default_openai_client,
)
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv
from langfuse import get_client, propagate_attributes
from openai import AsyncOpenAI
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from pydantic import BaseModel, Field

from .backend import fixture

PATTERNS = ("flat", "scoped", "progressive", "discover", "semantic", "domain")
EXPERIMENT_VERSION = "boundary-demo-v2"
PATTERN_DESIGNS = {
    "flat": {
        "focus": "完整工具目錄作為參照",
        "platform": "提供原始資料、正式規則與全部操作規格",
        "agent": "選工具、判斷有效交易、計算、彙整客服來源",
        "discovery": "初始工具清單",
    },
    "scoped": {
        "focus": "依任務限縮初始可見能力",
        "platform": "預先選定 sales_case 四支工具；不是角色或租戶授權",
        "agent": "在限定目錄選工具、依正式規則計算與彙整",
        "discovery": "預先選定的工具清單",
    },
    "progressive": {
        "focus": "將資料定位、中繼資料與內容分開",
        "platform": "提供穩定來源 ID、精簡中繼資料與按 ID 讀取",
        "agent": "決定讀哪些資料、是否需要中繼資料，並依規則計算",
        "discovery": "search_records 找資料；get_metadata 可選，get_content 取內容",
    },
    "discover": {
        "focus": "按需取得操作規格，再經固定入口執行",
        "platform": "提供同一操作目錄、規格與參數驗證／派送",
        "agent": "搜尋操作、讀規格、組參數、依正式規則計算",
        "discovery": "search_tools 找能力；get_tool_schema 讀規格",
    },
    "semantic": {
        "focus": "正式指標的計算責任移到後端",
        "platform": "定義指標及維度，執行正式公式與彙總",
        "agent": "選指標、期間與維度，回查客服來源並解釋結果",
        "discovery": "list_metrics／get_dimensions 探索指標與維度",
    },
    "domain": {
        "focus": "領域內規劃與工具協調移到內層 Agent",
        "platform": "執行真正的內層 Agent，提供共同規則與核心工具",
        "agent": "外層委派與呈現；內層選工具、計算及整理來源",
        "discovery": "外層看領域入口；內層使用 scoped 工具集合",
    },
}
ENV_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_BASE_URL",
)
QUESTION = (
    "計算 2026 年 9 月北區的淨營收，找出同期間北區退款金額最高的訂單，"
    "摘要該訂單客服紀錄中的退款原因，並列出來源 ID。"
)
RULES = """你是營運調查助理。必須使用提供的工具取得原始資料或已定義的指標。
淨營收＝期間內成功付款總額－期間內成功退款總額。
付款依 paid_at、退款依 refunded_at 各自判斷期間，不依訂單建立或付款日期排除退款。
期間為 [2026-09-01T00:00:00+08:00,2026-10-01T00:00:00+08:00)，時區 Asia/Taipei。
北區是 north；依訂單區域歸類。只計 succeeded，不計 failed 或 pending。
同一訂單可有多筆退款，找期間內成功退款合計最高者。
所有 amount_minor 是 TWD 分，回覆的 *_twd 欄位使用 TWD 元（除以 100）。
原因必須來自實際取得的客服紀錄，並引用來源 ID，不猜測因果。
資料不足時明確說明，不可編造。工具名稱與操作順序由你依任務自行決定。
"""
GUIDANCE = {
    "flat": "提供完整操作目錄，可依任務選擇工具。",
    "scoped": "本次已載入 sales_case 能力集合。",
    "progressive": "先定位相關記錄；metadata 可檢查結構，再按需批次取得內容。",
    "discover": "先搜尋操作目錄，按需讀取操作 schema，再由 call_tool 傳入參數執行。",
    "semantic": "業務指標已定義；可探索指標與維度，查詢結果後回查客服來源。",
    "domain": "提供營運調查領域服務，可將問題交給服務，再依返回的證據組織回答。",
}


class SalesAnswer(BaseModel):
    net_revenue_twd: float
    top_refund_order_id: str
    top_refund_twd: float
    refund_reasons: list[str]
    source_ids: list[str]
    limitations: list[str] = Field(description="Missing evidence or uncertainty; empty if none.")


def load_settings(env_file: Path | None = None) -> None:
    load_dotenv(env_file or Path.cwd() / ".env", override=False)
    missing = [key for key in ENV_KEYS if not os.environ.get(key, "").strip()]
    if missing:
        raise ValueError("Missing environment settings: " + ", ".join(missing))


_initialized = False


def initialize_tracking() -> Any:
    global _initialized
    client = get_client()
    if not _initialized:
        # Instrument the Agents SDK once, replacing its default trace exporter.
        OpenAIAgentsInstrumentor().instrument()
        set_default_openai_client(
            AsyncOpenAI(max_retries=0, timeout=60),
            use_for_tracing=False,
        )
        _initialized = True
    return client


def safe_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value and key not in ("OPENAI_MODEL", "LANGFUSE_BASE_URL"):
            text = text.replace(value, "[REDACTED]")
    return text[:2000]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    temp.replace(path)


@dataclass
class RunSummary(RunHooks):
    """Only counts/usage and short call names; detailed I/O stays in Langfuse."""

    model_usage: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    request_attempts: int = 0

    async def on_llm_start(
        self,
        context: Any,
        agent: Any,
        system_prompt: Any,
        input_items: Any,
    ) -> None:
        self.request_attempts += 1

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        self.model_usage.append(
            {
                "response_id": response.response_id,
                "usage": asdict(response.usage),
            }
        )

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        self.tool_calls.append(tool.name)

    def usage(self) -> dict[str, Any]:
        reported = (
            bool(self.model_usage)
            and len(self.model_usage) == self.request_attempts
            and all(row["usage"]["total_tokens"] > 0 for row in self.model_usage)
        )
        return {
            "input_tokens": sum(r["usage"]["input_tokens"] for r in self.model_usage),
            "output_tokens": sum(r["usage"]["output_tokens"] for r in self.model_usage),
            "model_requests": self.request_attempts,
            "mcp_calls": len(self.tool_calls),
            "usage_complete": reported,
        }


def server_environment(
    pattern: str,
    run_id: str,
    batch_id: str,
    deadline: float,
    inner_results: Path | None,
) -> dict[str, str]:
    env = {"PYTHONUNBUFFERED": "1"}
    if pattern == "domain":
        env.update({key: os.environ[key] for key in ENV_KEYS})
        env.update(
            {"DEMO_RUN_ID": run_id, "DEMO_BATCH_ID": batch_id, "DEMO_DEADLINE": str(deadline)}
        )
        if inner_results is not None:
            env["DEMO_INNER_RESULTS"] = str(inner_results.resolve())
    return env


async def run_agent(
    pattern: str,
    run_id: str,
    batch_id: str,
    deadline: float,
    *,
    question: str = QUESTION,
    role: str = "outer",
    inner_results: Path | None = None,
) -> dict[str, Any]:
    client = initialize_tracking()
    summary = RunSummary()
    started = time.monotonic()
    experiment_pattern = "domain" if role == "inner" else pattern
    result: dict[str, Any] = {
        "pattern": experiment_pattern,
        "experiment_version": EXPERIMENT_VERSION,
        "server_pattern": pattern,
        "role": role,
        "demo_run_id": run_id,
        "model": os.environ["OPENAI_MODEL"],
        "status": "failed",
        "answer": None,
        "error": None,
        "visible_tools": [],
        "trace_id": None,
    }
    try:
        async with asyncio.timeout_at(deadline):
            with client.start_as_current_observation(
                name=f"mcp-pattern-{experiment_pattern}-{role}",
                as_type="span",
                input=question,
                metadata={
                    "pattern": experiment_pattern,
                    "server_pattern": pattern,
                    "role": role,
                    "demo_run_id": run_id,
                    "batch_id": batch_id,
                    "fixture_version": fixture()["version"],
                    "experiment_version": EXPERIMENT_VERSION,
                    "pattern_design": PATTERN_DESIGNS[experiment_pattern],
                },
            ) as observation:
                result["trace_id"] = client.get_current_trace_id()
                with propagate_attributes(
                    session_id=run_id,
                    tags=["mcp-pattern-demo", experiment_pattern, role],
                    metadata={"demo_run_id": run_id, "batch_id": batch_id, "role": role},
                ):
                    async with MCPServerStdio(
                        name=f"{pattern}-{role}",
                        params={
                            "command": sys.executable,
                            "args": ["-m", f"mcp_pattern_demo.servers.{pattern}.server"],
                            "env": server_environment(
                                pattern,
                                run_id,
                                batch_id,
                                deadline,
                                inner_results,
                            ),
                        },
                        cache_tools_list=True,
                        client_session_timeout_seconds=120,
                    ) as server:
                        agent = Agent(
                            name=f"{pattern}-{role}",
                            instructions=RULES + "\n" + GUIDANCE[pattern],
                            model=os.environ["OPENAI_MODEL"],
                            mcp_servers=[server],
                            model_settings=ModelSettings(parallel_tool_calls=False, store=False),
                            output_type=SalesAnswer,
                        )
                        tools = await agent.get_all_tools(RunContextWrapper(context=None))
                        result["visible_tools"] = [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.params_json_schema,
                                "strict": tool.strict_json_schema,
                            }
                            for tool in tools
                        ]
                        observation.update(
                            metadata={
                                "pattern": experiment_pattern,
                                "server_pattern": pattern,
                                "role": role,
                                "demo_run_id": run_id,
                                "batch_id": batch_id,
                                "fixture_version": fixture()["version"],
                                "experiment_version": EXPERIMENT_VERSION,
                                "pattern_design": PATTERN_DESIGNS[experiment_pattern],
                                "visible_tools": result["visible_tools"],
                            }
                        )
                        completed = await Runner.run(
                            agent,
                            question,
                            hooks=summary,
                            max_turns=6 if role == "inner" else 20,
                            run_config=RunConfig(
                                workflow_name=f"MCP {pattern} {role}",
                                group_id=run_id,
                                trace_metadata={"demo_run_id": run_id, "role": role},
                            ),
                        )
                        result["answer"] = completed.final_output.model_dump()
                        result["sdk_usage"] = asdict(completed.context_wrapper.usage)
                        result["status"] = "completed"
                        observation.update(output=result["answer"])
    except Exception as exc:
        result["error"] = safe_error(exc)
    finally:
        result.update(summary.usage())
        result["tool_sequence"] = summary.tool_calls
        result["model_usage"] = summary.model_usage
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        result["usage_complete"] = result["usage_complete"] and result["status"] == "completed"
        await asyncio.to_thread(client.flush)
    return result
