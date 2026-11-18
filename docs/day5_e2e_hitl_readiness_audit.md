# End-to-End Human-in-the-Loop Scientific AI Agent Readiness Audit

Audit date: 2026-11-18 (Asia/Taipei). Scope: read-only feasibility, interfaces,
saved-evidence integrity and handoff design. The only repository change is this
report. No proposed workflow command below was executed.

## 1. Executive verdict: CONDITIONAL GO

The existing case-specific scripts can support a small, sequential,
researcher-controlled Afghanistan dry run. **The complete requested workflow is
not ready to execute unchanged:** Post-Spatial has no EPZ evidence tool, and no
record currently joins the Pre-Spatial assessment, subsequent human decision,
spatial execution and final human review into one continuous run.

The appropriate next work is a bounded, read-only EPZ evidence interface, followed
by a researcher-maintained handoff record and separate execution approval. No
scientific algorithm, general workflow engine or autonomous executor is needed.
Manual recordkeeping is sufficient for the first supervised case; an automated
manifest writer is not a prerequisite.

Existing individual milestones are supported by source, saved records and review
documentation. They do **not** constitute a completed continuous end-to-end run.
In particular, the saved A/B selection and Framework D records do not reference
the accepted Pre-Spatial assessment. The accepted Post-Spatial run never retrieved
an epicentral cell or EPZ diagnostic. Shared evidence hashes demonstrate common
inputs, not a prospective human decision made after that Pre-Spatial assessment.

Execution remains **NO-GO in this audit**. The conditional technical verdict does
not verify local isolation, authenticate a human or authorize a live API call,
Framework A/D processing, diagnostic generation or Stage 2 execution.

## 2. Current implementation and checkpoint inventory

Git initially reported dubious ownership. Read-only commands succeeded with a
per-command `safe.directory` setting; global configuration was not changed.
Initial working tree: clean. Branch: `agent/day5-controlled-host`. HEAD:
`1c2db23c3480c9e041427a38a490932958fb4d30`, carrying `epz-diagnostic-v1`.
The preceding checkpoints include `mvp03-live-openai-responses-v1` at `0189f57`
and `mvp03-live-pre-spatial-v1` at `7a84225`. References were inspected, not moved.

The 2026-10-28 handoff and earlier execution-scope documents are historical
records. Their descriptions of pending milestones are superseded, where
supported, by current code, saved evidence and the later validation reviews.

| Stage | Existing implementation and evidence | Supported status and limits |
| --- | --- | --- |
| Scientific Request | `src/workflow/scientific_request.py::dispatch_scientific_request` | Strict JSON-native V1 dict; only `temporal_review`, explicit retrospective mode, resource IDs bound separately by the host. No request-file CLI or general acquisition host. |
| Temporal review / MVP-01 | `run_temporal_review`, `planning_evidence.py`, `window_planning.py`; `examples/review_afghanistan_mvp.py` | Existing composition computes A once, reads saved historical B+C, exports five artifacts plus a final run record. Saved 744-hour evidence has 37 positive, 610 normal and 97 negative classifications. |
| Candidate proposals | `plan_anchor_based_daily_windows` and saved `window_proposal.json` | Deterministic daily expansion produces Cluster 0: June 11-13, 72 hours; Cluster 1: May 28-June 2, 144 hours. The separate May 28-June 1 reference has 120 hours. Proposals are not execution choices. |
| Human selection / MVP-02A | `examples/select_afghanistan_mvp_window.py` | Exact bundle binding, explicit candidate or independent bounds, rationale and daily-file inventory. No authentication, assessment link or execution authorization. |
| Spatial A/B / MVP-02B | `examples/compare_afghanistan_mvp_spatial.py`; Modern spatial adapter | Saved status is `executed` for A and B. Wrapper reuses Modern D; fixed A=120-hour independent reference, B=Cluster 1 144-hour candidate. No generalized arbitrary-window execution interface. |
| Pre-Spatial / MVP-03 | `scientific_evidence_tools.py`, `scientific_review_agent.py`; `afghanistan_mvp03_api_pre_03` | Recorded live OpenAI `gpt-6-luna`: seven turns, six evidence calls, eight exact facts; `valid_first_submission`, empty flags, Cluster 1 follow-up recommendation. This audit checked saved bytes and facts, not the provider. |
| Post-Spatial / MVP-03 | Same Agent; `afghanistan_mvp03_api_post_01` | Recorded live OpenAI: six turns, four evidence calls, fifteen exact facts; `valid_corrected_submission`, empty final flags. One wording correction; no demonstrated numerical/citation correction. Epicentral reasoning was not tested. |
| EPZ Diagnostic V1 | `examples/diagnose_afghanistan_epicentral_zone.py`; two saved `diagnostic.json` files | Deterministic offline saved-array diagnostic. [Validation record](day5_epicentral_zone_diagnostic_validation.md) records researcher acceptance for descriptive analysis. Two saved outputs are byte-identical. No Agent integration exists. |
| Final human scientific review | MVP-03 and EPZ review documents | Separate milestone reviews exist. No final human disposition tied to all eight stages of one run. |

The [Pre-Spatial review](day5_mvp03_live_pre_spatial_review.md) documents failed
Runs 01/02 and accepted-for-review Run 03. Only Run 03's saved files were needed
for this audit; failed-run files were not reopened. The [Post-Spatial review](day5_mvp03_live_post_spatial_review.md)
retains a provisional scientific pass and an explicit epicentral-coverage gap.

Historical B+C remains **1999-01-01 through 2021-12-31**, based on the original
saved historical TEC and verified catalog pathway: 741 daily representative
catalog events, 74 eligible M>=6 events, 34 pre-event significant cells and
Day -8 / Day -22 anchors. Reading its saved context is not a new B+C reproduction.
No new 23-year GIM acquisition or reconstruction is needed or proposed.

## 3. End-to-end handoff matrix

