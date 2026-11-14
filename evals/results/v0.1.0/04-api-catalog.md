# 物流平台 MCP 設計

採用 **Discover + Execute＋Scoped Capabilities**：外層固定三個普通工具，內層對受管理的 OpenAPI 操作目錄搜尋、取規格及驗證後派送。2,500 個且持續成長的操作適合按需探索；Client 不需動態載入工具。每個工作通常三四個唯讀操作，固定參數派送即可，**不生成或執行程式**；環境沒有隔離能力，也不應開放任意 URL、函式名稱或反射執行。

## 事實、假設與責任

- 已知：OpenAPI 目錄可查詢；權限包含倉庫與方法，取得規格後仍可能撤權／改版；本期只開唯讀。
- 假設：服務端能從可信認證取得 principal，已有可逐操作檢查的授權服務；目錄可建立 operation_id、spec_version／digest 與固定後端 route 的對照。若原目錄缺版本，先由匯入流程產生不可變規格摘要，不接受任意最新版本替代。認證方式、MCP／SDK／transport 版本、既有 API 延遲與一致性能力待整合時確認。
- Host／Client：維持三個固定工具，Agent 根據任務搜尋、讀規格並組參數；多步結果在一般呼叫流程中銜接。
- Server：管理操作 allowlist、規格快照與驗證，逐入口授權、限制成本並派送；目錄匯入程序核定唯讀分類與目的端。不能只憑 HTTP GET 或 OpenAPI 描述判定唯讀。
- 後端：維持資料與業務規則，對 principal／可信委派範圍再驗證倉庫、物件、方法與欄位權限。服務憑證不得擴大使用者實際權限。

## 三個固定工具契約

下列數值為初始設計上限，待容量驗證。所有工具拒絕額外欄位；operation_id 是不透明目錄 ID，不能當 URL／程式碼使用。工具風險標記只是提示，權限由服務端執行。

| 工具 | 輸入與範圍 | 輸出與界限 |
| --- | --- | --- |
| `search_operations` | query（1–200 字）、選填 warehouse_id、domain、cursor、limit（1–20）。先按 principal 的方法與倉庫權限及唯讀 allowlist 過濾，才排序、分頁與計算可見數量。warehouse_id 只是選取條件。 | operation_id、用途摘要、唯讀分類、spec_version／digest、必要輸入摘要、cursor／has_more。最多 20 筆、32 KiB；游標綁 principal、範圍與目錄版本。搜尋無結果回 `empty`，權限系統故障回錯誤，不偽裝空結果。 |
| `get_operation_spec` | operation_id、搜尋取得的 spec_version；可含 warehouse_id。按 ID 直接讀亦重新驗證方法／倉庫權限與唯讀狀態。 | 精簡但足以驗證的輸入／輸出 schema、required／值域、參數位置、業務前置條件、資源欄位、分頁／排序、錯誤及重試規則、資料一致性、版本／digest、目錄來源。單份最多 64 KiB；過大規格經匯入時拆為可操作的合法 schema 引用，必須取得完整適用 schema 才可執行。不能靜默省略驗證條件。 |
| `execute_operation` | operation_id、spec_version／digest、parameters（只含該 schema 允許欄位）、選填後端分頁 cursor；不接任意 URL、headers、credential 或程式。執行時重查最新授權、唯讀 allowlist、規格有效性，驗證型別、額外欄位、日期、warehouse／物件關係與成本。 | operation_id、實際 spec_version、來源服務、request_id、data_as_of／快照（若有）、結構化 data、next_cursor、完整性與警告。單頁最多 100 筆、128 KiB；不能安全分頁的超額結果回錯誤。結果游標綁操作、參數、principal、範圍及資料快照；後續每頁仍重新授權。 |

規格描述及 API 回傳全部視為資料；內含「忽略限制」等文字不改變流程。搜尋索引和快取須有權限版本或短效失效機制，但不把快取命中當授權結果；每次搜尋、取規格及執行都以當前可信權限檢查。後端搜尋若不能原生範圍查詢，Server 必須安全地預先篩選可見操作，避免未授權名稱、數量、摘要或錯誤洩漏。

