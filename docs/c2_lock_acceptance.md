# C2 E1 acceptance specification（Checkpoint 3B-2C-2C-2B）

C2 已被接受為後續驗證方向；**這不是部署批准，E1 尚未執行**。本文件不重做架構比較。
新增規格、validator 與 plan builder 都只處理記憶體內資料，不查 OS、不讀取來源檔案、
不轉換／套用 SDDL、不執行 access probes，也不呼叫 Store、signer 或科學模組。

## 獨立版本與公開介面

`src/workflow/c2_lock_acceptance.py` 提供：

- `C2AcceptanceSpecificationV1.from_dict/from_json/to_dict/to_json/paths/content_sha256`：
  不可變、可 round-trip 的獨立宣告契約；回傳 dict 為獨立副本。
- `build_c2_acceptance_specification(run_id, store_id)`：純 incomplete template，不生成 UUID。
- `build_c2_e1_plan(specification)`：30 個 resource rows、18 個 E1 case groups、固定 blockers
  及 researcher checklist。所有 case 都 `enabled=false / NOT_RUN`，原因固定
  `execution_disabled_in_this_checkpoint`；整體固定 `BLOCKED / NO_GO`。

新契約 `specification_type=c2_lock_namespace_acceptance_specification`、`schema_version=1`、
`layout_version=c2_separate_coordination_v1`、`purpose=synthetic_E1_only`。
這裡的 V1 是 **C2 契約本身第一版**，不是既有 Windows Inspector／Store V1。
舊 `RESOURCE_LAYOUT`、十個舊 acceptance cases、部署 preparation V1 全部保留；
兩種 specification type 相互拒絕，不能把 C2 資料送入舊 dry_run 冒充已支援。
只重用舊 inspector 的純 scalar／bounded JSON 驗證 helper，不呼叫其 native backend。

完整頂層欄位如下，拒絕未知／缺漏欄位與任何 approved/trust/execute/path override：

| 欄位 | 意義 |
| --- | --- |
| specification_type/schema_version/layout_version/purpose | 上述固定值；version 必須 exact int，不接受 bool |
| run_id/store_id | 各自 canonical UUIDv4 宣告，非發現或配置結果 |
| deployment_root | 固定 acceptance parent + run_id，無任意 root／UNC／relative path |
| roles | A={sids:完整 SID list,pids:list}；W/V/M={sid:null或完整SID,pids:list}；已填 SID 全部互異，PID 不重複 |
| identity_expectations | acceptance_parent/root/authority/data_store/coordination/lock_parent/history_lock 七個 immutable baseline |
| artifact_sha256 | runtime/application/dependencies/bootstrap/configuration/registry/independent_checkpoint 七項 raw artifact hash 宣告或 null |

每個 identity baseline 恰有 resolved_path、volume_guid、volume_serial、file_id、owner_sid、
sddl 六欄，可為 null。已知 resolved path 必須等於固定 C2 路徑；已知 volume 宣告須一致，
file identity 不得 alias；owner 不得是 A，若 M SID 已填，須一致。SDDL 只驗證 bounded
非空字串，**不解譯或認證其有效性**；不以 candidate masks 自動產生 actual SDDL。
其他祖先與 release/anchor 檔案仍必須在獨立 evidence inventory 逐一取得實際 baseline；
這七欄集合不是完整 Windows acceptance evidence，更不是核發權限的輸入。

沿用 64 KiB／16-container strict JSON codec；拒絕重複 keys、浮點數、NaN/Infinity、
超限／過深輸入。無效 specification 拋 ValueError，沒有可執行 fallback。
canonical spec 為 UTF-8、排序 keys、compact separators、保留 Unicode、末尾一個 LF；
`content_sha256` 只識別 **spec bytes**，不涵蓋 builder 程式、完整 plan snapshot 或原始
檔案，也不認證研究者。批准前必須獨立保留完整 plan、code revision/hash 與來源證據。

純資料使用範例（UUID 僅為示意，未預留／驗證唯一性）：

```python
from src.workflow.c2_lock_acceptance import build_c2_acceptance_specification, build_c2_e1_plan
spec = build_c2_acceptance_specification(
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
)
plan = build_c2_e1_plan(spec)  # BLOCKED；沒有任何 I/O 或測試執行
```

## C2 layout 與測試資產

