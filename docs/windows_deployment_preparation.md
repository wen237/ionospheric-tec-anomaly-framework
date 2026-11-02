# Synthetic Windows deployment preparation（Checkpoint 3B-2C-2C-2）

本次只產生可審查的提案；**部署 NO-GO**。沒有部署執行器、帳號／ACL 指令、
軟體安裝、金鑰生成、Store 初始化或清理。既有授權 V1 與
[inspector V1](windows_isolation_acceptance.md) 完全不變。下述權限是候選政策，
尚未套用或通過原生有效存取測試，不能將此文件或其 digest 當成批准。

## 介面與可重現的操作 manifest

新增純函式 `build_deployment_preparation(specification, *, artifact_sha256=None)`。
輸入沿用 `AcceptanceSpecificationV1` 物件、dict 或 bounded JSON；未知值保留 null。
可選 hashes 只接受 `ARTIFACT_LAYOUT` 的十二個固定鍵，值為 lowercase SHA-256 或 null。
不讀來源檔案、不呼叫 inspector、不生成 RunId、不匯入簽章／科學模組。

回傳獨立契約 `manifest_type=windows_synthetic_deployment_preparation`、`schema_version=1`，
包含完整固定 layout、角色宣告、候選權限、artifact declarations、操作清單與 blockers。
每筆操作列出 exact target、required privilege、before/after owner/DACL 政策、原因、
failure conditions、verification、containment、approval gate；全部 `enabled=false`、
`status=NOT_RUN`，十個隔離案例也全部為 `NOT_RUN`。沒有任何執行或批准開關。

`content_sha256` 涵蓋**排除該 digest 欄位**後的 UTF-8 canonical JSON：排序 keys、
compact separators、ensure_ascii=False、禁止 NaN/Infinity、末尾一個 LF。
相同輸入得到相同內容；這只識別提案內容，不認證研究者、來源、OS 或已安裝 bytes。
即使所有 SID/hash 宣告齊全，輸出仍固定 `BLOCKED / NO_GO`。

[範例規格](windows_deployment_preparation.example.json) 使用一個**僅供審閱的候選 RunId**；
沒有建立、預留或查詢該 root，也沒有證實唯一性。範例不捏造完整主機 SID、W/V/M
或 DACL，因此應得到 BLOCKED。純準備命令只在開發 repository 輸出提案，不是可信啟動：

```powershell
.\.venv\Scripts\python.exe -B -c "from pathlib import Path; import json; from src.workflow.windows_deployment_preparation import build_deployment_preparation; print(json.dumps(build_deployment_preparation(Path('docs/windows_deployment_preparation.example.json').read_text(encoding='utf-8')),ensure_ascii=False,indent=2))"
```

只有這個明確範例 JSON 由命令讀取；builder 本身沒有檔案 I/O。不要將金鑰、憑證或
研究資料傳入。宣告的 artifact hashes 尚未測量；實際軟體來源、精確版本、wheel／DLL
清單與 hashes 均待獨立核定，不會從開發 `.venv` 偷渡為部署信任。

## Exact layout 與 principal assignments

