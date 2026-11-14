# 責任邊界示範 v2：結果與修改判斷

正式 batch：`20261016T101858Z-b3971043`；實驗版本 `boundary-demo-v2`，使用 `.env` 的 `gpt-6-luna`。六組各一次，沒有為改變 Token 排序追加樣本。第一輪 batch `20261016T083212Z-f5cc0e0a` 保留。

## 共同要求與調整

淨營收是正式指標，所有組別共用規則；允許 Agent 依規則自行計算。目標是觀察能力、資訊、計算與協調邊界，不做最佳 Pattern 排名。

- Progressive 移除每筆 content_fields；同批 13 筆交易，中繼資料由 2,401 降至 1,402 字元，完整內容仍為 1,768 字元。此處是相同 JSON 序列化的字元長度，不是 Token。
- 保留原題、fixture、模型、獨立 Server 與其餘介面行為。中繼資料仍可選用，沒有強制工具順序。
- 報表補設計責任、初始工具名稱、首次 Input 與 Total；batch／trace 加入實驗版本與設計說明。

## 結果

| Pattern | 初始工具數 | 首次 Input | 模型請求 | MCP 呼叫 | Input | Output | Total | 秒 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Flat | 20 | 1,136 | 4 | 3 | 7,765 | 652 | 8,417 | 39.879 |
| Scoped | 4 | 755 | 5 | 4 | 8,625 | 930 | 9,555 | 16.906 |
| Progressive | 3 | 751 | 8 | 7 | 19,753 | 1,016 | 20,769 | 20.844 |
| Discover | 3 | 683 | 8 | 7 | 13,677 | 706 | 14,383 | 16.082 |
| Semantic | 5 | 770 | 8 | 7 | 10,746 | 602 | 11,348 | 13.888 |
| Domain（內外合計） | 外層 1／內層 4 | 外層 602 | 7 | 5 | 10,992 | 1,334 | 12,326 | 25.382 |

合計 76,798 Token，40 次模型生成、33 次 MCP 呼叫。Domain 外層 2,175、內層 10,151 Token。首次 Input 是完整請求；Domain 的首次 Input 是外層，內層首次 Input 為 893。耗時是外層端到端時間，包含 Server 啟動與委派，不加總重疊的父子 span。

六組答案皆為淨營收 61,500 元、O02 退款 5,000 元。助理逐項對照六組外層與 Domain 內層摘要，皆可由 N02a（螢幕閃爍／R02a 3,000 元）及 N02b（配件缺漏／R02b 2,000 元）支持；這不是人類審閱或通用事實忠實度驗證器。

## Langfuse 核對

透過 API 重新讀取七條完整 Trace，包含 input、output、usage、model、metadata 與狀態。保存在 batch 的 `trace-audit/`，不是只讀本機 SDK 摘要。

- 40 個唯一 response ID，全部 completed，沒有 error 或 incomplete_details。
- 每一回合的工具名稱及參數 schema 與該層 saved visible_tools 相同。
- 逐次核對 Langfuse 互斥 usage buckets、OpenAI Response usage、SDK usage，完全相符。
- 工具數與實際順序、最終結構化答案與本機結果相同；所有工具 envelope 為 ok，無 ERROR／WARNING。
- 無相同名稱與參數的重複呼叫。最終引用皆由該層工具回傳且存在於 fixture；Domain 外層的原始查詢可追至內層。

## 回扣觀察問題

| 觀察問題 | 本輪證據 | 判斷 |
| --- | --- | --- |
| 介面改變是否進入 Agent 的實際行為？ | Scoped 只看四支工具；Progressive 搜尋／中繼資料／內容；Discover 搜尋後取得三份 schema，再用 call_tool 執行 | 機制可觀察；不推論固定呼叫順序 |
| 計算與協調是否轉移？ | Semantic 回傳後端算好的 6,150,000 分及退款分組；Domain 真正執行內層四次查詢並回來源 | 責任位置有差異；不宣稱專家品質或治理效益 |
| 初始資訊較少是否必然累計較省？ | Scoped 首次 755 小於 Flat 1,136，但多查訂單，總量 9,555 大於 8,417；Discover 增加規格探索 | 本次可見初始量與總量不必同向，不能排選型名次 |
| 回答是否符合共同正式規則？ | 六組數值正確，客服摘要有實際來源，公式對所有組公開 | 本次符合；不推論長期穩定性或 Semantic 降錯率 |

Progressive 仍取回全部 13 筆交易與兩筆客服內容；內容篩選沒有減少，但這是全量彙總的任務需求。精簡格式沒有改變需求，不應為了省 Token 而漏讀金額。

Discover 本次搜尋只回四個相關候選，與前次八個含雜訊的候選不同；搜尋程式沒改，是 Agent 查詢字詞不同。這也說明新舊單次用量差額不能全歸因於 Progressive 修改。

Semantic 仍有 list_metrics 及 get_dimensions 的重複維度資訊；屬可精簡的介面重疊，並非執行錯誤。Domain 使用同一模型與規則，只展示委派，不涉及第三方 Agent 接入驗證。

## 是否再次修改

本輪不再修改 Server 行為、不再追加模型執行。冗餘 metadata 已修正；機制、來源與計帳均足以支撐文章的單次示範。簡易搜尋與維度重複資訊保留並交代限制。未驗證的角色／租戶授權、外部 Agent 接入、專家能力、統計表現不納入成果。

23 項測試、Ruff check／format、git diff --check 通過。原始結果、完整 observations、核對程式與原始碼雜湊都保存在本機 artifacts；詳細 Trace 連結見該批 results.md。