## 成功與錯誤流程

```text
principal = 驗證身分
候選 = 在當前方法／倉庫權限 ∩ 唯讀 allowlist 中搜尋
對每個所需操作取得已授權、固定版本的規格
Agent 依規格建立 parameters
每次 execute：
  重新認證／授權 principal、方法、倉庫、物件、欄位
  驗證 operation_id 的固定 route 及唯讀分類
  比對 spec_version／digest 仍可用
  驗證完整 schema、資源關係及查詢預算
  以受限憑證呼叫受允許後端，後端再次授權
  過濾輸出並回傳來源、版本、完整性及游標
彙整三四項結果；每項保留來源與時間，不宣稱跨 API 同一快照
```

- **取得規格後撤權：** execute 拒絕；已讀規格、既有游標及 operation_id 不能延續權限。查詢進行中的撤權由後端原子授權／資料存取邊界處理；僅在 Server 呼叫前檢查不足以消除時間差。
- **改版：** 回 `spec_version_conflict`，不自動套用新版參數；重新取授權規格、重新驗證與組參數。後端若支援舊版且仍在 allowlist，可明確執行指定版本。route 變動不允許請求自行跟隨任意目的端。
- **未知 ID／不可見操作：** 對外使用一致的 `operation_unavailable`，不揭露是否存在；未授權倉庫同樣避免存在性洩漏。已授權操作的非法欄位、型別或業務值回可修正的 `invalid_argument`。
- **逾時／限流／短暫失敗：** 僅對已確認無副作用的操作做最多 2 次有限退避，遵守 Retry-After 與總期限，每次重試重新授權與檢查規格。初始期限每次 10 秒、工作 60 秒，可取消；不無限重試。認證失效先重新認證；權限拒絕、規格衝突及非法參數不盲目重試。
- **空結果／部分失敗：** 合法查無資料回 `empty`；服務故障、截斷與缺頁不當成功。四操作中一項失敗，逐項標狀態，只對完整足夠的資料下結論；多步查詢沒有跨服務交易或一致快照保證。快照失效／游標過期要求重查，明示資料時間變化。

每次以關聯 ID 串起搜尋、規格與執行；稽核 principal 參照、權限版本、倉庫／操作、spec digest、後端 request_id、耗時、大小及拒絕原因，不記錄憑證或多餘敏感 payload。本期唯讀，寫入核准、提交狀態查詢與寫入冪等鍵不適用；任何疑似有副作用的操作先排除，不能透過 generic dispatcher 開啟。

## 選型代價與驗證計畫

相較直接暴露全部操作，固定三入口減少常態規格負擔並適用現有 Client，但增加探索往返、搜尋召回風險、目錄治理、版本驗證及派送器責任；固定入口數少不代表權限小。直接提供少量常用工具是可行替代，但不足涵蓋每週擴充的目錄，本期不額外混用。沒有大量單份內容需求，因此不另建資料 Progressive Disclosure 流程；後端結果分頁只是必要大小控制。未見需共用完整領域流程或統一指標的需求，不另引入 Domain Delegation／Semantic Contract。Resources／Prompts 不能作核心依賴，因 Client 只確認固定工具支援。

後續驗證：代表性任務能找到並完成三四個正確操作；搜尋與直接 ID 讀取皆無越權 metadata；撤權涵蓋搜尋後、取規格後、後續分頁及重試；版本衝突不得靜默升版；拒絕未知 ID、任意 URL、額外欄位、錯倉庫／物件、寫入與偽裝唯讀操作；測試空結果、逾時、部分失敗、游標竄改／過期及大小邊界；比較搜尋召回、往返、延遲與傳輸量。本次只提供設計，未呼叫 API、未建立服務、未執行實作或模型測試。

## 實際讀取的安裝副本檔案

- `SKILL.md`
- `references/selection-guide.md`
- `references/implementation-baseline.md`
- `references/scoped-capabilities.md`
- `references/discover-execute.md`
- `references/semantic-contract.md`（同批讀取，作為其他案例的選型參照；本案例未採用）
- `assets/architecture-template.md`
- `assets/interface-contract-template.md`
