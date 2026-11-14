# mcp-pattern-reference-arch
A repository of MCP patterns that provides reference architectures for MCP developers.

本專案包含可獨立使用的 **mcp-architecture skill** 與原有的六組可執行示範。Skill 協助從需求選型、定義責任及介面契約；示範提供程式、測試與實驗證據。

## MCP Architecture Skill v0.1.0

入口：[skills/mcp-architecture/SKILL.md](skills/mcp-architecture/SKILL.md)。本版支援設計新 MCP 與審查既有架構，涵蓋五種可組合的 Pattern：Scoped Capabilities、Progressive Disclosure、Discover + Execute、Semantic Contract、Domain Delegation，並保留少量直接工具的基線。

- [選型流程](skills/mcp-architecture/references/selection-guide.md)：先決定業務規則、計算、授權與協調的責任，再安排能力入口。
- [實作對照](skills/mcp-architecture/references/implementation-map.md)：Pattern 對應本機函式、測試、已驗證範圍與缺口。
- [新情境及驗收](evals/rubric.md)：六個跨領域設計／審查案例、獨立安裝副本的行為驗證；結果見 [v0.1.0 驗證報告](evals/results/v0.1.0/report.md)。

在 repository 中可直接要求 Agent：

```text
請讀取 skills/mcp-architecture/SKILL.md，依照其中的流程，
為我的研究文件服務設計 MCP。資料有穩定章節 ID 與 ACL，
Client 只支援工具。請給出選型依據、介面契約與驗證計畫。
```

支援 Agent Skills 的環境可將整個 `skills/mcp-architecture/` 目錄安裝至該環境指定位置；保留 references、assets、agents 及 LICENSE.txt。安裝後使用 `$mcp-architecture` 或由環境判斷觸發。Host 的安裝與探索方式須依其文件設定，本 repository 不會自動變更全域設定。

核心 skill 不依賴原 repository、Notion、模型金鑰、Langfuse 或 Python 套件；只有執行下方示範才需安裝示範相依套件。Skill 設計可跨技術棧使用；v0.1.0 尚未提供多 SDK 的自動程式產生器。

封裝及實作對照檢查（只用 Python 標準函式庫）：

```sh
python3 evals/check_package.py --repo-root .
```

來源與版本依據見 [sources.md](skills/mcp-architecture/references/sources.md)。五種分類是本專案的設計歸納，採用後仍需驗證授權、失敗行為及目標 Client。

## 六組可執行示範

使用 **OpenAI Agents SDK＋Langfuse**，在同一份 Mock 資料上展示五種 MCP Pattern 與 Flat 基準組。每個 Server 有獨立資料夾、工具註冊與 stdio 入口；每個樣本都建立新的 MCP 程序與 Agent 對話。共用唯讀資料與業務操作，使差異集中在能力介面。

本輪 `boundary-demo-v2` 從平台端觀察：已有企業 API 與資料時，如何分配能力可見性、資訊取得、計算與協調責任。淨營收是正式指標；各組取得同一份規則，允許 Agent 依規則自行計算，或由後端指標查詢完成計算。五種 Pattern 可組合，這裡分開示範以看清機制；Token 與耗時用來解釋單次路徑，不做選型排名。

這版使用 MCP Python SDK 的 **FastMCP／stdio**，沒有 FastAPI 或 HTTP endpoint。Discover + Execute 使用固定參數呼叫，不執行生成程式。

## 啟動

