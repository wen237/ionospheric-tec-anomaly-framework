# MVP-03 Run 02 validation and bounded recovery

Scientific & Security Review. Run 02 remains `rejected_assessment`; no API call
was made during this task and neither saved live run was overwritten.

## Recorded-code offline reproduction

Verified Run 02's saved artifact pins under `outputs/afghanistan_mvp03_api_pre_02/`.
Before changing code, the Agent module matched the recorded SHA-256 exactly:
`77d15447d29c9139ded230b7d4cd727e35d0c7e6afe3d906512ae1a6141621da`.
Using that code, replayed the saved six evidence results and seventh-turn
submission with an offline model double. It reproduced `rejected_assessment`;
direct validation raised `unsupported_observed_value`.

Inspected all observed values, citation locations, recommendation fields and
keyword-checkable narrative independently, rather than stopping at that first
error. The findings are:

| Category | Run 02 finding |
| --- | --- |
| Invalid scientific evidence reference | **None found.** All saved citations resolve. |
| Correct reference, mismatched value | `observed_facts[4]`, `R5 /data/hourly/120`: the claim says code `0` / `valid_normal`; the inspected row says code `-1` / `negative`. Both timestamps are `2022-06-02T00:00:00Z`. Exact-value rejection is correct. |
| Action outside mode | `recommendation.action = review_spatial_comparison` is invalid in Pre-Spatial mode. |
| Invalid action/cluster pairing | `recommendation.cluster_id = 1` is invalid with that action. Only `investigate_candidate` may carry a cluster ID. |
| Causal/predictive language | `scientific_inferences[0].text` includes “not evidence that the anomaly is a precursor”. This is a negative scientific statement, incorrectly flagged by the old embedded-keyword check. It is not an affirmative precursor claim. |

An in-memory diagnostic correction of the observed value alone exposed the old
validator's three remaining flags: mode, cluster pairing and causal language.
No additional invalid references or numerical narrative were found. This audit
does not establish semantic entailment of every scientific inference.

## Changes

- `src/agent/scientific_review_agent.py`: aggregates schema-valid assessment
  problems by static category and host-generated field location. Reference
  validity and exact observed-value equality remain separate checks. Feedback
  contains at most twelve issues and 4 KiB, with a truncation indicator. It never
  supplies actual source values, replacements, raw exceptions, credentials,
  local filesystem paths or full scientific artifacts.
- Extended the existing recovery path to value, recommendation and flagged
  scientific-language failures. The model can submit at most one correction,
  using only previously inspected results. No further evidence tools are offered
  or dispatched. Ten model turns, eight tool requests and 128 KiB history remain
  unchanged; retries do not reset budgets. Provider transport retries remain zero.
- Pre-Spatial submission schemas omit `review_spatial_comparison`. The Host still
  independently rejects mode violations and invalid action/cluster pairings even
  when a caller bypasses the provider schema. Post-Spatial retains its actions.
- Added only a narrow exemption for the explicit negative precursor phrase above.
  Affirmative claims, double negation, “not only” and ambiguous precursor language
  still require review. This is not a general language classifier.
- Added `assessment_outcome` alongside the existing status in returned results,
  trace entries, saved run records and readable reports. Outcomes distinguish
  `valid_first_submission`, `valid_corrected_submission`, rejected/flagged first
  or second submissions, and `uncorrectable_assessment_failure`. Attempt numbers,
  both submitted argument sets and validation results remain recorded. Malformed
  assessment structure is uncorrectable in this bounded path and stops immediately.
- `tests/agent/test_scientific_review_agent.py`: targeted regression cases for
  the mismatch, independent mode/action checks, negation, combined errors,
  correction success/failure, bounded feedback, preserved source hashes, trace
  outcomes and security limits. Existing reference, provider-mock and budget tests
  remain active; scientific-language tests now assert typed validation failures.
- `docs/day5_mvp03_run02_validation_review.md`: this review record.

No production rule contains Run 02's hourly pointer, a replacement anomaly value,
or a default cluster/action repair. The Host never rewrites submitted content.

## Diagnostic replay of the new recovery

Replayed the real saved transcript with an explicit scripted eighth-turn
correction. The offline fake model supplied the exact row from its previously
inspected result and proposed `request_external_evidence` with a null cluster ID.
The Host accepted that diagnostic submission for researcher review, with eleven
checked facts, no flags and outcome `valid_corrected_submission`. The first
submission remained rejected in the diagnostic trace. Original files were not
changed. This is not actual LLM self-correction or a retroactive Run 02 success.

The new first feedback identifies three errors without exposing the row's value:
`unsupported_observed_value` at `/observed_facts/4/value_json`,
`recommendation_outside_evidence_mode` at `/recommendation/action`, and
`unexpected_cluster_recommendation` at `/recommendation/cluster_id`.

## Verification

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -k 'causal_language or missing_historical or provider_mock_replays_reference' -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -k 'run02 or mode_aware or action_cluster_pairing or combined or validation_feedback or uncorrectable_first' -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/agent/test_scientific_review_agent.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_explicit_window.py tests/workflow/test_temporal_window.py tests/workflow/test_window_planning.py tests/workflow/test_planning_evidence.py -q -p no:cacheprovider
```

Initial causal/reference/provider smoke tests: **20 passed, 58 deselected**, 2.81 s.
New targeted tests: **21 passed, 78 deselected**, 17.48 s.
Permitted workflow regressions: **234 passed**, 2.57 s.
Full Agent suite: **99 passed**, 180.19 s. No test failures occurred.

## Readiness and limits

The implementation is ready for a separately researcher-controlled Run 03 with
the checks above passed. It does not authorize or start that run. Actual model
self-correction remains unverified. More than twelve independent issues may
require the model to check unlisted fields itself; there is still only one
correction. Malformed structure, exhausted budgets, repeated errors and failed
continuation retain rejection/abstention. Passing mechanical validation does not
establish scientific causality, predictive performance or human authorization.

Accepted evidence, algorithms, evidence tools, prior outputs, configuration and
patch backups were preserved. No Framework D, Legacy Stage 2, signing, Store or
authorization operation, installation, commit, push or PR occurred.

Windows Local Isolation: **NOT VERIFIED**  
Trusted Human Authorization: **NOT VERIFIED**  
Execution Eligibility: **FALSE**

Stopped at Scientific & Security Review.
