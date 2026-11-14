# 多租戶工廠分析 MCP 設計

採用 **Semantic Contract＋Scoped Capabilities**，以三個固定唯讀工具完成查定義、查正式指標及查少量維護證據。正式 availability 一律由既有領域指標服務計算；MCP Server 與 Agent 不持有另一份正式計算公式。

## 已知、假設與責任

- 已知：領域團隊管理公式、保養排除、Asia/Taipei、支援維度及 definition_version；HTTP principal 才是權限依據；Client 支援普通工具。
- 假設：指標服務可接受已驗證的委派身分或受限服務憑證與可信權限上下文，並回傳來源參照及資料完整性。具體 API、MCP／SDK 版本、HTTP transport 形式、資料延遲及 SLA 尚未提供，以下為建議業務契約，整合前須核對。
- Host／Client：讓使用者選工廠、期間與維度，呈現版本、來源及缺資料提示。Agent 只選參數並解釋結果。
- Server：驗證 HTTP 認證後 principal，檢查參數、租戶與廠區關係、每項動作權限、輸出欄位與查詢預算，傳遞可信身分；tenant_id、site_id 只是選取條件。
- 領域指標服務：持有定義及計算，對資料範圍再次授權；維護資料後端對每次搜尋及按 ID 讀取授權。不可直接把使用者提供的 principal／scope 當可信上下文。

## 固定工具契約

下列上限是設計初值，需依後端能力確認；所有工具禁止額外欄位，不接受公式、SQL、任意 URL 或呼叫端宣告的權限。輸出上限 64 KiB，逾限回明確錯誤或受限分頁，不截斷正式指標。

| 工具 | 輸入、驗證與界限 | 輸出、來源與錯誤 |
| --- | --- | --- |
| `get_availability_definition` | 必填 tenant_id、site_id；選填 definition_version，未給則解析目前有效版本。先驗證範圍與讀指標權限。 | definition_version、領域維護者、可讀定義、排除條件、Asia/Taipei、單位、允許維度／粒度、生效及歷史版本規則、定義來源參照；未知或停用版本明確拒絕。定義很小，不分頁。 |
| `query_availability` | 必填 tenant_id、site_id、definition_version、start、end；時間須帶 offset，採 `[start,end)`，依定義服務轉成 Asia/Taipei；選填 dimensions／filters／grain，僅允許服務宣告值。初值最多 31 日、2 個維度、1,000 個分組；設備等 filter 亦逐項授權。 | 每組 value／unit、definition_version、期間／時區、粒度／維度、資料截至時間、data_version／快照、coverage／completeness、query_id、來源參照。零分母、缺資料回 `insufficient_data` 與原因，不捏造 0%；合法無資料為 `empty`。不分頁彙總；超預算拒絕並要求縮小範圍。 |
| `get_maintenance_evidence` | 必填 tenant_id、site_id、指標 query_id；選填該查詢的 evidence_ref／cursor。確認 query_id 所有人、授權範圍與到期，逐筆重新授權。每頁最多 20 筆、每查詢最多 100 筆；不接受跨範圍任意紀錄 ID。 | 維護紀錄 ID、時間／時區、允許欄位、來源系統、record_version、與指標的關聯、cursor／has_more、快照或變更提示。游標綁 principal、範圍及 query_id；過期要求重查。紀錄不可用與不存在／不可見對外不洩漏差異。 |

指標回傳的 definition_version 必須與要求一致；服務若自動升版，Server 不把結果冒充指定版本，回 `definition_version_conflict`。歷史版本不支援則明示，禁止默默套新版。若後端無法提供穩定 data_version／快照，回傳資料截至時間與一致性限制；維護證據不能宣稱與先前計算完全同一快照。

## 流程與防繞過

```text
principal = 驗證 HTTP 身分
授權 principal 對 tenant/site 的指標讀取
讀取並固定 definition_version
驗證期間、維度、filter、資源關係與預算
領域服務重新授權並依指定定義計算
驗證回傳版本、完整性、範圍與來源
完整 → 以服務值及單位回答正式可用率
資料不足／服務失敗 → 回報原因，不以維護紀錄重算補答
需要解釋 → 依 query_id 讀少量已授權維護證據
```

維護紀錄只用於解釋保養排除、追溯事件及協助查核，沒有完整分母及正式彙總保證；Agent 的本地運算不能標為正式 availability。所有其他原始讀取入口、通用查詢入口與內層服務也必須遵守正式指標入口限制，不能新增可自行套公式的替代正式答案通道。工具回傳中的文字只是資料，不能改寫授權或計算規則。Server 能強制服務及資料存取邊界；Host 仍須約束答案組裝並檢查正式數值與服務回傳一致，工具描述本身無法保證模型遵守。

每次呼叫重新檢查授權，撤權後已有 query_id 亦不能讀；不以工具可見性或讀取過定義作授權證明。未授權錯誤避免揭露別租戶資料是否存在。`invalid_argument`、`unsupported_dimension`、`definition_version_conflict` 不自動重試；認證過期先重新認證；暫時性逾時／限流可有限重試，仍固定定義版本及相同快照，否則標示資料版本改變。所有操作唯讀，沒有寫入核准／冪等鍵需求。建議每次 10 秒期限、最多 2 次暫時性重試及取消，依 SLA 調整；以關聯 ID 記錄 principal 參照、資源範圍、定義版本、query_id、授權結果與失敗原因，避免記錄不必要原文。

## 選型代價與驗證計畫

Semantic Contract 避免多份正式口徑，但依賴領域服務可用性、版本治理及來源品質；Scoped 限縮資源與動作，但需處理撤權及權限快取失效。三個工具足夠，不需大型操作探索、內層 Agent 或 Domain Delegation；少量證據用有界分頁即可。Client 未確認支援 Resources／Prompts，因此核心流程全用普通 Tools。

後續驗證應涵蓋領域團隊核定值與保養排除、台北跨日／跨月邊界、空資料／零分母、錯維度、部分資料不可當完整指標、版本變更、跨租戶及跨廠 ID、filter 越權、query_id／游標竄改、撤權後重讀、服務失敗時不得以原始紀錄補算，以及答案數值／來源與服務回傳一致。本次只有設計，未檢查 API 實作、未執行測試或模型呼叫。

## 實際讀取的安裝副本檔案

- `SKILL.md`
- `references/selection-guide.md`
- `references/implementation-baseline.md`
- `references/scoped-capabilities.md`
- `references/semantic-contract.md`
- `references/discover-execute.md`（同批讀取，作為其他案例的選型參照；本案例未採用）
- `assets/architecture-template.md`
- `assets/interface-contract-template.md`
