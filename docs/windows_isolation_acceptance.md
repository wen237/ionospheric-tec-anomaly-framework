# Windows isolation acceptance harness V1（僅檢查與 dry run）

這是待研究者審查的診斷工具，不是受信任的啟動器。開發 repository 與
`.venv` 仍非受保護部署；W、V 尚未部署。工具不匯入既有授權、簽章、Store
或科學模組，也不建立帳號、目錄、金鑰、Store 或驗收環境。

## 安全使用

在原生 Windows PowerShell 中，明確指定已知 PID 與欲檢查的路徑：

```powershell
.\.venv\Scripts\python.exe -I -S -B src/workflow/windows_isolation_acceptance.py inspect --pid 12345 --path 'C:\ProgramData\TEC-Authorization-Acceptance'
```

`12345` 為佔位值，必須由研究者換成實際 PID。可重複 `--pid`、`--path`；
每類最多 32 個。沒有程序列舉、目錄掃描、預設目標或自動提權。輸出僅寫到
stdout，不自動儲存報告；輸出含 SID、路徑和權限，分享前須遮蔽個人資訊。
單一檔案僅使用標準函式庫，可用 `-I -S -B` 避免工作目錄、使用者 site 與
site 初始化參與此腳本的匯入；這些參數不能證明 Python 本體或標準函式庫可信。

程序查詢只要求 `PROCESS_QUERY_LIMITED_INFORMATION`、`TOKEN_QUERY`。
報告包含 PID、映像路徑、同一程序 handle 取得的建立時間及 primary token，
不從父程序、檔案擁有者或使用者名稱推論 token。`creation_filetime` 是十進位
字串，單位為自 1601-01-01 UTC 起的 100 ns。映像路徑不認證可執行檔內容。
token 另列 integrity SID、elevation/type、群組 attributes（含 enabled／deny-only）、
restricting SIDs、privilege attributes/ enabled 及 AppContainer 狀態。
不讀取命令列、環境變數、程序記憶體或私鑰。