| Transition | Upstream output -> downstream input | Existing contract | Missing handoff / implication | New code necessary? |
| --- | --- | --- | --- | --- |
| A. Request -> temporal review | Explicit V1 request + separately acquired series and historical summary -> dispatcher -> temporal/context/proposal tuple | Case/event identifiers, canonical inclusive UTC analysis bounds, UTC convention, detector parameters, selected anchor IDs, source declarations and full-series fingerprint | Example internally builds the request; user cannot pass arbitrary request JSON through its CLI. Event magnitude/coordinates/depth live in the fixed example's confirmed-event record, not the request's minimal event object. Host acquisition and quotas remain manual. | **No for this fixed case**, if researcher reviews the constructed request and resource binding before running. A generic request-file host is deferred. |
| B. Temporal review -> Pre-Spatial | Six-file MVP-01 bundle -> `EvidenceTools(root, "pre_spatial")` -> five bounded evidence views | Bundle hash/size and semantic validation; exact proposal reconstruction without rerunning A; in-memory snapshots and rechecks | Agent requires the fixed child name `afghanistan_mvp01_review`, not an arbitrary tuple. A fresh parent directory can supply it. Later selections/D/EPZ must remain outside this mode's views and question. | **No.** Existing fixed layout and CLI suffice. Preserve the boundary when adding EPZ. |
| C. Pre-Spatial -> researcher selection | Checked assessment + inspected candidates -> explicit human choice/rationale -> `selection_record.json` | Recommendation cites tool result IDs/JSON Pointers; selection pins proposal, parent evidence and full selected candidate | No selection field identifies the Agent run, assessment bytes, reviewer or decision time. Candidate justification can default to generated policy text. Rejection has no dedicated selection artifact. Recommendation never authorizes execution. | **No schema change required initially.** A separate manual handoff entry pins the assessment, choice/rejection, proposal, evidence and researcher's own rationale. |
| D. Selection -> Framework D | Two original-format selection records + same review bundle + explicit local Modern directory -> comparison `plan`, then human-only `run` | Exact field set, A/B mode/bounds, event, rationale, 15-day references, k=3, original daily-file SHA-256 matches; source/selection/bundle rechecks before and after D | Records are usable unchanged only for this fixed A/B experiment and matching inventory. Wrapper does not authenticate its caller or consume a human approval credential; `run` is a direct capability. Scope/approval and actual local invocation must be recorded separately. | **No for approved fixed A/B.** Do not add approval fields to strict selection schemas or expose `run` to the Agent. Other choices require a separate design review. |
| E. Framework D -> EPZ | Saved A/B arrays, summaries, selections and difference array -> offline diagnostic | `EvidenceTools(..., "post_spatial")` validates fixed saved artifacts; diagnostic checks common event/canonical grid and rechecks snapshots/code, then writes one fresh JSON | No raw GIM is needed. The loader needs the parent temporal bundle and original selection records as well as arrays. Center membership differs from historical visual cell overlap; diagnostic creation is a separate human-approved stage. | **No.** Existing CLI suffices; do not run D or infer geometry from a plot. |
| F. EPZ -> Post-Spatial | Pinned saved V1 diagnostic + matching spatial evidence -> model-selectable read-only evidence tool | Current Post-Spatial has global summaries, comparison and nearest-cell lookup only | No diagnostic loader, allowlisted EPZ tool, EPZ availability state, source citation or Agent integration tests. Diagnostic acceptance explicitly did not authorize Agent integration. | **Yes: one narrow saved-report retrieval interface with offline tests**, detailed below. No new EPZ calculation. |
| G. Post-Spatial -> final researcher review | Agent request/trace/assessment/run record -> human scientific assessment/disposition | Exact inspected source snapshots, code/configuration, response usage/IDs, checked values and pointers, status/outcome, fresh output files | Agent run has no workflow ID, link to the Pre-Spatial decision or final human outcome. Existing Post run contains no EPZ evidence. | **No automated review code needed.** A manual handoff record joins these identities and records accept/reject/needs-evidence with reasons; acceptance is never automatic. |

### Request fidelity and hard-coded boundaries

`dispatch_scientific_request` already preserves the explicit request and delegates
once to the existing temporal review. Source references in metadata are inert;
only the host-bound summary path is read. The workflow fingerprints the **full**
supplied time series, including reference rows, and records source declarations.
The example additionally hashes original input files before/after review and
saves the final request with that provenance.

The example fixes `case_id=afghanistan_2022`, event `us7000hj3u` at
`2022-06-21T20:54:34Z`, M6.0, epicenter `(33.020,69.464)`, depth 4 km; scientific
input coordinates remain `(33.02,69.46)` and the chosen TEC center `(32.5,70)`.
Analysis is May 22 00:00 through June 21 23:00 UTC, with 15 reference days and
threshold multiplier 3. The dispatcher accepts more general requests, but
`validate_bundle` deliberately rebuilds this fixed example request. A general
request is therefore **not** automatically compatible with these downstream
case-specific scripts. No claim of arbitrary-case readiness is justified.

The analysis inventory extends past the earthquake origin on its final day;
this is retrospective. The selection wrapper separately rejects target windows
ending at/after the event. Do not reinterpret the analysis as a prospective test.
The daily planner requires at least one valid target-polarity hour, no opposite
hours and all 24 hours present/classifiable. June 2 contributes one negative
hour; preserve its resulting 144-hour candidate rather than truncating it to
match the historical reference. A K-means anchor alone never supplies bounds.

### Pre-Spatial isolation finding

By source inspection, Pre-Spatial initializes only the six MVP-01 snapshots; it
does not read or test selection/spatial paths. Its five tools are inventory,
temporal summary, hourly interval inspection, historical context and candidate
listing. The published 120-hour reference is visible as historical context;
later execution selections are absent. Its submit schema excludes
`review_spatial_comparison`. Tests explicitly assert the six-source boundary and
refusal of spatial tools. Saved Run 03 contains only those permitted retrievals.

This is an application-interface finding, not proof of Windows isolation. Future
Pre-Spatial prompts must also exclude later decisions/results; a question string
is not a safe place to bypass the evidence boundary.

### Selection and execution fidelity

