# 五種 MCP Pattern：Real Agent 示範實作計畫 v1

狀態：已實作並完成六組真實 Agent 示範；七條 Langfuse trace（含 Domain 內層）已讀回並與 SDK 用量對帳。正式 batch 為 20261016T083212Z-f5cc0e0a，結果保存在 artifacts，操作方式見 README。

第二版 `boundary-demo-v2` 已完成，batch 為 `20261016T101858Z-b3971043`。六組答案符合共同規則，七條 Trace 的 40 次生成均完成逐筆工具規格、用量與答案核對；本輪停止調整的理由見[結果審閱](experiment-review-v2.md)。前一版結果保留。

## 1. 目標與已定範圍

### 本輪修訂：boundary-demo-v2

文章服務平台端設計者：已有 API、資料與服務，需要思考能力、資訊與責任邊界，再組合合適的 Pattern。本輪沿用原任務、fixture、模型設定及六個獨立 Server，只精簡 Progressive 重複中繼資料並補強結果說明。

共同要求：淨營收是企業正式指標，所有組別取得相同規則；只要符合規則，允許 Agent 自行計算，不要求所有組別經過官方指標服務。原始查詢與 Semantic 的差異是計算放在哪裡，不是規則誰能自行發明。

本輪的觀察問題與證據：

| 問題 | 需要看到的證據 | 推論邊界 |
| --- | --- | --- |
| 能力入口不同，Agent 是否走出對應路徑？ | 實際送進模型的工具規格、工具參數與回傳 | 一次執行不代表固定或最佳路徑 |
| 計算與協調責任是否真的轉移？ | 原始介面回記錄、Semantic 回已計算指標、Domain 真正啟動 inner Agent | 不推論額外專家知識、授權或品質優勢 |
| 初始資訊較少是否必然代表累計較省？ | 首次 input、逐次用量、模型／MCP 次數與完整內外層成本 | 不預設省 Token；本次結果只描述這次路徑 |
| 回答是否符合共同業務要求？ | 金額／訂單核對、客服原文與來源逐項對照 | 自動原因檢查是關鍵字代理；人工與助理審閱分開記錄 |

驗收重點是協定與資料正確、機制可觀察、使用量可對帳。較高 Token、未呼叫可選 metadata 或沒有減少內容讀取，都不是自動失敗。若發現執行錯誤、來源缺漏、冗餘格式或機制未實作，才修正並另建批次；不為改變排名反覆調參。

Progressive 保留 search／metadata／content 三個入口，移除逐筆 content_fields，類型與內容用途由工具說明交代，不強制呼叫中繼資料。營收彙總仍可能需要讀取全部符合條件的金額，不另加垃圾長文或擴增題目製造優勢。Discover 的簡易字詞搜尋與 Semantic 的維度探索維持原版，留待結果說明其限制。

Scoped 只示範靜態能力集合，未驗證角色或租戶授權。外部團隊 Agent 的接入情境只在文章討論，這次不實作。Domain 沿用同模型與共同規則，計入內外層用量。

以下為前一版已完成的固定契約與實作規格；新批次結果完成後另行記錄，保留第一輪觀察。

使用一份固定 Mock 資料、一個題目、一個模型，執行 Flat 基準組與五種 MCP Pattern，各一次。以真實 Agent 的工具選擇、探索過程、答案與 token，提供文章可以引用的具體案例。一次執行的結果用於解釋這次行為，不推論通用的選型勝負。

使用者已確認 OpenAI Agents SDK、Langfuse，以及固定參數形式的 Discover + Execute。其餘採下列最小實作決策，現在沒有阻擋計畫的未決問題：

| 項目 | v1 決策 |
| --- | --- |
| 語言與執行 | Python、uv；使用 OpenAI Agents SDK 原有執行迴圈 |
| MCP | 六個獨立資料夾與 stdio Server 入口，各自註冊工具；應用程式透過 SDK 持有 MCP Client |
| 資料 | 固定 JSON，20 筆訂單及付款／退款／客服紀錄；全部虛構、唯讀 |
| 模型 | 六組及 P5 內層使用同一個設定的模型；各組開新對話 |
| 追蹤 | Langfuse＋OpenInference 現成整合；補 Pattern 與工具 schema 資訊 |
| 執行樣本 | flat、scoped、progressive、discover、semantic、domain，共六個樣本 |
| 評分 | 確定性金額／ID 比對，客服原因人工對照來源；不使用 LLM Judge |
| 不在 v1 範圍 | Code Mode、多模型、規模掃描、故障注入、統計檢定、組合 Pattern、自建追蹤平台、UI、資料庫 |

