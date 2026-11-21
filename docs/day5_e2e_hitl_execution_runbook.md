# E2E-02B: researcher-controlled execution preparation

Preparation date: 2026-11-18 (Asia/Taipei). **Every workflow command below is
PROPOSED / NOT EXECUTED.** This document and the [blank handoff template](day5_e2e_hitl_handoff_template.json)
prepare a future review; they record no new scientific run, selection or approval.
Stop now at **E2E Execution Preparation Review**. Actual execution requires
separate researcher approval. Run individual approved sections in order; never
combine this runbook into a script, pipeline, scheduler or autonomous executor.

## 1. Choose the demonstration and establish prerequisites

| Classification | What the new record may claim |
| --- | --- |
| `evidence_handoff_replay` | New approved Agent calls and present human review of existing temporal/D/EPZ evidence. No fresh D/EPZ computation and no retroactive authorization of earlier D runs. |
| `continuous_scoped` | New request intent, fresh A/temporal review, live Pre, subsequent human selection and separate execution approval, fresh researcher-local D, fresh EPZ, live Post and final human review, in that order. Historical B+C remains explicitly reused. |

Fix the classification and its UTC timestamp **before the first live call**.
Neither class establishes raw-observation-to-final-result reprocessing. Original
historical NPY timestamps/interpolation quality and raw-source custody are not
established by a saved summary. Never describe independent historical Pre/Post
runs as this new continuous workflow or reuse their run IDs as new stage IDs.

The researcher must choose/provide these prerequisites; preparation did not open
recorded external source paths or verify their accessibility:

- The reviewed current checkout, an existing working `.venv`, scientific
  dependencies in `requirements.txt`, and the optional live SDK specified by
  `requirements-agent.txt`. Previous records used Python 3.10.6; confirm the
  actual environment and save its versions. No dependency installation is part
  of this preparation. The comparison wrapper disables Cartopy boundaries and
  needs no boundary download.
- For a continuous run, the existing **2022 Modern daily NPZ inputs** covering
  May 7 through June 21 inclusive: 15 reference days before the May 22 analysis
  start, then the full analysis period. Use the owning day's 00-23 UTC maps;
  existing adapters exclude the extra 25th map. Do not change grids or polarity.
- The saved B+C summary produced from the researcher's **original 1999-2021
  historical TEC** and verified catalog pathway. Record its identity/hash and
  reuse. No replacement dataset, new 23-year GIM download, reconstruction or
  synthetic input is permitted. Missing files mean STOP for supplied/mounted
  original inputs, not substitution.
- For replay, the already bound MVP-01 bundle, both selections, complete A/B
  comparison and reviewed EPZ diagnostic under their existing evidence root.
  Raw GIM/historical TEC need not be reopened for saved-evidence validation.
- A researcher-selected OpenAI model and separate approval for **one Pre and one
  Post evaluation**, their permitted evidence sharing and cost scope. Configure
  credentials privately outside this record. Do not print a key, inspect secret
  files, dump environment variables or put credentials in commands/artifacts.
- Review of the execution profile and its applicable prerequisites in section
  1.1 before D execution. A JSON decision, hash, successful process or this runbook
  does not authenticate a human or prove isolation. Codex, the Agent and Stage 2
  receive no authority to execute D.

### 1.1. Execution profiles and E2E-03 policy clarification

**Policy revision: 2026-11-19. Researcher review required before application.**
This revision replaces the blanket independent local-security prerequisite above
with the two profiles below. It changes documentation only: no active approval,
STOP, security flag or scientific execution status changes automatically.

**Researcher-Personal Local Scientific Execution**
(`researcher_personal_local_scientific_execution`) is a single-researcher MVP
profile in which the researcher personally invokes the reviewed scientific
entry point on their declared local machine. Require all of the following:

1. An explicit researcher decision approving this profile and the exact run.
2. Fixed reviewed experiment scope, A/B selection and Plan artifact pins, UTC
   windows, scientific parameters and original source references.
3. Validated actual Python environment/dependency versions and scientific input
   structure, canonical grid compatibility, UTC coverage and current source
   hashes. Review missing-data limitations under the existing algorithms;
   acceptance does not mean every input is finite or every detector sample valid.
4. A fresh approved output destination outside inputs, selections and the parent
   review bundle, with existing no-overwrite/source-recheck safeguards retained.
5. Manual local execution by the researcher, with no delegation to Codex, the
   Scientific Agent, Stage 2, a scheduler or another automated executor.
6. Reproducible records of the actual command, declared operator/machine,
   interpreter/dependencies, start/end UTC, immediate exit code, input/code pins,
   output hashes and validation, retaining partial failures without automatic retry.