The comparison wrapper accepts the existing selection records without changes.
It insists on A's independent May 28-June 1 window and B's Cluster 1 May 28-June 2
window. It also compares the entire current input inventory with the saved one,
including directory identity and extra entries. Moving inputs, changing directory
contents or copying a bundle into another root can invalidate bindings. Do not
rewrite saved paths or hashes to make a replay pass; retain original evidence
locations. New continuous runs generate their own consistent records in a fresh
root. An incompatible or rejected selection stops this fixed A/B sequence.

Existing `planning_approval.py` intent/decision declarations are not a shortcut:
they are not consumed by this wrapper, require a candidate-specific configuration
and always deny execution eligibility. The preparation manifest concerns an
earlier two-stage contract, not this Pre/EPZ/Post lineage. Reusing those as new
approval credentials would expand scope without closing the trust gap.

## 4. Missing links and minimal change recommendations

### Blocking for the first complete continuous dry run

1. **Validated EPZ retrieval:** implement only the bounded, Post-Spatial saved-JSON
   interface in Section 6 after separate approval. Prove isolation, binding,
   citations, budgets and failure behavior with synthetic offline tests.
2. **One explicit lineage record:** before execution, researcher assigns a new run
   identity and records request, evidence and stage references as described
   below. This can be manually maintained; no engine, database or exporter is
   required. Without it, independent successful stages still do not prove a
   continuous human-in-the-loop run.
3. **Separate researcher decisions:** approve the live calls and evidence sharing,
   review the actual Pre result, explicitly approve/reject the selected comparison
   with a personal scientific rationale, and separately approve local D execution.
   Resolve applicable security prerequisites independently. Current state does
   not permit Codex or the Agent to execute D.
4. **Researcher-bound inputs for fresh processing:** explicitly supply and verify
   the existing Modern 2022 files and original-TEC-derived B+C summary. Their
   external paths were not opened or tested in this audit. No data are to be
   downloaded, reconstructed or synthesized if unavailable.
5. **Final human disposition:** record scientific acceptance, rejection or request
   for more evidence against the exact final assessment and evidence pins.

### Small manual handoff record

Use one local, researcher-maintained `handoff_record.json` or equivalent reviewed
record in the fresh run root. This is a proposed operational record, not a new
authorization mechanism or an artifact created by this audit.

| Required content | Purpose |
| --- | --- |
| Run ID, schema label, `case_id`, confirmed event, run class (`replay` or `continuous_scoped`) | Distinguish run identity from the constant scientific case identity. |
| Explicit initial request intent, resource bindings, finalized `scientific_request.json` path/SHA-256/size, reviewed parameter/event agreement | Demonstrate request-first intent and exact inputs; note that the wrapper adds measured provenance before saving. |
| Temporal run record, proposal and evidence pins; historical summary identity/hash and reused-versus-regenerated status | Bind candidates to the snapshot and preserve historical/2022 separation. |
| Pre Agent run-record, request, trace and assessment pins; status/outcome and model configuration | Identify the actual assessment reviewed, not merely its recommendation text. |
| Human choice or rejection, reviewer declaration, UTC time, own justification, candidate/report pointer, exact bounds and both selection pins | Link the human's decision to the Pre assessment and proposal. Declared identity/time is not authenticated presence. |
| Separate scope-approval reference and local execution log: sanitized exact argv, start/end UTC, machine/operator declaration, input pins, parameters, exit status, comparison/output pins | Record who reports executing which fixed experiments, and distinguish an observed invocation from a reconstructed equivalent. No secrets in argv/logs. |
| EPZ diagnostic pin, source-artifact pins, accepted conventions and separately referenced review status | Bind geometry evidence to the same A/B outputs without altering the accepted diagnostic. |
| Post Agent run/artifact pins, actual EPZ retrieval/result IDs/pointers, status/outcome, usage/model/configuration | Demonstrate model access and actual citation rather than tool availability alone. |
| Final reviewer/time, accept/reject/needs-evidence, scientific reasons, limits and referenced final assessment/evidence pins | Preserve the final human scientific decision separately from technical validation. |

Record stage order when events occur; do not backfill an assertion that old D
outputs were caused by a later Pre recommendation. Freeze/hash the final handoff
record for review; its own digest can be retained separately. Absolute external
source paths remain local and are not publication material. Per-artifact hashes
provide reproducible evidence identity; they do not reproduce a stochastic model
assessment or authenticate raw observations.

### Useful but non-blocking

An offline handoff consistency checker, sanitized argv/timing capture, a small
request-file CLI and a reusable handoff schema could reduce clerical errors.
Record them as later improvements. General request transport quotas remain an
unresolved host responsibility; the current fixed local example is not an
untrusted service. Stronger semantic review of narrative support is useful;
exact pointer validity alone does not establish inferential support.

## 5. Saved-evidence replay versus a continuous new dry run

| Claim | What would actually happen | Permissible description |
| --- | --- | --- |
| Existing independent checkpoints | Review already saved Pre, selections/D, EPZ and Post from their separate tasks | Validated individual stages with shared evidence. No completed continuous E2E claim. |
| New saved-evidence handoff replay | New separately approved Pre/Post calls and explicit present human review, using already saved temporal/D/EPZ evidence; handoff declares reuse | **Evidence-handoff replay.** A present selection may ratify compatibility with old outputs; it did not authorize their original execution. |
| New continuous scoped dry run | One new request intent, fresh A review bundle, live Pre, subsequent human selection/approval, researcher-local fresh D A/B, fresh offline EPZ, live Post and final human review | Continuous **Human-in-the-Loop** dry run with saved historical B+C context. Fresh A/D/EPZ processing is distinct from B+C reuse. |
| Full scientific re-execution from observations | Independently approved reacquisition/loading of original observation inputs and rerunning all required processing, A/B/C/D with full upstream provenance | Not demonstrated or proposed here. Existing modern NPZ inputs and historical NPY/summary provenance do not establish raw observation/interpolation history. |

The smallest eventual baseline is the saved-evidence replay after EPZ integration;
it limits computational work while testing the new handoff. The requested
continuous demonstration additionally requires the new ordered human actions and
fresh local scientific stages. Choose and declare the run class **before** the
first live call. Reusing saved D always prevents a claim of fresh full
computational execution. Neither class establishes seismic causation.

