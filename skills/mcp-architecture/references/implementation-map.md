# 實作對照

依據本專案 2026-11-14 的本機工作樹及既有 `boundary-demo-v2` 文件。下列路徑以 repository 根目錄為起點，屬可選的程式證據；安裝副本不需包含 repository。只有取得原始碼並實際執行，才能宣稱本次驗證。示範版本範圍由專案 `pyproject.toml` 與 `uv.lock` 決定。

## 程式、測試與證據邊界

| 設計 | 程式位置與符號 | 對應測試 | 已示範／未涵蓋 |
| --- | --- | --- | --- |
| Flat／Scoped | `src/mcp_pattern_demo/registry.py::CORE`、`catalog`、`register`；`src/mcp_pattern_demo/servers/flat/server.py::build_server`；`src/mcp_pattern_demo/servers/scoped/server.py::build_server` | `tests/test_mcp_servers.py::test_flat_and_scoped_core_schemas_are_identical`、`test_independent_stdio_server_namespaces` | 20／4 個工具，核心描述及輸入 Schema 一致；沒有角色或租戶授權 |
| Progressive | `src/mcp_pattern_demo/backend.py::search_records`、`get_metadata`、`get_content`、`selected`；`src/mcp_pattern_demo/servers/progressive/server.py::build_server` | `tests/test_backend.py::test_progressive_preserves_evidence_without_leaking_note_body`、`test_progressive_metadata_is_smaller_for_the_aggregation_records` | ID、metadata／內容與批次限制；未涵蓋搜尋分頁、快照與一般回傳預算 |
| Discover | `src/mcp_pattern_demo/registry.py::search_tools`、`get_tool_schema`、`call_tool`；`src/mcp_pattern_demo/servers/discover/server.py::build_server` | `tests/test_backend.py::test_discovery_dispatch_is_equivalent_and_validates_arguments`；`tests/test_mcp_servers.py::test_independent_stdio_server_namespaces` | 簡易搜尋、固定入口與參數驗證；無生成程式、授權、寫入與規格版本協商 |
| Semantic | `src/mcp_pattern_demo/backend.py::METRICS`、`list_metrics`、`get_dimensions`、`query_metrics`；`src/mcp_pattern_demo/servers/semantic/server.py::build_server` | `tests/test_backend.py::test_raw_and_semantic_agree_with_independent_reference`、`test_metric_contract_rejects_undefined_metrics_and_dimensions`、`test_invalid_queries_are_not_empty_success` | 後端公式、單位、定義版本、來源及日期／狀態驗證；無定義審核與版本遷移 |
| Domain＋Scoped | `src/mcp_pattern_demo/servers/domain/server.py::analyze_sales_case`；`src/mcp_pattern_demo/runtime.py::run_agent`、`server_environment` | `tests/test_domain.py::test_standalone_domain_does_not_require_runner_private_environment`；`tests/test_mcp_servers.py::test_independent_stdio_server_namespaces` | 委派接線及獨立入口；單元測試替代 inner runner，真實 Agent 另有歷史實驗；未示範租戶身分與一般循環控制 |
| 評估隔離 | `src/mcp_pattern_demo/evaluation.py::evaluate`；`src/mcp_pattern_demo/expected.json` | `tests/test_backend.py::test_evaluation_requires_sources_and_correct_cents` | evaluator 讀標準答案，Server／runtime 不讀；原因關鍵字僅為代理檢查 |
| 用量與追蹤 | `src/mcp_pattern_demo/runtime.py::RunSummary`；`src/mcp_pattern_demo/demo.py::totals`；`src/mcp_pattern_demo/verification.py::read_trace` | `tests/test_runtime.py::test_failed_model_attempt_is_counted_and_marks_usage_incomplete`、`test_real_sdk_loop_invokes_usage_hooks_without_external_api`；`tests/test_verification.py::test_langfuse_exclusive_buckets_match_inclusive_sdk_usage`、`test_unfinished_or_missing_usage_is_not_success` | 缺失用量不當零、SDK hook、bucket 重組；本機 mock 檢查不等於遠端服務驗證 |

## 值得沿用的結構

- Server 入口註冊介面，共用後端承擔查詢及公式，避免每個 Pattern 複製業務計算。
- Flat／Scoped／Discover 共用操作定義，降低不同介面的契約漂移。
- 來源與版本隨結果回傳；委派計入內外層成本。
- 同一任務分開展示五個設計軸，另用組合情境檢查遷移能力。

## 不能直接升格為通用範本的設定

`runtime.QUESTION`、`RULES`、`SalesAnswer`、固定日期／區域／TWD 分、二十個操作、批次上限、模型回合數及停用平行呼叫都屬營收示範。設計 skill 不需 OpenAI Agents SDK 或 Langfuse；真正執行該範例才依原專案安裝及設定。

## 既有證據如何使用

`docs/experiment-review-v2.md` 記錄六組各一次的真實模型執行與追蹤核對；`docs/pattern-design-review.md` 第一輪由 v2 補充。這些證明該次路徑與責任分配可觀察，不能用作穩定效益或正式環境認證。

本機檢查可執行 `uv run pytest -q`、`uv run ruff check src tests`、`uv run ruff format --check src tests`。`uv run mcp-pattern-demo --list-tools` 只列本機工具。完整模型實驗會呼叫模型並送追蹤資料，依使用者實際要求與既有授權執行，不是載入 skill 的必要步驟。
