# MVP-03 invalid citation recovery — Scientific & Security Review

Date: 2026-11-13. No API experiment was rerun. The original live run remains
`rejected_assessment`; offline diagnostics do not change its scientific status.

## Reproduction

Read `outputs/afghanistan_mvp03_api_pre_01/agent_trace.json` and verified all
artifact hashes against its run record. Before editing code, verified that the
current Agent module matched its recorded SHA-256:
`b8f7fbd19420a6ef1795f3d530a178b571927bfa931c8ab6ea795f871b26d675`.

Replayed the saved five tool results and sixth-turn submission using `FakeModel`
and a recorded-result-only evidence double. The recorded code reproduced
`rejected_assessment`, with `invalid_or_unsupported_assessment`; direct validation
raised `KeyError` at the nonexistent historical pointer. No scientific tool or
provider was invoked during replay.

The two bad references are in `observed_facts[2]` and
`recommendation.evidence[3]`: `R2 /data/analysis/silhouette` instead of
`R2 /data/silhouette`. An explicit in-memory diagnostic correction of those two
fields passed the original validator with no flags. That correction was never
written into the saved run or implemented as automatic pointer repair.

With the new recovery loop, replaying the same trace plus a scripted corrected
submission completed on turn seven: five evidence results, first submission
rejected, second submitted for researcher review, no final flags. This establishes
offline contract behavior, not actual LLM self-correction.

## Exact changes

- `src/agent/scientific_review_agent.py`: typed reference errors with static error
  code `invalid_evidence_reference` and a host-generated assessment-field location.
  No raw exception, invalid pointer content, source value, credential or local
  filesystem path is copied into feedback. JSON Pointer resolution remains exact;
  malformed escapes and noncanonical array indices are rejected.
- The loop returns a `function_call_output` for a correctable reference failure.
  It permits at most two assessment submissions total, exposing only
  `submit_assessment` on the correction turn. Other requested tools are rejected
  without execution. Both attempts, their arguments, validation outcome and
  numbered attempt are preserved in the trace.
- Recovery requires remaining capacity in the original ten-turn and 128 KiB
  history budgets. The eight-tool maximum is unchanged; submissions do not reset
  or replenish it. No additional evidence is retrieved during recovery. Provider
  transport retries remain zero.
- Exact-value/type checks, unsupported numerical/causal/predictive-claim handling,
  researcher control, source rechecks and mode restrictions remain active.
  Non-reference schema/value/claim failures do not gain a recovery attempt.
- `tests/agent/test_scientific_review_agent.py`: focused synthetic regression and
  orchestration cases for missing references in facts and recommendations, valid
  correction, repeated invalidity, valid first submission, strict pointer syntax,
  scientific claim checks, mode/tool/turn/history boundaries and mocked provider
  continuation. The production implementation contains no silhouette-specific
  path or Cluster 1 recommendation.
- `docs/day5_mvp03_invalid_citation_recovery.md`: this review record.

## Verification

Executed commands:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -k 'reference or recovery or valid_first_submission' -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_explicit_window.py tests/workflow/test_temporal_window.py tests/workflow/test_window_planning.py tests/workflow/test_planning_evidence.py -q -p no:cacheprovider
```

Focused recovery selection: **21 passed, 57 deselected**, 31.08 s.
Permitted workflow regressions: **234 passed**, 10.40 s.
Full Agent suite: **78 passed**, 144.90 s. No test failures occurred.

## Limits and preserved state

Feedback reports the first failing reference location; it does not provide a
replacement pointer or certify other claims. The model must check all citations
against already inspected evidence. Only one correction is available, and none
is possible after the final permitted model turn or when history capacity is
exhausted. Failed correction, adapter failure or an out-of-scope recovery action
retains rejection/abstention. A valid correction still requires researcher review.
Semantic interpretation is not proven by citation and keyword checks. Actual
model self-correction remains unverified until a separately authorized new live run.

Original live outputs, accepted evidence, scientific algorithms, evidence tools,
configuration and patch backups were preserved. No Framework D, Stage 2, signing,
Store or authorization operation, installation, commit, push or PR occurred.

Windows Local Isolation: **NOT VERIFIED**  
Trusted Human Authorization: **NOT VERIFIED**  
Execution Eligibility: **FALSE**

Stopped at Scientific & Security Review.