## 6. EPZ Agent integration assessment

**Current interface: missing.** `definitions("post_spatial")` adds only
`get_spatial_experiment_summary`, `compare_spatial_experiments` and
`inspect_spatial_grid_cell`. No loader reads either saved diagnostic, and no
result can cite it. The diagnostic uses the Agent's offline evidence loader;
that dependency does not provide the reverse diagnostic-to-Agent handoff.

The smallest addition is one proposed `get_epz_diagnostic_summary({})` tool in
Post-Spatial, with an optional **host-only** diagnostic binding (for example a
new `--epz-diagnostic` CLI argument). This flag/tool does not exist today. The
researcher supplies the one approved relative artifact identity under the
evidence root; the model supplies no path, radius, event override or output
destination. Existing non-EPZ runs remain usable when the binding is absent.

Minimum contract for that implementation:

- In Pre-Spatial, expose no EPZ tool, initialize no diagnostic, perform no EPZ
  existence check and reveal no EPZ availability. Reject an explicit Pre-mode
  diagnostic binding before opening it. Add tests for this exact boundary.
- In Post-Spatial, read only the bound file through existing bounded, strict
  JSON/path controls. Reject traversal, redirection, nonfinite/duplicate JSON,
  unsupported type/version/shape and oversized content. Use the current 2 MiB
  file cap and 24 KiB tool-response cap; return a compact projection rather than
  full provenance/code dictionaries. Extend output-directory protection to the
  bound diagnostic directory.
- Require record type `afghanistan_epicentral_zone_diagnostic`, version 1, matching
  case/event, canonical grid, A/B windows/parameters/denominators and exact source
  SHA-256/size map matching the validated temporal/spatial snapshot. A mismatched,
  stale or missing report is unavailable; never silently regenerate or repair it.
- Bind the diagnostic bytes themselves to a separately researcher-reviewed
  SHA-256/size pin in the handoff. Its internal source hashes do not self-authenticate
  its own scientific values. Validate row/column identities and saved scalar,
  count/ratio and B-minus-A consistency against those arrays with bounded checks;
  do not call the diagnostic generator, recompute a new EPZ experiment or run D.
- Preserve the accepted diagnostic's historical code/environment provenance.
  Adding this tool changes `scientific_evidence_tools.py`, which is among the
  diagnostic's recorded direct-code fingerprints. Do not reject or rewrite an
  accepted historical diagnostic merely because its generating code differs
  from the new reader. Record reader and generator versions separately; a fresh
  diagnostic records its own then-current generating code.
- Return event/reference/membership convention, shared mask identity and centers,
  distances/boundary margins, both experiments' per-center counts/ratios and
  original denominators, global peaks and membership, regional summaries,
  B-minus-A changes, units, unavailable validity counts and scientific limits.
  Include artifact/hash/size citations, retain snapshot rechecks and sanitize
  errors. Do not provide a fitted radius, association score, causal verdict or
  prewritten scientific assessment.
- Keep `submit_assessment`'s existing exact-value and successful-result JSON
  Pointer checks. No new assessment schema or approval action is needed. Prove
  the new projection can be cited in fake/offline loop tests before any live run.
  Test altered sources, wrong event/window/denominator, changed report, missing
  pin, output limits and attempts to call generators/network/protected functions.

The saved diagnostic has no explicit `nearest_epicentral_center` field.
`closest_included_center_to_boundary` means proximity to the **boundary**, not
proximity to the epicenter. Keep the existing
`inspect_spatial_grid_cell(latitude=33.020, longitude=69.464)` lookup for that
distinct question; it selects `(32.5,70)` by absolute latitude and circular
longitude, without interpolation. Do not label that general lookup algorithm a
great-circle nearest-neighbor search. The diagnostic separately records
great-circle distances for included centers and global peaks.

### Saved evidence the future Agent must distinguish

The following are **read from saved JSON**, not recomputed by this audit, and
must not be inserted into the live question as expected answers.

| Quantity | Experiment A | Experiment B |
| --- | --- | --- |
| Original ratio denominator | 120 hours | 144 hours |
| Global negative maximum center | `(30,70)` | `(30,70)` |
| Negative count / percentage at that maximum | `102 / 85.0` | `103 / 71.52777777777779` |
| Nearest epicentral sample center | `(32.5,70)` | `(32.5,70)` |
| Negative count / percentage there | `95.0 / 79.16666666666666` | `96.0 / 66.66666666666666` |
| Third included center `(35,70)`: negative count / percentage | `85.0 / 70.83333333333334` | `86.0 / 59.72222222222222` |
| Negative regional grid-hour occurrence sum | `282` | `285` |
| Unweighted regional mean negative percentage | `78.33333333333333` | `65.97222222222223` |

The shared EPZ contains three centers, with saved radius
`380.1893963205613 km`, spherical radius `6371.0088 km`, inclusive membership
`distance <= radius` and zero tolerance. Saved negative B-minus-A aggregate
change is `+3` grid-hour occurrences and mean cell-wise ratio change
`-12.361111111111112` percentage points. The mean of differences must retain its
saved precision; do not replace it with rounded subtraction of displayed means.
Regional positives are zero. A's positive global maximum remains 10% at
`(-22.5,-155)` and `(-22.5,-150)`; B's is `8.333333333333332` at the same centers.

Preserve exact JSON numeric values in checked facts; per-center counts may be
integer-valued floats while global-peak counts are integers. The host checks
canonical JSON equality, not a display-rounded approximation.

The accepted convention is great-circle **grid-center membership**. It does not
reproduce the historical paper's visual grid-cell/EPZ-circle overlap rule. No
grid-cell intersection or physical areal coverage was calculated. Three spatially
correlated centers, unweighted percentages and grid-hour sums establish neither
unique anomaly hours nor association significance. A global maximum can lie
inside this reference zone and still differ from the nearest epicentral center;
neither observation establishes seismic causation. Effective detector-valid
counts remain null; finite-input availability never replaces the denominators.
Kp, Dst and F10.7 remain unevaluated.

