# MVP-03 Live Post-Spatial Readiness Review

Date: 2026-11-17. Checkpoint: `7a84225`, tag
`mvp03-live-pre-spatial-v1`, branch `agent/day5-controlled-host`.

**Verdict: GO for technical readiness for one separately researcher-authorized,
read-only live Post-Spatial evaluation. No blocking defect was identified. Proceed
with the existing implementation; no new functionality or budget increase is
required.** This audit does not authorize or initiate that evaluation, protected
scientific computation, or any subsequent action.

## Sources inspected

Required repository files:

- `docs/day5_mvp03_live_pre_spatial_review.md`
- `docs/day5_mvp03_evaluation.md`
- `docs/day5_mvp02b_execution_scope.md`
- `src/agent/scientific_evidence_tools.py`
- `src/agent/scientific_review_agent.py`
- `examples/run_afghanistan_mvp_agent.py`
- `tests/agent/test_scientific_review_agent.py`

Also inspected the handoff, reused saved-bundle/array validation helpers in
`examples/select_afghanistan_mvp_window.py` and
`examples/compare_afghanistan_mvp_spatial.py`, and relevant regression fixtures.
The older execution-scope/evaluation documents record earlier milestones; their
archived execution commands were not treated as instructions or authorization.

Read the six fixed MVP-01 files under `outputs/afghanistan_mvp01_review/`, both
selection records under `outputs/afghanistan_mvp02b_selections/`, and the fixed
comparison summary/report, experiment summaries, copied selections, execution
status records, spatial arrays, difference array and plot bytes under
`outputs/afghanistan_mvp02b_comparison/`. Plots were hashed, not regenerated or
visually re-reviewed. Recorded external raw-GIM/TEC/catalog/code paths were not
opened. No missing evidence was reconstructed.

Run 03's saved output pins and Agent code hash were also checked. Its unchanged
status is `submitted_for_researcher_review`, outcome `valid_first_submission`;
the current Agent module matches its recorded code hash. That establishes a
Pre-Spatial baseline, not successful Post-Spatial reasoning or live self-correction.

## Real saved-evidence validation

Called the existing `EvidenceTools('outputs', 'post_spatial')` interface:

```text
temporal_historical = validated_snapshot
spatial = validated_snapshot
fixed-file snapshots checked = 23
```

The existing validator passed artifact SHA-256/size checks, parent bindings,
selection-copy equality, saved source-declaration matching, UTC windows,
canonical 71-by-73 arrays, integral count bounds, count/ratio consistency, peak
summaries, saved reference checks and cell-wise B-minus-A consistency. All six
Experiment A historical checks match. Source snapshots were rechecked after
inspection. These checks inspect saved results and repeat contract arithmetic;
they do not execute Framework A, B, C or D.

| Saved observation | Experiment A | Experiment B |
| --- | --- | --- |
| Selection basis | Researcher-saved independent historical reference | Researcher-saved Cluster 1 candidate |
| Inclusive UTC start | 2022-05-28 00:00 | 2022-05-28 00:00 |
| Inclusive UTC end | 2022-06-01 23:00 | 2022-06-02 23:00 |
| Target hours / ratio denominator | 120 | 144 |
| Negative global peak (%) | 85.0 | 71.52777777777779 |
| Negative global peak grid | (30.0, 70.0) | (30.0, 70.0) |
| Negative occurrences at that peak | 102 | 103 |
| Nearest grid to confirmed epicenter | (32.5, 70.0) | (32.5, 70.0) |
| Negative occurrences at nearest grid | 95 | 96 |
| Negative ratio at nearest grid (%) | 79.16666666666666 | 66.66666666666666 |
| Positive global peak (%) | 10.0 | 8.333333333333332 |

