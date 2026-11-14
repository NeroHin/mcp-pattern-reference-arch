"""CLI: isolated MCP processes, SDK execution, and a compact six-pattern report."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from agents.mcp import MCPServerStdio

from .evaluation import evaluate
from .runtime import (
    EXPERIMENT_VERSION,
    PATTERN_DESIGNS,
    PATTERNS,
    QUESTION,
    RULES,
    initialize_tracking,
    load_settings,
    run_agent,
    safe_error,
    write_json,
)
from .verification import read_trace


def totals(runs: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("input_tokens", "output_tokens", "model_requests", "mcp_calls")
    result = {key: sum(run[key] for run in runs) for key in keys}
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    result["usage_complete"] = all(run["usage_complete"] for run in runs)
    return result


def report(batch: dict[str, Any], path: Path) -> None:
    text = [
        "# MCP Pattern 示範結果",
        "",
        f"Batch: `{batch['batch_id']}`",
        "",
        f"模型：`{batch['model']}`。每組一次，不能推論穩定節省率。",
        "",
        "觀察能力、資訊與責任如何分配，以及本次 Agent 實際採取的路徑；不做 Pattern 排名。",
        "",
        "共同前提：淨營收是正式指標；各組取得相同規則，允許 Agent 依規則自行計算。",
        "",
        "原因摘要的自動檢查僅為關鍵字代理，仍需人工對照客服來源。",
        "",
        "| Pattern | 狀態 | 自動核對 | 工具數 | 模型請求 | MCP 呼叫 |"
        " 首次 Input | Input | Output | Total | 秒 | Langfuse |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for sample in batch["samples"]:
        count = sample["totals"]
        first_usage = sample["outer"].get("model_usage", [])
        first_input = first_usage[0]["usage"]["input_tokens"] if first_usage else "not_reported"
        links = []
        for run in [sample["outer"], *sample["inner"]]:
            url = run.get("tracking", {}).get("trace_url")
            if url:
                links.append(f"[{run['role']}]({url})")
        text.append(
            f"| {sample['pattern']} | {sample['outer']['status']} | "
            f"{sample['evaluation']['automated_pass']} | {len(sample['outer']['visible_tools'])} | "
            f"{count['model_requests']} | {count['mcp_calls']} | "
            f"{first_input} | {count['input_tokens']} | {count['output_tokens']} | "
            f"{count['total_tokens']} | "
            f"{sample['outer']['elapsed_seconds']} | {' / '.join(links) or 'not_reported'} |"
        )
    text.extend(
        [
            "",
            "首次 Input 是外層第一次模型請求的完整 input（含指令、工具與輸出要求），"
            "不是單獨 schema 用量。",
            "Domain 的請求數、MCP 次數與累計 Token 包含內外層；首次 Input 與工具數僅描述外層。",
            "耗時是外層端到端時間，包含委派；不加總重疊的父子 span。",
            "各組介面引導不同，且固定停用平行工具呼叫；數字用來解釋這次路徑。",
        ]
    )
    for sample in batch["samples"]:
        design = batch.get("pattern_designs", PATTERN_DESIGNS)[sample["pattern"]]
        text.extend(
            [
                "",
                f"## {sample['pattern']}",
                "",
                "介面設計（不是模型執行結果）：" + design["focus"] + "。",
                "",
                "平台負責：" + design["platform"] + "。",
                "",
                "Agent 負責：" + design["agent"] + "。",
                "",
                "探索方式：" + design["discovery"] + "。",
                "",
                f"追蹤完整：{sample['tracking_complete']}；"
                f"usage 完整：{sample['totals']['usage_complete']}。",
            ]
        )
        for run in [sample["outer"], *sample["inner"]]:
            first_usage = run.get("model_usage", [])
            first_input = first_usage[0]["usage"]["input_tokens"] if first_usage else "not_reported"
            text.extend(
                [
                    "",
                    f"{run['role']} 初始工具："
                    + "、".join(tool["name"] for tool in run["visible_tools"]),
                    "",
                    f"{run['role']} 工具順序：" + " → ".join(run["tool_sequence"]),
                    "",
                    f"{run['role']} 用量：input={run['input_tokens']}，"
                    f"output={run['output_tokens']}。",
                    "",
                    f"{run['role']} 首次 Input：{first_input}。",
                ]
            )
            if run.get("error"):
                text.extend(["", "錯誤：" + run["error"]])
        text.extend(
            [
                "",
                "```json",
                json.dumps(sample["outer"]["answer"], ensure_ascii=False, indent=2),
                "```",
            ]
        )
    path.write_text("\n".join(text) + "\n")


async def verify_sample(client: Any, sample: dict[str, Any]) -> None:
    runs = [sample["outer"], *sample["inner"]]
    for attempt in range(10):
        for run in runs:
            if run.get("trace_id"):
                run["tracking"] = await asyncio.to_thread(
                    read_trace,
                    client,
                    run["trace_id"],
                    run,
                )
        if all(run.get("tracking", {}).get("status") == "verified" for run in runs):
            break
        if attempt < 9:
            await asyncio.sleep(3)
    sample["tracking_complete"] = (
        bool(runs)
        and all(run.get("tracking", {}).get("status") == "verified" for run in runs)
        and (sample["pattern"] != "domain" or bool(sample["inner"]))
    )


async def inspect_tools(patterns: list[str]) -> None:
    for pattern in patterns:
        async with MCPServerStdio(
            params={
                "command": sys.executable,
                "args": ["-m", f"mcp_pattern_demo.servers.{pattern}.server"],
            },
            name=pattern,
        ) as server:
            tools = await server.list_tools()
            print(
                json.dumps(
                    {"pattern": pattern, "tools": [t.name for t in tools]}, ensure_ascii=False
                )
            )


async def execute(args: argparse.Namespace) -> int:
    selected = list(PATTERNS) if args.pattern == "all" else [args.pattern]
    if args.list_tools:
        await inspect_tools(selected)
        return 0
    load_settings(args.env_file)
    client = initialize_tracking()
    if not await asyncio.to_thread(client.auth_check):
        raise ValueError("Langfuse authentication failed")
    if args.verify_batch:
        path = args.verify_batch.resolve()
        batch = json.loads(path.read_text())
        for sample in batch["samples"]:
            await verify_sample(client, sample)
        write_json(path, batch)
        report(batch, path.with_suffix(".md"))
        print(f"Updated tracking verification: {path}")
        return 0 if all(s["tracking_complete"] for s in batch["samples"]) else 1
    batch_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = args.output_dir.resolve() / batch_id
    directory.mkdir(parents=True)
    batch: dict[str, Any] = {
        "batch_id": batch_id,
        "experiment_version": EXPERIMENT_VERSION,
        "experiment_intent": "觀察介面與責任分配造成的實際路徑；不做最佳 Pattern 排名",
        "metric_contract": "正式規則一致即可，允許 Agent 自行計算",
        "pattern_designs": PATTERN_DESIGNS,
        "model": os.environ["OPENAI_MODEL"],
        "fixture_sha256": hashlib.sha256(
            files("mcp_pattern_demo").joinpath("fixtures.json").read_bytes()
        ).hexdigest(),
        "question": QUESTION,
        "rules": RULES,
        "settings": {
            "parallel_tool_calls": False,
            "store": False,
            "max_turns_outer": 20,
            "max_turns_inner": 6,
            "timeout_seconds": args.timeout,
            "api_max_retries": 0,
        },
        "versions": {
            name: importlib.metadata.version(name)
            for name in (
                "openai-agents",
                "mcp",
                "langfuse",
                "openinference-instrumentation-openai-agents",
            )
        },
        "samples": [],
    }
    for pattern in selected:
        run_id = f"{batch_id}-{pattern}"
        inner_path = directory / f"{pattern}-inner.json"
        print(f"Running {pattern} …", flush=True)
        outer = await run_agent(
            pattern,
            run_id,
            batch_id,
            time.monotonic() + args.timeout,
            inner_results=inner_path,
        )
        inner = json.loads(inner_path.read_text())["runs"] if inner_path.exists() else []
        sample = {
            "pattern": pattern,
            "outer": outer,
            "inner": inner,
            "totals": totals([outer, *inner]),
            "evaluation": evaluate(outer["answer"]),
            "tracking_complete": False,
        }
        if pattern == "domain" and not inner:
            sample["totals"]["usage_complete"] = False
        batch["samples"].append(sample)
        # Persist immediately, before querying an external tracking backend.
        write_json(directory / "results.json", batch)
        report(batch, directory / "results.md")
        print(
            f"{pattern}: {outer['status']}; answer={sample['evaluation']['automated_pass']}; "
            f"tokens={sample['totals']['total_tokens']}; tracking=pending readback",
            flush=True,
        )
    # Query after collection so early traces have time to become readable.
    for sample in batch["samples"]:
        print(f"Verifying Langfuse: {sample['pattern']} …", flush=True)
        await verify_sample(client, sample)
        write_json(directory / "results.json", batch)
        report(batch, directory / "results.md")
    print(f"Results: {directory / 'results.md'}")
    return (
        0
        if all(
            s["outer"]["status"] == "completed"
            and s["tracking_complete"]
            and s["evaluation"]["automated_pass"]
            and s["totals"]["usage_complete"]
            for s in batch["samples"]
        )
        else 1
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated MCP pattern demonstrations.")
    parser.add_argument("--pattern", choices=[*PATTERNS, "all"], default="all")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument(
        "--list-tools", action="store_true", help="Inspect MCP without model calls."
    )
    parser.add_argument(
        "--verify-batch", type=Path, help="Recheck a results.json without model calls."
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        code = asyncio.run(execute(args))
    except Exception as exc:
        print(safe_error(exc), file=sys.stderr)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