Saved JSON still says `researcher_review=pending` and
`agent_integration=not_authorized`. The later validation document records limited
scientific acceptance separately. Preserve both records and obtain separate
integration approval; do not rewrite the old JSON or infer execution authority
from acceptance of its descriptive analysis.

## 7. Exact proposed human-controlled workflow sequence

**Design only; no commands in this section were run.** Start only after the
missing interface passes its separately approved review and the researcher
approves the chosen run class and live call scope. This sequence describes a new
continuous scoped run; the replay variant below omits scientific generation.

The researcher chooses `$RunRoot` as a fresh local-only root such as
`outputs/afghanistan_e2e_hitl_01`, `$Py` as `.venv/Scripts/python.exe`, an explicit
`$ModernFiles` array, its actual `$ModernDataDir`, the original-TEC-derived saved
`$HistoricalBcSummary` and an explicitly approved `$Model`. These are host-bound
inputs, not values supplied by model tools. Existing `gpt-6-luna` records identify
the baseline model only; this audit did not check provider availability.

1. **Scientific Request and resource review.** Inspect the existing
   `build_request([0,1])` object with the confirmed event record and fixed example
   parameters. Record the human's request intent and proposed bindings before
   processing. An optional existing-code preview command is:

   ```powershell
   & $Py -B -c 'import json; from examples.review_afghanistan_mvp import build_request; print(json.dumps(build_request([0,1]), sort_keys=True, indent=2))'
   ```

   The request's cluster IDs specify anchors to consider, not windows approved
   for execution. The fixed wrapper later appends measured file provenance;
   verify that its exported request agrees with this reviewed scientific intent.
   No external-request-file flag is assumed.

2. **Researcher generates the new temporal bundle**, loading saved historical
   B+C context rather than rerunning B/C:

   ```powershell
   & $Py -B -m examples.review_afghanistan_mvp --modern-files $ModernFiles --historical-summary $HistoricalBcSummary --cluster-ids 0 1 --output-dir "$RunRoot/afghanistan_mvp01_review"
   ```

   Review all six files, source pins, coverage, candidate rule and boundary days;
   record the request/proposal/evidence pins. Missing inputs or abstention stop
   dependent work. Do not acquire replacement historical datasets.

3. **One separately approved live Pre-Spatial call sequence**, in a new directory:

   ```powershell
   & $Py -B -m examples.run_afghanistan_mvp_agent --live --mode pre_spatial --model $Model --evidence-root $RunRoot --output-dir "$RunRoot/agent_pre"
   ```

   Inspect the actual trace, checked facts, recommendation and uncertainties.
   Pin all five outputs. No later selection, D or EPZ information is supplied.

4. **Human selection and separate execution decision.** Record the actual Pre
   assessment reviewed, accept/reject choice and personal rationale in the handoff.
   Stop if rejected. Only if the researcher explicitly chooses the fixed A/B
   scope may they create these two new original-format selection records:

   ```powershell
   & $Py -B -m examples.select_afghanistan_mvp_window --review-bundle "$RunRoot/afghanistan_mvp01_review" --modern-data-dir $ModernDataDir --start-utc 2022-05-28T00:00:00Z --end-utc 2022-06-01T23:00:00Z --justification $ReferenceRationale --output-dir "$RunRoot/afghanistan_mvp02b_selections/experiment_a_reference_120h"
   & $Py -B -m examples.select_afghanistan_mvp_window --review-bundle "$RunRoot/afghanistan_mvp01_review" --modern-data-dir $ModernDataDir --cluster-id 1 --justification $CandidateRationale --output-dir "$RunRoot/afghanistan_mvp02b_selections/experiment_b_candidate_144h"
   ```

   `$ReferenceRationale` and `$CandidateRationale` are the researcher's nonempty
   statements. Set `$SelectionA` and `$SelectionB` to these exact
   `selection_record.json` paths. A Cluster 0 choice or revised bounds cannot
   proceed through this fixed wrapper; stop for scope review. The Agent need not
   agree with the human; any departure needs an explicit explanation.

5. **Researcher-local D planning, then a separate approval stop.** The researcher
   may inspect the non-executing plan after input access is approved:

   ```powershell
   & $Py -B -m examples.compare_afghanistan_mvp_spatial plan --selection-a $SelectionA --selection-b $SelectionB --review-bundle "$RunRoot/afghanistan_mvp01_review" --modern-data-dir $ModernDataDir --output-dir "$RunRoot/afghanistan_mvp02b_comparison"
   ```

   This command reads/hashes real local inputs, so it was not invoked in this
   audit. Confirm exact windows, 15 reference days, k=3, ascending canonical grid,
   source integrity and approved fresh destination. Record approval and applicable
   independently established security prerequisites. **Only the researcher on
   their local machine**, after this separate approval, may issue:

   ```powershell
   & $Py -B -m examples.compare_afghanistan_mvp_spatial run --selection-a $SelectionA --selection-b $SelectionB --review-bundle "$RunRoot/afghanistan_mvp01_review" --modern-data-dir $ModernDataDir --output-dir "$RunRoot/afghanistan_mvp02b_comparison"
   ```

   Record sanitized exact invocation, operator/time/exit result, selected
   experiments, code/environment and all input/output pins. No Codex, Agent,
   Stage 2 or automated handoff action invokes this command. A partial output
   without the final comparison summary is incomplete; retain it for inspection.

6. **Validate the saved D handoff, then generate EPZ offline**, under the approved
   descriptive conventions and without changing D:

   ```powershell
   & $Py -B -m examples.diagnose_afghanistan_epicentral_zone --evidence-root $RunRoot --output "$RunRoot/afghanistan_epz_diagnostic/diagnostic.json"
   ```

   Pin/review the diagnostic, its 23 source snapshots and the exact geometry/count
   semantics. This is a separate diagnostic generation, not a model action.