令 P=`C:\ProgramData\TEC-Authorization-Acceptance`，R=`P\<run_id>`，S=`<store_id>`。
P 若已存在，只能先獨立審查，不允許自動接管。R 必須 fresh、disposable，不能落在
repository、`.venv`、profile、production 或未知既有部署。所有內部路徑只從兩個 UUID 推導。

```text
C:\ / C:\ProgramData                         既有祖先：唯讀觀察，無本次政策變更
P                                           既有或後續另批的 M-controlled parent
R\authority\store\history.jsonl             E1 僅為 plain synthetic fixture
R\authority\store\head.json
R\authority\store\checkpoint.json
R\authority\store\e1-publication.tmp         明確核定的 W publication source
R\authority\coordination\S\history.lock      M 預建永久空檔，非 data 子目錄
R\release\runtime\python.exe                 須保護完整 EXE/DLL/stdlib inventory
R\release\app / R\release\deps               須保護所有 installed-file bytes/import paths
R\anchors\registry.json / verifier.json / minimum-checkpoint.json
R\bootstrap\manifest.json
R\e1-control-A\source.tmp                    A 的 positive control（每個 A token 均測）
R\e1-control-W\source.tmp
R\e1-control-V\source.tmp
```

E1 的 history/markers/anchors 是 M 在未來單獨批准後預建的**無授權效力合成 bytes**；
不使用 AuthorizationStore.initialize、不生成 public/private keys，也不把 fixture 當成有效
V1 config/registry/Store。writer publication 僅測 filesystem mechanics；目前舊 Store
與 LocalVerifier 仍不實作 C2，不能為 E1 改動或呼叫它們來宣稱 C2 end-to-end 成功。

Publication source 使用固定 `e1-publication.tmp`；每次建立／關閉／replace／再次建立的
確切順序與目標均須列入批准 inventory，不能把 prefix 或 parent 路徑當成任意子檔授權。
control source 由 M 預建，明確授該角色所需 read/write/DELETE，用於排除「來源不可用」
造成的假 denial。所有 A SIDs 只在 control-A 共享合成控制資產，不構成彼此間的信任邊界。

## Proposed rights matrix（不是有效存取計算或實際 DACL）

