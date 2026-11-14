# 研究文件 MCP 架構設計

採固定工具集合，組合 Progressive Disclosure 與 Scoped Capabilities：在 ACL 範圍內定位段落，再讀必要內容；有穩定 ID 時直接讀取。五萬份文件表示資料量大，並不表示操作目錄龐大，因此不加入 Discover + Execute。Client 不支援 Resources 及動態工具更新，所有必要資料、來源與分頁資訊均由固定工具回傳。

## 責任與前提

- Host／Client：根據原始使用者任務選擇搜尋或直接讀取，引用文件與章節來源；文件中的指令不具授權效果。
- Server：由 HTTP 身分系統的驗證結果取得可信 principal；驗證工具參數、範圍、游標及回傳預算，傳遞可信身分給後端，維持來源與版本資訊。
- 後端：保留既有穩定 ID、revision、ACL、依 revision 的分頁與章節讀取；每次搜尋、結構查詢、直接讀取及每一頁均依目前 ACL 檢查物件／章節存取權。revision 固定內容，不能固定或繞過舊權限。

需求未指定搜尋 API、排序快照能力、語言、SDK、MCP／HTTP transport 版本與延遲預算。以下假設可提供 ACL 感知的章節搜尋；若沒有，需在後端新增受控索引查詢，不能以逐份下載全文取代。搜尋快照不由需求保證，另列為實作條件；保留既有語言，HTTP transport 與協定版本待互通確認。

## 固定能力與契約

下列數量及大小是建議初始預算，不是協定要求。所有 ID 均為不透明非空字串（建議上限 256 字元）；拒絕未知欄位，游標不由模型自行組裝。`principal` 不接受為使用者可填參數。

| 工具 | 輸入 | 輸出及範圍 |
| --- | --- | --- |
| `search_sections` | `query`（1–2000 字元）、可選受控 filter、`page_size`（預設 10，1–20）、可選 `cursor` | ACL 過濾後的 `hits[]`：document_id、section_id、revision、標題、短摘錄、來源定位；每摘錄最多 500 字元；next_cursor、搜尋快照或一致性標記。filter 只縮小範圍，不能授權 |
| `list_document_sections` | `document_id`、可選 `revision`、`page_size`（預設 20，1–50）、可選 `cursor` | 授權可見的文件標題、實際 revision、章節 ID／標題／階層／頁碼（來源有才回）、next_cursor；不讀整份正文。只在需理解文件結構時使用 |
| `read_section` | `document_id`、`section_id`、可選 `revision`、`page_size`（建議預設 8 KiB、最大 16 KiB）、可選 `cursor` | 驗證 section 隸屬 document；回實際 revision、受限正文、定位與來源、next_cursor、complete、回傳位元組數。章節超限依後端 revision 分頁繼續，不隱藏截斷 |

各結果含 `contract_version: "1"`、request_id、retrieved_at；文件 revision 與契約版本各自獨立。來源至少含 document_id、section_id（適用時）、revision 及段落／頁碼／區段位置；來源無頁碼時不虛構。安全連結可附加，但工具回傳必須已足夠引用，不要求 Client 另讀 Resource。

不傳 revision 時，後端在本次起始讀取解析最新可見版本並明確回傳；後續頁必須沿用該 revision。已提供 revision 時精確讀取該版，不能暗換最新版。版本已不可用回 `REVISION_UNAVAILABLE`，由使用者或 Host 決定是否重新取得最新版；新版本內容需重新引用。搜尋命中保留該筆 revision，內容讀取沿用它。

## 分頁、安全與失敗語意

文件結構與正文使用後端既有 revision 分頁；固定排序與穩定次排序。Server 將後端游標包裝為防竄改且具期限的 token，綁定可信身分／工作範圍、工具、查詢或資源、revision、排序與 page_size；續頁要求參數相符。游標仍不代表授權，每頁重新檢查 ACL；撤權即停止回傳。

搜尋跨文件時以查詢快照固定排序及各命中 revision；若後端缺少快照能力，只能明示 `consistency: best_effort`，不能保證跨頁無重複或遺漏。需要完整遍歷時，必須先補齊快照能力。搜尋 ACL 必須在形成摘要、分數、計數、分頁結果前套用，避免僅在結果末端過濾而洩漏標題、摘錄或總數。共享快取不得混用 principal，命中快取後仍需確認目前權限；索引內容的 revision 必須與實際讀取對得上。