7. **One separately approved live Post-Spatial call sequence.** The next command
   is a **proposed interface after implementation**: `--epz-diagnostic` is not
   supported today. Its proposed value is a host-bound relative identity:

   ```powershell
   & $Py -B -m examples.run_afghanistan_mvp_agent --live --mode post_spatial --model $Model --evidence-root $RunRoot --epz-diagnostic afghanistan_epz_diagnostic/diagnostic.json --question $PostQuestion --output-dir "$RunRoot/agent_post"
   ```

   `$PostQuestion` asks the model to retrieve and cite the EPZ evidence, distinguish
   global peaks/nearest epicentral sample/included centers, compare counts and
   denominators, and state physical uncertainty. Supply no expected numbers,
   causal answer or prior model conclusion. The model chooses its tools; the host
   does not prefetch EPZ content into the prompt. If it omits EPZ retrieval or
   citation, mark coverage incomplete rather than injecting a conclusion or
   silently retrying a billable run.

8. **Final researcher scientific review.** Validate the actual trace, exact
   references, assessment outcome and evidence continuity. Record final
   accept/reject/needs-evidence and reasons in the handoff, freeze its digest and
   preserve all stage artifacts. Technical validity is not scientific acceptance.

For an **evidence-handoff replay**, keep the existing evidence at its bound
locations and use fresh Agent output directories plus a new manual handoff record.
Reuse the saved D and EPZ pins explicitly; skip temporal/D/EPZ generation commands
when those stages are replayed. The proposed host binding may identify
`afghanistan_epz_diagnostic_run01/diagnostic.json` under `outputs`. Present human
ratification is not retroactive original execution approval. Do not copy old
bundles to a new root and edit their parent bindings to manufacture continuity.

## 8. Required approval, runtime and security gates

- Separate researcher approval is required for EPZ Agent implementation, permitted
  evidence sharing and eventual live Pre/Post evaluations. Approve the model and
  one bounded run of each mode; no repeated billable trials without approval.
- Local D execution has its own researcher approval and applicable isolation
  prerequisites. A selection JSON, model recommendation, `plan` subcommand,
  successful assessment or manual manifest is not an authenticated credential.
  The direct `run` capability has no software gate proving a human is its caller.
- Preserve existing limits: **8 evidence calls**, **10 model turns**, **128 KiB
  history**, **32 KiB model-response/argument envelope**, **24 KiB tool response**,
  **2 KiB evidence-tool arguments**, **2 assessment submissions** with at most one
  assessment-only correction, **12 feedback issues**, **4 KiB feedback**, and
  **168 hours** per temporal interval query. NPZ limits remain bounded to 12
  entries, 8 MiB expanded, approved shapes/numeric dtypes and no pickle loading.
- Existing live adapter configuration is explicit model, `store=false`,
  `tool_choice=required`, `parallel_tool_calls=false`, 4,096 output tokens per
  response, 60-second timeout and zero transport retries. This is configuration
  observed in code/records, not an external API-policy verification.
- The EPZ tool must fit the existing budgets. For example temporal summary,
  historical context, candidates, A summary, B summary, comparison, EPZ summary
  and nearest-cell lookup use eight retrievals, leaving turns nine/ten for
  submission/correction. This is a feasibility path, not a scheduled model trace;
  payload/history fit after integration remains to be measured offline.
- Record requested and returned model IDs, SDK/code/environment, usage and actual
  response/tool trace. Existing Pre/Post token totals are historical usage, not
  invoices or guaranteed future costs. No pricing lookup or new cost claim was
  made. Budget exhaustion or invalid assessment yields an explicit incomplete
  or abstained result, never automatic approval or a paid retry.
- Researcher configures credentials outside artifacts. Do not open secret files,
  print keys, copy environment dumps or include credentials in commands. Tools
  remain read-only and path-free from the model's perspective; deny framework
  execution, selection mutation, signing, Store access and shell/network tools.
- Use fresh stage output directories. Preserve accepted outputs, failed traces,
  selections, checkpoints and historical code declarations. Research arrays,
  plots, raw inputs and full local traces stay ignored/uncommitted. Current
  evidence paths may contain private host information; review any sharing.
- Snapshot hashes, path checks and test sentinels do not prove Windows process/OS
  isolation, hostile-race resistance, authenticated original data custody or
  trusted human presence. Establish those claims independently before changing
  any protected-execution eligibility declaration.

## 9. Scientific and technical acceptance criteria

These are proposed checks for a future approved run, **not new passes claimed by
this audit**. A rejection or evidence request can be a valid scientific outcome;
it must be recorded honestly rather than converted into a successful D run.

| Check | Required evidence / failure condition |
| --- | --- |
| One request and case | Same case/event, distinct run ID, initial reviewed request intent and pinned final request throughout; mismatches stop. Explicit run class and saved B+C reuse. |
| Temporal proposal integrity | Complete final bundle; exact hashes/sizes; existing bundle validator passes; full-series/source binding, coverage, UTC and policy agree. No anchor-to-window shortcut or post-hoc truncation. |
| Genuine live Pre | Saved config/provider/response IDs/usage and successful model-selected tools, not FakeModel; observed values match successful result pointers. Trace/snapshots contain no later selections/D/EPZ. |
| Explicit human decision | Reviewer/time/rationale declaration pins exact Pre assessment, evidence/proposal and candidate or rejection. Human execution approval is separately recorded; neither is inferred from the model. |
| Exact execution inputs | A/B bounds, 120/144 inclusive hours, 15 reference days, k=3 and canonical coordinates match selection/plan/execution records; sources match original pins immediately before/after D. |
| Human-only local D | Independent evidence of the researcher's local invocation and approval, not merely a JSON `executed` label. No Agent/Codex/Stage 2 executor is given this capability. |
| D output integrity | Final comparison exists; existing offline saved-output validation passes all hashes, selection copies, parent/event bindings, arrays, count/ratio and B-minus-A checks. Fresh computation and reused results are labeled separately. |
| Preserved regression reference | For a fresh A, retain 120 hours, 71x73=5,183 finite cells, +10% peaks at (-22.5,-155)/(-22.5,-150), -85% peak at (30,70). Report deviations; never tune references to pass. B is not required to match A's ratios. |
| EPZ identity and integrity | Diagnostic's own trusted pin and complete saved-source binding pass; correct type/version, event, canonical grid, windows and denominators. Missing/stale evidence fails closed, without regeneration by the Agent. |
| EPZ interpretation | Preserve grid-center versus historical cell-overlap distinction, exact per-center values, shared mask, unchanged denominators, percentage-point differences, grid-hour and unweighted-mean units, null effective validity and missing controls. |
| Genuine live Post with EPZ | Trace must show an actual successful EPZ tool call and final facts/citations resolving into that result, alongside the separate nearest-cell/global-peak distinction. Tool availability alone is insufficient. |
| Exact grounding | Every observed fact equals its actual successful tool-result JSON value; all cited result IDs/pointers exist; narratives remain tentative. Existing lexical checks do not replace human semantic review. |
| Scientific restraint | No automated precursor, predictive, association-significance or causal decision. Spatial coincidence is descriptive; Kp/Dst/F10.7 and data-quality/control limits remain explicit. |
| Technical versus scientific status | Preserve first/corrected/flagged/rejected/abstained outcome, flags and original submissions. `submitted_for_researcher_review` is not final acceptance. Human review records its independent outcome. |
| Reproducible handoff | Exact local references and pins for all stages, sanitized argv/times/operator declarations, model/config/code/environment, actual trace/usage, review order and final record digest. Unknown details remain unknown. |
| Checkpoint/evidence preservation | Before/after evidence hashes and file inventory unchanged except fresh separately authorized outputs; no accepted artifact rewrite, overwrite, commit/tag mutation or research-data staging. |