需要 Python 3.11 以上與 [uv](https://docs.astral.sh/uv/)。

```sh
uv sync --locked
```

在 repository 根目錄的 `.env` 設定下列變數，或直接透過環境提供：

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL=
```

模型沿用 `OPENAI_MODEL`，不自動替換。使用既有 Langfuse 專案即可；`.env` 與產出資料夾都已排除於 Git。

```sh
# 只連接本機 MCP、查看各組工具清單，不呼叫模型
uv run mcp-pattern-demo --list-tools

# 六組各跑一次：會呼叫真實模型，並將虛構題目、工具與回答送到 Langfuse
uv run mcp-pattern-demo --pattern all

# 單獨執行一組，或指定不同設定檔
uv run mcp-pattern-demo --pattern discover
uv run mcp-pattern-demo --pattern scoped --env-file /path/to/settings.env
```

每批產出 `artifacts/<batch_id>/results.json` 與 `results.md`，包含答案、自動核對、模型請求／MCP 次數、token、實際可見的工具 schema、工具順序與 trace 連結。Domain 另外保存內層 run 摘要，與外層以相同 Langfuse session 關聯。

第二版報表另外提供介面設計的責任分配、初始工具名稱、首次請求 Input Token 及累計 Total Token。介面設計與實際路徑分開呈現；首次 Input 是完整請求，不是單獨的 schema 用量。原始批次保留，新執行另建 batch。

第二版 batch `20261016T101858Z-b3971043` 已完成六組執行與七條 Langfuse Trace 核對。[結果與修改判斷](docs/experiment-review-v2.md) 記錄觀察問題、實際路徑、用量與本輪停止調整的依據。公開版保留合成資料的觀察，原始追蹤與文章編輯草稿保留在本機。

Langfuse 入庫可能稍有延遲；若結果顯示 tracking 不完整，可只重新讀回追蹤，**不重跑模型**：

```sh
uv run mcp-pattern-demo --verify-batch artifacts/<batch_id>/results.json
```

CLI 在執行失敗、自動核對不通過、usage 或追蹤不完整時回傳非零狀態，並保留結果。原因摘要的自動檢查僅為關鍵字代理，仍須人工對照 N02a／N02b 的原文。

## Server 分組

各組的差異在能力可見性、資料取得層次、計算及協調責任。請搭配[設計差異與 Langfuse 實測審閱](docs/pattern-design-review.md) 查看實際資料流、工具參數、首輪與累計 token，以及目前 Progressive 示範的限制。

```text
src/mcp_pattern_demo/
  servers/
    flat/server.py          # 20 支直接操作工具，基準組
    scoped/server.py        # 4 支相同的核心工具
    progressive/server.py   # search_records / get_metadata / get_content
    discover/server.py      # search_tools / get_tool_schema / call_tool
    semantic/server.py      # 指標、維度、查詢與客服證據
    domain/server.py        # 真實領域 Agent，再連接 scoped MCP
  backend.py                # 共用查詢與指標定義
  registry.py               # 唯一操作目錄、schema 與參數驗證
  runtime.py                # SDK 執行及現成追蹤整合
  demo.py                   # CLI、結果表與 Langfuse 對帳
  evaluation.py             # Evaluator 專用；Server／Agent 不載入標準答案
  fixtures.json
  expected.json
```

各 Server 可獨立啟動，例如 `uv run python -m mcp_pattern_demo.servers.discover.server`；stdout 留給 MCP 協定。沒有共用的模式開關把六組工具一起註冊。資料及操作函式共用，可避免各組業務計算或來源內容不一致。

## 固定案例與量測

同一題：計算 2026 年 9 月北區淨營收，找退款金額最高訂單，從客服紀錄摘要原因與來源。固定資料的正解為淨營收 **NT$61,500**、最高退款訂單 **O02／NT$5,000**，原因為螢幕閃爍與配件缺漏。

各組自行選工具與順序。整體 token 採 SDK 實際回報，並與 Langfuse generation 對帳；Domain 計入內外層，不重複加總父 span。Langfuse 的互斥 input／cache、output／reasoning buckets 會重新合計成 SDK 的完整 input／output 用量。未知用量標不完整，不當作零消耗成功。

每組一次僅展示這次行為，不能推論穩定節省率；初始工具數較少也不保證總用量較低。完整資料、契約與驗收說明見[實作計畫](docs/experiment-plan.md)。

## 驗證

```sh
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
```

測試不呼叫真實模型，涵蓋日期／狀態／跨月退款、原始與語意查詢一致性、漸進讀取的來源保留、固定入口參數驗證、六個獨立 stdio Server 清單、Flat／Scoped schema 一致及 Langfuse 用量對帳。

相依版本鎖定於 `uv.lock`。本版選用 MCP SDK 1.x 的 FastMCP API（`mcp>=1.26,<2`）；MCP 2.x 的 Server API 已改名，不能直接移除版本範圍而沿用本版 import。