## 2. 固定題目、資料與答案

六組使用相同題目：

> 計算 2026 年 9 月北區的淨營收，找出同期間北區退款金額最高的訂單，摘要該訂單客服紀錄中的退款原因，並列出來源 ID。

共同提供的業務規則：

- 淨營收＝期間內成功付款總額－期間內成功退款總額。付款依 paid_at、退款依 refunded_at，兩者各自判斷期間，不能只看訂單建立日期。
- 時區 Asia/Taipei，期間為 `[2026-09-01T00:00:00+08:00, 2026-10-01T00:00:00+08:00)`。
- 區域依訂單歸屬判斷；退款最高訂單按期間內的成功退款加總，同一筆訂單可有多筆退款。
- failed 付款、pending 退款不計入；不涉及跨幣別、稅額或匯率。
- 所有組別都能取得相同定義與來源；只有 Evaluator 能讀預期答案。

fixture 設計如下，表中為 TWD 元，實際 JSON 金額存整數分。日期皆為 2026 年、+08:00，中午 12:00；表中另註時間者除外。付款 ID 依訂單尾碼為 P01～P20，退款 ID 如表列。

| 訂單 | 區域 | 付款金額／狀態／日期 | 退款 ID：金額／狀態／日期 |
| --- | --- | --- | --- |
| O01 | north | 10,000／succeeded／09-01 | R01：1,000／succeeded／09-05 |
| O02 | north | 20,000／succeeded／09-03 | R02a：3,000／succeeded／09-07；R02b：2,000／succeeded／09-19 |
| O03 | north | 15,000／succeeded／09-08 | R03：1,500／pending／09-10 |
| O04 | north | 8,000／succeeded／09-12 | R04：500／succeeded／09-20 |
| O05 | north | 12,000／succeeded／09-15 | 無 |
| O06 | north | 7,000／failed／09-16 | 無 |
| O07 | north | 9,000／succeeded／08-31 | R07：2,000／succeeded／09-04 |
| O08 | north | 6,000／succeeded／10-01 | R08：6,000／succeeded／10-03 |
| O09 | north | 5,000／succeeded／09-30 23:59:59 | 無 |
| O10 | north | 4,000／succeeded／10-01 00:00:00 | 無 |
| O11 | south | 14,000／succeeded／09-02 | R11：7,000／succeeded／09-06 |
| O12 | south | 9,000／succeeded／09-05 | 無 |
| O13 | south | 16,000／succeeded／09-09 | R13：1,600／succeeded／09-13 |
| O14 | south | 11,000／succeeded／08-28 | R14：1,100／succeeded／09-02 |
| O15 | south | 6,000／failed／09-21 | 無 |
| O16 | east | 13,000／succeeded／09-03 | R16：1,300／succeeded／09-10 |
| O17 | east | 18,000／succeeded／09-07 | 無 |
| O18 | east | 10,000／succeeded／09-11 | R18：1,000／pending／09-15 |
| O19 | east | 7,000／succeeded／09-22 | 無 |
| O20 | east | 4,000／succeeded／10-02 | 無 |

客服資料至少包含 O02 的兩份獨立紀錄：N02a 記載「螢幕閃爍，對應 R02a 退款 3,000 元」，N02b 記載「配件缺漏，對應 R02b 退款 2,000 元」。其餘訂單的客服紀錄各有固定 ID 與簡短內容；metadata 僅提供類型、時間、order_id 與中性標題，不提前洩漏原因答案。不以隨機垃圾文字放大回傳量。

預期答案：成功付款 70,000 元、成功退款 8,500 元、淨營收 **61,500 元**；退款最高訂單 **O02，5,000 元**；原因須有「螢幕閃爍、配件缺漏」及 **N02a、N02b** 來源。O07、O09、O10、R03、O11 用於檢查日期、狀態與區域是否處理正確，不另增加測試題。

## 3. 共用後端與工具契約

所有組別操作同一份 JSON 與共用函式。每個回應包含 data、source_ids、fixture_version；空結果與 INVALID_ARGUMENT／NOT_FOUND 錯誤明確區分。來源 ID 可回查原始記錄。