Positive peak coordinates also remain unchanged: (-22.5, -155.0) and
(-22.5, -150.0). The global negative peak and nearest epicentral grid differ.
Negative count differences span 0..19 with 3,712 changed cells; positive count
differences span 0..7 with 124 changed cells. Initial-reference finite-input
differences are zero across the grid. These numbers were obtained through the
validated saved evidence, not substituted from the request.

The saved comparison records Cluster 0 as
`valid_candidate_not_selected_for_this_comparison`; its only experiments are A
and B. This supports “Cluster 0 was not executed in this A/B comparison,” not a
claim about every possible research run. The selections remain researcher
records, not Agent-generated execution choices or authenticated human approvals.

## Tool-interface findings

| Post-Spatial tool | Input contract | Result meaning |
| --- | --- | --- |
| `get_spatial_experiment_summary` | Exact `experiment` key; A or B only | Saved selection origin, window, parameters, fixed denominator, global peaks and reference checks |
| `compare_spatial_experiments` | Empty argument object | Whole-grid B-minus-A statistics, denominator pair and peak-coordinate stability; ratio differences are percentage points |
| `inspect_spatial_grid_cell` | Exact numeric latitude/longitude keys; finite values in [-90,90]/[-180,180]; booleans rejected | Requested coordinate, nearest actual saved coordinate, both experiments' counts/ratios/denominators and cell differences |

Nearest-grid selection uses the saved ascending coordinates, absolute latitude
distance and circular longitude distance; first index wins ties. It does not
interpolate or apply a second legacy latitude flip. Counts are occurrences,
ratios are percentages divided by all target hours, and differences have the
explicit direction B minus A. Some saved count values serialize as integer-valued
floats; the model must preserve exact JSON values/types in checked facts.

Effective detector-valid counts remain `null`. Finite-input counts are availability
diagnostics, not substituted detector counts or ratio denominators. Kp, Dst and
F10.7 remain unavailable. Historical observation quality and interpolation history
are explicitly `unknown` in the historical tool.

All three spatial tools are absent from the Pre-Spatial allowlist and returned
`tool_not_allowed` there. Four real-interface invalid-argument checks also returned
`invalid_arguments`. The inspected outputs are compact, JSON-serializable
`ok/data/sources` objects; the existing loop sends their JSON strings as function
outputs. Observed payloads were 1,198..2,413 bytes for the illustrative comparison
path, below the 24 KiB per-tool cap.
No model-accessible function executes D, modifies selections or grants authority.
Input-schema and provider-loop mock tests remain the compatibility evidence;
numeric spatial calls have not yet been tested with a real model.

## Budget sufficiency

Existing limits remain eight tool requests, ten model turns, 128 KiB history and
32 KiB per model response. One meaningful comparison can fit within eight
retrievals: temporal summary, historical context, candidate windows, A summary,
B summary, comparison, global-peak cell and nearest epicentral cell. This covers
selection provenance and missing physical/data-quality context without needing
an additional inventory call. The model remains free to choose its sequence;
this is a feasibility example, not a fixed retrieval pipeline.

That illustrative serialized context measured 18,695 bytes before the final
assessment and actual provider/reasoning items. Each tool payload fits its cap.
Submission on turn nine leaves turn ten for the existing single assessment-only
correction, if needed and if history capacity remains. Provider transport retries
remain zero. Actual model overhead, redundant calls or inefficient choices may
still cause bounded abstention; no blocking budget defect was demonstrated.

## Scientific acceptance criteria for the future live run

The researcher should check exact cited observations and the interpretation:

1. Distinguish the global maximum from the nearest epicentral grid; do not imply
   they coincide or infer seismic origin from geographic proximity.
2. Distinguish counts from ratios: occurrences can increase while the fixed-hour
   ratio decreases. A lower ratio alone does not show disappearance.
3. Retain the separate 120-hour and 144-hour denominators; do not replace them
   with finite-input counts or unknown detector-valid counts.
4. Preserve the independent historical reference and deterministic daily-policy
   candidate as separate methodological outputs. Neither window was selected by
   the current LLM, and neither is automatically optimal.
