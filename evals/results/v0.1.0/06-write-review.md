# 庫存保留派送器審查

保留固定 allowlist 派送；目前只有兩個操作，直接公開 `get_stock`／`reserve_stock` 也可行，但無須為本次修正改介面。既有低風險授權繼續有效，不新增逐次人工核准。最優先修正可信身分與資源授權接線，以及 timeout 後盲目重送寫入。

本次證據只有需求提供的合成程式及敘述。未讀取真實服務、未執行測試、未發送寫入；後端可能已有的保護均不能視為已驗證。

## 有依據的發現與最小修正

| 分類／優先度 | 證據與影響 | 最小修正 |
| --- | --- | --- |
| 已知介面缺陷／高 | `call_tool(operation_id, arguments)` 沒有 principal；HTTP 已有的可信身分未傳入。Schema 驗證後直接 `operation.run(**arguments)`，此處不能依可信身分驗證租戶、倉庫與動作。這證明此層缺少檢查，不足以證明後端已能成功越權。 | 從已驗證 HTTP 上下文注入 principal／scope，搜尋及派送共用授權規則；Server 與後端檢查目標倉庫及 `read`／`reserve` 動作。 |
| 已知危險重試／高 | `except TimeoutError: return operation.run(**arguments)` 對所有操作重送。已知保留單可能提交後才 timeout，且無冪等／查狀態契約，因此可能重複保留。 | 立即移除寫入的自動重送；回提交狀態未知。補後端原子冪等與狀態查詢後，才允許安全重試。 |
| 已知搜尋行為、風險有條件／中 | `search_tools` 回整個目錄，沒有依 principal 過濾。若不同身分可見操作不同，會暴露不該看到的能力；目前兩個名稱是否都允許公開尚未知。 | 搜尋先按動作權限過濾，回有界 ID、用途、風險及契約版本；即使名稱公開，執行仍須獨立授權。 |
| 已知輸出契約缺口／高 | 沒有提交查詢契約，成功直接回傳後端值，timeout 只處理一次重送；無法一致區分未提交與提交結果未知。第二次 timeout 還可能直接拋出。 | 定義業務狀態 envelope 與錯誤對映，未知狀態不得標為失敗且可重試。 |
| 已知未處理路徑、影響待確認／中 | `CATALOG[operation_id]` 對未知 ID 會拋出查找例外；Schema 驗證也在 `try` 外。上層是否有安全錯誤對映未知。 | 在統一邊界轉為穩定的未知操作／非法參數錯誤，不回堆疊或目錄內容。Schema 是否拒絕額外欄位需查驗，不能僅憑函式名稱判定。 |

Client 傳來的 `tenant_id` 是不可信選取值，不能授權。最小做法是從 principal 導出租戶，移除公開參數；若需保留相容性，必須核對其屬於 principal 可用租戶，且不得讓 `**arguments` 蓋過可信上下文。多租戶使用者也只能在後端驗證過的成員範圍內選取。倉庫須確實屬於該租戶，庫存項目須屬於該倉庫；拒絕時避免洩露他人資源是否存在。

## 修正後的責任與契約

Host／Client 表達使用者意圖並保留同一請求的冪等鍵；MCP Server 依 allowlist 解析操作、驗 Schema／業務限制及授權；warehouse 後端負責最終庫存約束、資源授權、原子保留與冪等。annotations 或搜尋結果僅供選擇，不授予權限。