## 10. Deferred work

Ollama comparison follows the established E2E baseline, using the same frozen
evidence, questions and scoring with separate approval. Also deferred: general
workflow engines, queues, databases, dashboards, scheduling, autonomous D/Stage 2,
arbitrary-case/window support, production request transport/resource management,
authentication/authorization infrastructure and OS-isolation certification.

Scientific extensions require separate researcher design: grid-cell intersection
or historical figure-overlap reproduction, sensitivity of the EPZ reference,
area weighting, detector-valid denominators, space-weather inputs, physical
mechanisms, null/control designs, multiple-event/prospective evaluations and
causal or predictive claims. No new algorithms, thresholds, source grids,
polarity conventions or dependencies are recommended for the present handoff.

Differences from Legacy remain explicit: ascending Modern latitude receives no
second flip; the 144-hour daily-policy candidate is distinct from the 120-hour
historical reference; great-circle center membership is distinct from historical
visual cell overlap. This audit changes none of those definitions or outputs.

## 11. Files inspected, operations performed and review stop

### Source, tests and documentation

Read the pasted request and `AGENTS.md` / `docs/agent_handoff.md`. Source inspection
covered the five prioritized examples (`review`, `select`, `compare`, `diagnose`,
`run_agent`) and these exact implementation paths:

- `src/workflow/scientific_request.py`
- `src/workflow/temporal_workflow.py`
- `src/workflow/planning_evidence.py`
- `src/workflow/window_planning.py`
- `src/workflow/planning_approval.py`
- `src/workflow/preparation_manifest.py` (targeted interface search)
- `src/workflow/modern_spatial_input_adapter.py`
- `src/agent/scientific_evidence_tools.py`
- `src/agent/scientific_review_agent.py`

The example paths are `examples/review_afghanistan_mvp.py`,
`examples/select_afghanistan_mvp_window.py`,
`examples/compare_afghanistan_mvp_spatial.py`,
`examples/diagnose_afghanistan_epicentral_zone.py` and
`examples/run_afghanistan_mvp_agent.py`. The two additional direct diagnostic
dependencies `src/spatial_verification/spatial_grid.py` and
`src/workflow/spatial_summary_export.py` were byte-hashed for provenance; their
scientific functions were not executed. No change to the IDE's open
`src/spatial_verification/gim_loader.py` was needed.

Tests read/searched, with focused fixture and assertion inspection:

- `tests/workflow/test_scientific_request.py`
- `tests/workflow/test_scientific_review_integration.py`
- `tests/workflow/test_review_afghanistan_mvp.py`
- `tests/workflow/test_select_afghanistan_mvp_window.py`
- `tests/workflow/test_compare_afghanistan_mvp_spatial.py`
- `tests/workflow/test_diagnose_afghanistan_epicentral_zone.py`
- `tests/agent/test_scientific_review_agent.py`

These cover request/resource boundaries, stale lineage, deterministic evidence,
original-source matching, strict selections, harmless D doubles, Pre isolation,
bounded retrieval, exact citations/recovery, corruption, NPZ limits, and EPZ
offline geometry/semantics. No current test connects a diagnostic to a model
tool. **No tests were run.** Historical documentation records 99 Agent / 86
workflow tests in Post readiness, and 43 EPZ tests in its validation record;
those are prior results, not this audit's executions. The explicit audit
prohibition takes precedence over the general full-suite instruction: no
`python -m pytest tests -q`, protected test collection or scientific test run
was attempted.

Documentation inspected in full or targeted sections/searches:
`docs/day5_mvp03_live_pre_spatial_review.md`,
`docs/day5_mvp03_live_post_spatial_review.md`,
`docs/day5_mvp03_live_post_spatial_readiness.md`,
`docs/day5_mvp03_evaluation.md`, `docs/day5_mvp02b_execution_scope.md`,
`docs/day5_epicentral_zone_diagnostic_scope.md`,
`docs/day5_epicentral_zone_diagnostic_validation.md`,
`docs/day5_checkpoint5a_controlled_host_review.md` and `README.md` status/test
references. No external web source was opened; literature statements above
describe the accepted local convention, not a new literature verification.

### Saved evidence and observed integrity checks

Exactly **36 saved files** were inventoried and byte-hashed under these local
`outputs/` children:

| Child directory | Files inspected |
| --- | ---: |
| `afghanistan_mvp01_review` | 6: request, temporal/context/proposal JSON, review note, run record |
| `afghanistan_mvp02b_selections` | 2: A/B selection records |
| `afghanistan_mvp02b_comparison` | 16: plan/summary/report/difference NPZ and two sets of selection/status/summary/arrays/positive/negative plots |
| `afghanistan_epz_diagnostic_run01` / `...run02` | 2: accepted diagnostic JSON files |
| `afghanistan_mvp03_api_pre_03` / `...post_01` | 10: request/trace/assessment JSON/assessment Markdown/run record per mode |