令 `R = C:\ProgramData\TEC-Authorization-Acceptance\<researcher-reviewed UUIDv4>`。
所有可變操作限制在 R；僅建立 acceptance parent 的提案以固定 parent 為目標。
既有 acceptance parent 只能先獨立審查，不允許自動覆蓋其 owner/ACL。
不得更動 `C:\`、`C:\ProgramData` 的政策，也不得改指 repository、`.venv` 或 profile。

```text
R\release\runtime\python.exe                 候選獨立 CPython x64（非 venv）
R\release\runtime\python314.dll / python3.dll / python314.zip / python314._pth
R\release\app\src\workflow\...              授權與必要的既有模組 closure
R\release\app\src\temporal_anomaly\...      既有型別匯入依賴；不執行科學計算
R\release\deps\...                           wheels、原生 DLL 及 transitive dependencies
R\bootstrap\writer-launcher.exe              待另行實作／審查，現在不存在
R\bootstrap\verifier-launcher.exe            同上，不可由 Agent 設定或更換
R\bootstrap\manifest.json                    固定 paths/pins 的啟動 manifest
R\bootstrap\runtime-files.json               installed-file inventory
R\bootstrap\application-files.json           installed-file inventory
R\bootstrap\dependency-files.json            installed-file inventory
R\anchors\registry.json                      既有 public-key registry V1
R\anchors\verifier.json                      既有 VerifierConfigurationV1
R\anchors\minimum-checkpoint.json            Store 外部的 StoreCheckpointV1
R\anchors\retained-checkpoints\...           M 保留的核定 floor；每個 filename 待核定
R\authority\store\history.jsonl              既有 Store V1
R\authority\store\head.json
R\authority\store\checkpoint.json
R\authority\store\history.lock               永久同一個 file identity
R\logs\writer\... / R\logs\verifier\...       各自診斷，非 authoritative evidence
```

runtime 內部檔名以 CPython 3.14 候選為例，**精確檔案集合仍是 blocker**。正式 proposal
須將 runtime/dependency inventories、temporary/log/retention names 展開為每筆確切變更，
再批准；上層 bundle 路徑絕不授權修改任意子檔案。本 checkpoint 不產出假的 V1 Store、
registry、config 或 checkpoint bytes；其內容與 raw-byte pins 須在後續批准階段生成及核對。

| Role | 現有證據／提案 | 部署前必須補齊 |
| --- | --- | --- |
| A | host RID 1001 與 worker RID 1003 都屬潛在不可信主體 | 全部完整 SIDs、actual primary tokens、groups、privileges、可控制的程序／登入 session；不能由 RID 猜 domain |
| W | 專用 standard user；未部署時提議 `TECA-W-<RunId前12個hex>` | 研究者核定名稱無碰撞、建立後完整 SID、憑證及 signer capability 由 trusted side 持有 |
| V | 專用 standard user；提議 `TECA-V-<同上>` | 與 A/W/M 不同 SID；固定唯讀 verifier 入口與啟動憑證 |
| M | 另行指定可信維護 SID，不自動建立 | 不得等同已被 A 控制的 1001 或 1003；獨立 session／操作管道與 pin custody |

這些是提案，不是新建帳號。若 M 仍是 Agent 控制的同一個 SID，直接 NO-GO。
非 elevated 的樣本 token 不證明其無法取得更高權限；須檢查群組、linked-token／提權路徑、
SeTakeOwnership/Restore/Backup/Debug/Impersonate 等能力及實際 session 控制。

## 候選 principal/resource 權限矩陣

以下 masks 為檔案／目錄 object-specific rights，非 PowerShell `Modify`。
R=`0x120089`、RX=`0x1200a9`、RW=`0x12019f`、DELETE=`0x10000`。
所有資源由 M 與 SYSTEM 持有維護 FullControl（`0x1f01ff`）；不給 W/V FullControl
或 directory DELETE_CHILD（`0x40`）。A 不應獲得任何 allow；也不得有 Everyone、
Authenticated Users、Users 或 CREATOR OWNER FullControl 等間接寬鬆 ACE。
這是預期政策，不是「A=0」就證明有效權限為零。[檔案存取權限](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)
說明 Windows 依實際 token 與 security descriptor 判定 access。

| Resource | 預期 owner | W | V | Inheritance／替換政策 |
| --- | --- | --- | --- | --- |
| R 與結構目錄 | M | RX／traverse | RX／traverse | protected DACL，初建即限制；祖先不得讓 A replace 或 DELETE_CHILD |
| runtime/app/deps 與 launcher | M | RX | RX | M/SYSTEM、W/V RX 的 reviewed OI/CI；不得載入 A-writable 位置 |
| registry/bootstrap/config/external floor/inventories | M | R | R | protected、逐檔核定，不由 W 更新 pins |
| Store directory | M | RX + FILE_ADD_FILE (`0x1200ab`) | RX | 無 DELETE_CHILD、WRITE_DAC/OWNER；新檔 OI/IO 規則見下 |
| history.jsonl（初始化封存後） | M | RW | R | protected；既有 Python `ab` 可能要求 GENERIC_WRITE，不能假稱 OS append-only |
| head.json/checkpoint.json | W（替換後） | RW + DELETE | R | 源 temporary file owner/DACL 隨 replacement 保留並須實測；不靠每次 M 修 ACL |
| history.lock | M | RW | **RW 例外** | protected、無 DELETE、無替換；A/W/V 無 parent DELETE_CHILD |
| writer logs | M 的目錄、W 的新檔 | 目錄 RX+ADD_FILE；自己檔 RW+DELETE | 無 | OI/IO 只給 W，不是 loader/config/anchor 來源 |
| verifier logs | M 的目錄、V 的新檔 | 無 | 同上，限 V | 不得給另一角色寫入權；可變檔名須另行核定 |

政策中的 `directory_child_inheritance` 是**宣告於父目錄的提案**，不再以
DIRECTORIES_ONLY 描述 object inheritance。`directory_self` 列出 self-only ACE 的
權限及空 flags；`inheritable_aces` 另列每個角色的 mask 與 flags，均含 INHERIT_ONLY，
不回頭增加父目錄權限。`child_files` 列出預期在子檔案生效的權限；
`child_directories` 分開列出預期生效權限與僅供後代傳遞的 inherit-only 權限。
OI-only ACE 在子目錄可成為 inherit-only carrier，不能當成目錄上的有效 grant；
CI ACE 才在子目錄生效。這些仍是預期表示，並非 AccessCheck 或 DACL setter。
詳見 [Microsoft ACE 繼承規則](https://learn.microsoft.com/en-us/windows/win32/secauthz/ace-inheritance-rules)。

`anchor` recipe 明列 W/V R 的 child-file inheritance；若該 recipe 用於父目錄，
W/V 的 OI/CI/IO ACE 預期把 R 傳給子檔案及子目錄。但實際 layout 的 anchors/bootstrap
結構目錄仍採 container 政策，**不能假定它們自動給新檔 W/V R**。每筆
`stage_reviewed_artifact` 的 anchor 檔案，及外部 floor 發布，均明確要求逐檔套用
`anchor` 的 protected DACL（M/SYSTEM FullControl、W/V R、OWNER RIGHTS RC）；
其 W/V R 與 recipe 的 child-file 權限一致，且不能被 marker 的 W RW+DELETE 取代。
這個逐檔 DACL 要求仍須另行批准，現在不會執行。

Store 新檔的候選 inherited ACE：M/SYSTEM FullControl；W RW+DELETE；V R；
OWNER RIGHTS 僅 READ_CONTROL (`0x20000`)。W/V/OWNER RIGHTS 為 object-inherit、
inherit-only，避免將新檔 DELETE 誤套到 Store directory；M/SYSTEM 的繼承用 ACE
為 OI/CI/IO，父目錄本身另以 self-only ACE 保持原定權限。
history/lock 再由 M 設成個別 protected DACL，避免繼承 DELETE。初次 initialize
產生的 history 暫由 W 擁有，必須在 W/V 停止時由 M 完成一次 sealing 才能發布。

OWNER RIGHTS (`S-1-3-4`) ACE 會改變 owner 隱含 READ_CONTROL/WRITE_DAC 的處理；
候選政策用明確 RC 避免 W 因新檔 owner 身分取得隱含 WRITE_DAC。它不消除其他 ACE、
群組、privilege 或惡意建立時自帶 security descriptor 的能力，因此可信 W 啟動仍必要。
不得用普通 Deny ACE 或 OWNER RIGHTS 名稱就宣告已防護。[Microsoft SID 定義](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-identifiers)
與 [default descriptor／rename 行為](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)
是此候選政策的依據；仍須 native 測試。

**Lock blocker：** `validate/append` 以 existing `r+b` 開檔，V 因而需要該檔案 RW；
V 在 OS 層能寫 lock bytes，只有可信 verifier 程式承諾不寫，不能稱 OS 完全唯讀。
既有 initialize 的 `a+b` 可使用 M 預建的 empty lock，且 root 此時只能有該 lock。
只要 lock 存在，其 protected DACL 可以限制 deletion。但若 M／故障移除它，
W 為 mkstemp 所需的 FILE_ADD_FILE 亦能建立同名檔案；不存在物件沒有 DACL 可限制。
因此「W 可在同目錄建 temp」與「missing lock 的任何 W OS recreation 皆拒絕」
尚不能同時成立。必須另行審查 namespace broker／layout 改設計或明確政策裁定；
本次不改 Store 或 inspector contract，也不將 API fail-closed 偷換成 OS denial。

## Runtime／trusted startup 相容性準備

優先評估仍在支援期的 **CPython 3.14 x64、一般 GIL build**，精確 patch、官方
發行物與 installed-byte hashes 尚未核定，不能部署。支援狀態須在實際批准時再次核對
[Python 版本生命週期](https://devguide.python.org/versions/)。本次只讀到開發環境 metadata：
Python 3.10.6、numpy 2.2.6、cryptography 50.0.2、cffi 2.1.1、pycparser 3.11；
這不是新 runtime 的相容性證據，也沒有安裝或升級套件。

Source inspection 顯示 `local_authorizer -> authorization_store/signed_authorization ->
planning_approval -> planning_evidence/window_planning -> temporal_anomaly`，需要現有
NumPy 與 cryptography，以及所選 wheel 的 transitive/native dependencies。
只拷貝四個 authorization Python 檔案不完整。這些模組的必要型別匯入不代表執行科學
分析；本次準備工具連這些模組都不匯入。SciPy/sklearn/matplotlib 是否需要應依實際
closure 審核，不能無差別拷貝整個 development venv。

後續另行批准的隔離 build/compatibility 階段須：

1. M 從獨立驗證的官方 runtime 與固定 wheel inventory 建立新 release；鎖定完整
   archives/installed files hashes、架構／ABI、原生 DLL closure。若現有 NumPy wheel
   不支援目標 Python，NO-GO；任何版本替換須另審，不在此 checkpoint 偷升級。
2. 採用 protected `python314._pth` 或等價 reviewed PyConfig，僅列固定 stdlib、
   app、deps；不含工作目錄／user site／外部 venv，不執行 `import site`、`.pth`、
   sitecustomize/usercustomize。先驗證所選 wheels 在該模式可載入；不能以開放 site
   搜尋路徑補救。[Python Windows path 設定](https://docs.python.org/3.13/using/windows.html#finding-modules)
   說明 `._pth` 的用途；它不保護 Python 本體或 OS loader。
3. 保護 Python EXE/DLL、stdlib、`.pyd`、dependencies、VC runtime、launcher、config、
   CWD、TEMP 與所有 DLL search locations。`-I -S -B` 不是 DLL 安全政策。
   launcher 的 LoadLibrary/DLL policy 必須單獨審查並觀察實際載入位置，依據
   [Windows DLL search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order)。
4. 在新 runtime 先做不生成 keys 的 import/strict V1 serialization、既有固定 golden
   verification 等經審核測試；逐項確認不觸發 fixture key generation 或科學運算。
   後續只有 G4 明確批准後，才可生成 ephemeral synthetic keys／初始化 synthetic Store。
   本次只測純 preparation 與既有唯讀 harness，沒有執行這些新 runtime 測試。

可信啟動器目前**未實作**。後續須由 M 從不受 A 控制的帳號/session 啟動，使用固定
absolute EXE、固定 launcher/config/pins、受控 env/CWD/import/DLL paths。啟動即驗證
實際 primary SID、elevation、groups/privileges，錯誤即結束；不得信任環境變數的 role
名稱。W 不接受 Agent 指定 Python／腳本／callback／plugin／私鑰／任意 paths；V
只接既有 exact intent digest 介面。Agent 可替換 launcher、改 argv/env/config、使用
W/M 憑證或控制可信互動 session 時，一律 NO-GO。`runas` 名稱本身不是 token 證據。

## 分階段批准、驗收與失敗處置

manifest 中的 op IDs 只是穩定記錄，**不是可依序執行的 script**。各 gate 須由研究者
透過獨立可信管道批准 exact SIDs、bytes/hashes、targets、before/after native SDDL、
測試操作與 containment；未知值或未展開 child mutation 不能批准。沒有一個 Agent
提供的 digest、名稱、路徑或 `approved` JSON 欄位會解除停用。

| Gate | 必須另行批准的實際操作與驗收 | GO／NO-GO |
| --- | --- | --- |
| G0 軟體契約 | 本次純 validation、確保十項 case NOT_RUN、所有信任旗標 false | 通過只表示程式契約，不能 GO 部署 |
| G1 principals | W/V 帳號及 M 核定；實際完整 primary token；A host/worker 分開盤點 | SID 相同、A 可控制 W/V/M、特權不明即 NO-GO |
| G2 namespace | 新 root/必要 child 逐一初建即限制；原生 resolved path/volume/file ID/owner/SDDL、無 reparse、RunId 未使用 | 任何既有未知 target、祖先 DELETE_CHILD/ownership 旁路或 root 身分不明即停止 |
| G3 runtime/origin | 新 runtime/deps/app、native DLL、launchers 與 inventories；independent origin 和 pin custody | hashes 匹配只是必要條件；啟動器／搜尋路徑未證實則 NO-GO |
| G4 synthetic Store | 單獨批准 memory-only 測試 key；M 以 public key 建 registry；預建 lock；W initialize；M seal history；再以實際 bytes 核定 anchors | 不得使用 real keys/data；lock namespace 衝突未裁定不能進入此階段 |
| G5 effective access/Store | 各角色原生 token 實測下列十項，含 temporary owner/ACL、並行、鎖及 revoked lineage | mock 或只列 DACL 不能 PASS；任一 deny/success 不符合預期即 NO-GO |
| G6 floor/pins | M 獨立完整驗證 Store 後產生／保留新 floor；更新 external checkpoint/config/bootstrap 與獨立持有 pin | 驗證程序沒有獨立快照發布 API，須另行審查協調；W/V 停止時發布、再完整核對後啟動 |
| G7 retirement | 單獨批准 exact disposable root 的封存及清理 | 重新核對所有身分並停止程序；無自動 retry／recursive cleanup；不碰 acceptance parent 的其他 runs |

後續 G5 需要保留每次操作的 native token、Win32 錯誤碼、handle rights、前後 file ID、
owner／SDDL 與 bytes identity；絕不記錄私鑰。十項預期結果（本次全為 NOT_RUN）：

1. A（包括每個 1001/1003 實際 token）對 protected code/anchors 的寫入、rename、replace 失敗。
2. A 的 WRITE_DAC/WRITE_OWNER 失敗；owner/SDDL 不變。
3. A 從所有相關祖先以 DELETE_CHILD、DELETE、rename/reparse 替換的旁路失敗；不能靠 child deny 掩蓋 parent allow。
4. W 執行批准的合成 initialize/compare-and-append；history/markers 正確，並行 writer/reader 互斥，stale head 被拒。
5. V 讀取完整 Store／anchors，existing lock `r+b` 與 locking 成功，不改 lock bytes；權限例外只限此檔。
6. V 對 history/head/checkpoints/registry/bootstrap/config 寫入、replace 失敗，diagnostics 權限不外溢。
7. A/W/V 刪除／替換現有 lock 失敗且 file ID 不變；M 在專門批准故障測試移除 lock 時，validate/append 回 lock_unavailable 且不修復；另行驗證 W OS recreation 需求，未解決即 FAIL／NO-GO。
8. W 的 mkstemp、marker os.replace 後 owner/繼承 ACE/OWNER RIGHTS 符合核定政策；W 改 ACL/owner 失敗；不能假設 target 舊 DACL 自動沿用。
9. 合成 approved 後追加合法 revoked，V 不回退舊批准；輸出仍不是 execution permission。
10. 在每個 history append → head replace → checkpoint replace 中斷點，以及 conflicting markers、缺 lock/registry/config/external floor 時 fail closed；較新 retained floor 拒絕較舊 chain。

既有 `_publish()` 使用 mkstemp + **os.replace**，不能引用 Windows ReplaceFile 的 ACL
保留語意代替實測；三檔發布不是多檔 transaction，失敗可能已部分持久化。
checkpoint 只是 lower bound；只保留舊 floor，不能偵測 floor 之後的所有 rollback，
更不能證明全域 latest head。獨立 floor 更新與 config/bootstrap pins 也是多檔問題。

所有失敗均停止 W/V，保留 exact synthetic assets、原始觀察與診斷，交 M 另行決定
recovery。不得自動 reset Store、刪 temporary files、降 floor、改 ACL、retry 或清理。
目前 blockers（lock namespace、完整 SID/token、M 與 A 分離、exact inventories/SDDL、
可信啟動、runtime compatibility、checkpoint custody、實際 OS 測試與獨立批准）均未解除。

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```