| 核心操作 | 參數 | 回傳 |
| --- | --- | --- |
| list_payments | start、end、region | 期間／區域內付款，保留 status，讓模型依規則判斷 |
| list_refunds | start、end、region | 期間／區域內退款，保留 status、order_id |
| get_order | order_id | 訂單資料與區域 |
| get_case_notes | order_id | 該訂單完整客服紀錄及來源 ID |

所有期間都採 start 含、end 不含；日期需附時區。region 使用 north／south／east。不得讓工具從 expected_answer 讀結果。核心查詢支援篩選，不故意要求基準組全庫讀取。

另有 16 支固定 Mock 工具：list_products、get_product、list_shipments、get_shipment、list_warehouses、get_warehouse_stock、list_suppliers、get_supplier、list_campaigns、get_campaign、list_coupons、get_coupon、list_inventory_events、get_inventory_item、list_delivery_zones、get_delivery_zone。每支有合理描述、參數與固定小型回應，與本題無關。

六個介面如下：

| 組別 | 模型初始可見工具 | 實作與觀察 |
| --- | --- | --- |
| B0 flat | 4 核心＋16 無關，共 20 支 | 直接註冊全部工具；保留 Agent 自行選擇的過程 |
| P1 scoped | 同樣的 4 支核心工具 | 啟動時選 sales_case 工具集合；與 B0 的核心 schema／回傳完全相同 |
| P2 progressive | search_records、get_metadata、get_content，共 3 支 | 先找記錄 ID、看結構，再取需要的內容；不直接回傳計算完成的答案 |
| P3 discover | search_tools、get_tool_schema、call_tool，共 3 支 | 搜尋相同的 20 個操作；規格按需取得，再用固定入口執行 |
| P4 semantic | list_metrics、get_dimensions、query_metrics、get_order、get_case_notes，共 5 支 | 依既定指標計算，客服證據仍查原始紀錄 |
| P5 domain | analyze_sales_case，共 1 支 | MCP 工具內使用另一個真正的 SDK Agent，提供 4 支核心操作，自行調查後回傳結果與來源 |

P2：search_records 接受 kind（payment／refund／case_note）、期間、區域、order_id 等可選條件，回傳記錄 ID／中性標題；get_metadata 接受 IDs，回傳型別、時間與來源，不含完整金額／客服內文；get_content 批次接受 IDs 回傳原始內容。三者都可定位相同來源，metadata 的用途在工具說明中交代，由 Agent 決定是否呼叫，不硬性強制順序。

P3：search_tools(query) 以固定字詞／別名比對目錄，回傳 operation_id 與說明；get_tool_schema(operation_id) 回傳參數 schema；call_tool(operation_id, arguments) 依 registry 驗證參數後執行共用操作。搜尋不使用額外模型或向量庫，底層操作不額外註冊給外層 Agent。取得 schema 後仍透過固定入口呼叫，不做動態工具注入。

P4：list_metrics 提供 net_revenue、refunded_amount 的定義與單位；get_dimensions(metric_id) 回傳可用維度；query_metrics 接受 metric_id、start、end、region、group_by。net_revenue 可依 region 分組；refunded_amount 可依 region 或 order_id 分組，均只計 succeeded。未定義指標與不支援維度回明確錯誤。Agent 可查指標後自行挑出退款最高訂單。

P5：analyze_sales_case(question) 啟動一個領域 Agent，收到共同業務規則，使用同一模型與 4 支核心操作。回傳數值、訂單、原因、來源與資料缺口；外層負責組織最後回答。不能預寫答案，也不能由內層再次委派。六個樣本包含一個額外的內層 SDK run，不等於只有六次模型請求。

## 4. SDK 執行與最小追蹤

```text
CLI（--pattern）
  → OpenAI Agents SDK Agent／Runner
    → SDK 持有的 MCP Client（stdio）
      → 依 Pattern 啟動的 Mock MCP Server
        → 共用 backend／fixtures.json

SDK／模型／工具 observations → OpenInference → Langfuse
P5 的 Server 內另啟動 SDK Agent，同樣送到 Langfuse
```

沿用 SDK 的執行迴圈與本機 MCP 連線，不自行寫 Agent loop。各組共同提示包含題目、業務定義及固定輸出欄位，僅增加介面必要說明；不指定必勝呼叫路徑，不加入額外工具搜尋或 hosted tools。SDK 設定及相依套件版本於實作時鎖定。