數值皆為 object-specific masks：R=`0x120089`、RX=`0x1200a9`、RW=`0x12019f`、
T=FILE_TRAVERSE=`0x20`、DELETE=`0x10000`、WRITE_DAC=`0x40000`、
WRITE_OWNER=`0x80000`。FILE_ADD_FILE=`0x2`、ADD_SUBDIRECTORY=`0x4`、
DELETE_CHILD=`0x40` 都是**目錄**能力；file WRITE_DATA=`0x2`、APPEND_DATA=`0x4`
是不同物件的能力，不能混用解讀。[Microsoft FILE_* 權限定義](https://learn.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants)

| Resource | Owner／policy | A | W | V | M |
| --- | --- | --- | --- | --- | --- |
| C:\、ProgramData、P | 不產生 masks 或改 ACL，實際 owner/DACL/ancestor substitution 必須獨立確認 | 觀察既有有效能力 | 同左 | 同左 | 獨立審查；不得自動接管 |
| R、authority、coordination、S lock parent、release/anchors/bootstrap 結構目錄 | M；protected explicit DACL | T only | RX | RX | FullControl `0x1f01ff` |
| data Store directory | M；protected explicit DACL | T only | RX + ADD_FILE `0x1200ab` | RX | FullControl |
| history.jsonl | M；protected explicit DACL | 無 allow | RW（不是 OS append-only） | R | FullControl |
| publication temp／head／checkpoint | M 預建 marker；W 新建／replace 後 owner 必須符核定 W SID | 無 allow | RW+DELETE `0x13019f` | R | FullControl |
| permanent lock | M；protected explicit DACL；file ID 不變 | 無 allow | **RW exception** | **RW exception** | FullControl；runtime 期間不替換 |
| runtime/app/deps 的 executable／DLL／Python bytes | M；逐檔 inventory 明列 protected RX policy | 無 allow | RX | RX | FullControl |
| config/registry/bootstrap/independent checkpoint | M；逐檔 protected R policy | 無 allow | R | R | FullControl |
| control-A/W/V directory | M；explicit DACL，僅指定角色 | own control: RX+ADD_FILE，其餘 T | 同規則 | 同規則 | FullControl |
| control source.tmp | M 預建；explicit DACL | own control source: RW+DELETE，其餘無 allow | 同規則 | 同規則 | FullControl |

SYSTEM 可保留 FullControl，屬受信任 OS 邊界，不是另一個 Agent grant。A 在新 C2
結構目錄的 T-only 提案是為了讓 probe 可到達明確 target，避免依賴 bypass-traverse
privilege；不含 list/create/write/delete/owner/DACL。這不改 V1 的 A=0 提案。
不得給 A/W/V 所屬的 Everyone、Users、Authenticated Users 等群組寬鬆額外權限。
非 elevated 的 token 不證明不能提權；restricting SIDs、deny-only groups、linked-token、
privileges 與 A 可控制的 credentials/session 都必須審查。

所有新結構目錄都**不給 A/W/V ADD_SUBDIRECTORY、DELETE、DELETE_CHILD、WRITE_DAC、
WRITE_OWNER**。只有 data 與各角色自己的 control directory 可 ADD_FILE；不能因此
讓 coordination/S lock parent 也可 ADD_FILE。global ancestors 若有 unrelated-child
creation 權限，不可直接斷言會替換受保護的現存 component；須測確切 substitution path。
任一可替換／移除既有 protected component 的能力，或無法證實其不可替換，皆 STOP。

data 的新 child files 明列 OI/IO 的 W RW+DELETE、V R、M/SYSTEM FullControl、
OWNER RIGHTS (`S-1-3-4`) RC=`0x20000`。control 新檔只給該角色 RW+DELETE；
其他新目錄的 file defaults 僅 M/SYSTEM/OWNER RIGHTS。OI-only 在 child directory
只是 inherit-only carrier，不是 directory write grant；新 child directories 均需獨立
protected policy，不能將 file DELETE 變成 directory DELETE_CHILD。[ACE 繼承規則](https://learn.microsoft.com/en-us/windows/win32/secauthz/ace-inheritance-rules)

history/lock 以 protected per-file DACL 覆蓋 mutable-file inheritance；anchor 檔案明確
逐檔給 W/V R，runtime inventory 逐檔給 RX，不依賴結構目錄 defaults。OWNER RIGHTS
與實際新檔 owner 必須量測；若 creator/group/privilege 使 W 取得 WRITE_DAC/OWNER
或權限外溢就 STOP。plan 的 actual_sddl 永遠 null，actual_effective_access 永遠 UNKNOWN。

**RW lock 例外不能被抹去：** W/V 可獲得 WRITE_DATA/APPEND_DATA/WRITE_EA/
WRITE_ATTRIBUTES 相應 handle 能力；E1 正常 lock/unlock 不寫任何 lock bytes，但不是
OS 完全唯讀。同一 token 的其他程序如何使用此能力，必須另測 hardlink/reparse。
只證實程式不寫 bytes，不能證實 OS 不允許寫。

## E1 case groups 與 expected outcomes

以下 18 組全部 NOT_RUN。roles/targets 會在 plan 中解析為固定路徑；每組須依完整 A
token 清單、W/V 的不同 processes，以及每個 resource/one-bit mask 展開個別 evidence
records。group 不是單一 probe，不能只測一個 A PID 或 broad GENERIC_ALL 就結案。

| Case ID | 實際 token／操作 | 預期與必要證據 |
| --- | --- | --- |
| native_primary_tokens | A/W/V/M 的明確 PID + creation time + handle-bound primary token | 取得獨立原生身分；不能用 username/parent/file owner/caller role string |
| ancestor_namespace | A/W/V 對既有祖先與新 protected parents | exact path 的 rename/substitution/delete-child/owner/DACL 旁路被 OS 拒絕；無法證明則 STOP |
| runtime_anchor_read | W/V 開 fixed code RX、anchors R | 成功；另有獨立 bytes provenance、runtime/DLL/import inventory，成功開檔不是來源認證 |
| individual_rights | A/W/V 的 matrix required_individual_denials | 每個 bit 分別 request。directory: ADD_FILE、ADD_SUBDIR、DELETE_CHILD、DELETE、WRITE_DAC/OWNER；file: READ_DATA、WRITE_DATA、APPEND、EA、EXECUTE、ATTR、DELETE、WRITE_DAC/OWNER，依 allow mask 排除合法 bits |
| writer_publication | W 在 data 建固定 source、write/flush/close，再 replace head/checkpoint | 成功，無 broad Modify/DELETE_CHILD，無 Store API、簽章或真實研究資料 |
| owner_inheritance_after_replace | W 建立／替換後 | actual owner/DACL/inheritance、source/target file IDs 與核定政策一致；不假定舊 target DACL 保留 |
| existing_lock_RW | W/V existing open，read/write-compatible handle、正常鎖操作 | 成功，lock bytes/hash/file ID/link count 不變；例外權限只能限該檔，不外溢到 data |
| cross_process_locking | distinct W/V processes、同 file identity、offset=0,length=1 | 先 W 持鎖，V 非阻塞 contention；release／holder exit 後 V 成功。再反向測，設 bounded deadline，無永久等待 |
| existing_lock_delete_replace | A/W/V；來源用各自已證實可用的 control source | DELETE/open、native delete、rename/replace 與 parent checks 按政策被拒，lock ID/bytes/SDDL 不變 |
| M_quiesced_missing_lock_injection | M，在獨立批准且所有 role processes/handles 停止後 | 只移除指定犧牲 lock；記錄舊 file ID，沒有 auto restore；不是 Writer 能力測試 |
| missing_lock_existing_open | W/V existing-only open | file-not-found，名稱仍不存在。這是 missing-open observation，**不是 ACL-denial PASS** |
| missing_lock_name_recreation | A/W/V 直接 CREATE_NEW、copy、rename、hard-link 到精確 missing 名稱 | parent 存在且 control source 可用時，OS permission denial；不能只呼叫 create=False API |
| lock_parent_new_names | A/W/V 對 coordination 與 S parent 的新增檔／目錄 | 個別 ADD_FILE/ADD_SUBDIRECTORY 與核定 new-name attempt 被拒；無 prefix 白名單假設 |
| existing_lock_reparse | A/W/V，在核定的 RW/privilege 狀態下 set/remove reparse 的能力觀察 | 本版要求原生拒絕；允許或證據不明即 STOP，不能以應用層拒絕冒充 OS denial |
| hardlink_alias_outside_coordination | 各 token 將現有 lock 連到自己 writable control | 不預先聲稱 RW token 一定不能建 alias。本版 denial-required-or-STOP；成功便記錄 capability、link count 與 shared-descriptor 影響並停止，交研究者重審 |
| handle_identity_and_no_follow | W/V 使用實際 opened handle／native no-follow protocol | opening/locking/release 前後 volume/file ID/owner/DACL/link count=1 一致；拒絕任何 reparse/alias/新 lock identity，不找舊 V1 lock fallback |
| verifier_data_unchanged | V 對 history/markers/anchors 的個別 mutation attempts | OS denial，加上 bytes/security/identity 前後不變；不拿「control-V 可寫」推論其可寫 data |
| independent_evidence_and_stop | M 保留完整原始記錄與外部批准 | 原始 evidence 由獨立 trusted custody 留存，無 retry/repair/rollback/cleanup 或授權升級 |

硬連結名稱共享檔案的 security descriptor，不產生一套較弱的 link DACL；
但 alias 與 RW capability 仍可能造成污染／DoS，不能忽略。[CreateHardLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw)
Reparse 操作及 no-follow handle 行為亦須獨立量測，readonly parent 並不自動證明
所有 file-object 操作被拒。[Reparse point operations](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-point-operations)

## 必須保留的 evidence record 與判讀規則

後續 collector 尚未實作。本版要求每個展開的操作至少保留以下欄位，不能只交 Python
exception、mock、icacls 清單或一張設定截圖：

1. case/subcase ID、RunId/store_id、spec hash、完整 reviewed plan/code hash、獨立批准
   reference、時間與來源程序；若時鐘不可驗證亦標 unknown。
2. 實際 PID/creation time、同 process handle 的 primary SID/token type、integrity、
   elevation、groups（enabled/deny-only）、restricting SIDs、privileges、AppContainer，
   以及是否有 impersonation／linked-token 路徑。測試期間 token 或 process identity 變更即 STOP。
3. exact API、target/control source、desired-access **逐 bit**、disposition、sharing、flags、
   region offset/length、native return、即時 GetLastError/必要 NTSTATUS、是否真的到達 native call。
4. 前後 exact/resolved paths、volume GUID/serial、filesystem、handle file IDs、link count、
   reparse tag／attributes、owner、原始與 canonical DACL/繼承狀態、synthetic bytes hashes。
   marker ID 可按核定替換流程改變；permanent lock ID 不能默默變更。
5. 相同 token、相同有效參數的 positive control 與 source DELETE/read 可用證據；
   W/V mutation denial 必須排除 missing parent/source、invalid filename、read-only attribute、
   分享衝突、持鎖狀態或 collector 自己的 application check。不得為了 control 修改 target ACL。
6. observer 的可信身分、完整性與保管鏈；所有 missing/failed acquisitions 明列 UNKNOWN，
   不省略不利記錄、不假造 PASS。不得記錄私鑰、環境 secrets 或無關個人資料。

permission denial 要求 native ERROR_ACCESS_DENIED 等與該操作相符且經 controls 歸因的
結果；單有 error 5 仍不保證原因一定是預期 DACL。FILE_NOT_FOUND/PATH_NOT_FOUND
不能當 permission denial；SHARING_VIOLATION/LOCK_VIOLATION 只可支持相應 sharing／
locking case。應用程式在 native call 前拒絕只算 application rejection／未測 OS 能力。
若發現合法 write mask 之外的能力，立即 STOP，不以收緊程式分支代替 OS policy 重審。

## Researcher authorization checklist／STOP 與剩餘 blockers

下面每項須由研究者透過獨立可信管道核定；JSON 裡填 SID/hash/SDDL 或全欄填齊不算批准。
plan 的 checklist 一律 NOT_VERIFIED；本工具不接收批准或原生結果，也不產生 eligibility。

- [ ] 核定新的 exact R/RunId/store_id、七個 baseline 與完整資產 inventory；證實從未使用，
      無 aliases/reparse，指定 local NTFS volume；範例 UUID 不能直接視為已核定。
- [ ] 提供全部 A host/worker 完整 SID 與 token 變體；W/V/M 分離、standard startup、
      credentials/session 不受 A 控制。RID 1001／1003 只是線索，不能推導完整 SID 或完整能力覆蓋。
- [ ] 審閱每個新目錄／檔案 before/after owner、exact native SDDL、group/privilege 影響，
      明確同意 RW lock 例外、A T-only 與每個 control grant；不更動 global ancestor ACL。
- [ ] 核定只含 synthetic bytes 的 pre-created files、control sources、固定 publication
      source 重用順序及 failed-probe containment；無 key generation、signer、Store initialization。
- [ ] 另行審查 native probe/evidence collector 與可信啟動方式；不得從 Agent 指定任意
      EXE/path/plugin/callback，也不得把現有 V1 inspector 當 C2 executor。
- [ ] 逐項批准 destructive attempts、M-only quiesced missing-lock injection、reparse/hardlink
      及雙向跨程序鎖時序；缺失後不 recreate、不修復、不讓新舊 lock handles 共存。
- [ ] 獨立驗證 runtime/code/dependency/DLL/import inventory 與 bootstrap/config/registry/floor
      raw-byte hashes，保管批准與原始 evidence；目前 artifact hashes 只是 unknown／宣告。
- [ ] 同意任何非預期成功、無法歸因的失敗、未知證據、owner/DACL/token/identity 漂移，
      或 E1 fixture 誤用為有效授權資料，都 STOP／NO_GO；無 broad Modify/FullControl 補救。
- [ ] 指定 M 封存與獨立批准的 retirement；不自動 cleanup、重試、降 checkpoint、回滾或修 Store。

目前所有 native cases 未執行；collector、no-follow/identity protocol、可信啟動、完整
token/ancestor/pin custody、跨程序／角色實測與 RW reparse/hardlink 能力均未建立。
既有 Store V1 尚不使用 external lock；獨立 checkpoint 仍僅是 retained lower bound，
不是 global latest-head／人類在場或 execution permission 的證明。

本 checkpoint 只允許純規格測試及既有允許的唯讀 harness。任何真正 Windows mutation
必須等待本規格的 Scientific & Security Review，並取得另一次明確 sacrificial-deployment
批准。E1 即使未來通過，也不能自動解除人類授權／執行 flags。

## 本次驗證紀錄

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_c2_lock_acceptance.py tests/workflow/test_windows_deployment_preparation.py tests/workflow/test_windows_isolation_acceptance.py -q -ra --tb=short -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pip check
```

C2 新增 48 個純資料測試，覆蓋獨立 type/layout、V1 未變、固定 paths／舊 lock fallback
拒絕、角色與 physical-identity 衝突、bounded JSON、矩陣／control／RW 例外與不可執行性。
完整允許的三檔 focused set 通過；既有兩個 native smoke 僅為唯讀診斷，不是 E1 cases。
未執行生成私鑰、Store 初始化、科學流程或破壞性 native probes 的 suites。

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
Deployment Decision: NO_GO
```