7. Researcher review of all remaining conditions and a separate explicit decision
   before execution. Missing required scientific/runtime evidence means STOP.

This profile does not require a multi-user identity platform, independent human
authentication or implementation/acceptance of a controlled-runner Windows
isolation platform. Researcher identity and local-condition declarations remain
self-attestation. Windows Local Isolation and Trusted Human Authorization remain
NOT VERIFIED; `execution_eligible=false` remains the protected-execution state.
The separate manual decision records manual scope; these flags are not a manual
readiness verdict or permission for any Agent. Separate Pre/Post model approvals
and all scientific, source-integrity and output requirements still apply.

**Agent-Controlled Protected Execution** retains all existing strict requirements:
independent trusted human authorization, accepted Windows isolation and separate
principals, protected code/input and signer/registry/Store custody, current
revocation/expiry/trusted-time checks and revalidation at the protected execution
boundary. See [future runner responsibilities](local_authorization.md#future-runner-responsibilities-and-scientific-limits)
and [Windows acceptance](windows_isolation_acceptance.md). These prerequisites
remain unresolved; Agent-controlled D remains prohibited. The manual profile
provides no approval flag, fallback or bypass for this future execution model.

**Active-run adoption STOP:** before applying this revision to
`afghanistan_e2e_hitl_01`, the researcher must review the policy change and the
focused prerequisite findings, including NaNs and the full-target-hour ratio
denominators. In a separately authorized record update, document explicit profile
acceptance, actual recording UTC, the reviewed Runbook version/hash, exact approved
scope/Plan/selection pins and the disposition of remaining conditions. Distinguish
requirements outside this profile from verified evidence; never relabel unverified
isolation or identity as verified. Earlier approval does not imply adoption of
this revision. Retain the current execution STOP until that review and decision
are recorded; this documentation edit neither updates the handoff nor releases it.

The fixed case is `afghanistan_2022`, event `us7000hj3u`, origin
`2022-06-21T20:54:34Z`, M6.0, epicenter `(33.020,69.464)`, depth 4 km. Scientific
input coordinates remain `(33.02,69.46)`; their nearest sample is `(32.5,70)`.
Do not substitute historical filename coordinates `(33.092,69.514)`.
All windows below are inclusive UTC hours; the analysis is retrospective and
extends through the event date. This is not a prospective prediction test.

## 2. Create the future local record and review the request

Use a new ASCII run ID, independent of the constant case ID. Replace the angle
bracket placeholders manually; they are intentionally unusable defaults.

```powershell
# PROPOSED / NOT EXECUTED — researcher setup after preparation approval
$Py = (Resolve-Path -LiteralPath '.venv/Scripts/python.exe').Path
$RunId = '<new unique ASCII workflow ID>'
$RunClass = '<continuous_scoped or evidence_handoff_replay>'
if ($RunId -notmatch '^[A-Za-z][A-Za-z0-9_-]{0,63}$') { throw 'Choose a new valid run ID.' }
if ($RunClass -notin @('continuous_scoped', 'evidence_handoff_replay')) { throw 'Choose the run classification.' }
$RunRoot = Join-Path 'outputs' $RunId
if (Test-Path -LiteralPath $RunRoot) { throw 'Use a fresh run root; do not overwrite.' }
New-Item -ItemType Directory -Path $RunRoot -ErrorAction Stop | Out-Null
$Handoff = Join-Path $RunRoot 'handoff_record.json'
Copy-Item -LiteralPath 'docs/day5_e2e_hitl_handoff_template.json' -Destination $Handoff -ErrorAction Stop
(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
```

Edit **only the new local copy**, preserving the repository template. Set
`is_template=false`, the new ID, classification, its fixed-at time, actual creation
time, declared researcher identity and research intent. Leave future decisions,
successes, model results and timestamps null/pending. A state of `unknown` is not
a failed check; `not_yet_executed` is not completion. Record actual failures and
rejections explicitly; use `completed_and_verified` only with evidence of checks.

For artifact references, `workflow_root` identifies this new root;
`evidence_root` identifies the bound evidence location; `approved_external_input`
uses an opaque input identity with a private local path mapping. Record lowercase
SHA-256 and exact byte size, not display-rounded sizes. Empty arrays/null fields
in the template mean not yet recorded. Every human declaration remains
unauthenticated. Do not turn the template's `execution_eligible=false` into a
credential or permission for an Agent.

For continuous execution, bind the researcher-supplied input locations and
enumerate the fixed 46 expected filenames, without downloading anything:

```powershell
# PROPOSED / NOT EXECUTED — continuous_scoped only
$EvidenceRoot = $RunRoot
$ModernDataDir = '<researcher-supplied existing Modern NPZ directory>'
$HistoricalBcSummary = '<researcher-supplied original-TEC-derived B+C summary>'
$ModernFiles = @(for ($Day = [datetime]'2022-05-07'; $Day -le [datetime]'2022-06-21'; $Day = $Day.AddDays(1)) {
    Join-Path $ModernDataDir ('codg{0:000}0.{1:00}i.npz' -f $Day.DayOfYear, ($Day.Year % 100))
})
$ModernFiles
$ReviewBundle = Join-Path $EvidenceRoot 'afghanistan_mvp01_review'
```

Review the explicit list, accessibility and approved input identities; record
each file's pin and the historical summary's pin in `scientific_request`.
Do not infer readiness just from 46 filenames existing.

For replay, use this alternative binding block and skip the continuous input
setup above. It identifies existing evidence and creates no selection or output:

```powershell
# PROPOSED / NOT EXECUTED — evidence_handoff_replay only
$EvidenceRoot = '<approved existing evidence root, retaining its original bindings>'
$ReviewBundle = Join-Path $EvidenceRoot 'afghanistan_mvp01_review'
$ComparisonDir = Join-Path $EvidenceRoot 'afghanistan_mvp02b_comparison'
$SelectionA = Join-Path $EvidenceRoot 'afghanistan_mvp02b_selections/experiment_a_reference_120h/selection_record.json'
$SelectionB = Join-Path $EvidenceRoot 'afghanistan_mvp02b_selections/experiment_b_candidate_144h/selection_record.json'
$EpzRelative = '<approved existing EPZ JSON identity relative to evidence root>'
$EpzPath = Join-Path $EvidenceRoot $EpzRelative
```

For replay, copy historical input identities/pins as **saved declarations**;
do not claim the external raw sources were rehashed. Pin the actual saved bundle
files separately. Agent output directories must be fresh for this new run.

Review the fixed request **before** temporal computation:

```powershell
# PROPOSED / NOT EXECUTED — preview metadata only, no detector or model call
$RequestIntent = Join-Path $RunRoot 'scientific_request_intent.json'
@'
import json
from examples.review_afghanistan_mvp import build_request
print(json.dumps(build_request([0, 1]), sort_keys=True, indent=2))
'@ | & $Py -B - | Out-File -LiteralPath $RequestIntent -Encoding utf8 -NoClobber
```

Review and pin that preview; record the actual scientific question/intent in the
handoff, reviewer/time and event/parameter confirmation. Anchor IDs `[0,1]` mean
anchors to consider, **not** windows approved for execution. The existing example
constructs this request internally; there is no `--request` CLI. It later adds
measured provenance and exports `scientific_request.json`. Pin the preview and
final artifact separately, and compare scientific fields, resource IDs and event
identity; provenance is populated by the host, not guessed in the preview.
The minimal request event omits magnitude/coordinates/depth; confirm those against
the fixed confirmed-event record and the handoff's expected case contract.

The same preview may document a replay's new intent. Set `$EvidenceRoot` to the
existing approved source root for replay; the old canonical request is then
**reused evidence**, not a newly computed request artifact. Do not change the
classification after a live call.

To measure any artifact's bytes, use the following only on an explicitly approved
file. Measurements identify bytes; they are not human approval:

```powershell
# PROPOSED / NOT EXECUTED — repeat manually for each approved artifact
$ArtifactPath = '<explicit approved existing file>'
(Get-FileHash -LiteralPath $ArtifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
(Get-Item -LiteralPath $ArtifactPath).Length
```

## 3. Temporal review and evidence validation

**Continuous only:** record actual start/end UTC and exit result, and generate a
fresh bundle using existing Framework A with saved B+C context:

```powershell
# PROPOSED / NOT EXECUTED — continuous_scoped; computes A, does not recompute B/C
& $Py -B -m examples.review_afghanistan_mvp --modern-files $ModernFiles --historical-summary $HistoricalBcSummary --cluster-ids 0 1 --output-dir $ReviewBundle
```

Read all six generated files: `scientific_request.json`, `temporal_evidence.json`,
`historical_context.json`, `window_proposal.json`, `review_note.md` and
`run_record.json`. The final record must exist and its five child pins must match.
Complete the matching template references and `source_origin=fresh_computation`;
identify historical context as reused. Record actual environment/code/input pins
from the bundle and confirm the final request against the reviewed intent.

The non-selecting inspector validates the bundle and inventories target/reference
source files without computing A/D or creating a selection:

```powershell
# PROPOSED / NOT EXECUTED — continuous_scoped, approved access to real local inputs
$ReadinessPath = Join-Path $RunRoot 'temporal_handoff_inspection.json'
& $Py -B -m examples.select_afghanistan_mvp_window --review-bundle $ReviewBundle --modern-data-dir $ModernDataDir --inspect | Out-File -LiteralPath $ReadinessPath -Encoding utf8 -NoClobber
```

Require matching original source identities/hashes, complete target/reference
coverage and `source_integrity_ready`; note that this inspector does not validate
NPZ numerical contents. Pin this inspection as `temporal_review.validation_record`.
Missing, ambiguous or altered inputs and proposal abstention mean STOP for review.

**Replay:** point `$ReviewBundle` to the existing bundle; reuse its exact files
and pins, set `source_origin=reused_saved_evidence`, and record this run's review
times separately from unknown/historical generation times. Do not invoke the
temporal generator or raw-input inspector for a saved-only replay. For either
classification, require this existing read-only snapshot validation before Pre:

```powershell
# PROPOSED / NOT EXECUTED — existing saved-evidence validator; no scientific runner
@'
import sys
from src.agent.scientific_evidence_tools import EvidenceTools
e = EvidenceTools(sys.argv[1], "pre_spatial")
assert e.status == dict(temporal_historical="validated_snapshot")
assert len(e.sources) == 6
e.recheck()
print(e.status)
'@ | & $Py -B - $EvidenceRoot
```

Review the actual anchor-based daily expansion policy: at least one valid
target-polarity hour, no opposite-polarity hours, all 24 hours present/classifiable,
consecutive days expanded from the historical anchor. June 2's one negative hour
is sufficient under that rule. Preserve its 144-hour candidate; do not truncate
it to match the separate 120-hour historical reference or infer bounds from an
anchor alone. The wrapper cannot support an arbitrary different case by merely
editing metadata.

## 4. One separately approved live Pre-Spatial evaluation

**STOP for model/cost/evidence-sharing approval first.** Fill
`pre_spatial_agent.run_approval` with the researcher's actual decision, identity,
time and explicit model/cost/sharing scope. Rejection or more-evidence request
stops the sequence. Select a currently approved model; no fallback is implied.

```powershell
# PROPOSED / NOT EXECUTED — one researcher-approved live evaluation only
$PreModel = '<researcher-approved OpenAI model identifier>'
$PreQuestion = 'Which temporal candidates merit spatial follow-up, and what inspected evidence and uncertainties support that recommendation? Use only temporal and historical evidence.'
$PreOutput = Join-Path $RunRoot 'agent_pre'
& $Py -B -m examples.run_afghanistan_mvp_agent --live --mode pre_spatial --model $PreModel --evidence-root $EvidenceRoot --question $PreQuestion --output-dir $PreOutput
```

Record exact sanitized argv, actual start/end UTC and process exit result as they
occur. Pin all five outputs: `agent_request.json`, `agent_trace.json`,
`scientific_assessment.json`, `scientific_assessment.md`, `run_record.json`.
Populate requested provider/model, returned model IDs from trace, status/outcome,
flags and source validation, retaining SDK/configuration/code/usage in pinned
artifacts. No historical Agent run may stand in for these new calls.

Require actual live response IDs/usage and successful model-selected retrievals,
exact-value fact grounding and intact six-source Pre isolation. Inspect the
candidate rule, limitations and semantic support of citations, not just pointer
existence. Do not supply later selections, D or EPZ through the question.
**Exit code zero only means the CLI finished:** it can save a rejected/abstained
assessment. Invalid/flagged results, missing evidence or integrity failure mean
preserve the output and STOP; never silently repeat a billable evaluation.
`submitted_for_researcher_review` is not scientific approval.

## 5. Researcher decision, then the two explicit selections

Only after reviewing that exact new Pre assessment, complete `human_selection`:
pin the reviewed assessment, proposal and temporal run record; record
`approve`, `reject` or `request_more_evidence`, actual UTC time, reviewer and own
scientific rationale. Preserve disagreement with the Agent and explain any
departure. An Agent recommendation never authorizes execution.

For the **continuous fixed A/B scope**, only an explicit human choice of both
following experiments permits these selection-record commands. Independent A is
the historical **Vision Model and Selected Window Rule** reference, not a daily
candidate. B is the saved eligible Cluster 1 daily-policy candidate. Supply
nonempty, researcher-written rationales and record exact inclusive bounds:

```powershell
# PROPOSED / NOT EXECUTED — after actual Pre review and explicit human choice
$SelectionRoot = Join-Path $EvidenceRoot 'afghanistan_mvp02b_selections'
$SelectionADir = Join-Path $SelectionRoot 'experiment_a_reference_120h'
$SelectionBDir = Join-Path $SelectionRoot 'experiment_b_candidate_144h'
$ReferenceRationale = '<researcher rationale for the independent reference>'
$CandidateRationale = '<researcher rationale for the Cluster 1 comparison>'
& $Py -B -m examples.select_afghanistan_mvp_window --review-bundle $ReviewBundle --modern-data-dir $ModernDataDir --start-utc 2022-05-28T00:00:00Z --end-utc 2022-06-01T23:00:00Z --justification $ReferenceRationale --output-dir $SelectionADir
& $Py -B -m examples.select_afghanistan_mvp_window --review-bundle $ReviewBundle --modern-data-dir $ModernDataDir --cluster-id 1 --justification $CandidateRationale --output-dir $SelectionBDir
$SelectionA = Join-Path $SelectionADir 'selection_record.json'
$SelectionB = Join-Path $SelectionBDir 'selection_record.json'
```

Review and pin each record immediately after its command before proceeding to
the next step. A is May 28 00:00-June 1 23:00, **120 hours**; B is May 28 00:00-
June 2 23:00, **144 hours**. Record A's independent basis and B's cluster/report
pointer with exact pins. If B is ineligible, the researcher rejects the comparison,
chooses Cluster 0, or changes bounds, STOP: the fixed D wrapper rejects that scope.
Do not alter the planner, saved selections or thresholds to make it proceed.

For **replay**, create no replacement selection records. Pin/review the existing
A/B selections and record present human ratification/rejection after the new Pre
assessment, explicitly distinguished from the original decisions. Earlier D
execution cannot have been authorized by this new assessment or ratification.

## 6. Inspect the plan, then STOP before researcher-local D

**Continuous only:** the plan checks actual input pins and selection contracts,
and performs no D computation. Keep its destination directory nonexistent:

```powershell
# PROPOSED / NOT EXECUTED — plan only, with separately approved local input access
$ComparisonDir = Join-Path $EvidenceRoot 'afghanistan_mvp02b_comparison'
$PlanReview = Join-Path $RunRoot 'framework_d_plan_review.json'
& $Py -B -m examples.compare_afghanistan_mvp_spatial plan --selection-a $SelectionA --selection-b $SelectionB --review-bundle $ReviewBundle --modern-data-dir $ModernDataDir --output-dir $ComparisonDir | Out-File -LiteralPath $PlanReview -Encoding utf8 -NoClobber
```

Record `framework_d.authorization.plan_command`, the reviewed plan pin and actual
review time. Require A/B selection and parent pins, exact UTC windows/durations,
15 reference days, `k=3.0`, common canonical 71x73 grid/ascending latitude, original
source integrity and an approved fresh output location. Captured stdout may have
PowerShell BOM/line endings; pin its actual bytes, read it as UTF-8 and compare
plan **content** with the later program-written `comparison_plan.json`. Do not
rewrite either artifact to force byte equality. Program-generated source files
retain their own original bytes and internal bindings.

**MANDATORY HUMAN STOP:** first complete the profile review/adoption required by
section 1.1. Record a separate `framework_d.authorization.execution_decision`,
reviewer/time, rationale, approved execution profile/scope, exact A/B selection
pins, reviewed Plan pin and evidence for that profile's applicable prerequisites.
Unresolved mandatory prerequisites or a decision other than approve mean STOP.
For the manual profile, independent authentication and controlled-runner isolation
remain unverified and outside its requirements; retain the security flags above.
Neither plan success nor a declaration in this JSON authenticates authorization.
No script, Agent, Codex action, Stage 2 call or approval flag triggers execution.

**Only the researcher, on their own approved local machine, may manually issue
this standalone command after the separate approval.** It is deliberately not
chained to planning, an `if` approval branch, another stage or an executor:

```powershell
# PROPOSED / NOT EXECUTED — record actual UTC immediately before the manual D command
$DStartedAtUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
```

```powershell
# PROPOSED / NOT EXECUTED — RESEARCHER-ONLY manual command after the STOP gate
& $Py -B -m examples.compare_afghanistan_mvp_spatial run --selection-a $SelectionA --selection-b $SelectionB --review-bundle $ReviewBundle --modern-data-dir $ModernDataDir --output-dir $ComparisonDir
```

```powershell
# PROPOSED / NOT EXECUTED — immediately after that command, before other native commands
$DExitCode = $LASTEXITCODE
$DEndedAtUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$DStartedAtUtc
$DEndedAtUtc
$DExitCode
```

Record the real sanitized command, declared local operator/machine, start/end UTC,
immediate native `$LASTEXITCODE` and execution result/failure. Do not substitute
an equivalent reconstructed command for an unknown actual invocation. Hash/source
checks before/after D are already in the wrapper. A final `comparison_summary.json`
and all declared child artifacts are required; a partial directory is retained
as failure evidence. No overwrite, cleanup, resume or automatic retry is provided.
Directory location/extra entries are part of input inventories: do not move data,
add files there, or rewrite parent bindings between selection, plan and execution.

For **replay**, skip both plan and run commands. Set D's `source_origin` to
`reused_saved_evidence`; mark the new execution/authorization stages
`not_applicable`, leave actual execution/approval fields null, and pin the saved
comparison/outputs. Historical operator/time details stay unknown if unavailable.
The new record documents present validation, not new or retroactively approved D.

For either class, inventory every comparison artifact (including selections,
statuses, experiment summaries, arrays, differences and images), record relative
identities/hash/sizes in `framework_d.output_artifacts`, and validate the saved
handoff through the existing read-only loader:

```powershell
# PROPOSED / NOT EXECUTED — saved-result consistency validation only
@'
import sys
from src.agent.scientific_evidence_tools import EvidenceTools
e = EvidenceTools(sys.argv[1], "post_spatial")
assert e.status == dict(temporal_historical="validated_snapshot", spatial="validated_snapshot")
assert len(e.sources) == 23
e.recheck()
print(e.status)
'@ | & $Py -B - $EvidenceRoot
```

Capture/pin the check result in the handoff, including actual operator/time and
whether the source was fresh/reused. This checks saved shapes, counts/ratios,
selection copies, parents and B-minus-A consistency; it is not a new D execution
or proof of original raw observation quality. Preserve A's fixed reference checks:
120 hours, 5,183 finite cells, positive maximum 10% at `(-22.5,-155)` and
`(-22.5,-150)`, negative maximum 85% at `(30,70)`. Report mismatches without tuning
references. B's longer denominator is not required to reproduce A's percentages.

## 7. EPZ diagnostic, independent review and host binding

**Continuous only:** after D validation and approval of this offline diagnostic
stage, use a fresh output file outside the fixed source directories:

```powershell
# PROPOSED / NOT EXECUTED — continuous_scoped; offline EPZ generation, no D/LLM
$EpzRelative = 'afghanistan_epz_diagnostic/diagnostic.json'
$EpzPath = Join-Path $EvidenceRoot $EpzRelative
& $Py -B -m examples.diagnose_afghanistan_epicentral_zone --evidence-root $EvidenceRoot --output $EpzPath
```

Record new generation times, source comparison pin and `source_origin=fresh_computation`.
For replay, skip generation, bind the already accepted report at its existing
relative identity and record `source_origin=reused_saved_evidence`. Do not move
old bundles or edit their absolute parent bindings to manufacture a new run.

Review the diagnostic against the exact A/B comparison, its 23-artifact source
map and accepted V1 convention: `R=10**(0.43*M)`, saved M6.0, radius
380.1893963205613 km, sphere 6371.0088 km, inclusive great-circle **grid-center**
membership with zero tolerance, common canonical mask and original 120/144
denominators. Record the scientific convention/reviewer/time in the handoff.
Historical generator fingerprints are provenance, not requirements that current
reader bytes match old code. Do not alter the diagnostic's historical
`researcher_review=pending` / `agent_integration=not_authorized` fields; present
review is recorded separately.

Measure candidate pins, then **STOP for independent researcher review**:

```powershell
# PROPOSED / NOT EXECUTED — measurements only; these do not constitute approval
(Get-FileHash -LiteralPath $EpzPath -Algorithm SHA256).Hash.ToLowerInvariant()
(Get-Item -LiteralPath $EpzPath).Length
```

The researcher must review the artifact and its source/scientific consistency,
then record its specific approved identity/SHA-256/size, reviewer/time/rationale
and pin-review status in the handoff's EPZ block, separately from checksum
measurement. An optional separate review note may be pinned in
`reviewed_pin_record`; otherwise leave that optional reference null. Obtain the
approved values from this actual human review. **Do not automatically assign a
self-computed hash to approval**, and never reuse an old report's hash/byte size
for a fresh diagnostic simply because scientific numbers look similar.

After that review, enter the approved values manually and validate the binding
without a model call or diagnostic regeneration:

```powershell
# PROPOSED / NOT EXECUTED — enter pins from the separately reviewed record
$ApprovedEpzSha256 = '<independently reviewed lowercase SHA-256>'
$ApprovedEpzSizeBytes = [long]::Parse('<independently reviewed exact byte size>')
@'
import sys
from src.agent.scientific_evidence_tools import EvidenceTools
e = EvidenceTools(sys.argv[1], "post_spatial", epz_diagnostic=sys.argv[2],
                  epz_sha256=sys.argv[3], epz_size_bytes=int(sys.argv[4]))
assert e.status.get("epz_diagnostic") == "validated_snapshot"
assert len(e.tool_definitions()) == 9
e.recheck()
print(e.status)
'@ | & $Py -B - $EvidenceRoot $EpzRelative $ApprovedEpzSha256 $ApprovedEpzSizeBytes
```

Pin/capture the validation result and complete `diagnostic_validation_status` and
`pin_review_status` only after inspecting the result. A missing, stale, corrupt,
changed or mismatched report is rejected without repair. Record the exact same
artifact/pins in `post_spatial_agent.bound_epz_diagnostic`.

## 8. One separately approved live Post-Spatial evaluation

**STOP for the Post model/cost/sharing decision.** A Post run without a validated
EPZ binding offers only eight evidence tools and does not meet this demonstration's
EPZ requirement. A validated pinned binding permits the ninth; tool availability
alone does not prove the model used it.

```powershell
# PROPOSED / NOT EXECUTED — one separately researcher-approved live evaluation
$PostModel = '<researcher-approved OpenAI model identifier>'
$PostQuestion = 'Retrieve and cite the bound EPZ diagnostic. Distinguish global peaks, the nearest epicentral sample and included EPZ centers. Compare per-center counts, original denominators and signed experiment differences. State missing evidence and uncertainties before any physical interpretation.'
$PostOutput = Join-Path $RunRoot 'agent_post'
& $Py -B -m examples.run_afghanistan_mvp_agent --live --mode post_spatial --model $PostModel --evidence-root $EvidenceRoot --epz-diagnostic $EpzRelative --epz-sha256 $ApprovedEpzSha256 --epz-size-bytes $ApprovedEpzSizeBytes --question $PostQuestion --output-dir $PostOutput
```

Record actual command/times/exit result and pin all five Agent artifacts. Record
provider/requested and returned model IDs, exact configuration/code/usage,
assessment status/outcome and flags; verify `run_record.json.epz_binding` and its
diagnostic source snapshot against the approved pins. Source-root identity is
host-bound; the model supplies no path, radius, selection or execution arguments.

Inspect `agent_trace.json` for an actual model-selected
`get_epz_diagnostic_summary({})` call with `result.ok=true`. Record its
`result_id`, `call_id` and response ID. Require the final assessment to cite
successful EPZ result data through real JSON Pointers and **exact JSON values**,
including original integer-versus-float values and full saved precision. Record
citations as `{result_id,pointer}` entries. A source hash or invented pointer is
not a scientific fact. Check that the model also inspects the nearest epicentral
sample through the existing cell lookup, rather than confusing a global peak or
the diagnostic's closest-to-boundary center with that sample.

If EPZ retrieval/citation is omitted, a claim lacks semantic support, assessment
validation fails or evidence changes, preserve every output and STOP for human
review. Do not manually inject findings, repair a submission, auto-approve it or
silently run another billable evaluation. An approved later attempt requires its
own explicit scope and fresh output location, with the failed attempt retained.

## 9. Final researcher scientific review and preservation

The researcher must verify these conditions against actual artifacts, not the
template's expectations or historic model outputs:

- Same event, scientific parameters, source identities and classification
  throughout; real chronological request -> temporal review -> live Pre -> human
  choice -> separate approval -> local D -> EPZ -> live Post -> final review for
  `continuous_scoped`. Selection and approval occur after Pre, not backdated.
- Separate 120/144-hour selection bases, correct daily expansion and preserved
  UTC boundaries; exact selected parameters/inputs agree with plan and execution.
- D was executed only by the researcher on the independently approved local
  machine; saved `executed` labels alone do not establish operator presence.
- Original source and output pins match; Pre is isolated; actual live response
  evidence exists; EPZ retrieval and exact citations are present and valid.
- Distinguish global maximum from nearest epicentral sample; both from all EPZ
  centers. Historical negative peak `(30,70)` and nearest sample `(32.5,70)` are
  distinct. Verify the actual new saved evidence before attributing any result.
- Preserve occurrence counts versus percentages, full target-hour denominators,
  null effective detector-valid counts and availability caveats. B-minus-A
  ratios use **percentage points**. Increased counts and decreased percentages
  can coexist with a longer denominator; this is not a seismic-association score.
- EPZ center membership is descriptive geometry, distinct from the historical
  paper's visual grid-cell overlap. Three coarse, spatially correlated centers
  do not measure physical areal coverage or significance; grid-hour sums are
  not unique anomaly hours and regional means are unweighted.
- Kp, Dst, F10.7, upstream quality, original interpolation history, controls and
  mechanism evidence remain explicit gaps unless separately approved evidence
  actually exists. Spatial coincidence establishes no causality, precursor or
  predictive performance. Exact citation validity does not prove an inference.

Complete `final_researcher_review` with `accepted`, `rejected` or
`needs_additional_evidence`, scientific justification, verified/unverified claims,
limitations, exact final assessment pin, reviewer and actual UTC time. A valid
Agent submission is not scientific acceptance. Record rejected/failed stages and
unperformed downstream work honestly; do not manufacture a completed E2E chain.

Preserve the full directory tree, source bindings, approved input list, previews,
review notes, plans, sanitized actual commands/times, all Agent requests/traces/
assessments/run records, both selections, every comparison artifact, diagnostic,
pin approval and final review. Keep failed/partial outputs and exact historical
references. Record all additional artifact pins under `preservation`; moving
bound files can invalidate location-sensitive contracts. A protected local copy
is archival evidence, not a reason to rewrite the originals.

Finalize the handoff before hashing it. Store its final digest separately to
avoid a self-referential hash; never edit the finalized file without making a new
explicit revision and retaining the previous record:

```powershell
# PROPOSED / NOT EXECUTED — after all actual reviews and handoff edits finish
Get-FileHash -LiteralPath $Handoff -Algorithm SHA256 | Out-File -LiteralPath (Join-Path $RunRoot 'handoff_record.sha256') -Encoding utf8 -NoClobber
```

Keep scientific data, arrays/images/raw GIM, local handoffs, full traces and
private path mappings out of Git. Hashes establish byte identity, not raw-source
authenticity, immutable model behavior, trusted authorization or Windows isolation.

## 10. Runtime boundary, interface verification and present stop

Current backend is the existing explicit OpenAI Responses API adapter. Preserve
eight evidence calls, ten model turns, two assessment submissions with at most
one assessment-only correction, 128 KiB history, 32 KiB model envelope, 24 KiB
tool response, 2 KiB tool arguments, 2 MiB file cap and existing NPZ/header caps.
Provider configuration remains 4,096 maximum output tokens per response,
60-second timeout, zero transport retries, `store=false`,
`parallel_tool_calls=false`, `tool_choice=required`. One evaluation may contain
multiple billable model turns; recorded usage is not an invoice or a guaranteed
cost. Budget exhaustion/failure leads to review, never a paid automatic retry.
Ollama comparison and any autonomous infrastructure remain deferred.

The following CLI interfaces were verified **by source/AST inspection**, not by
executing `--help`, scientific wrappers or live clients:

| Existing module | Verified options used here |
| --- | --- |
| `examples.review_afghanistan_mvp` | `--modern-files`, `--historical-summary`, `--cluster-ids`, `--output-dir` |
| `examples.run_afghanistan_mvp_agent` | `--live`, `--mode`, `--model`, `--evidence-root`, `--question`, `--output-dir`, `--epz-diagnostic`, `--epz-sha256`, `--epz-size-bytes` |
| `examples.select_afghanistan_mvp_window` | `--review-bundle`, `--modern-data-dir`, `--inspect` or `--cluster-id` or `--start-utc`, `--end-utc`, `--justification`, `--output-dir` |
| `examples.compare_afghanistan_mvp_spatial` | positional `plan` / `run`; `--selection-a`, `--selection-b`, `--review-bundle`, `--modern-data-dir`, `--output-dir` |
| `examples.diagnose_afghanistan_epicentral_zone` | `--evidence-root`, `--output` |

Preparation created only this runbook and the blank JSON template. Actual
operations were read-only Git/source inspection, baseline file hashing and
standard-library static JSON/template/interface/Markdown consistency checks.
Static verification passed: strict JSON (duplicate/nonfinite values rejected),
eight ordered stages, 32 blank artifact references, unset future decisions and
timestamps, matching fixed-case metadata and 120/144-hour duration arithmetic,
nine proposed CLI calls checked against five source parsers, four inline Python
snippets parsed without execution, and all 20 PowerShell blocks parsed with
PowerShell's syntax parser without executing them. The checker's option-token
pattern was corrected to retain digits in `--epz-sha256`; the final interface
checks passed. Markdown links/whitespace also passed. Baseline comparison retained
all 240 pre-existing repository files and all 83 existing output files unchanged;
exactly the two requested documentation paths were added.
No application modules, proposed command blocks, tests, scientific algorithms,
diagnostic generator or model/API calls were executed. Existing modified and
untracked E2E-02A files were retained; no implementation/dependency/selection/
authorization record or real workflow output was created, and no Git commit,
tag, push or PR was made.

**Present stop: E2E Execution Preparation Review.** Outstanding researcher choices
are classification/run ID, intent, original local inputs or replay root, model/
cost/sharing scope, actual selection, independently reviewed prerequisites and
separate D/pin/Post approvals. No real Dry Run begins without explicit approval.

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```