Langfuse 使用官方範例的 openinference-instrumentation-openai-agents／OpenAIAgentsInstrumentor；父程序與 P5 子程序分別初始化且各自 flush。只採一條 instrumentation 路線，避免重複送出同一模型呼叫。

每個樣本記錄 pattern、demo_run_id、batch_id、模型設定、fixture_version、初始工具名稱／schema、最終答案與 correctness。模型及工具的參數、回傳、耗時與 usage 使用現成 observations；若自動記錄缺少初始工具清單，只補一筆 metadata／observation。

P5 跨程序若形成不同 trace，以共同 demo_run_id／Langfuse session 關聯，另標 outer／inner。v1 不開發跨程序 trace propagation；在彙總表附上全部相關 trace 連結。只有 auth_check 成功不能當成追蹤完成，須確認實際模型與工具 observation 可見。

特別分清：Client 的 tools/list 是載入 MCP 清單；P3 的 search_tools 是模型主動探索操作；P2 找資料、P4 找指標、P1 事先縮小能力，不能全部算成同一種 discovery。

## 5. Token、答案與結果表

Token 採每次模型生成的實際 usage：input、output 分開列，總量為兩者加總。探索、錯誤與重試包含在其中。P5 計入 outer＋inner；只加總最底層 generation，避免將 root／Agent 彙總重複加一次。cached／reasoning 若是子欄位，不重複相加。

SDK run usage 與 Langfuse generation 做一次對帳；自動整合缺漏時保留 SDK 已回報的用量，並將追蹤標為不完整，不估造數字。Langfuse 的互斥 cache／reasoning buckets 重新合計後與 SDK inclusive input／output 對帳。v1 不估算 schema token，也不推估費用；初始工具數／schema 用來解釋過程，完整 token 以實際用量為準。

Agent 最後回覆固定欄位：net_revenue_twd、top_refund_order_id、top_refund_twd、refund_reasons、source_ids、limitations。金額檢查用 Decimal 正規化至分；61,500 與 61,500.00 視為相同，不以排版差異判錯。SDK 是否直接用結構化輸出依鎖定版本處理，不影響各組共同輸出要求。

| Pattern | 答案正確 | 初始工具數 | 模型請求數 | MCP 呼叫數 | Input token | Output token | 耗時 | Trace 連結 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

每組一列；P5 同列附 outer／inner 分項及總量。耗時為端到端牆鐘時間，不把重疊的父子 span 相加。模型請求數由 generation 計數，MCP 呼叫數由實際工具呼叫計數，兩者不混用。初始工具數另以實際送入模型的清單確認。

金額與訂單 ID 採確定性核對；原因摘要人工確認確實由 N02a、N02b 支持。失敗、少用工具、額外往返與較高 token 都保留；重新執行另建 demo_run_id，不覆蓋第一次觀察。可以展示這次數字差異，但不稱為穩定節省率。

## 6. 預定檔案與執行介面

實作交付項目如下；為符合使用者的隔離需求，各 Pattern 有獨立 Server 資料夾：

```text
pyproject.toml / uv.lock       相依套件與鎖定版本
.env.example                  設定名稱，不含金鑰
src/mcp_pattern_demo/
  fixtures.json               固定業務資料及無關工具的小型回應
  backend.py                  共用查詢、來源與指標計算
  registry.py                 20 個操作的描述、schema、dispatcher
  servers/flat/server.py      直接暴露 20 支工具
  servers/scoped/server.py    限縮為 4 支核心工具
  servers/progressive/server.py  資料探索與分層讀取
  servers/discover/server.py  固定操作探索／呼叫入口
  servers/semantic/server.py  指標契約
  servers/domain/server.py    內部真實 Agent 委派
  runtime.py                  SDK 執行與 Langfuse 初始化
  evaluation.py               答案核對（僅 Runner 載入）
  verification.py             Langfuse API 讀回與用量對帳
  demo.py                     SDK Agent、Langfuse 初始化、CLI 及簡單答案核對
  expected.json               Evaluator 專用答案；Server／Agent 不讀取
artifacts/<batch_id>/
  results.json                六組答案、檢查結果、usage、trace IDs／URLs
  results.md                  一張結果表及每組實際過程短註
```

兩份 artifact 是示範摘要，不是另一套事件儲存或追蹤系統；詳細模型／工具過程以 Langfuse 為主。

