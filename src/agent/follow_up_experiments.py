"""Bounded, cited follow-up proposals; never selections or execution commands."""

from src.agent.scientific_evidence_tools import compact, object_schema
from src.workflow.window_sensitivity import bounds


MAX_PROPOSALS = 3
_TEXT = dict(type="string", minLength=1, maxLength=1200)
_REF = object_schema(dict(result_id=dict(type="string", maxLength=16), pointer=dict(type="string", maxLength=256)))
_WINDOW = object_schema(dict(start_utc=dict(type="string", maxLength=32), end_utc=dict(type="string", maxLength=32),
                             inclusive_hours=dict(type="integer", minimum=1, maximum=744)))
PROPOSALS_SCHEMA = dict(type="array", maxItems=MAX_PROPOSALS, items=object_schema(dict(
    scientific_question=_TEXT,
    supporting_evidence=dict(type="array", items=_REF, minItems=1, maxItems=8),
    reason_for_investigation=_TEXT,
    experiment_type=dict(type="string", enum=["nested_window_comparison", "space_weather_control", "independent_case_validation"]),
    proposed_experiment=_TEXT,
    proposed_windows=dict(type="array", items=_WINDOW, maxItems=2),
    evaluation_criteria=dict(type="array", items=_TEXT, minItems=1, maxItems=6),
    scientific_limitations=dict(type="array", items=_TEXT, minItems=1, maxItems=6),
    human_approval_required=dict(type="boolean", enum=[True]),
    execution_eligible=dict(type="boolean", enum=[False]),
)))


def check_proposals(checked, results, resolve, issue):
    """Validate structure, inspected bounds and citations; return prose to check."""
    proposals = checked["follow_up_experiments"]
    narratives = []
    inspected_windows = {}
    window_results = set()
    for result_id, result in results.items():
        if result.get("ok") is not True:
            continue
        data = result.get("data", {})
        for key in ("baseline", "extended", "window"):
            value = data.get(key)
            if isinstance(value, dict) and {"start_utc", "end_utc", "inclusive_hours"} <= value.keys():
                inspected_windows[compact(bounds(value))] = result_id
        if data.get("record_type") == "window_sensitivity_diagnostic":
            window_results.add(result_id)
    checked_refs = {(f["result_id"], f["pointer"]) for f in checked["observed_facts"] if "value" in f}
    for i, proposal in enumerate(proposals):
        root = f"/follow_up_experiments/{i}"
        support_ids = set()
        has_fact = False
        for j, ref in enumerate(proposal["supporting_evidence"]):
            resolved, _ = resolve(ref, f"{root}/supporting_evidence/{j}")
            if resolved:
                support_ids.add(ref["result_id"])
                has_fact |= (ref["result_id"], ref["pointer"]) in checked_refs
        if not has_fact:
            issue("proposal_without_checked_observations", root + "/supporting_evidence")
        windows = proposal["proposed_windows"]
        for j, window in enumerate(windows):
            try:
                checked_window = bounds(window)
                if compact(checked_window) not in inspected_windows:
                    raise ValueError("Uninspected proposed window")
            except (ValueError, TypeError):
                issue("proposal_window_not_inspected", f"{root}/proposed_windows/{j}")
        if len({compact(w) for w in windows}) != len(windows):
            issue("duplicate_proposal_windows", root + "/proposed_windows")
        if proposal["experiment_type"] == "nested_window_comparison":
            if len(windows) != 2 or not support_ids & window_results:
                issue("nested_proposal_requires_hourly_window_evidence", root)
            elif not any(all(w in results[r]["data"].values() for w in windows) for r in support_ids & window_results):
                issue("nested_proposal_windows_differ_from_support", root + "/proposed_windows")
        for field in ("scientific_question", "reason_for_investigation", "proposed_experiment"):
            narratives.append((f"{root}/{field}", proposal[field]))
        for field in ("evaluation_criteria", "scientific_limitations"):
            narratives.extend((f"{root}/{field}/{j}", text) for j, text in enumerate(proposal[field]))
    if checked["recommendation"]["action"] == "propose_follow_up" and not proposals:
        issue("follow_up_action_requires_proposals", "/follow_up_experiments")
    return narratives


def window_comparison_proposal(data, result_id):
    """Offline demonstration helper, driven by inspected evidence, not durations.

    No scientific selection is made. Low additional contribution is a relative
    rate comparison, explicitly separate from data quality and attribution.
    """
    reduced = any(data["contribution"][p]["lower_additional_anomaly_rate_than_baseline"] for p in ("positive", "negative"))
    polarity = next((p for p in ("negative", "positive") if data["contribution"][p]["lower_additional_anomaly_rate_than_baseline"]), "negative")
    reason = ("The additional exposure has a lower anomaly rate for an inspected polarity; compare its temporal and spatial contribution before deciding whether either window is appropriate."
              if reduced else "Additional exposure changes the inspected evidence; compare both complete windows before deciding whether either is appropriate.")
    return dict(scientific_question="How sensitive are the temporal and spatial observations to the independently motivated nested window bounds?",
                supporting_evidence=[dict(result_id=result_id, pointer="/data/baseline/inclusive_hours"),
                                     dict(result_id=result_id, pointer=f"/data/contribution/{polarity}/lower_additional_anomaly_rate_than_baseline")],
                reason_for_investigation=reason, experiment_type="nested_window_comparison",
                proposed_experiment="Review both saved windows and the actual added hourly decisions, then compare space-weather context and independently chosen control cases. Retain both windows pending human review.",
                proposed_windows=[data["baseline"], data["extended"]],
                evaluation_criteria=["Compare anomaly counts, occurrence ratios and added-hour rates by polarity using full target-hour denominators.",
                                     "Compare spatial distributions and epicentral grid cells alongside rolling-reference validity and missingness.",
                                     "Check UTC-aligned geomagnetic and solar context while respecting native index cadences."],
                scientific_limitations=["Retrospective window sensitivity is descriptive and cannot establish earthquake attribution or predictive performance.",
                                        "Lower contribution may reflect missingness or environmental variation; it is not a reason to favor a hypothesis-matching shorter window."],
                human_approval_required=True, execution_eligible=False)