Plots and NPZs were hashed as bytes only; images were not visually re-reviewed,
and arrays were not loaded or recalculated. Standard-library Python 3.10.6 on
stdin (`-B`, no script file) performed hash/size comparisons, fixed local
artifact lookups, selection-copy/parent/event/window agreement, all six Pre and
23 Post source-snapshot pin comparisons, both diagnostic 23-source/7-code pin
comparisons, current Agent code-pin comparisons and independent pointer/value
resolution for **8 Pre + 15 Post final facts**. All checked comparisons passed.
Both diagnostic JSON files have equal bytes. This is byte/declaration integrity
and saved-fact grounding, not a fresh numerical or full evidence-loader validation.

The existing `EvidenceTools`, planner, `_build_report`, `diagnose`, Agent runner,
SDK and Framework A/B/C/D functions were **not invoked**, even for validation.
Recorded external scientific/code/source paths were never followed; code pins
were compared only against explicitly enumerated local repository files.

Selected reviewer-computed pins (full child maps remain in their original local
records):

| Artifact, relative to `outputs/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `afghanistan_mvp01_review/scientific_request.json` | 10364 | `16f1893874cdfaa35ff31c3412d5198e65496151085e0e499d261dd1d00996c3` |
| `afghanistan_mvp01_review/window_proposal.json` | 36881 | `34bf442f7b55d160b3cb35fdf765dace5e9f942308dc187329c4a768dda3fc90` |
| `afghanistan_mvp02b_comparison/comparison_summary.json` | 43809 | `588a7f44b11ea678a5ab98df2ce787a43f38f08100f309a7dd5c56e8e4b5562b` |
| `afghanistan_mvp03_api_pre_03/run_record.json` | 8763 | `21801b8147dcf4e19a7f3d00fc7b5cc0e4b343bfd0fe7ea7cca2db9a9687cf01` |
| `afghanistan_mvp03_api_post_01/run_record.json` | 11722 | `10f0fa2771ef83709a1cf4a8218e2c50a2585eb59320066cae849bc0c54c0729` |
| Either accepted `afghanistan_epz_diagnostic_run0N/diagnostic.json` | 23441 | `d0e7d0e2127ba66599b9dd0a808be1b1cc0add5ecae2902fae09bcbbc952c1b4` |

Complete 36-file inventory digest:
`78ee9f0848fa023e00899e74d07c7238b798603f7329362bd58a4076e5a0caff`.
Encoding: ASCII sorted compact JSON mapping paths relative to `outputs/` to
`{size_bytes,sha256}`, no newline. Hash is an audit baseline, not authentication.
Before/after checks retained the same file set, sizes and hashes.

### Actual commands and document checks

Inspection used `Get-Content -LiteralPath ... -Encoding UTF8`, indexed slices for
long files, `rg --files` inventories and `rg -n` interface/test/document searches.
The initial unmodified `git status --short --branch` failed with dubious ownership
(exit 1). The successful read-only Git commands were:

```powershell
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework status --short --branch
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework log -5 --oneline --decorate
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework rev-parse HEAD
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework ls-files outputs
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework check-ignore outputs/afghanistan_mvp01_review/run_record.json outputs/afghanistan_mvp02b_comparison/comparison_summary.json outputs/afghanistan_epz_diagnostic_run01/diagnostic.json outputs/afghanistan_mvp03_api_pre_03/run_record.json outputs/afghanistan_mvp03_api_post_01/run_record.json
```

`ls-files outputs` returned no tracked outputs. All five explicitly checked output
paths are ignored. The expanded in-memory integrity program described above
exited 0. This exact compact inventory program also ran and exited 0; its digest
and pins matched the initial 36-file baseline:

```powershell
@'
from pathlib import Path
import hashlib, json
names = [
 'afghanistan_mvp01_review', 'afghanistan_mvp02b_selections',
 'afghanistan_mvp02b_comparison', 'afghanistan_epz_diagnostic_run01',
 'afghanistan_epz_diagnostic_run02', 'afghanistan_mvp03_api_pre_03',
 'afghanistan_mvp03_api_post_01']
root = Path('outputs')
pins = {}
for name in names:
    for p in sorted((root/name).rglob('*')):
        if p.is_file():
            b = p.read_bytes()
            pins[p.relative_to(root).as_posix()] = {
                'size_bytes':len(b), 'sha256':hashlib.sha256(b).hexdigest()}
encoded = json.dumps(pins,sort_keys=True,separators=(',',':')).encode('ascii')
print(json.dumps({'files':len(pins),'inventory_sha256':hashlib.sha256(encoded).hexdigest(),'pins':pins}))
'@ | & '.venv/Scripts/python.exe' -B -
```

Only this document was written, using `apply_patch`. Final standard-library
Markdown verification passed: all 11 numbered sections and all three local links
were present, code fences balanced, final newline present and no trailing
whitespace. `git diff --check` exited 0; because the report is untracked, its
whitespace was also checked directly. Final `git status --short --branch` showed
only `?? docs/day5_e2e_hitl_readiness_audit.md`. The repeated 36-file inventory
matched every original size/hash and the digest above. No pytest or scientific
validation ran. No implementation, dependency,
selection/authorization record, existing evidence/checkpoint, API call, secret
access, numerical experiment, commit, tag, push or PR was made.

Stop point: **Scientific & Security Review**. Remaining blockers are the EPZ
Agent interface, prospective handoff/approval records, independently reviewed
security prerequisites and the researcher's future input binding/execution.

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```

**Single smallest next implementation step:** after separate researcher approval,
add one bounded Post-Spatial-only tool that validates and retrieves a pinned saved
EPZ Diagnostic V1 report, with focused offline integration/isolation tests. Keep
all accepted outputs unchanged and stop for review before any live E2E run.