執行設定：OPENAI_API_KEY、OPENAI_MODEL、LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY、LANGFUSE_BASE_URL。使用者現有 Langfuse 端點即可，不在專案內部署平台。金鑰由本機環境提供，程式不將金鑰寫入摘要或追蹤 metadata。

CLI：`uv run python -m mcp_pattern_demo.demo --pattern flat` 或 `--pattern all`；all 依序執行六組，每組使用全新 SDK 對話與 MCP Server 程序。也可使用 uv run mcp-pattern-demo；--list-tools 不呼叫模型，--verify-batch 可只重查追蹤。

## 7. 實作順序、偽碼與完成條件

| 順序 | 工作 | 驗收 |
| --- | --- | --- |
| 1 | 固定 fixture、規則、expected；實作共用 backend | 手算與獨立參考計算一致；日期／status／多筆退款處理正確 |
| 2 | 實作 Flat Server、SDK runner 與 Langfuse 接線 | 簡單 smoke run 的模型／MCP 呼叫及 usage 在 Langfuse 可見 |
| 3 | 加 Scoped、Progressive、Discover、Semantic | 註冊工具清單正確；各入口能取得相同來源／定義；固定入口有參數驗證 |
| 4 | 加 Domain | 真正執行內層 Agent；內外 trace 可關聯；usage 皆可取得 |
| 5 | 封存設定後六組各跑一次，產出摘要 | 保存原始成功或失敗結果；答案、token、耗時與 trace 連結可對照 |

smoke run 用來檢查接線，另標 setup，不混入六組示範結果。實作中的小型契約檢查涵蓋核心計算、工具註冊、dispatcher 驗證與來源定位，不另建大型評估框架。

```text
開發時：
    建立 fixture 與 evaluator 專用 expected
    以獨立參考算法核對金額、訂單與來源
    實作共用操作、registry 與六種介面
    smoke run 確認 Langfuse 真正收到模型／工具與 usage

正式示範：
    建立 batch_id，固定模型、提示、fixture 與套件版本
    for pattern in [flat, scoped, progressive, discover, semantic, domain]:
        新建 demo_run_id、對話及 Server
        記錄模型可見的工具名稱與 schema
        呼叫 SDK Runner，由模型自行探索與使用工具
        若 domain：內層共享 demo_run_id，另標 inner
        成功、失敗或逾時都保存結果與可取得的 usage
        停止內層／Server，flush 追蹤並確認 Langfuse 可見
        核對答案，填入 results.json／results.md
    人工查看每組探索過程與客服原因來源
```

外層 SDK max_turns 設為 20、內層 6（固定入口需多次探索／規格／執行往返）；SDK turn 上限不當作模型請求數。每個樣本總時間上限 120 秒，內層使用剩餘時間並禁止再委派；外層逾時一併取消內層與 Server。API 不確定重試與 usage 遺失需標記，不能當作完整成本樣本。

完成表示六組都有可查看的答案或明確失敗與 Langfuse 連結，工具探索／實際可見清單可解釋、token 已對帳、P5 內層已計入，並完成同題結果表。若接線／追蹤不完整，先修正後再產出對應示範，保留原失敗紀錄。答案全部正確不是展示的先決條件，錯誤也能成為文章內容。

## 8. 文章交付與依據

每種 Pattern 的文章素材固定四項：介面有哪些入口、實際工具探索／呼叫片段、答案與 token 結果、這次行為的解釋與限制。從 Langfuse 取 trace 連結或截圖即可，不另做視覺化系統；本計畫不直接改寫 Notion 文章。

- 作者的 MCP 設計文章：提供五種 Pattern 的設計主線；私人工作區連結不隨公開版散布。
- [OpenAI 官方 MCP／Tracing 文件](https://developers.openai.com/api/docs/guides/agents/integrations-observability)：SDK 管理本機 stdio MCP 與執行追蹤，實作時參考。
- [Langfuse 官方 OpenAI Agents SDK 整合](https://langfuse.com/integrations/frameworks/openai-agents)：OpenInference 整合與追蹤查看，實作時參考。具體套件版本／MCP span 欄位於實作鎖定後確認。

程式與相依版本已鎖定，核心計算、獨立 stdio Server 與追蹤計帳均有測試；真實 run 的狀態、token 與追蹤讀回結果以各批 artifacts 為準，不把原先預期值當成實測數字。
