# 來源與證據

本版整理日期：2026-11-14。分開使用以下層級；產品案例及協定文件會演進，落地時核對目標版本。

## 協定與封裝

- [Agent Skills specification](https://agentskills.io/specification)：SKILL.md 與按需參考資料的格式。格式相容不保證各 Host 的安裝或執行行為相同。
- [MCP Server 概念](https://modelcontextprotocol.io/docs/learn/server-concepts)：Tools、Resources、Prompts 的用途。
- [MCP Tools](https://modelcontextprotocol.io/specification/latest/server/tools)：工具列舉、呼叫、Schema 與回傳；`latest` 會變動，設計時以實際 SDK／協定版本為準。
- [MCP Authorization](https://modelcontextprotocol.io/specification/latest/basic/authorization)：HTTP 授權流程與 stdio 憑證取得的區別；資源與動作授權仍需實作。

## 產品案例

2026-11-14 檢視以下官方來源，作為設計背景；並未部署或驗證這些產品：

- [GitHub MCP Server](https://github.com/github/github-mcp-server)：Toolsets、個別工具選擇與 Read-only。
- [Figma MCP Tools](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/)：metadata 提供精簡結構，再取得所需 design context。
- [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode-mcp/)：搜尋規格與在受控環境執行生成程式；不是本機固定派送的等價實作。
- [dbt MCP](https://docs.getdbt.com/docs/dbt-ai/about-mcp)：透過 MCP 取得 Semantic Layer 等能力。

以上產品不限定使用者應採相同工具名稱、框架或部署方式。

## 專案歸納與實作

[mcp-pattern-reference-arch](https://github.com/NeroHin/mcp-pattern-reference-arch) 的五種 Pattern 是作者的設計歸納，並非 MCP 官方分類。主要材料為作者的 MCP 設計文章及本機六組營運調查實作；私人文章與追蹤連結不是安裝依賴，也不隨封裝散布。

本版實作對照以 2026-11-14 工作樹為準；當時內容尚未完整出現在遠端 main。函式與測試位置見 implementation-map.md。歷史六組實驗是合成資料、單次執行；本版新情境另行驗證架構決策，不把它混同真實 MCP 執行或效能基準。
