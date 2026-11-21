# MVP-03 Scientific & Security Review

Implemented a bounded model-controlled, read-only scientific Agent. Offline
verification passed. **No actual LLM was called. Live scientific reasoning and
provider compatibility remain unverified until a separate researcher-invoked run.**

## Files and scope

New files:

- `src/agent/__init__.py`
- `src/agent/scientific_evidence_tools.py`
- `src/agent/scientific_review_agent.py`
- `examples/run_afghanistan_mvp_agent.py`
- `requirements-agent.txt` (optional OpenAI SDK; not installed during this task)
- `tests/agent/__init__.py`
- `tests/agent/test_scientific_review_agent.py`
- `docs/day5_mvp03_evaluation.md`

Existing algorithms, thresholds, evidence schemas, planner, research selections,
MVP-01/MVP-02 outputs, security infrastructure and patch backups were preserved.
The existing 5A review document remains present and unchanged. Work stays on
`agent/day5-controlled-host`; no commit, push or PR was made. No Legacy behavior
changed. Spatial views retain the saved canonical ascending Modern coordinates.

## Model-controlled loop

The model initially receives the question, mode, instructions and tool schemas,
without scientific results. Each response chooses a single tool and arguments.
The host validates the request, returns a bounded result with a sequential result
ID and source hashes, and asks the model what to do next. The model chooses both
retrieval order and when to submit an assessment or abstain. There is no fixed
host retrieval chain. Evidence loading validates snapshots; it does not insert
them into the model context. The fake adapter is explicitly an offline double.

