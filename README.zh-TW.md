# MCP Pattern Reference Architecture

[English](README.md) | [繁體中文](README.zh-TW.md)

如果你想把既有 API 或資料服務接成 MCP Server，這個專案可以幫你想清楚：要提供哪些工具、一次回傳多少資料，以及哪些工作應該交給後端處理。

專案提供一個協助設計的 skill，以及可以實際執行的範例，讓你看見不同設計會如何影響 Agent 的操作。

## 這裡有什麼？

| 內容 | 用途 | 從這裡開始 |
| --- | --- | --- |
| **mcp-architecture skill** | 協助 Agent 設計或審查 MCP Server，說明選擇理由，定義輸入、輸出、權限與失敗處理方式 | [SKILL.md](skills/mcp-architecture/SKILL.md) |
| **六組可執行範例** | 使用相同的合成資料與後端，以五種設計和 Flat 基準組完成同一個任務 | [範例程式](src/mcp_pattern_demo) |
| **驗證情境** | 檢查 skill 能否處理原範例以外的設計與審查需求 | [驗證報告](evals/results/v0.1.0/report.md) |

## 五種 Pattern，白話來說

| Pattern | 做法 | 適合什麼情況 |
| --- | --- | --- |
| **Scoped Capabilities** | 提供這次工作需要的工具 | 已經知道任務、角色、專案或工作範圍 |
| **Progressive Disclosure** | 先找到相關資料，再取得需要的細節 | 文件或資料很多，但每次通常只需要一部分 |
| **Discover + Execute** | 先找操作、讀參數規格，再透過固定入口呼叫 | API 操作很多，或操作目錄經常變動 |
| **Semantic Contract** | 由後端維護業務定義 | 指標需要一致的公式、單位與時間範圍 |
| **Domain Delegation** | 把完整任務交給領域服務或工作流程 | 多個 Agent 需要共用同一套領域流程 |

先從幾個清楚、直接的工具開始。遇到具體問題，再加入合適的 Pattern；不同 Pattern 也可以一起使用。

這些名稱是本專案整理設計方法的分類，並非 MCP 官方分類。[選型流程](skills/mcp-architecture/references/selection-guide.md) 有更完整的判斷依據與取捨說明。

## 使用 skill

使用 skill 不需要先執行範例，也不需要設定 API 金鑰。

在這份儲存庫中，可以直接請 Agent：

```text
請讀取 skills/mcp-architecture/SKILL.md，協助我設計研究文件服務的 MCP。
文件有固定的章節 ID 與存取權限，Client 只支援工具。

請說明採用哪些 Pattern、工具的輸入與輸出，以及如何驗證設計。
```

如果使用的環境支援 Agent Skills，可以把整個 `skills/mcp-architecture/` 資料夾放到該環境指定的位置。請保留其中的參考資料、範本、中繼資料與授權檔案。安裝方式依使用的環境而定，自動探索 skill 的支援程度也可能不同。

安裝後，若環境支援，可以用 `$mcp-architecture` 呼叫。

v0.1.0 著重**設計與審查**，協助整理架構與實作計畫，尚未提供各種 SDK 的自動程式產生器。核心 skill 可獨立使用，不需要 Notion、Langfuse、模型 API 或 Python 套件。

可搭配以下內容使用：

- [選型流程](skills/mcp-architecture/references/selection-guide.md)：選擇與組合 Pattern。
- [實作對照](skills/mcp-architecture/references/implementation-map.md)：找到各範例的程式、測試與限制。
- [介面契約欄位](skills/mcp-architecture/assets/interface-contract-template.md)：定義參數、結果、權限、錯誤與重試方式。

## 執行範例

### 1. 安裝並檢視工具

