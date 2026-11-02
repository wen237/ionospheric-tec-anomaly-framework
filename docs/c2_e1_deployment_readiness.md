# C2 E1 首次實驗部署準備（Checkpoint 3B-2C-2C-3）

日期：2026-11-02。研究者確認「VM 尚未確認；先以專用 VM 為首選規劃」。
**目前 NO_GO；本文件沒有授權 setup 或 E1 execution。** 本次只新增這份 runbook，
不新增 schema、validator、部署框架、native probe、collector 或 privileged launcher。
沿用已接受的 [C2 V1 規格與 18 組案例](c2_lock_acceptance.md)，不改其程式或資料契約。

## 1. 建議實驗目標與目前可知範圍

首選是**由研究者獨立管理的 Windows 11 x64 可犧牲 VM**，使用仍在支援期且合法授權
的 edition/build、local NTFS C:、一個固定 fresh RunId，沒有研究資料、Store 或私鑰。
優先使用既有可用且不受 Agent 管理的 hypervisor／遠端實驗主機；不要為本 checkpoint
在開發工作站安裝或啟用虛擬化功能。實際 guest build、hypervisor version、授權、資源、
映像來源與管理者仍未知，不能聲稱 VM 已準備好。

VM 的目的先是限制故障／破壞範圍。**同一個 Agent-controlled host 帳號管理的 VM，
不會自動成為可信 M 的邊界。** 若 A 能控制 VM console、磁碟、checkpoint、管理 API
或輸入研究者密碼的 host desktop，就可能讀取／操控 guest；單純 guest SID 不同不足。
Microsoft 明確將 compromised host 列為 virtualization 的威脅：
[Hyper-V host trust boundary](https://learn.microsoft.com/en-us/windows-server/security/guarded-fabric-shielded-vm/guarded-fabric-and-shielded-vms)。
本案不建立 shielded-VM/HGS 架構，先要求獨立可信的管理 host／console。

未來環境批准應限定：一個明確 VM ID、研究者管理的乾淨映像、無 domain／production
credentials、不掛工作站磁碟或 research shares；關閉 clipboard/drive/USB redirection
與 host filesystem sharing，guest 測試時無對外網路，除非另有明確批准的證據通道。
VMConnect enhanced session 會提供 clipboard／drive 等整合，因此不能忽略：
[VMConnect local resources](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/use-local-resources-virtual-machine-connection)。
乾淨 checkpoint／映像可留作重建新 run 的起點，但不得在驗收中還原同一 RunId、
保留舊證據卻使用舊 baseline；失敗後由研究者決定退休，不做自動 rollback。

本次 sandbox 可見的唯讀查詢：

| 查詢 | 實際結果 | 能支持的結論 |
| --- | --- | --- |
| Get-Command Get-VM | 找到 Hyper-V 模組命令 | 命令可見，不能證明有合適 VM 或可使用它 |
| Get-Service vmms | Status=Running | 服務可見且在執行，不能證明 Agent 與管理者分離 |
| Win32_OperatingSystem CIM query | HRESULT 0x80041003，拒絕存取 | OS 資訊 UNKNOWN；沒有提高權限或繞過此拒絕 |

沒有列舉 VM、讀取 VM 磁碟、改動 hypervisor、帳號或設定。這些 sandbox 觀察不能當
native host 的權限證據。研究者若有選定候選 VM，可在**獨立可信的 native host session**
手動執行以下唯讀命令，回報時只提供該 VM 的必要資訊：

```powershell
whoami /user
Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
Get-VM -Name '<researcher-selected-VM>' | Select-Object Name,Id,State,Generation,Version
```

上述命令不是建立 VM 的批准；不要在 Agent 可控制的 console 輸入管理憑證。
若 VM 不可用，**不自動改用目前原生工作站**。其額外風險包括真實個人／研究資料、
已登入 session、credential caches、Agent 同 SID 的 UI/process 控制，以及失敗後難以
完整退休帳號／ACL。使用工作站必須另審 full host capabilities、不同 M 管理 session、
資料隔離與復原計畫；目前沒有這些證據，所以工作站替代方案也 NO_GO。

## 2. 精確角色提案與可信啟動

不沿用開發 host RID 1001 或 sandbox RID 1003 作 W/V/M。新 guest 的完整 SIDs
只在後續批准建立／查核後填入既有 C2 specification，不預測或要求特定 RID。

| C2 role | 建議 guest principal | 限制／證據 |
| --- | --- | --- |
| A | E1_AHost、E1_AWorker，兩個專用 standard local users | 都填入 roles.A.sids；首次是乾淨 guest 中的實際測試 token，**不是**現有 Codex host/worker token 的認證 |
| W | E1_W，專用 standard local user | 不在 Administrators 或 VM 管理群組；不持有 M/V credentials，不使用研究者 host 身分 |
| V | E1_V，另一專用 standard local user | 與 W/A/M 不同 SID；授權資料唯讀，只有既有 lock RW 例外及 E1 control fixture 的測試權限 |
| M | E1_M，專用 guest 維護帳號 | 只由研究者控制，負責 setup、observer 與後續另批 fault injection；不執行 Agent/Codex |

hypervisor／證據保管者是 guest 以外的可信前提，不是塞入 roles.M 的另一個 host SID；
roles.M 必須是實際 guest M primary token。每個角色用不同、不重用的憑證；所有密碼
只交 Windows logon，由研究者透過可信 console 輸入，永不放 argv、環境變數、repo、
JSON、PowerShell history、named-pipe payload 或 Agent chat。

首次不做自訂 credential launcher：使用獨立 VM console 的 Windows logon／Switch User
進入 W 或 V session，以已保護的固定 executable 路徑啟動單一 native worker。保留其他
session 的 background process 供跨程序鎖測試，不能以 logout 提前殺掉 holder。
若 guest 不允許所需 session／process 存活方式，先停止設計，不解除系統限制來趕進度。
禁止 runas /savecred、Agent terminal 代輸密碼、共享 desktop 自動化或 user-writable shortcut。

worker 啟動後只做 identity/status 輸出並等待研究者，先不執行 mutation：

1. 自查當前 process primary token 與預期完整 SID/type、integrity/elevation；若有 thread
   impersonation、身分不符或未知狀態就退出，不能當 OS denial。
2. M observer 以 PID+creation-time 綁定的 process handle **獨立查詢**該 primary token，
   包含 groups、deny-only、restricting SIDs、privileges、AppContainer 與 session；與 worker
   自報值比對。完整 A token coverage 不由一個 PID 或 non-elevated 推論。
3. M 核對實際 image path、artifact identity／hash、process instance 與 baseline，研究者
   才在其可信 session 放行已批准的固定 case；每個 worker 只做一個有限 case 然後退出。

跨帳號 token 查詢是**尚未證實的可行性門檻**，不是「M 是 admin 所以一定可以」。
OpenProcessToken 受 process/token access 及跨帳號權限影響：
[OpenProcessToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocesstoken)。
既有 inspector 只要求 query rights，不能保證一定可讀別人的 token。若 M 無法獨立讀取
W/V，立即 UNKNOWN／NO_GO；不得只接受 W/V 自報，也不自動啟用 SeDebug、改 process
DACL、改用 SYSTEM/service 或授 broad rights。必要的 query-access／launch 修正須另審批准。

首次 guest A users 可先用 standard Medium token，避免把 Low-integrity 的拒絕誤稱 DACL
保護。現有 Agent 的 restricted／Low／Untrusted 或其他實際 token 變體仍未涵蓋，
不得宣告「所有 Agent capabilities 已驗證」。若要加入這些變體，逐項核定並量測，
不變更已接受的 C2 roles/schema。

## 3. 只需審查的最小實作，不再建立 framework

本次**不提供或執行**下列 mutating artifacts；它們是下一步各自需審查的工作項目。
不做 broker、generic task runner、JSON-to-SDDL converter 或任意 path/command API。

| 單一用途 artifact | 最小責任與 API／限制 | 當前狀態 |
| --- | --- | --- |
| 固定 run 的 setup 程式 | M only；只建核定 P/R/固定 children，以初始 restrictive security descriptor 建立；copy 精確 artifact inventory；CREATE_NEW 預建空 coordination lock 與合成 fixtures；按**人工獨立核定的 exact DACLs**配置，不自動翻譯 candidate masks | 未實作／未批准 |
| 小型 native probe executable | 建議單一 C/Win32 source，獨立可信 builder 編譯；無 Python/NumPy/cryptography 依賴。只有編入／核定的 root、store_id、SID、case、target 表；無任意 path、shell、callback、plugin、credential handling 或 cleanup | 未實作／未批准 |
| M native observer | 只讀取 selected process/token、opened-file identity/security/bytes metadata，接收並保留原始 case records；不能建立 fixtures、設定 ACL、寫 Store、執行 probe 或注入 fault | 未實作／跨帳號 query 未證實 |

setup 的安全要求是「初建即限制」，不是先繼承寬鬆 ACL 再慢慢修補。P 若已存在且
owner／DACL 不符，停止，不接管；P 以外的 global ancestor ACL 不修改。全部 W/V/A
都停止時完成 setup，M 以實際 handle 量測並核對 exact DACL、owner、volume/file IDs、
link count 與無 reparse，之後才啟動角色。失敗保留原地交 M，不遞迴刪除／重試。

probe 不需要執行任何 Python runtime 或授權模組。C2 layout 中 runtime/python.exe
仍須是**獨立核定的真實 CPython artifact**，或該 runtime case 就維持 NOT_RUN；
不可把 dummy bytes 命名為 python.exe 便宣稱 runtime 已部署。未來可經另批將精確
official runtime package 作唯讀測試資產複製到 R，不安裝 pip／科學依賴，不跑它。
native probe 與 observer 的 compiler/SDK、build flags、binary hashes、DLL inventory
也需核定；目前這些 artifact 與 builder 可用性未知，不能填入假的 release hashes。

native API 範圍應鎖定：

- 程序：OpenProcess(QUERY_LIMITED_INFORMATION)、OpenProcessToken(TOKEN_QUERY)、
  GetTokenInformation、GetProcessTimes、QueryFullProcessImageNameW；不 request VM_READ/WRITE、
  injection、token duplication 或 impersonation，不自行調 privilege。
- 檔案 baseline：OPEN_EXISTING + FILE_FLAG_OPEN_REPARSE_POINT，以 READ_CONTROL／
  READ_ATTRIBUTES 查 GetFinalPathNameByHandle、GetFileInformationByHandle(Ex)、volume info、
  owner/group/DACL、inheritance、mandatory label；hash 僅讀核定 synthetic/artifact files。
- case return：worker 每次 native call 後**先保存**原始 return/GetLastError，再做 logging；
  desired mask、disposition、sharing、flags、source/target、offset/length 都保留。
  不只記 Python exception，不以 error 5 一律歸因 DACL。
- lock：優先沿用 native CRT `_locking`，對應既有 msvcrt.locking 的 byte-range protocol，
  offset 0/length 1、非阻塞。先以 OPEN_EXISTING/no-follow handle 核對 identity/reparse，
  再經 `_open_osfhandle` 交給 CRT，審查 handle ownership、close/unlock 及錯誤記錄；
  不用會跟隨 reparse 的一般 path fopen 代替。CRT failure 保留 errno/_doserrno，
  GetLastError 只在該 API 有定義時解讀。若改測 LockFileEx，還需另證與既有 CRT 互通，
  不能只測新 API 自我互通就宣稱保留既有行為。

token integrity 與 file mandatory label 不能漏掉，MIC 可在 DACL 之前拒絕存取：
[MIC](https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control)。
查 LABEL_SECURITY_INFORMATION 的所需權限與讀完整 SACL 不同，不能為收集 label
自動加 ACCESS_SYSTEM_SECURITY／audit policy：
[SECURITY_INFORMATION query rights](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-information)。
原始 security descriptor 與轉成 SDDL 的視圖都保留；現有 inspector 只提供部分欄位，
不足以單獨當完整 per-operation collector，也不能把它的 point-in-time 檢查當 race-free open。

### 原始 records 與獨立 observer 的界線

最小可審查的收集通道可採**固定 RunId 的 local log-only pipe**，僅傳 case records，
不接收 path/command，也不回傳執行指令；不具 broker 或 signer 能力。pipe 名稱、
client/server SID DACL、remote rejection、first-instance／server identity、bounded messages
與 evidence sink 都必須在未來批准 inventory 中明列，現在不建立 pipe。
M 可透過 [GetNamedPipeClientProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)
取得實際 client PID，再從已開啟 process handle 查 SID/creation time，而不是信 payload。

raw API returns 仍是**受審 worker 內部量測並回報**；M 獨立量測的是 caller token、
process/binary identity、前後 file/security state 與接收來源。log-only pipe 並不能讓 M
獨立看到每個 kernel call，也不證明 A 無法干擾自己 SID 的程序。首輪僅針對乾淨 VM、
受控 workers 做 ACL 實驗，不能宣稱可抵抗 Agent 注入或完全惡意的 A 偽造 records。
若 review 要求獨立 kernel trace／對抗惡意 A 的證據，現有設計不足，維持 NO_GO；
額外 tracing driver、audit policy、process protection 或 privileged launcher 必須另批，
不得悄悄裝 Procmon/service 或用只讀 observer 名義擴張能力。

evidence sink 提議 `R\bootstrap\e1-observer.jsonl`，由 M 預建、M-only write，另列於
既有 bootstrap directory 的人工 asset inventory，不改 C2 V1 schema。它不是 W/V 可寫
的 control log，也不覆寫 manifest.json。M 在可信 host 另外保留 hashes／完整原始證據；
匯出目的地與方式另批，不讓 Agent 決定。observer 可讀 fixture content 作 pre/post hashes，
但 bytes-lock 持有期間只查 metadata，避免干擾鎖／sharing 結果。

## 4. 首次批准邊界與 18 組案例的順序

須分開批准，不能以「同意 C2」或「同意 R」涵蓋所有 Windows 系統變更：

| Gate | 可批准的具體範圍 | 不包含 |
| --- | --- | --- |
| E0 環境／身分 | 一個精確 VM ID／host 管理邊界、合法 guest 映像、五個 guest accounts、可信 console／build/artifact transfer；帳號與 hypervisor 的系統變更逐項列出 | 開發 workstation、其他 VM、真實資料、未列 registry/service/security-policy 更動 |
| S0 namespace setup | 固定 P 若需初建及單一 R、store_id、C2 exact layout、控制 source、真正 runtime/artifacts、M evidence sink、人工核定 owner/DACL 與空 lock | 任意 children、existing-path 覆寫、Store.initialize、金鑰、科學依賴安裝、既有 ACL 自動接管 |
| E1-first | 下表 F0/F1/F2 的有限 native operations、逐 bit OPEN_EXISTING 權限檢查、核定 data/control writes、雙向 cross-process locking、M evidence capture | delete/replace coordination lock、ancestor substitution、reparse/hardlink、missing-lock 注入、cleanup |
| E1-fault（另批） | 特定 fault family 的 exact targets/API/控制來源／預期錯誤，M-only quiescence 與處置 | 沿用舊批准做新測試、失敗後自動重建 lock 或 rollback |

批准與量測不能循環依賴：E0 尚未建立帳號時，核定的是 VM、帳號名稱、membership／
privilege 目標及憑證保管，SID 留 unknown；E0 完成後才獨立查出實際 SID，再核定 S0
的 exact ACLs。S0 對新資產的批准前提是「必須不存在」，不是捏造尚未分配的 file ID；
建立後由 M 量測實際 IDs/owner/DACL/hashes，**停在第二個 hold point**，由研究者獨立
核定並填入既有 C2 baselines，才能批准 E1-first。不能以程式第一次看見的 ID 自動信任。

所有 probe 的 filesystem mutations 僅限核定 R 內；P 初建、guest accounts、VM custody、
log-only pipe 與 M evidence export 是上表**另列**的非 R 邊界，不能藏在一般 E1 probe。
任何未核定 UUID、SID、SDDL、檔案 bytes/hash、pipe／log 路徑仍未知就不能批准 setup。
本文件沒有指定已核准的 UUID 或 VM，示例與 spec hash 均不是研究者授權。

| 順序 | 既有 case group | 首次可批准的部分與後續界線 |
| --- | --- | --- |
| F0-1 | native_primary_tokens | 第一關：M 必須獨立辨識全部實際 processes；查不到就停止，不做 mutation |
| F0-2 | handle_identity_and_no_follow | read-only baseline、actual handles/no-follow、file ID/link count/owner/DACL/label；與 approved inventory 一致 |
| F0-3 | runtime_anchor_read | W/V fixed artifact 開檔與來源核對；無 runtime execution。artifact 缺失則本組未完成，不用 dummy 代替 |
| 全程 | independent_evidence_and_stop | 從 F0 起啟用記錄／保管；需完成整輪 review 才能判定本組，不能預先 PASS |
| F1-1 | existing_lock_RW | W/V existing RW open，正常操作不寫 lock bytes；單檔 exception 明列 |
| F1-2 | cross_process_locking | W 持鎖/V conflict→release/V success，再反向；同 physical ID，時間有界，額度由批准 packet 定義 |
| F1-3 | writer_publication | 通過前述關卡後，W 在同一外部 lock 協調下建立固定 temp/flush/close/replace synthetic markers；不呼叫 Store API |
| F1-4 | owner_inheritance_after_replace | 每次 mutation 後立刻量測；非預期 owner/ACL 或隱含 WRITE_DAC 即停止 |
| F2 | individual_rights | 本輪只做逐 bit OPEN_EXISTING access requests，取得 handle 就 close；非預期 grant 立即 STOP，不進一步執行刪除或 setter |
| F2 子集 | verifier_data_unchanged | 支持 pre/post bytes 及 denied write-handle requests；完整 write/delete/replace attempts 尚未批准，不標整組 PASS |
| F2 子集 | ancestor_namespace、lock_parent_new_names | metadata 與 directory rights 的開檔檢查；真正 rename/substitution／CREATE_NEW 試探留待另批 |
| E1-fault | existing_lock_delete_replace | 全部正常 holder 結束、control source/DELETE 可用性已證實後，才可批准實際 namespace attempts |
| E1-fault | existing_lock_reparse | 單獨犧牲 run、精確 tag/API；允許或不可判讀即停止，不以 application rejection 記為 OS denial |
| E1-fault | hardlink_alias_outside_coordination | 單獨犧牲 run；允許建 alias 即記錄 link-count/shared-descriptor capability 並停止，不能隱藏結果 |
| E1-fault 最後 | M_quiesced_missing_lock_injection | M 確認所有 role process/handles 都已停止後，才移除指定 empty lock；故障注入有自己的批准 |
| 注入後 | missing_lock_existing_open | W/V file-not-found、沒有建立；這不是 ACL enforcement 證據 |
| 注入後 | missing_lock_name_recreation | native CREATE_NEW/copy/rename/hardlink insertion 的 direct denial；parent 與來源 controls 皆有效，缺 parent／分享衝突不可當 PASS |

子集成功不等於整個 case group 完成，更不等於全部 18 組完成。本次所有 group 均
保持 NOT_RUN。F2 的 access-handle denial 也不能取代後續實際 namespace-operation case。
不同 fault families 應分別批准 fresh RunId／baseline；不得為繼續下一組而 recreate
舊永久 lock 或還原同一 run。任何成功的非預期 mutation 都保留現場，不自動刪除／修復。

DELETE/replace denial 測試前必須排除正常 CRT handle 的 sharing restrictions 與 byte-range
lock：關閉所有相關 role handles，observer 讀 metadata 使用適當分享並及時關閉。
否則 ERROR_SHARING_VIOLATION／LOCK_VIOLATION 不是預期 ACL-denial 證據。
每次先保存 native error，再做紀錄；無法區分 DACL/MIC/sharing/缺檔原因就 UNKNOWN／STOP。

## 5. 最短 GO／NO-GO 清單

這是**分階段能否進入 E0、S0、E1-first 的清單**，不是解除 deployment flags 的開關：

- [ ] **可信實驗目標已具名**：獨立管理的 VM／host／console、合法 supported guest、
      無 research data／host shares；A 不可管理 VM、VHD、snapshots 或憑證輸入管道。
- [ ] **身分與啟動可行**：E0 先核定 names/membership／保管；完成後，S0 前填入 guest
      A/W/V/M 實際完整 SIDs，無沿用 host 1001 為 trusted role。E1-first 前證實 W/V 不提權、
      M 能獨立查 token、可信 session 不由 Agent 控制。
- [ ] **可審的 artifacts 已存在**：一次性固定 setup/probe/observer、可信 builder、
      runtime/code/DLL hashes 與人工核定 exact DACLs，沒有 generic runner、隱藏 credential path。
- [ ] **批准邊界已填實**：VM/account 的 E0 與固定 R 的 S0 分開，S0 前核定 absence／
      before/after policy／inventory，S0 後另核定 actual baselines；E1-first 前核定 control
      sources、pipe／sink／export、F0/F1/F2 操作清單與 bounded 時序。
- [ ] **證據能回答 OS／application 的差異**：M 獨立 token/metadata、worker-origin raw API
      records、positive controls、native errors、mandatory labels、pre/post identities 有保管鏈；
      若要求 kernel-independent trace／抵抗惡意 A，沒有相應批准能力就 NO_GO。
- [ ] **故障保持停用**：RW、reparse、hard-link、no-follow 仍是明列 blockers；first-run
      不順帶做 fault injection。失敗停止、保留、另批 retirement，不加 FullControl、不 retry。

目前 VM、完整 guest SIDs、跨帳號 observer、native artifacts、exact DACLs、批准 packet
及後續 fault evidence 皆未具備。既有 spec 的 10 個 blockers 不在此 checkpoint 移除；
RW lock 與 pathname separation 仍不足以證實防 reparse/hardlink。故結論維持 NO_GO。

## 6. 本次驗證範圍

沒有新程式碼，因此不新增對文件內容或既有實作逐行鏡像的測試。只重跑允許的現有
C2／部署準備／唯讀 inspector focused tests；不執行 key fixtures、Store/signature tests、
Framework A/B/C/D、Stage 2 或先前的 tempfile replacement experiments。唯讀 Hyper-V
命令可見性／服務狀態不是 VM availability 或實際 W/V/M acceptance 的證據。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_c2_lock_acceptance.py tests/workflow/test_windows_deployment_preparation.py tests/workflow/test_windows_isolation_acceptance.py -q -ra --tb=short -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pip check
git diff --check
```

實際觀察：focused tests **176 passed，0.73 秒，無 skip**；pip check 回報
`No broken requirements found.`。沒有測試或宣告 E1 已通過；本次 OS 可見性查詢的
拒絕／未知結果保留於第 1 節。diff 檢查另涵蓋本次未追蹤的新文件。

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
Deployment Decision: NO_GO
```