The optional OpenAI adapter uses Responses API function calls with an explicit
researcher-configured model, `store=False`, and `parallel_tool_calls=False`.
It replays all response output items in memory, including opaque reasoning
continuation items, followed by function-call outputs. Hidden reasoning is not
written into the trace. Response IDs, returned model IDs, usage, calls, rejected
requests and tool results are recorded. Provider exception text is suppressed.
Injected test clients are labeled offline. This implementation follows the
[official function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)
and [conversation-state guide](https://developers.openai.com/api/docs/guides/conversation-state).

The live model must support these tool and continuation options; unsupported
models fail to an abstention without substituting another model. The SDK is
lazy-imported, and imports, ordinary tests and evidence inspection make no API
calls. No model identifier was supplied by the researcher, so none was guessed.

## Read-only tools and information boundary

| Tool | Arguments | Modes |
| --- | --- | --- |
| `get_evidence_inventory` | none | both |
| `get_temporal_summary` | none | both |
| `inspect_anomaly_interval` | exact UTC `start_utc`, `end_utc` | both |
| `get_historical_context` | none | both |
| `list_candidate_windows` | none | both |
| `get_spatial_experiment_summary` | `experiment`: A or B | post only |
| `compare_spatial_experiments` | none | post only |
| `inspect_spatial_grid_cell` | numeric latitude, longitude | post only |

`submit_assessment` terminates the loop; it is not a scientific execution tool.
Pre mode never reads or checks the spatial/selection roots. Its saved proposals
omit the planner's `selected` field, which is not a researcher execution choice.
No recorded Experiment A/B selection or spatial numerical result enters pre mode.
The published reference retains its separate method and duration.

Post mode exposes recorded selections as researcher records, never Agent choices
or authenticated approvals. Every cell in the saved matrices can be queried;
whole-grid difference statistics summarize the full comparison. Full matrices,
images and catalog event lists are not sent to the model. Coordinate queries
return requested and actual nearest-grid coordinates, both experiments, count
and ratio differences, denominators, and finite-input diagnostics. Longitude
distance is circular; first index wins ties. No interpolation or second latitude
flip is applied. Effective detector-valid counts remain unknown.

Only fixed filenames under the explicit evidence root are read. Recorded raw
GIM/TEC/catalog/code paths remain inert provenance. Hashes, copied selections,
parent bindings, metadata, canonical array shapes/coordinates, count/ratio
relations, peaks and saved B-minus-A arrays/statistics are checked. Recorded
daily source hashes are compared to the original MVP-01 declarations by filename;
raw daily files are not reopened. Existing pure bundle/array validators are
reused. Replaying the saved planning contract does not rerun Framework A, B, C
or D. Source consistency, saved-content consistency and numerical correctness
of the original detector remain distinct claims.

Observed facts must contain exact JSON values at cited pointers inside successful
tool results. Incorrect values/types, absent citations and uninspected candidate
recommendations are rejected or flagged. Numerical narrative and detected causal
or predictive assertions produce a flagged abstention. Inferences and alternatives
retain separate labels and evidence references. These checks do **not** prove
semantic entailment or detect every paraphrased unsupported claim; all scientific
interpretation remains subject to human review.

Operational caps: eight tool requests, ten model turns, 128 KiB conversation,
32 KiB model response, 2 KiB tool arguments, 24 KiB tool response, 2 MiB per source
artifact, 8 MiB uncompressed NPZ, and 168 hours per interval query. NPY headers
are checked before allocating arrays. Questions are limited to 8,000 UTF-8 bytes.
The provider output budget is 4,096 tokens, with no automatic retry. These are
interface limits, not scientific thresholds or CPU/memory isolation guarantees.

## Executed verification

Commands used from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_explicit_window.py tests/workflow/test_temporal_window.py tests/workflow/test_window_planning.py tests/workflow/test_planning_evidence.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -k 'live_adapter or provider_errors or live_cli' -q -p no:cacheprovider
```

Results: **38 Agent tests passed** in 111.89 s; **234 regressions passed** in
10.82 s. After distinguishing injected offline clients in provider metadata, the
affected adapter/error/CLI subset passed: **3 passed, 35 deselected** in 6.68 s.
The initial Agent run had 37 passes and one failed test assertion: it searched
all schema text for the word `spatial`, also matching the guarded terminal-action
enum. The assertion now checks that spatial retrieval tools are absent.

Tests use hand-authored synthetic saved evidence and controllable fake models.
They cover model-dependent retrieval (including a Cluster 0 recommendation),
both modes, exact citations, denominator behavior, nearest-grid distinctions,
invalid/duplicate/nonfinite arguments, interval/output/tool budgets, unsupported
claims, missing/corrupt spatial evidence, repinned false peaks/differences,
changed snapshots, oversized NPY shapes, offline CLI output, fresh directories,
provider error redaction and mocked Responses continuation. The protected-call
sentinel was active. No full suite was run because its protected computations and
authorization operations are outside this task's permitted scope.

Real artifacts were additionally inspected read-only with a protected-call
sentinel. An initial overly broad sentinel also blocked the existing evidence
validator's inert `TemporalAnomalyResult` constructor; it was narrowed to block
detector execution while allowing contract validation. The completed inspection
performed no A/B/C/D calculation, Stage 2, signing, Store or authorization operation.

## Two-mode evaluation

Final CLI runs, using explicit fake scripts only:

```powershell
.\.venv\Scripts\python.exe -B -m examples.run_afghanistan_mvp_agent --mode pre_spatial --evidence-root outputs --output-dir outputs/afghanistan_mvp03_offline_final/pre_spatial --fake-script outputs/afghanistan_mvp03_offline_evaluation/pre_spatial_fake_script.json
.\.venv\Scripts\python.exe -B -m examples.run_afghanistan_mvp_agent --mode post_spatial --evidence-root outputs --output-dir outputs/afghanistan_mvp03_offline_final/post_spatial --fake-script outputs/afghanistan_mvp03_offline_evaluation/post_spatial_fake_script.json
```

Both returned `submitted_for_researcher_review`, with `live_model_called: false`.
That status means structural submission, not scientific acceptance. Each directory
contains `agent_request.json`, `agent_trace.json`, `scientific_assessment.json`,
`scientific_assessment.md` and `run_record.json`, with source and code fingerprints.
The initial adaptive fake harness, scripts and evaluation metadata are also under
`outputs/afghanistan_mvp03_offline_evaluation/`. All these outputs are local-only
and ignored by Git. The final CLI output directories must not be reused.

Example fake pre trace:
`get_evidence_inventory` → `get_temporal_summary` → `get_historical_context` →
`list_candidate_windows` → `inspect_anomaly_interval` → `submit_assessment`.
Example fake post trace: temporal → historical → A summary → B summary → full-grid
comparison → global peak cell → epicentral nearest cell → inventory → submission.
The adaptive fake obtained peak-query coordinates from the returned peak summary.
These are test scripts, not demonstrations of genuine LLM reasoning.

| Evaluation | Observed offline result | Live LLM evaluation |
| --- | --- | --- |
| Pre information boundary | six MVP-01 files only; spatial calls rejected | pending |
| Candidate comparison | Cluster 0: 72 h; Cluster 1: 144 h; original reference: 120 h, separately preserved | pending |
| Temporal evidence | 744 hours; positive 37, negative 97, normal 610, missing/unclassifiable zero | pending |
| Historical context | historical anchors, mixed polarity and silhouette exposed separately from the 2022 case | pending |
| Post source/content checks | 23 fixed-file snapshots validated; saved selections unchanged | pending |
| Numerical grounding | seven pre and sixteen post facts checked against inspected tool data | pending |
| Denominator and coordinate distinctions | directly accessible and represented in fake assessment | pending |
| Missing physical evidence | Kp, Dst, F10.7 explicitly unavailable | pending |
| Causal/predictive restraint | adversarial assertions rejected/flagged; hypotheses labeled for review | pending semantic evaluation |

Values below were read from validated saved arrays, not substituted from the
request or used as Agent decision constants:

- A global positive maximum 10%; negative maximum 85% at (30, 70).
- B positive maximum 8.333333333333332%; negative maximum
  71.52777777777779%; both polarities retain their global peak coordinates.
- At the global negative peak: 102/120 versus 103/144 occurrences per target hours.
- At the nearest epicentral grid (32.5, 70): 95/120 (79.16666666666666%) versus
  96/144 (66.66666666666666%). The confirmed event and scientific input coordinates
  remain separately reported.
- Negative count differences span 0..19 across 3,712 changed cells; positive
  differences span 0..7 across 124 changed cells. Initial-reference finite-input
  differences are zero everywhere. All six saved A historical checks match.

A lower fixed-duration ratio can coexist with increased counts; it does not by
itself show disappearance. Broad grid changes and stable global peaks do not
identify an earthquake cause. Storm attribution requires actual physical indices.
This retrospective single-event comparison establishes no predictive performance.

## Remaining prerequisites and first live run

The OpenAI SDK and API credentials are not configured in this environment. Install
`requirements-agent.txt` separately and configure `OPENAI_API_KEY` securely. The
researcher must set `SCIENTIFIC_AGENT_MODEL` to an actual model identifier with the
required function-calling/continuation capabilities. No default model is provided.

Proposed first explicit live command (not executed):

```powershell
.\.venv\Scripts\python.exe -B -m examples.run_afghanistan_mvp_agent --live --mode pre_spatial --model "$env:SCIENTIFIC_AGENT_MODEL" --evidence-root .\outputs --output-dir .\outputs\afghanistan_mvp03_live_pre_spatial_01
```

Start with pre mode to evaluate tool selection without post-result information.
A subsequent separate post-mode evaluation should assess the distinctions above.
Researcher review must examine relevance, cited entailment, alternative hypotheses
and abstention; passing contract checks alone is insufficient.

Hash snapshots are not authenticated origin or trusted custody. Concurrent source
changes are checked before tool exposure and at loop completion, but the interface
is not an OS sandbox. External provider confidentiality, model nondeterminism,
semantic errors, process resource isolation and incomplete original observation
quality remain limitations. There are no execution tools, arbitrary model-supplied
paths, shell commands, executable callbacks, signing keys or authorization Stores.
Future scientific execution must independently recheck raw input integrity and
obtain the applicable researcher authorization; Agent output cannot supply either.

**Windows Local Isolation: NOT VERIFIED**  
**Trusted Human Authorization: NOT VERIFIED**  
**Execution Eligibility: FALSE**

Stopped at Scientific & Security Review. MVP-03 is ready for researcher review of
the implementation; it is not fully live-validated.