需要 Python 3.11 以上版本與 [uv](https://docs.astral.sh/uv/)。

```sh
git clone https://github.com/NeroHin/mcp-pattern-reference-arch.git
cd mcp-pattern-reference-arch
uv sync --locked
uv run mcp-pattern-demo --list-tools
```

最後一個指令會啟動本機 MCP Server 並列出工具，不會呼叫模型，也不需要 API 金鑰。

### 2. 設定模型與 Langfuse

在儲存庫根目錄建立 `.env`，或直接設定以下環境變數：

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL=
```

[.env.example](.env.example) 已列出相同的空白欄位。請用 `OPENAI_MODEL` 指定要使用的模型，執行程式不會自動改用其他模型。

### 3. 執行任務

```sh
# 六組範例各執行一次
uv run mcp-pattern-demo --pattern all

# 也可以只執行其中一組
uv run mcp-pattern-demo --pattern discover
```

這些指令會呼叫你設定的模型，並將合成題目、工具輸入與輸出、模型回覆送到你設定的 Langfuse 專案。目前的執行程式需要同時設定模型與 Langfuse。

每組範例都會啟動獨立的 MCP 程序與新的 Agent 對話。實作採用 MCP Python SDK 的 FastMCP，以 stdio 連線，搭配 OpenAI Agents SDK 與 Langfuse。SDK 版本範圍鎖定為 `mcp>=1.26,<2`。

## 範例在比較什麼？

六組範例回答同一個問題：計算 2026 年 9 月北區淨營收，找出退款總額最高的訂單，並從客服紀錄整理退款原因與來源。

這份合成資料的答案是：

- 淨營收：NT$61,500。
- 退款最高訂單：O02，共 NT$5,000。
- 退款原因：螢幕閃爍與配件缺漏。

| 範例 | 初始工具 | 改變了什麼 |
| --- | --- | --- |
| Flat | 20 個直接操作工具 | Agent 一開始就看見完整操作目錄 |
| Scoped | 4 個任務相關工具 | 只提供這次任務選定的工具 |
| Progressive | 3 個工具 | 先找紀錄，必要時讀中繼資料，再取得內容 |
| Discover | 3 個工具 | 先找操作規格，再透過固定入口執行 |
| Semantic | 5 個工具 | 後端計算已定義的指標，Agent 再查客服證據 |
| Domain | 外層 1 個工具 | 內層 Agent 使用 Scoped 的 4 個工具完成調查 |

各組共用後端與資料，差異在於提供什麼介面，以及由誰完成工作。每個 Server 在 [servers/](src/mcp_pattern_demo/servers) 都有獨立入口。

Scoped 範例使用靜態工具集合，尚未實作租戶授權。Discover 採固定參數派送，不會執行模型產生的程式。

## 結果與限制

每次執行會建立 `artifacts/<batch_id>/results.json` 與 `results.md`，記錄答案、自動檢查、工具定義與呼叫順序、Token 用量、耗時及追蹤連結。Domain 會記錄外層與內層結果。

如果追蹤資料尚未完整入庫，可以只重新查詢追蹤，不必重跑模型：

```sh
uv run mcp-pattern-demo --verify-batch artifacts/<batch_id>/results.json
```

執行失敗、答案自動檢查未通過、用量或追蹤不完整時，指令會以非零結束代碼表示。退款原因的檢查使用關鍵字與來源 ID，仍需要另外對照客服原文。

目前有兩種驗證紀錄：

- [可執行範例的結果](docs/experiment-review-v2.md)：六種介面各執行一次模型。這些結果說明當次發生的事情，無法證明長期的成本或速度優勢。
- [Skill 驗證](evals/results/v0.1.0/report.md)：由 Agent 回答六個新設計與審查情境，再依評分規準審閱。這六個情境尚未實作成新的 MCP Server。

初始工具較少，不保證整段任務的 Token 用量較低。採用 Pattern 後，也仍須驗證權限、失敗處理、資料限制與 Client 相容性，才能判斷是否適合正式環境。

私人設定、原始追蹤與本機工作紀錄都已排除於 Git。公開報告使用合成資料，並移除私人追蹤連結。

## 執行檢查

```sh
python3 evals/check_package.py --repo-root .
uv run pytest -q
uv run ruff check src tests evals/check_package.py
uv run ruff format --check src tests evals/check_package.py
```

封裝檢查會確認 skill 內部連結與具名實作對照是否有效。測試涵蓋共用計算、參數驗證、來源 ID、獨立 stdio Server 與用量核對，不會呼叫真實模型或遠端追蹤服務。

更多細節：[設計審閱](docs/pattern-design-review.md)、[實驗規格](docs/experiment-plan.md)、[資料來源](skills/mcp-architecture/references/sources.md)。

## 授權

[Apache-2.0](LICENSE)。