- `search_tools`：輸入有界查詢字串／游標；可信 principal 由請求上下文提供。只回授權目錄與規格版本，不回其他租戶資料。兩操作可單頁回傳，仍設回傳預算；缺權限不以空目錄掩蓋服務失敗。
- `call_tool`：輸入 `operation_id`、契約版本及該操作嚴格參數。`get_stock` 使用倉庫／商品 ID；`reserve_stock` 另含正整數 `quantity` 與 `idempotency_key`。數量上限、ID 格式、字串長度、回傳大小及庫存單位依既有業務規則定稿；拒絕未知欄位、舊規格與不一致的資源關係。
- `reserve_stock` 冪等：後端以可信租戶、穩定呼叫者、操作及鍵建立唯一範圍，綁定正規化後的倉庫、商品、數量等參數雜湊。相同鍵／參數回同一保留結果，相同鍵／不同參數回 conflict；並行請求也只能提交一次。鍵與結果需和保留單以原子方式落地，不能只放 Server 記憶體。有效期須涵蓋業務允許的重試及調解時間；到期後不可直接把舊請求當新單重送。
- 新增 `get_reservation_status` 或同等後端契約：依冪等鍵／保留單 ID 查詢並重新授權，回 `pending`、`committed`、`rejected`、`not_found` 或 `unknown`。查到 `not_found` 不一定代表原請求永不會提交，須以後端一致性及併發保證決定能否重送。
- 回傳：含 `request_id`、`operation_id`、`status`、`commit_state`、保留單 ID／結果、結構化錯誤、`retryable` 與 `next_action`；狀態查詢只回授權欄位。`commit_state` 區分 `committed`、`not_committed`、`unknown`。庫存不足是明確拒絕，不是 timeout；取消亦不代表已撤銷保留單。

## 派送邏輯與路徑

```text
讀取可信 principal，驗證操作在 allowlist 與契約版本
驗證參數型別／大小／業務語意
依 principal、租戶、倉庫、商品及動作驗證權限
唯讀 → 在期限內讀取；暫時性錯誤才有界重試
寫入 → 依原有授權，以同一冪等鍵提交至後端
成功 → committed，回保留單 ID
明確拒絕／確定未提交 → not_committed，回可判斷原因
timeout／連線中斷 → 先查原鍵狀態
已提交 → 回原結果
仍處理／無法確定 → pending 或 unknown，提供查詢路徑，不另建單
只有後端冪等保證成立且期限允許時，才可使用同鍵有界重試
```

在後端冪等與查狀態尚未補齊前，timeout 一律回 `unknown` 並以 request ID 交既有調解流程，不自動重送。唯讀重試也應設定次數、退避及整體期限；不重試非法參數、授權拒絕、庫存不足或參數衝突。重試由單一層負責，避免 Client、Server、後端各自放大請求。固定派送沒有任意程式執行問題，本次不需 Code Mode 或執行隔離改造。

## 可驗證修正的具體案例（尚未執行）

1. 使用者 A 傳租戶 B 或其倉庫 ID：搜尋、直接派送及狀態查詢均拒絕，不洩露 B 的資源存在性；攔截測試確認後端不收到未授權寫入。
2. 只有讀取權限：搜尋不顯示保留能力；猜到 `reserve_stock` ID 仍遭拒絕。搜尋後撤權，派送也須拒絕。
3. 提交前 timeout：無冪等時不重送；補齊後以同鍵安全恢復。提交後 timeout：查詢回原保留單，保留單總數仍為一。
4. 同鍵同參數重送及兩請求並行：只產生一張單；同鍵不同數量：conflict，庫存不再扣減。
5. 狀態查詢本身 timeout、pending 或查無結果但原請求仍在執行：回未知／處理中，不把它當可安全新建；測試最終提交後能找回原單。
6. 未知 operation、額外欄位、負數／超量數量、商品與倉庫不一致、舊契約版本：明確拒絕；錯誤不帶堆疊或敏感資料。
7. 正常讀取與成功保留、庫存不足、唯讀暫時性失敗：狀態及重試建議正確，回傳有界，期限與重試次數不超額。

待確認的是 warehouse 現有授權強度、Schema 嚴格性、錯誤包裝、提交交易性、查詢一致性、冪等保留期限及 Client／transport 版本。取捨是先停止危險重送會降低短期自動恢復率；原子冪等及查詢補齊後才能安全恢復，無需增加每筆人工核准。

## 實際讀取的安裝副本檔案

- `SKILL.md`
- `references/selection-guide.md`
- `references/implementation-baseline.md`
- `references/domain-delegation.md`
- `references/scoped-capabilities.md`
- `references/discover-execute.md`
- `assets/architecture-template.md`
- `assets/interface-contract-template.md`