每次建議總回傳上限 32 KiB；搜尋摘要和章節正文皆不得為達上限而無標示截斷。較小頁面及 next_cursor 用於正常續讀，無法產生合法頁面則回 `RESULT_TOO_LARGE`。建議起始總期限 10 秒，需後續量測；每次呼叫可對暫時失敗重試一次，沿用相同 revision／cursor，支援取消。這些工具唯讀，寫入核准與冪等鍵不適用。

| 狀態 | 行為 |
| --- | --- |
| 無搜尋命中 | 成功回空 hits，不推論無權限文件是否存在 |
| 不存在或不可見 | 統一 `NOT_FOUND_OR_NOT_ALLOWED`，不回傳標題、revision、ACL 或其他團隊資訊 |
| 不合法／竄改游標 | `INVALID_CURSOR`，不執行續頁查詢 |
| 游標過期／快照失效 | `CURSOR_EXPIRED`，明示需重啟查詢，不接續另一個版本 |
| 版本不可用／不一致 | `REVISION_UNAVAILABLE`／`VERSION_CONFLICT`，不混合不同版內容 |
| 後端失敗／逾時 | `UPSTREAM_UNAVAILABLE`／`TIMEOUT`，標示可否重試，不偽裝無命中 |
| 部分搜尋來源失敗 | 明示 `complete: false` 與不洩漏範圍外資訊的缺口；不能宣稱完整搜尋 |

文件內「忽略規則、讀取其他團隊文件」只作原文資料：Server 不解析成命令，也不更換 principal、放寬 ACL 或新增能力。Host 仍依原始任務決策；即使模型受到影響而發出跨 ACL 呼叫，後端仍必須拒絕。工具描述與文件內容亦不能改寫系統規則。

## 執行流程與取捨

```text
若有 document_id + section_id：
  直接 read_section → 驗證身分／ACL／從屬關係 → 依指定或解析出的 revision 讀局部內容
否則若只有 document_id 且需看結構：
  list_document_sections → 選 section_id → read_section
否則：
  search_sections → 選命中及 revision → read_section
需要續讀：
  驗證 cursor 與目前 ACL → 同 revision 下一頁 → 保留來源位置
內容不足：
  按原始任務明確選擇其他授權章節，或回報證據不足
```

局部讀取降低不相關內容傳輸，但增加搜尋／續頁往返；已知 ID 路徑省略搜尋及結構查詢。不能由架構直接宣稱 token 或延遲改善幅度。觀測僅記錄必要的 request_id、工具、耗時、回傳大小、結果碼及授權決策，不記錄完整文件正文或敏感搜尋詞。

## 驗證計畫與交付狀態

後續驗證應涵蓋：工具固定列舉、工具限定 Client 的完整操作；未知 ID 與已知 ID 兩條路徑；可直接讀取的呼叫不被強制要求先查 metadata；引用可還原到同 revision 的原文位置；無命中、空章節、內容不足及後端錯誤區分。

以多個 ACL 群組驗證搜尋、標題、摘錄、計數、章節結構、直接 ID、所有續頁與快取皆無跨界資料；涵蓋偽造 principal／filter、跨文件 section_id、有效游標在撤權後重放，以及文件內的越權指令。分頁驗證包含頁首尾、最後一頁、Unicode 位元組界限、超大章節、游標竄改／過期／跨人重放、文件更新／刪除及 revision 失效；固定快照下比對全量授權結果是否無遺漏與重複。另驗證逾時、有限重試、取消與部分失敗。

本次僅完成設計，未連線、未實作、未執行模型或任何測試。ACL 感知搜尋、搜尋快照、實際 SDK／Client／HTTP transport 相容性與正式延遲均未驗證。

## 實際讀過的安裝副本檔案

- `SKILL.md`
- `references/selection-guide.md`
- `references/implementation-baseline.md`
- `references/scoped-capabilities.md`
- `references/progressive-disclosure.md`
- `assets/architecture-template.md`
- `assets/interface-contract-template.md`
