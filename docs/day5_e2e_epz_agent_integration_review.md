# E2E-02A: EPZ read-only Agent integration review

Date: 2026-11-18 (Asia/Taipei). Scope: one saved-evidence retrieval tool and
offline verification. No live Agent, Framework D, EPZ generation or E2E run.

**Offline technical verdict: PASS within this scope.** Live EPZ use by a model
and continuous E2E operation remain untested; researcher acceptance is pending.

## Changes and interface

Task changes:

| Path | Change |
| --- | --- |
| `src/agent/epz_evidence.py` | Case-specific V1 saved-report validation and compact projection; no generator import or geometry calculation. |
| `src/agent/scientific_evidence_tools.py` | One new Post-Spatial tool, optional pinned host binding, snapshot rechecks and reparse-point rejection. |
| `src/agent/scientific_review_agent.py` | Use binding-aware advertised tools; protect the bound diagnostic directory from run outputs and record host binding/reader fingerprint. Assessment validation and budgets unchanged. |
| `examples/run_afghanistan_mvp_agent.py` | Optional diagnostic/path/hash/size CLI binding; invalid bound evidence stops before model-client creation. |
| `tests/agent/test_epz_evidence.py` | Hand-authored synthetic reports, existing synthetic spatial fixtures, FakeModel and forbidden-execution/network sentinels. |
| `docs/day5_e2e_epz_agent_integration_review.md` | This review. |

The pre-existing untracked `docs/day5_e2e_hitl_readiness_audit.md` belongs to the
preceding task and is preserved unchanged. No scientific implementation, saved
selection, experiment summary, array, diagnostic, live run record or checkpoint
was modified. Work remains on `agent/day5-controlled-host`; no commit/tag/push/PR.

The only added model tool is `get_epz_diagnostic_summary({})`. It accepts no
arguments. Existing Post-Spatial tools remain available, including the separate
nearest-grid lookup needed to distinguish the global peak from the nearest
epicentral sample. No execution, selection, authorization or radius-selection
capability was added.

Host API:

```python
EvidenceTools(
    evidence_root, "post_spatial",
    epz_diagnostic="afghanistan_epz_diagnostic_run01/diagnostic.json",
    epz_sha256="d0e7d0e2127ba66599b9dd0a808be1b1cc0add5ecae2902fae09bcbbc952c1b4",
    epz_size_bytes=23441,
)
```

Equivalent optional CLI flags are `--epz-diagnostic`, `--epz-sha256` and
`--epz-size-bytes`; supply all three. The path is an ASCII relative JSON identity
under the host-controlled evidence root, with forward slashes. Traversal,
absolute/drive/UNC paths, alternate data streams, unsupported extensions,
redirected components and Windows reparse points are rejected. Bound-root
ancestors are also checked for redirection. Existing file/path controls remain
subject to local file custody and race limitations.

Pins must come independently from the researcher's reviewed artifact identity;
computing a file hash and presenting it as approval is not supported. The code
checks supplied pins against bytes; it does not authenticate the person supplying
them or create an approval record. The accepted saved report's historical
`pending` / `not_authorized` fields remain unchanged and do not grant authority.

## Evidence validation and response

The reader first requires validated temporal/historical and spatial snapshots.
Before parsing the diagnostic it checks its host-supplied SHA-256 and byte size.
It then checks:

- Exact V1 type/schema, case/event, canonical axes/orientation, A/B window and
  selection identities, 120/144-hour denominators and scientific parameters.
- Exact 23-artifact source hash/size map against the existing spatial evidence;
  original raw scientific paths remain inert and are never reopened.
- The accepted case-specific V1 reference, three-center mask fingerprint,
  unique ordered canonical indices, saved distance/margin and membership
  consistency, included/excluded boundary points and shared peak distances.
- Per-center counts, percentages and availability against saved arrays; global
  peaks/ties/membership, regional sums/means/ranges, signed B-minus-A cell changes
  and aggregate changes against validated saved differences.
- Exact descriptive units, scientific caveats, null effective detector-valid
  counts, source-scope declarations and historical generator metadata shape.

The accepted radius and mask fingerprint are explicit **V1 contract constants**
from the validation checkpoint, not new scientific thresholds or a general EPZ
algorithm. The reader reconstructs mask bytes from the saved indices for a hash
comparison and performs bounded consistency arithmetic on saved observations.
It does not calculate haversine distances, derive a new radius, search for new
members or call the diagnostic generator. Saved distance accuracy and geometric
completeness rely on the accepted V1 reference and independently reviewed report
pin; no new independent geometry validation is claimed.

Historical generator fingerprints are validated as declarations and never opened
as paths or compared to current source bytes. Accepted older diagnostics remain
valid when the evidence reader changes. New Agent run records separately pin
`epz_evidence.py`, the existing reader, model loop and CLI; they also retain the
explicit host binding and diagnostic source snapshot.

