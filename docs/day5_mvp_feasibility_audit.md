# Day 5 — Scientific AI Agent MVP feasibility audit

2026-11-03 (Asia/Taipei). **MVP Feasibility Review; implementation approval pending.**

## 1. Executive verdict

**A minimal scientific vertical slice is feasible with the existing algorithms and accessible real data. It is not yet an end-to-end Agent demonstration.** The shortest path is a small Modern-A review example, an explicit researcher selection, and a separately approved extension of the existing Modern-D example. The comprehensive 5B host/codec plan is unnecessary for this local, researcher-controlled slice. No A/B/C/D rewrite, resource registry or new authorization infrastructure is needed.

Current branch: `agent/day5-controlled-host`; HEAD/main are `6911ec9` (Day 4 PR #4). Initial tracked diff was empty; four untracked patch backups were present. The requested `docs/day5_checkpoint5a_controlled_host_review.md` was **absent at audit start**, including from Git's tracked-file listing and the repository filename search. It was neither recreated nor changed; restore the earlier copy separately if archival retention is required. This audit creates only this report.

## 2. Existing component map and exact connections

| Existing output → required next input | Status / smallest connection |
| --- | --- |
| Modern daily NPZ → `TECTimeSeries` → A evidence | **Ready.** [`load_temporal_tec_from_modern_gim`](../src/workflow/modern_temporal_input_adapter.py) already returns the series required by [`dispatch_scientific_request`](../src/workflow/scientific_request.py) / [`run_temporal_review`](../src/workflow/temporal_workflow.py). A small example must compose them and persist results. No scientific adapter change is needed. |
| Historical reproduction-summary V1 → historical evidence | **Ready.** [`load_historical_bc_evidence`](../src/workflow/planning_evidence.py) accepts the actual saved summary. Both local copies passed validation. Consume historical context without rerunning B/C or presenting it as a fresh reproduction. |
| Temporal Evidence V1 + historical evidence + case event/selected clusters → candidate proposal | **Ready.** [`plan_anchor_based_daily_windows`](../src/workflow/window_planning.py), already composed by Day 4 review, provides deterministic proposals or abstention. Researcher-supplied actual UTC event metadata and explicit cluster selection are still required. |
| Candidate proposal → explicit researcher selection | **Needs a small handoff.** Persist proposal/evidence hashes; record selected candidate and exact inclusive bounds, or an independent window plus scientific justification. A choice is review data, not trusted authorization. No automatic selection or anchor-to-window conversion. |
| Explicit selection → Modern D | **Scientific API ready; execution blocked in this audit.** [`select_explicit_window`](../src/workflow/explicit_window.py) returns the aware-UTC `TemporalWindow` accepted directly by [`run_spatial_verification_from_modern_gim`](../src/workflow/modern_spatial_input_adapter.py). It takes an explicit daily-file list, reference days and k. A small researcher-side example must connect the saved selection and actual files after separate execution approval. |
| Day 4 artifacts → Preparation Manifest / Legacy Stage 2 | **Incompatible without extra packaging; unnecessary for the first slice.** [`PreparationManifest` V1](../src/workflow/preparation_manifest.py) requires temporal-plot and clustering-summary relative paths. [`export_preparation`](../src/workflow/preparation_export.py) requires a `PreparationWorkflowRunResult`, not Day 4's three dictionaries. Do not manufacture that result or rename the historical summary as clustering-summary V2. |
| Modern D result → maps + scientific report | **Needs case-level assembly.** [`reproduce_afghanistan_spatial_visuals.py`](../examples/reproduce_afghanistan_spatial_visuals.py) already calls Modern D, plots with `grid_orientation="canonical"`, and exports correct peaks. Parameterize this example; retain numeric arrays, selection/provenance and a short report. Its current peak JSON alone is not a full reproducibility record. |

### Why the existing Stage 2 runner cannot simply receive Modern files

[`run_stage2`](../src/workflow/stage2_runner.py) calls [`run_spatial_verification_workflow`](../src/workflow/spatial_verification_workflow.py), which validates a Preparation Manifest and its two artifact files, then calls the Legacy [`spatial_adapter`](../src/workflow/spatial_adapter.py). That loader expects `gimYYYYDDD.npz` under its Legacy year-directory convention, with `gim`/`gim_time`, flattened grid rows and 0.1-TECU scaling. Modern `codgDDD0.22i.npz` has `tec`/`epochs`/`lat`/`lon`, 25 maps and TECU units. The Modern bridge selects each day's own 00–23 hours and returns ascending physical latitude.

The result objects also differ: Modern D returns `SpatialAnomalyResult`; the Stage 2 exporters require `SpatialVerificationWorkflowResult` containing a manifest. Moreover, `export_spatial_plots` supplies no orientation argument, while `run_stage2` does not forward `grid_orientation="canonical"` to the summary exporter; their defaults are Legacy. Swapping only the loader would risk a second latitude flip. Keep the Legacy pathway unchanged and use the already established Modern example for the first approved slice. A unified Modern Stage 2 interface can follow later.

[`run_preparation_workflow`](../src/workflow/preparation_workflow.py) genuinely recomputes B/C from original hourly inputs and currently uses the Legacy temporal loader for A. It remains useful for that existing pathway, but running it merely to obtain a manifest adds unnecessary work and does not solve the Modern connection.

## 3. Real-data readiness and observed checks

The following are accessible now; no replacement data or downloads are needed:

| Input/artifact | Read-only observation / validation scope |
| --- | --- |
| Original saved `I:\IRSL\GIMTEC_interpolation_py\Afghanistan19990101_20211231\tec33.092_69.514.npy` | 1,613,120 bytes; float64 `(201624,1)`; all 201,624 values finite, range 0.7–118.9. SHA-256 matches the handoff's `4c642c…f8f3e`. This is original saved TEC, not proof of hourly observations: its UTC timeline is assigned and interpolation history is unknown. |
| Original `eqlist.npy` in that directory | 59,408 bytes; float64 `(741,10)`; SHA-256 matches handoff `07740b…4c136`. Legacy comparison baseline. |
| `C:\Users\Wen\Documents\GitHub\earthquake-data-tools\afghanistan_usgs_filtered.csv` | 152,799 bytes; SHA-256 matches handoff `c78896…cd47b`; existing `load_usgs_earthquake_csv` accepted 741 records. Historical catalog, not the missing 2022 case-event record. |
| `outputs/afghanistan_historical_bc/afghanistan_historical_bc_summary.json` and repeat-directory copy | Each 33,108 bytes; byte-identical SHA-256 `1897b0d1aa7b8781ecbc6e54a84c418f2e70f2aaccd07ac6be6b5f34e443f57d`; both pass the existing evidence loader. Declared source hashes match the originals checked above. Saved comparisons report 74 events, 34 pre-event cells (18 positive/16 negative), cluster 0 Day −8 / positive and cluster 1 Day −22 / negative; silhouette 0.31105623341145205; reference and Legacy comparisons pass. This audit did not recompute B/C. |
| `C:\Users\Wen\Documents\GitHub\gim-data-tools\processed\codg1270.22i.npz` … `codg1720.22i.npz` | All 46 daily files for May 7–June 21, 2022; 9,598,765 compressed bytes total; every TEC member is float64 `(25,71,73)`. Existing Modern loading succeeded for the complete series. Includes the 20 May 13–June 1 files needed for the five-day D reference and the June 2 file needed for the possible longer candidate. These are processed GIM inputs, not raw observations. |
| Existing A plot: `outputs/afghanistan_2022/afghanistan_2022_fig1b_temporal.png` | Present, 489,745 bytes. Fresh non-plotting A check produced 744 analysis hours: **37 positive, 610 valid normal, 97 negative, zero unclassifiable or missing timestamps**; input includes 360 reference hours (1,104 total). Requested grid location (33.02,69.46), selected cell (32.5,70). No new plot was written. |
| Existing D artifacts: `outputs/afghanistan_2022/spatial_corrected/` | Both corrected PNGs and the 850-byte peak JSON are present. JSON records May 28 00:00–June 1 23:00 UTC, reference=15, k=3, canonical orientation; positive 10% at (−22.5,−155)/(−22.5,−150), negative 85% at (30,70). These are prior results, not a fresh D run. |
| Frozen spatial reference / synthetic fixtures | `validation/spatial_verification/reference/afghanistan_spatial_reference.npz` exists with four `(71,73)` numeric matrices, coordinates and window-hours metadata. It is a saved regression reference. Tests' hand-authored historical summaries and tiny grids are synthetic; they are not evidence that the real-data composition has run. The seven-day modern historical reconstruction under `outputs/` is optional archival output, not a replacement for original TEC. |

No complete Day 4 real-case evidence/proposal bundle, Preparation Manifest or end-to-end run record was found under the current `outputs/` tree. The inspected 2022 examples/peak JSON contain location/magnitude and analysis bounds, but no sourced case-event ID and exact UTC origin time. **Researcher action:** supply/confirm that event record and source, cluster IDs to evaluate, and later the selected D window; do not infer the event time from the analysis endpoint or use a local-date label as UTC. No missing TEC/catalog attachment is currently required.

## 4. Material scientific difference: candidate versus reference window

Fresh A evidence aggregation confirms these days have all 24 hours present and classifiable:

| UTC date | Positive / negative hours |
| --- | --- |
| May 27 | 1 / 0 |
| May 28–June 1 | 0 / **18, 16, 24, 20, 17**, respectively |
| June 2 | **0 / 1** |
| June 3 | 0 / 0 |

Consequently, if the researcher-confirmed UTC event maps the selected negative anchor into this episode, the unchanged daily-expansion rule would include **May 28 00:00–June 2 23:00 (144 hours)**. This is an inference from inspected policy and freshly validated daily evidence, **not an executed event-bound proposal**. No event time was invented. It differs from the prior **May 28–June 1 (120-hour)** D reference. Do not clip it, change the one-anomaly rule, or expect the five-day D percentages for six days. The researcher may select the five-day interval independently with an explicit reason, or select the actual proposal and assess its different results. Both routes must retain the discrepancy and derivation.

## 5. Minimum implementation plan and acceptance

| Priority / exact file(s) | Smallest work and dependency | Acceptance / data / approval |
| --- | --- | --- |
| **P0.1 — next task:** proposed `examples/review_afghanistan_mvp.py`, `tests/workflow/test_review_afghanistan_mvp.py` | Compose the existing Modern temporal loader → Day 4 dispatcher. Accept explicit researcher-owned case metadata, NPZ paths, historical summary and selected cluster IDs. Save unchanged temporal evidence, historical context and proposal, plus a small input/hash/parameter run index, into a fresh local-only directory; refuse overwrite. No D or authorization imports/calls. Depends on the sourced event record, not on a new host infrastructure. | Synthetic adapter tests: dispatcher parity, abstention, invalid UTC/cluster IDs, no-overwrite and forbidden calls. Then real-data review-only run: the 744-hour counts above, deterministic evidence/proposal hashes, and visible five-/six-day difference if applicable. Coding and real review run await approval of this bounded task; D remains excluded. |
| **P0.2 — selection and approved Modern result/report:** `examples/reproduce_afghanistan_spatial_visuals.py`, proposed `tests/workflow/test_afghanistan_mvp_selection.py` | Add explicit selection/review-bundle inputs and configurable paths to the existing Modern example; record candidate linkage or independent justification. Reuse `select_explicit_window`, Modern D and canonical plotting/peak extraction. Save numeric count/ratio arrays, source/selection hashes, parameters/environment, maps, peak summary and a concise case report/index without inventing a Preparation Manifest. The selection is not a credential; keep this a researcher-side invocation. | Synthetic tests with D/plot calls replaced by harmless stubs: stale binding, independent rationale, UTC bounds, canonical orientation and no-overwrite. **Actual D and corresponding regression execution need separate researcher-approved scope and applicable security prerequisites.** For the independently selected five-day reference, verify 120 hours, 5,183 finite cells per map, 10%/85% and exact peak coordinates; for another interval, report rather than force agreement. Real data required for scientific acceptance. |
| **P0 input/decision prerequisite — no code** | Researcher confirms event ID/time/source, reviewed cluster selection and exact D interval/justification. Retain both the proposal and the human choice. | A missing/ambiguous event blocks real candidate planning; no selected/approved execution scope blocks D. A review declaration cannot change execution eligibility. |
| **P1 — actual LLM orchestration and evaluation** | After P0, add one minimal orchestration example using structured evidence and fixed permitted actions: inspect evidence, request a review, propose a selection for human review, or abstain. Record model/configuration, objective, action arguments, explanations, tool results and failures. Researcher-owned acquisition and protected execution remain outside Agent control. | Demonstrate real model-dependent action selection, including an abstention/failure case and the reference-window discrepancy. Replay scientific tools deterministically; evaluate scientific constraints and failure handling, not exact prose or a prewritten action sequence. A fixed pipeline does not qualify. Implementation/model use needs its own reviewed scope. |
| **P2 — deferred** | Comprehensive 5B codec/service host, generic registry/plugins, unified Modern Stage 2/manifest packaging, multi-case deployment and additional authorization infrastructure. | Not dependencies for the local P0 review slice. Revisit only when service exposure or deployment requires them; existing restrictions remain effective. |

### Three distinct completion levels

- **Level 1 — Scientific vertical slice:** real A + existing historical context → reproducible proposal/abstention → explicit documented researcher selection → separately approved Modern D → linked scientific artifacts/report. The path is identified here; Level 1 is not completed by this audit or a no-D preview.
- **Level 2 — Minimal Agent orchestration:** an actual LLM makes permitted evidence-aware action choices or abstains, with complete action/result/failure traces. P0 alone does not satisfy this level.
- **Level 3 — Controlled end-to-end demonstration:** execute the complete permitted task with real inputs, reproducible outputs, reviewed decisions, and explicit approval at protected boundaries; satisfy the security prerequisites for the chosen execution scope. Neither a saved approval field nor this audit establishes trusted human authorization or Windows isolation.

## 6. First dry run and approval boundary

The **first dry run is P0.1 only**, not a D run: use the 46 explicit Modern files, 2022-05-22 00:00–2022-06-21 23:00 analysis, 15 reference days, k=3, existing saved B+C summary, and researcher-confirmed event/cluster inputs. Acquire the series with the existing naive-UTC Modern adapter and declare `naive_utc` explicitly to V1. Keep historical and event dates distinct.

Expected artifacts in a new ignored `outputs/` directory: request/run index with ordered input hashes, `temporal_evidence.json`, `historical_context.json`, and `window_proposal.json`; a short review note may identify the pending selection and reference discrepancy. **No Framework D result is expected.** The future script must preserve V1 serialization/digests and never overwrite the validated folders.

Repeat into a second fresh directory: compare input hashes, detector settings, hourly counts, evidence/proposal content hashes and candidate bounds/abstention reasons. Keep volatile run timestamps outside canonical scientific comparisons. Ordered Modern filenames plus their SHA-256 values, joined by a space per line with final LF, had manifest SHA-256 `8901d9d6974d3fc3b303012faa4b07893115e145a6e0e421553a71caa85e1611` in this audit. Record code/dependency versions too.

Stop for researcher review before P0.2 execution. A future selection should bind the exact proposal/evidence and source inputs, identify proposed versus independent bounds, explain differences, and retain pending execution status. Only a separately approved scientific execution path may run D; exposing the bare Modern API to an Agent is not an approved shortcut. No Windows provisioning or new authorization system is implied by the local MVP plan.

## 7. Executed checks, limitations and remaining risks

Executed existing read-only diagnostic:

```powershell
.\.venv\Scripts\python.exe -B -m examples.review_afghanistan_framework_d_windows
```

Exit 0: the script's 744-hour / 37-positive / 610-normal / 97-negative checks passed. Additional read-only Python stdin checks (`.\.venv\Scripts\python.exe -B -`) used NumPy metadata/finite-value inspection, SHA-256, `load_usgs_earthquake_csv`, `load_historical_bc_evidence`, `build_temporal_evidence` and `aggregate_temporal_days`; results are recorded above. One exploratory metadata command failed before its reads because it named nonexistent `load_filtered_earthquake_catalog`; rerunning with the actual `load_usgs_earthquake_csv` succeeded. No scientific code was changed to resolve it.

Test inventory inspected: `tests/test_modern_gim_loader.py`, `tests/test_modern_spatial_input_adapter.py`, and workflow tests for scientific requests/review integration, evidence/planning, preparation contracts, Stage 2 and spatial exporters. They cover separate components; the missing real-case connection is not already an end-to-end Agent test. **No pytest suite was run in this audit.** Some existing tests actually invoke D, Stage 2 or authorization operations; those were not run. No fresh D equivalence, full-suite pass, new B/C reproduction, or candidate-selection result is claimed.

Material remaining risks: the unsourced exact case time can shift anchor mapping; the six-day policy differs from the five-day reference; prior peak JSON lacks input hashes/environment and full matrices; Modern plotting must explicitly remain canonical; historical source/interpolation limits and retrospective/causality limits remain. A local fixed case reduces immediate integration scope but provides no OS containment or trusted authorization. Coastlines may require local Cartopy/Natural Earth resources; the numerical/report core must not depend on an automatic download. Saved images were inventoried/hashed, not visually re-approved here.

Final preservation checks: tracked diff remains empty; only this new report joins the original four untracked patches. Their SHA-256 values and all seven existing output-file hashes remain unchanged. No production/test code, datasets, frozen references, branch references, authorization state or deployment configuration were modified. No commit, push or PR was created.

## 8. Bounded next task

**The smallest next code change is `examples/review_afghanistan_mvp.py` plus focused synthetic tests: load the existing Modern series, call the unchanged Day 4 dispatcher with the real B+C summary and explicit researcher metadata, and export a reproducible review-only bundle.** This connects existing scientific interfaces immediately, exposes the actual candidate/reference difference, and supplies the evidence a researcher and later LLM can inspect. It does not require implementing the comprehensive 5B host.

Stop at MVP Feasibility Review and await researcher approval.

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```