5. Separate observed spatial patterns and window sensitivity from physical
   attribution. Missing Kp/Dst/F10.7 cannot establish storm or earthquake causation.
   Global statistics and two grid queries do not establish full spatial coherence.
6. Separate source-hash consistency from raw-source custody, observational quality
   and original interpolation history. State remaining uncertainties and scope
   Cluster 0's non-execution to this comparison.

Accept only exact, existing citations/values as observed facts; keep interpretations
and alternatives separate and subject to researcher review. Earthquake causality,
validated precursors and predictive performance are not supported. The current
checks reject or flag recognized unsupported claims, but do not prove semantic
entailment or catch every paraphrase. Human-readable table formatting does not
relax exact-value checking; model facts must use the inspected JSON values/types.

## Focused tests

Executed existing synthetic Agent tests and pure window/planning regressions:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_explicit_window.py tests/workflow/test_temporal_window.py tests/workflow/test_window_planning.py -q -p no:cacheprovider
```

Agent tests: **99 passed**, 175.15 s. Workflow regressions: **86 passed**, 10.25 s.
No pre-existing or new test failure was observed in these runs.
No full suite was used. `test_planning_evidence.py` was not executed as a suite
because its temporal fixtures run Framework A; importing its hand-authored
historical fixture does not execute those tests. Agent fixtures use synthetic
saved classifications/arrays and injected fake clients, not scientific executors
or a live provider. Their temporary test artifacts are not research experiments.
FakeModel results verify contracts and safety, not genuine LLM reasoning.

Read-only real-evidence inspection also used runtime tripwires against detector,
spatial, B+C, Stage 2, authorization and network execution. No model adapter or
scientific executor was invoked. Artifact existence and all rechecks passed.

## Proposed live command — review only, NOT executed

This reuses Run 03's recorded explicit model. Credentials remain under researcher
control. The proposed output directory was absent during inspection; use a fresh
directory at execution time. No directory or experimental output was created now.

```powershell
.\.venv\Scripts\python.exe -B -m examples.run_afghanistan_mvp_agent --live --mode post_spatial --model gpt-6-luna --evidence-root .\outputs --output-dir .\outputs\afghanistan_mvp03_api_post_01 --question 'Using only validated saved evidence, compare A and B. Distinguish global peaks from the nearest epicentral grid, counts from ratios and their denominators, the independent reference from the generated candidate, observed patterns from physical attribution, and source integrity from observation quality. State missing physical evidence and whether Cluster 0 was included in this A/B comparison. Cite exact inspected values; recommend a next scientific action or abstain where evidence is insufficient.'
```

## Implementation recommendation and remaining limits

**No implementation changes are required before the first live Post-Spatial run.**
Preserve the current checkpoint, evidence, budgets and read-only allowlist. The
next step is separate researcher approval and invocation, followed by scientific
review of its actual trace and assessment. Post-Spatial LLM reasoning, live
self-correction, provider availability/usage and interpretation quality remain
unverified by this audit. No provider call was made to test them.

Stored hashes and array consistency do not authenticate origin, revalidate the
original detector's numerical algorithm, or establish current external raw-file
integrity; those recorded paths were deliberately not opened. No plot interpretation,
physical-attribution study or OS-isolation verification was performed. Missing
physical context and retrospective single-event scope remain scientific limits.

Only this report was added. No accepted evidence, source code, test code,
configuration, checkpoint or unrelated file was changed. No Framework A/B/C/D,
Legacy Stage 2, signing, Store or authorization operation was executed. No commit,
push, tag or PR was created.

Windows Local Isolation: **NOT VERIFIED**  
Trusted Human Authorization: **NOT VERIFIED**  
Execution Eligibility: **FALSE**

Stopped after the readiness report. Await separate researcher approval before
Live Post-Spatial Evaluation.