The response contains confirmed event/location, reference definition, grid
resolution, shared mask/centers/distances, both experiments' positive/negative
global peaks, per-center observations, original denominators, regional summaries,
signed changes, limitations, missing Kp/Dst/F10.7, diagnostic identity/pin and
relevant saved-source citations. Full axes and generator/code-provenance maps
are omitted from the model projection. No recommendation, causal interpretation,
association score or approval is constructed.

Malformed binding declarations raise `ValueError` before file acquisition.
Missing, corrupt, stale, inconsistent or pin-mismatched bound evidence is marked
`unavailable_or_invalid`; the tool returns `evidence_unavailable`. The CLI refuses
such a bound run before constructing a live or fake model. Changes after snapshot
acquisition produce `evidence_changed`; oversized responses produce
`tool_output_limit`. There is no repair, regeneration or retry.

## Isolation, compatibility and budgets

Pre-Spatial excludes the tool and rejects any explicit EPZ binding, including a
partial binding, before resolving/probing paths. Without a binding it reads only
its six original temporal/historical files and exposes no selection/spatial/EPZ
content or EPZ availability, even with a valid diagnostic under the same root.

Unbound Post-Spatial retains its original two availability statuses and 23
snapshots, does not probe an EPZ path, and advertises exactly the original eight
evidence tools. Invalid or unavailable bindings also omit EPZ advertising. Only
a validated, pinned binding adds the ninth tool. Direct unavailable EPZ calls
still fail safely. This preserves the diagnostic generator's existing unbound
offline-loader contract. A bound valid run adds one diagnostic snapshot and its
availability state.

No budgets were raised: eight evidence calls, ten model turns, two assessment
submissions with at most one assessment-only correction, 128 KiB history, 32 KiB
model envelope, 24 KiB tool output, 2 KiB tool arguments, 2 MiB files, existing NPZ
expansion/header limits and zero provider retries. Existing exact-value and JSON
Pointer assessment checks are reused unchanged. The new binding is not inserted
into the initial scientific prompt; the model must select the retrieval itself.

## Initial integration verification

No full suite was run: it includes protected operations and is outside this
task's permitted verification scope.

An initial three-case smoke command stopped at collection with one syntax error
in the new reader (a missing bracket), before tests ran. The typo was corrected.
Repeating that command passed **3 tests, 64 deselected in 22.67 seconds**:

```powershell
& '.venv/Scripts/python.exe' -B -m pytest tests/agent/test_epz_evidence.py -k 'approved_projection or fake_loop_exact or cli_fake_binding' -q -p no:cacheprovider
```

The complete focused file passed **66 tests, 1 skipped in 460.38 seconds**:

```powershell
& '.venv/Scripts/python.exe' -B -m pytest tests/agent/test_epz_evidence.py -q -p no:cacheprovider
```

The skipped case attempts an actual filesystem symlink: this account lacks
permission to create one. The separate Windows reparse-attribute simulation
passed. This is an explicit verification limit, not an isolation pass.

Safe existing Agent/window regressions passed **185 tests in 170.33 seconds**:

```powershell
& '.venv/Scripts/python.exe' -B -m pytest tests/agent/test_scientific_review_agent.py tests/workflow/test_explicit_window.py tests/workflow/test_temporal_window.py tests/workflow/test_window_planning.py -q -p no:cacheprovider
```

These retain the original Pre/Post evidence behavior, model-loop validation and
bounded recovery, mocked provider transport, explicit UTC bounds and pure window
planning. Diagnostic-generation tests and the protected full suite were not run.

One additional read-only compatibility check used the accepted saved report and
the independently recorded pin shown above, with framework/diagnostic/Agent/
network execution sentinels. It returned all three statuses `validated_snapshot`,
**24** source snapshots and an **11,415-byte** tool response, below 24 KiB. Saved
negative regional sums were 282 (A) and 285 (B); no new scientific finding is
claimed. The report's old generator fingerprints were accepted unchanged despite
the new reader code. No generator, framework, Agent loop or model ran. The stdin
command used `.venv/Scripts/python.exe -B -` and exited 0.

The new tests use hand-authored synthetic counts and frozen reference geometry;
they never run the EPZ generator. Fixture counts and FakeModel outcomes are not
real Afghanistan findings or genuine LLM scientific evaluations. Forbidden-call
sentinels cover scientific runners, diagnostic generation, live clients and
network calls. They are test controls, not Windows isolation certification.

AST parsing passed for all five changed Python files. `git diff --check` and
direct checks of the new files' whitespace/Markdown structure complete the
document verification; the saved-output inventory is independently rehashed
before handoff. Python used the existing 3.10.6 virtual environment; no dependency
was installed.

## Final compatibility correction

The initial integration advertised EPZ to every Post-Spatial model even when no
validated binding existed. The final correction changes only tool advertising:
`definitions(mode, epz_available=False)` preserves the original base catalogs;
`EvidenceTools.tool_definitions()` opts into EPZ only when the host binding,
validated projection and `validated_snapshot` status are present. `run_agent`
passes that list to the adapter, followed by the unchanged submission tool.
The direct-call dispatch catalog retains the previous safe failure behavior.
Scientific validation, output/assessment schemas, source checks and budgets are
unchanged.