路徑查詢使用 `OPEN_EXISTING`，僅要求 `READ_CONTROL | FILE_READ_ATTRIBUTES`；
若不可讀安全描述元，退回僅 attributes handle，ACL 狀態為 `UNKNOWN`。
不要求檔案資料讀寫、DELETE、WRITE_DAC、WRITE_OWNER、SACL，亦不讀檔案內容。
回報 owner、owner/DACL SDDL、DACL inheritance protection、attributes、file ID、
volume serial/GUID、filesystem 與 resolved path。祖先僅查 attributes/reparse；
若需父目錄 DACL，須另外明確指定該父目錄。查到 reparse point 即停止該路徑查詢。
API 的權限需求見 [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
與 [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)。

這些是當下的唯讀觀察，不是無競態的 trusted-open 保證。DACL/SDDL、owner、
elevation 或 `TokenHasRestrictions=true` 都不證明有效存取權限或完整 sandbox。
選定 PID 不能涵蓋 Agent 所有能力；sandbox worker 的觀察不能代替 native host
觀察。必須分別選定 VS Code、Codex host、worker 等實際程序；已知 host 的
1001 與舊 worker 的 1003 是不同 Agent 身分，不能只保護其中一個。

## 新的獨立資料契約

`AcceptanceSpecificationV1` 的 `specification_type` 為
`windows_isolation_acceptance_specification`，`schema_version=1`，用途固定為
`disposable_synthetic_only`。這是用途宣告，不會驗證資料內容。既有授權 V1
契約與科學計算完全不變。

- `run_id`：由研究者選定的 canonical UUIDv4；不在此工具生成或保留 UUID。
- `deployment_root`：固定為 `C:\ProgramData\TEC-Authorization-Acceptance\<run_id>`。
  此 checkpoint 不支援任意 root、UNC、device path、ADS、相對路徑或 path traversal。
  固定前綴只是限制選擇範圍，並不證明該處可供犧牲測試。
- `roles.A`：所有已識別 Agent SIDs 及明確 PIDs；`roles.W/V/M`：各自的 SID/PIDs。
  已填入 SID 必須互異，PID 不得重複。尚未部署的 SID 可為 null，結果為 `BLOCKED`。
- `root_expectations`：獨立核定的 resolved path、volume serial/GUID、owner SID、
  exact owner/DACL SDDL；未知值為 null，不從觀察結果自動補值。
- `resource_expectations`：各資源的預期 owner/SDDL。資源路徑由固定 layout 推導，
  不接受額外自訂檔案路徑。涵蓋 runtime/Python、app、dependencies、registry、
  bootstrap/config、Store root/history/head/checkpoint、永久 lock、外部 checkpoint、
  W/V diagnostics。實際 layout 見來源 `RESOURCE_LAYOUT`。

Python API `build_acceptance_specification(run_id, agent_sids=..., agent_pids=...)`
只回傳未完成模板；`from_dict/from_json` 嚴格驗證，`to_dict` 回傳獨立副本。
輸入上限 64 KiB、巢狀上限 16 層；拒絕重複 JSON keys、浮點數、NaN/Infinity、
非預期欄位及超限資料。canonical JSON 為 UTF-8、排序 keys、緊密 separators、
保留 Unicode、末尾一個 LF；`content_sha256` 識別這些 bytes。
它不認證發布者、研究者、來源程序或檔案，也不能自行核定 manifest。

研究者自行審閱並供應規格 JSON 後，可將它經 stdin 傳入：

```powershell
Get-Content -Raw -LiteralPath 'C:\ReviewedSyntheticSpec\acceptance.json' | .\.venv\Scripts\python.exe -I -S -B src/workflow/windows_isolation_acceptance.py dry-run --expected-manifest-sha256 '<reviewed-64-lowercase-hex-digest>'
```

以上路徑與 digest 均為佔位值；請勿傳入私鑰或研究資料。
CLI 只從有界 stdin 解析規格，不自行開啟輸入檔案。省略 digest 會 `BLOCKED`，
不匹配會 `FAIL`；匹配只證明內容一致，`researcher_approval_verified` 永遠為 false。
獨立批准及 pin custody 永遠不能由此診斷程式自行證實。

## 狀態與示意輸出

`PASS` 僅代表 schema 或特定已觀察事實符合宣告；`FAIL` 代表已知違規／無效規格；
`UNKNOWN` 表示不可取得或不足的證據；`BLOCKED` 表示缺少必要身分、資源或 pin；
`NOT_RUN` 表示刻意未執行。十個實際權限及 Store 驗收案例一律 `NOT_RUN`。
dry-run 總狀態依 FAIL、BLOCKED、UNKNOWN 排序，永遠不能得到隔離成功。
inspect CLI exit 0 僅表示已輸出診斷，仍須檢查 JSON；dry-run 固定 exit 2，
避免被呼叫端誤當驗收成功。無 execute、cleanup、trust 或繞過前置條件的選項。

下列為遮蔽且節錄的**示意**，不是本機驗收結果：

```json
{
  "report_type": "windows_isolation_acceptance_dry_run",
  "schema_version": 1,
  "status": "BLOCKED",
  "prerequisites": [
    {"check": "role_W", "status": "BLOCKED", "reason": "identity_or_live_process_not_deployed"},
    {"check": "role_V", "status": "BLOCKED", "reason": "identity_or_live_process_not_deployed"},
    {"check": "manifest_origin", "status": "UNKNOWN", "reason": "researcher_approval_and_bootstrap_custody_not_authenticated_here"}
  ],
  "acceptance_cases": [
    {"case_id": "permanent_lock_lifecycle", "status": "NOT_RUN", "reason": "execution_disabled_in_this_checkpoint"}
  ],
  "windows_local_isolation": "NOT VERIFIED",
  "trusted_human_authorization": false,
  "execution_eligible": false,
  "evidence_origin_authenticated": false,
  "researcher_approval_verified": false
}
```

## 後續真實部署的前置條件（本次不執行）

1. 研究者明確批准全新、可犧牲且僅含合成資料的部署，以及每項破壞性操作。
   核對 exact absolute/resolved root、volume、owner/SDDL、無 reparse、唯一且未使用
   run ID，並由獨立可信管道核定 manifest；任何必要證據缺失即 NO-GO。
2. 研究者另行核准 W/V 帳號及 ACL 部署；實際 primary token 證實所有 A 與 W/V/M
   的分離及可信啟動。啟動環境、Python/標準函式庫/dependencies、import paths、
   bootstrap/config/pin custody 必須受保護。metadata 不驗證這些檔案內容。
3. 另行審查真正的有效存取權限測試執行器；在各角色原生 token 下測試 A 的
   write/replace/WRITE_DAC/WRITE_OWNER、祖先 DELETE_CHILD／rename 等旁路皆被拒絕。
   不能只比對 DACL，也不能以 mock、名稱、低 integrity 或設定 pin 取代測試。
4. W 的允許操作與 V 的唯讀操作須實測；現有 lock 使用 `r+b`，V 必須具備該
   永久檔案必要的開啟權限，這是明確例外，不能擴張成資料寫入權。A/W/V 均不得
   刪除／替換 lock；validate/append 在 lock 缺失時不得重建。
5. 在可犧牲部署實測 W 新建 temporary files 的 owner/繼承 DACL，以及 head/checkpoint
   replace 後的 policy。單檔 atomic replace 不等於 history/head/checkpoint 多檔交易；
   必須測試中斷、部分發布、衝突與缺少 anchors 時 fail closed。
6. 獨立較新 checkpoint 的產生、保留及取用必須另有可信責任人；測試撤銷後不回退
   舊批准，以及 rollback 低於該 floor 被拒。舊 floor 不能證明之後沒有回滾。
   私鑰、signer、Store 執行及回滾測試均須另行批准，這個 harness 不實作或呼叫它們。

測試中的 synthetic API records 僅驗證程式分支，無法建立 Windows 隔離。
native smoke tests 只查目前測試程序與本模組 metadata；非 Windows 或證據不可取得時
明確 skip。完整既有 suite 含金鑰生成與科學測試，依本次研究者限制不執行；
僅執行符合絕對限制的新測試。

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```