| Evidence state | Evidence tools advertised to adapter | EPZ advertised? |
| --- | ---: | --- |
| Pre-Spatial, valid diagnostic present under the same root | 5 | No |
| Post-Spatial, no binding | 8 | No |
| Post-Spatial, wrong hash or size, missing/invalid report, or invalid spatial sources | 8 | No |
| Post-Spatial, validated researcher-pinned binding | 9 | Yes |

Counts exclude the unchanged `submit_assessment` tool. Tests inspect the actual
schema lists received by a callable `FakeModel` on both retrieval/submission
turns and verify that the correction turn receives only `submit_assessment`.
They deliberately attempt unadvertised calls as well: Pre returns
`tool_not_allowed`, unavailable Post returns `evidence_unavailable`, and valid
Post retrieves the unchanged projection. No actual LLM is involved.

Correction paths: `src/agent/scientific_evidence_tools.py`,
`src/agent/scientific_review_agent.py`, `tests/agent/test_epz_evidence.py` and this
existing review. No CLI or EPZ validator change was needed. An independent
read-only AST/schema comparison with `epz-diagnostic-v1` confirmed exact canonical
JSON equality for the original five Pre-Spatial and eight Post-Spatial tool
definitions, including descriptions and parameter schemas.

Focused adapter-visibility verification passed **9 tests, 66 deselected in
67.07 seconds**:

```powershell
& '.venv/Scripts/python.exe' -B -m pytest tests/agent/test_epz_evidence.py -k 'model_adapter_receives_only_available_evidence_tools or one_new_post_tool_and_no_pre_visibility' -q -p no:cacheprovider
```

Existing Agent regressions plus selected EPZ projection, direct-failure,
budget, citation and provenance checks passed **105 tests in 250.58 seconds**:

```powershell
& '.venv/Scripts/python.exe' -B -m pytest tests/agent/test_scientific_review_agent.py tests/agent/test_epz_evidence.py::test_approved_projection_and_scientific_distinctions tests/agent/test_epz_evidence.py::test_post_without_binding_is_backward_compatible tests/agent/test_epz_evidence.py::test_wrong_independent_pin_fails_closed tests/agent/test_epz_evidence.py::test_tool_arguments_and_output_budget tests/agent/test_epz_evidence.py::test_fake_loop_exact_citations_and_saved_provenance_without_mutation -q -p no:cacheprovider
```

Both correction test commands exited 0 with no failures or skips. The initial
integration's counts above remain historical results; the full EPZ file,
diagnostic generator and full repository suite were not rerun for this narrow
correction. The earlier symlink-creation limitation remains unchanged. Live
model behavior, Windows isolation and authenticated human presence are still
unverified.

Final syntax/whitespace checks passed for the three corrected Python files;
`git diff --check` exited 0. All **83** existing output files retained their
file set, sizes and SHA-256 values, with the inventory digest below unchanged.
The EPZ validator, diagnostic generator, CLI and preceding readiness audit also
retained their correction-start hashes. No scientific outputs, historical Agent
records, checkpoints, schemas or execution restrictions changed.

## Original artifacts and scientific limitations

Before implementation, all **83** pre-existing files under `outputs/` were
inventoried and SHA-256/size pinned in memory. Rechecks retain the same files and
pins. Complete inventory digest (sorted compact ASCII JSON of relative paths to
`{size_bytes,sha256}`, no newline):
`d1cf9f93989a764214b4be3b8b2340569e4f779b336b23e756885c0620e78315`.
Both accepted diagnostic JSON files remain 23,441 bytes, SHA-256
`d0e7d0e2127ba66599b9dd0a808be1b1cc0add5ecae2902fae09bcbbc952c1b4`.

Modern latitude stays ascending; no Legacy flip or fixed A reference changes.
Great-circle grid-center membership remains distinct from historical visual
grid-cell overlap. Three spatially correlated coarse-grid centers do not measure
physical areal coverage or spatial significance. Grid-hour sums are not unique
anomaly hours; regional percentages are unweighted descriptive means. Finite
availability is not an effective-valid denominator. Kp/Dst/F10.7 are unevaluated;
spatial coincidence establishes no causality, precursor or predictive skill.

## Review stop and remaining E2E requirements

Stop after offline Scientific & Security Review. Before any E2E evaluation, the
researcher must review this change, establish the manual request/assessment/
selection/output lineage and explicit human decisions, choose replay versus a
continuous new run, and separately approve evidence sharing and live call scope.
Fresh scientific processing and local D execution need their own researcher
approval and applicable independent security prerequisites. Technical retrieval
and valid citations are not scientific acceptance or execution authorization.

No live model, Framework A/B/C/D, EPZ generation, real E2E workflow, automatic
approval, dependency installation or Git publication was performed in this task.

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```
