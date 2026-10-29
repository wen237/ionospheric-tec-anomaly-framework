"""Synthetic-only tests of the declared retrospective DAILY policy."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import numpy as np
import pytest

from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.temporal_anomaly import TemporalAnomalyResult
from src.workflow.planning_evidence import (
    build_historical_bc_evidence,
    build_temporal_evidence,
    evidence_to_json,
    load_historical_bc_evidence,
)
from src.workflow.window_planning import aggregate_temporal_days, plan_anchor_based_daily_windows
# Reuse the existing hand-authored synthetic summary fixture, not research data.
from tests.workflow.test_planning_evidence import historical


START = datetime(2000, 12, 20)


def temporal_days(profiles, *, start=START, first_hour=0, last_hour=23, aware=False, location=False):
    """Construct synthetic detector-result metadata; no observed TEC is claimed."""
    epochs, observed, codes = [], [], []
    statistics = {name: [] for name in ("q1", "median", "q3", "upper_bound", "lower_bound")}
    defaults = dict(q1=9.0, median=10.0, q3=11.0, upper_bound=13.0, lower_bound=7.0)
    beginning = start + timedelta(hours=first_hour)
    ending = start + timedelta(days=len(profiles) - 1, hours=last_hour)
    if aware:
        beginning, ending = [value.replace(tzinfo=timezone.utc) for value in (beginning, ending)]
    for index, profile in enumerate(profiles):
        for hour in range(24):
            epoch = start + timedelta(days=index, hours=hour)
            if aware:
                epoch = epoch.replace(tzinfo=timezone.utc)
            if epoch < beginning or epoch > ending or profile == "missing_day" or (
                profile == "missing_positive" and hour == 1
            ):
                continue
            code = 0
            if profile in ("positive", "missing_positive", "unclassifiable", "insufficient") and hour == 0:
                code = 1
            elif profile == "negative" and hour == 0:
                code = -1
            elif profile == "mixed" and hour in (0, 1):
                code = 1 if hour == 0 else -1
            value = {1: 20.0, -1: 0.0, 0: 10.0}[code]
            if profile == "unclassifiable" and hour == 1:
                value = np.nan
            epochs.append(epoch)
            observed.append(value)
            codes.append(code)
            for name, default in defaults.items():
                statistics[name].append(np.nan if profile == "insufficient" and hour == 1 else default)
    result = TemporalAnomalyResult(
        epochs=np.array(epochs, dtype=object), observed=np.array(observed, dtype=float),
        anomaly=np.array(codes, dtype=np.int8),
        **{name: np.array(values, dtype=float) for name, values in statistics.items()},
        reference_days=15, threshold_multiplier=3.0, min_reference_samples=15,
    )
    series = None if not location else TECTimeSeries(
        epochs=result.epochs, tec=result.observed, requested_latitude=33.02, requested_longitude=69.46,
        grid_latitude=32.5, grid_longitude=70.0, latitude_index=48, longitude_index=50,
    )
    return build_temporal_evidence(
        result, case_id="synthetic_case", expected_start=beginning, expected_end=ending,
        input_time_convention="aware_utc" if aware else "naive_utc", time_series=series,
        provenance=dict(sources=[dict(identity="synthetic-source.npz", sha256=None)],
                        processing_history="Synthetic metadata; upstream quality unknown."),
    )


def event_for_anchor(index=1, *, start=START, relative_day=-8, hour=10, minute=30):
    epoch = start + timedelta(days=index - relative_day, hours=hour, minutes=minute)
    return dict(case_id="synthetic_case", event_id="synthetic-event", time_utc=epoch.isoformat() + "Z",
                source_reference="synthetic-catalog#synthetic-event")


def plan(historical, profiles, *, anchor_index=1, start=START, selected=(0,), event=None, **kwargs):
    temporal = temporal_days(profiles, start=start, **kwargs)
    return plan_anchor_based_daily_windows(
        temporal, build_historical_bc_evidence(historical),
        case_event=event or event_for_anchor(anchor_index, start=start),
        selected_cluster_ids=selected, mode="retrospective",
    )


def report(proposal, cluster_id=0):
    return next(item for item in proposal["anchor_reports"] if item["anchor"]["cluster_id"] == cluster_id)


@pytest.mark.parametrize("polarity,profile,cluster_id,relative_day", [
    (1, "positive", 0, -8), (-1, "negative", 1, -22),
])
def test_one_target_hour_and_23_normals_qualify_full_day(historical, polarity, profile, cluster_id, relative_day):
    proposal = plan(historical, ["normal", profile, "normal"], selected=[cluster_id],
                    event=event_for_anchor(relative_day=relative_day))
    result = report(proposal, cluster_id)
    assert result["status"] == "candidate"
    assert result["anchor"]["dominant_polarity"] == polarity
    assert result["included_days"] == ["2000-12-21"]
    assert result["candidate_window"] == dict(start_utc="2000-12-21T00:00:00Z",
                                              end_utc="2000-12-21T23:00:00Z",
                                              inclusive_hours=24, bounds="inclusive_hourly_samples")
    assert result["anchor_day_evidence"]["valid_normal"] == 23
    assert result["backward_stop"]["reason"] == "no_anomalies"
    assert result["forward_stop"]["reason"] == "no_anomalies"
    assert proposal["policy_name"] == "anchor_based_daily_expansion_v1"
    assert proposal["mode"] == "retrospective" and proposal["review_only"] is True
    assert "approval_status" not in proposal


@pytest.mark.parametrize("anchor_profile,reason", [("normal", "no_anomalies"),
                                                    ("negative", "opposite_polarity_only"),
                                                    ("mixed", "mixed_polarity")])
def test_invalid_anchor_abstains_without_expanding_good_neighbors(historical, anchor_profile, reason):
    proposal = plan(historical, ["positive", anchor_profile, "positive"])
    result = report(proposal)
    assert proposal["status"] == "abstained"
    assert result["status"] == "no_candidate" and result["reason"] == "invalid_anchor:" + reason
    assert result["candidate_window"] is None and result["included_days"] == []
    assert len(result["evaluated_days"]) == 1
    assert result["backward_stop"]["status"] == result["forward_stop"]["status"] == "not_attempted"
    assert result["anchor_day_evidence"]["polarity_boundary_confirmed"] is True


@pytest.mark.parametrize("reverse", [False, True])
def test_bidirectional_expansion_is_independent_and_does_not_skip_first_stop(historical, reverse):
    profiles = ["positive", "positive", "mixed", "positive", "positive", "positive", "normal"]
    if reverse:
        profiles = list(reversed(profiles))
    proposal = plan(historical, profiles, anchor_index=3)
    result = report(proposal)
    indices = [1, 2, 3] if reverse else [3, 4, 5]
    assert result["included_days"] == [(START + timedelta(days=index)).date().isoformat() for index in indices]
    assert result["candidate_window"]["inclusive_hours"] == 72
    stop = result["forward_stop"] if reverse else result["backward_stop"]
    other = result["backward_stop"] if reverse else result["forward_stop"]
    assert stop["reason"] == "mixed_polarity"
    assert other["reason"] == "no_anomalies"
    assert not stop["boundary_uncertain"] and stop["polarity_boundary_confirmed"]
    visited = {day["date_utc"] for day in result["evaluated_days"]}
    skipped_side = [5, 6] if reverse else [0, 1]
    assert not visited & {(START + timedelta(days=index)).date().isoformat() for index in skipped_side}


def test_negative_expansion_stops_on_first_opposite_day_in_each_direction(historical):
    proposal = plan(historical, ["negative", "positive", "negative", "negative", "negative", "positive", "negative"],
                    anchor_index=3, selected=[1], event=event_for_anchor(3, relative_day=-22))
    result = report(proposal, 1)
    assert result["included_days"] == ["2000-12-22", "2000-12-23", "2000-12-24"]
    assert result["candidate_window"]["inclusive_hours"] == 72
    assert result["backward_stop"]["reason"] == result["forward_stop"]["reason"] == "opposite_polarity_only"
    assert len(result["evaluated_days"]) == 5


@pytest.mark.parametrize("profile", ["missing_positive", "missing_day", "unclassifiable", "insufficient"])
def test_incomplete_anchor_explicitly_blocks_inclusion(historical, profile):
    proposal = plan(historical, ["positive", profile, "positive"])
    result = report(proposal)
    assert result["status"] == "no_candidate"
    assert "incomplete_or_unclassifiable_day" in result["reason"]
    assert result["backward_stop"]["status"] == "not_attempted"
    assert result["forward_stop"]["status"] == "not_attempted"
    assert len(result["evaluated_days"]) == 1
    assert result["data_quality_limitations"][0]["date_utc"] == "2000-12-21"
    assert result["data_quality_limitations"][0]["boundary_uncertain"]
    assert not result["anchor_day_evidence"]["polarity_boundary_confirmed"]


@pytest.mark.parametrize("profile,reason", [("missing_positive", "missing_hours"),
                                            ("unclassifiable", "unclassifiable_hours"),
                                            ("insufficient", "unclassifiable_hours")])
def test_quality_stop_is_uncertain_and_other_direction_continues(historical, profile, reason):
    proposal = plan(historical, ["positive", profile, "positive", "positive", "normal"], anchor_index=2)
    result = report(proposal)
    assert result["included_days"] == ["2000-12-22", "2000-12-23"]
    assert result["backward_stop"]["boundary_uncertain"] is True
    assert result["backward_stop"]["polarity_boundary_confirmed"] is False
    assert result["forward_stop"]["reason"] == "no_anomalies"
    assert result["data_quality_limitations"] == [dict(date_utc="2000-12-21", reasons=[reason], boundary_uncertain=True)]
    assert "2000-12-20" not in {day["date_utc"] for day in result["evaluated_days"]}


def test_daily_counts_preserve_missing_and_unclassifiable_separately():
    evidence = temporal_days(["positive", "negative", "mixed", "normal", "missing_positive",
                              "unclassifiable", "insufficient", "missing_day"])
    days = aggregate_temporal_days(evidence)
    assert days[0]["positive"] == 1 and days[0]["valid_normal"] == 23
    assert days[1]["negative"] == 1 and days[1]["valid_normal"] == 23
    assert days[2]["positive"] == days[2]["negative"] == 1
    assert days[3]["valid_normal"] == 24
    assert days[4]["missing_hours"] == days[4]["explicit_missing_hours"] == 1
    assert days[4]["positive"] == 1 and days[4]["valid_normal"] == 22
    assert days[5]["unclassifiable"] == days[6]["unclassifiable"] == 1
    assert days[7]["missing_hours"] == 24 and days[7]["valid_normal"] == 0
    for day in days:
        assert sum(day[name] for name in ("positive", "negative", "valid_normal", "unclassifiable", "missing_hours")) == 24


def test_partial_edge_days_are_not_misrepresented_as_complete(historical):
    evidence = temporal_days(["positive", "positive"], first_hour=6, last_hour=12)
    days = aggregate_temporal_days(evidence)
    assert days[0]["outside_analysis_hours"] == days[0]["missing_hours"] == 6
    assert days[1]["outside_analysis_hours"] == days[1]["missing_hours"] == 11
    assert all(not day["quality_complete"] for day in days)
    proposal = plan_anchor_based_daily_windows(
        evidence, build_historical_bc_evidence(historical),
        case_event=event_for_anchor(0), selected_cluster_ids=[0], mode="retrospective",
    )
    assert report(proposal)["status"] == "no_candidate"


def test_evidence_edge_is_uncertain_not_a_polarity_boundary(historical):
    result = report(plan(historical, ["positive"], anchor_index=0))
    assert result["candidate_window"]["inclusive_hours"] == 24
    for name in ("backward_stop", "forward_stop"):
        assert result[name]["reason"] == "outside_evidence"
        assert result[name]["boundary_uncertain"]
        assert not result[name]["polarity_boundary_confirmed"]


@pytest.mark.parametrize("start", [datetime(2000, 12, 30), datetime(2000, 2, 28)])
def test_cross_year_month_and_leap_day_expansion(historical, start):
    result = report(plan(historical, ["normal", "positive", "positive", "positive", "normal"],
                         anchor_index=2, start=start))
    assert result["included_days"] == [(start + timedelta(days=i)).date().isoformat() for i in (1, 2, 3)]
    assert result["candidate_window"]["inclusive_hours"] == 72


def test_day_zero_and_post_event_days_are_reported_without_hidden_truncation(historical):
    proposal = plan(historical, ["normal"] + ["positive"] * 10 + ["normal"])
    result = report(proposal)
    assert proposal["case_event"]["date_utc"] == "2000-12-29"
    assert proposal["case_event"]["time_utc"] == "2000-12-29T10:30:00Z"
    assert result["candidate_window"]["end_utc"] == "2000-12-30T23:00:00Z"
    assert result["contains_day_zero"] and result["contains_post_event_days"]
    assert result["contains_samples_at_or_after_event"]
    assert any("not necessarily entirely pre-earthquake" in text for text in proposal["limitations"])


def test_late_event_hour_is_distinct_from_day_zero_sample_end(historical):
    event = event_for_anchor(hour=23, minute=30)
    result = report(plan(historical, ["normal"] + ["positive"] * 9 + ["normal"], event=event))
    assert result["contains_day_zero"] is True
    assert result["contains_post_event_days"] is False
    assert result["contains_samples_at_or_after_event"] is False
    assert result["candidate_window"]["end_utc"] == "2000-12-29T23:00:00Z"


def test_multiple_anchors_keep_opposite_and_mixed_cluster_context(historical):
    profiles = ["normal"] * 25
    profiles[7], profiles[21] = "negative", "positive"
    start = datetime(2000, 12, 1)
    event = dict(case_id="synthetic_case", event_id="synthetic-event", time_utc="2000-12-30T05:06:07Z",
                 source_reference="synthetic-catalog#synthetic-event")
    proposal = plan(historical, profiles, start=start, event=event, selected=[1, 0])
    assert [item["status"] for item in proposal["anchor_reports"]] == ["candidate", "candidate"]
    assert report(proposal, 0)["included_days"] == ["2000-12-22"]
    assert report(proposal, 1)["included_days"] == ["2000-12-08"]
    assert report(proposal, 0)["anchor"]["n_negative"] == 1
    assert report(proposal, 0)["anchor"]["n_positive"] == 2
    assert report(proposal, 1)["anchor"]["dominant_polarity"] == -1
    for index in (0, 1):
        assert report(proposal, index)["anchor_source_reference"]["json_pointer"].endswith(f"/{index}")


def test_unselected_anchor_is_never_implicitly_mapped_or_expanded(historical):
    proposal = plan(historical, ["normal", "positive", "normal"])
    unselected = report(proposal, 1)
    assert unselected["status"] == "no_candidate" and unselected["reason"] == "not_selected"
    assert unselected["anchor_date_utc"] is None and unselected["evaluated_days"] == []
    assert unselected["anchor"] == historical["clustering"]["temporal_anchors"][1]


def test_empty_selection_explicitly_abstains(historical):
    proposal = plan(historical, ["positive"] * 3, selected=[])
    assert proposal["status"] == "abstained" and proposal["abstention_reason"] == "no_anchors_selected"
    assert all(item["reason"] == "not_selected" for item in proposal["anchor_reports"])


def test_tied_polarity_abstains_instead_of_using_centroid_sign(historical):
    for anchor in historical["clustering"]["temporal_anchors"]:
        anchor.update(n_positive=1, n_negative=1, n_members=2, dominant_polarity=0, centroid_polarity=0.2)
    result = report(plan(historical, ["positive"] * 3))
    assert result["reason"] == "invalid_anchor:ambiguous_anchor_polarity"
    assert result["candidate_window"] is None and len(result["evaluated_days"]) == 1


def test_selected_anchor_outside_evidence_abstains_with_quality_reason(historical):
    proposal = plan(historical, ["positive"] * 3, selected=[1])
    result = report(proposal, 1)
    assert result["reason"] == "invalid_anchor:outside_evidence"
    assert result["anchor_day_evidence"]["missing_hours"] == 24
    assert result["data_quality_limitations"][0]["boundary_uncertain"]


def test_anchor_hour_does_not_create_intraday_or_shifted_window(historical):
    historical["clustering"]["temporal_anchors"][0]["hour"] = 23
    result = report(plan(historical, ["normal", "positive", "normal"]))
    assert result["anchor"]["hour"] == 23
    assert result["candidate_window"]["start_utc"].endswith("T00:00:00Z")
    assert result["candidate_window"]["end_utc"].endswith("T23:00:00Z")


def test_mapping_uses_saved_rounded_day_not_truncated_centroid_day(historical):
    historical["clustering"]["temporal_anchors"][0]["centroid_day"] = -7.6
    historical["clustering"]["decoded_centers"][0][1] = -7.6
    result = report(plan(historical, ["normal", "positive", "normal"]))
    assert result["anchor_date_utc"] == "2000-12-21"
    assert result["anchor"]["centroid_day"] == -7.6
    assert result["anchor"]["rounded_day"] == -8


def test_full_b_overlap_stays_context_without_changing_daily_selection(historical):
    first = plan(historical, ["normal", "positive", "normal"])
    historical["statistical_significance"]["full_window"]["overlap_cells"][1]["positive_z"] = 3.0
    second = plan(historical, ["normal", "positive", "normal"])
    assert report(first)["candidate_window"] == report(second)["candidate_window"]
    assert first["evidence_references"]["historical"]["content_sha256"] != second["evidence_references"]["historical"]["content_sha256"]


def test_evidence_with_aware_input_and_location_is_supported(historical):
    proposal = plan(historical, ["normal", "positive", "normal"], aware=True, location=True)
    assert report(proposal)["status"] == "candidate"


@pytest.mark.parametrize("selection", [[True], [0.0], [0, 0], [2], "0", None])
def test_rejects_invalid_or_ambiguous_anchor_selection(historical, selection):
    with pytest.raises(ValueError, match="cluster IDs"):
        plan(historical, ["positive"] * 3, selected=selection)


@pytest.mark.parametrize("change", [dict(time_utc="2000-12-29"), dict(time_utc="2000-12-29T10:30:00"),
                                    dict(time_utc="2000-12-29T10:30:00+08:00"), dict(case_id="other_case"),
                                    dict(source_reference=""), dict(source_sha256="bad"), dict(event_id="")])
def test_rejects_untraceable_or_non_utc_case_event(historical, change):
    event = {**event_for_anchor(), **change}
    with pytest.raises(ValueError, match="case_event"):
        plan(historical, ["positive"] * 3, event=event)


@pytest.mark.parametrize("mode", ["prospective", "", None])
def test_requires_explicit_retrospective_mode(historical, mode):
    with pytest.raises(ValueError, match="retrospective"):
        plan_anchor_based_daily_windows(temporal_days(["positive"]), build_historical_bc_evidence(historical),
                                        case_event=event_for_anchor(0), selected_cluster_ids=[0], mode=mode)


@pytest.mark.parametrize("kind", ["version", "bool_version", "type", "counts", "classification", "float_code",
                                  "missing_row", "duplicate_hour", "wrong_time", "quality_label", "marker"])
def test_rejects_incompatible_or_tampered_temporal_evidence(kind):
    evidence = temporal_days(["positive"])
    if kind == "version":
        evidence["schema_version"] = 2
    elif kind == "bool_version":
        evidence["schema_version"] = True
    elif kind == "type":
        evidence["evidence_type"] = "historical_bc_context"
    elif kind == "counts":
        evidence["counts"]["positive"] += 1
    elif kind == "classification":
        evidence["hourly"][0]["classification"] = "valid_normal"
    elif kind == "float_code":
        evidence["hourly"][0]["anomaly_code"] = 1.0
    elif kind == "missing_row":
        evidence["hourly"].pop(1)
    elif kind == "duplicate_hour":
        evidence["hourly"][1]["timestamp_utc"] = evidence["hourly"][0]["timestamp_utc"]
    elif kind == "wrong_time":
        evidence["hourly"][0]["timestamp_utc"] = "2000-12-20T00:00:00+08:00"
    elif kind == "quality_label":
        evidence["hourly"][0]["result_present"] = 1
    else:
        evidence["hourly"][0]["observed"] = None
    with pytest.raises(ValueError):
        aggregate_temporal_days(evidence)


@pytest.mark.parametrize("kind", ["version", "type", "inner_version", "inner_type", "anchor_time_basis",
                                  "missing_fields", "invalid_composition", "wrong_probability"])
def test_rejects_incompatible_historical_evidence(historical, kind):
    evidence = build_historical_bc_evidence(historical)
    if kind == "version":
        evidence["schema_version"] = 2
    elif kind == "type":
        evidence["evidence_type"] = "case_temporal_anomalies"
    elif kind == "inner_version":
        evidence["historical_summary"]["schema_version"] = 2
    elif kind == "inner_type":
        evidence["historical_summary"]["summary_type"] = "other_summary"
    elif kind == "anchor_time_basis":
        evidence["anchor_time_basis"] = "individual_case_utc_dates"
    elif kind == "missing_fields":
        del evidence["historical_summary"]["statistical_significance"]
    elif kind == "invalid_composition":
        evidence["historical_summary"]["clustering"]["temporal_anchors"][0]["n_members"] = 10
    else:
        evidence["historical_summary"]["population_baseline"]["positive_probability"] = 0.5
    with pytest.raises(ValueError):
        plan_anchor_based_daily_windows(temporal_days(["positive"]), evidence,
                                        case_event=event_for_anchor(0), selected_cluster_ids=[0], mode="retrospective")


def test_deterministic_strict_json_source_hashes_and_no_input_mutation(historical):
    temporal = temporal_days(["normal", "missing_positive", "positive", "unclassifiable"], location=True)
    context = build_historical_bc_evidence(historical)
    event = event_for_anchor(2)
    before = deepcopy((temporal, context, event))
    first = plan_anchor_based_daily_windows(temporal, context, case_event=event,
                                           selected_cluster_ids=[1, 0], mode="retrospective")
    second = plan_anchor_based_daily_windows(temporal, context, case_event=event,
                                            selected_cluster_ids=[0, 1], mode="retrospective")
    assert first == second
    assert json.dumps(first, allow_nan=False, sort_keys=True) == json.dumps(second, allow_nan=False, sort_keys=True)
    assert (temporal, context, event) == before
    for name, source in (("temporal", temporal), ("historical", context)):
        assert first["evidence_references"][name]["content_sha256"] == hashlib.sha256(
            evidence_to_json(source).encode("utf-8")).hexdigest()


@pytest.mark.parametrize("changed_source", ["temporal", "historical"])
def test_valid_evidence_content_change_updates_digest_without_authenticating_sources(historical, changed_source):
    temporal = temporal_days(["normal", "positive", "normal"])
    temporal["provenance"]["sources"][0]["sha256"] = "a" * 64  # declaration, not a verified file
    context = build_historical_bc_evidence(historical)
    original = deepcopy((temporal, context))
    changed_temporal, changed_context = deepcopy(original)
    if changed_source == "temporal":
        changed_temporal["hourly"][24]["observed"] = 21.0  # still above the same upper bound
    else:
        changed_context["historical_summary"]["statistical_significance"]["full_window"]["overlap_cells"][1]["positive_z"] = 3.0
    changed = deepcopy((changed_temporal, changed_context))
    event = event_for_anchor()
    first = plan_anchor_based_daily_windows(temporal, context, case_event=event,
                                           selected_cluster_ids=[0], mode="retrospective")
    second = plan_anchor_based_daily_windows(changed_temporal, changed_context, case_event=event,
                                            selected_cluster_ids=[0], mode="retrospective")
    other_source = "historical" if changed_source == "temporal" else "temporal"
    assert first["evidence_references"][changed_source]["content_sha256"] != second["evidence_references"][changed_source]["content_sha256"]
    assert first["evidence_references"][other_source]["content_sha256"] == second["evidence_references"][other_source]["content_sha256"]
    assert temporal["provenance"] == changed_temporal["provenance"]
    assert context["historical_summary"]["inputs"] == changed_context["historical_summary"]["inputs"]
    assert report(first)["candidate_window"] == report(second)["candidate_window"]
    assert (temporal, context) == original
    assert (changed_temporal, changed_context) == changed


def test_existing_historical_loader_artifact_metadata_is_preserved(historical, tmp_path):
    path = tmp_path / "synthetic-summary.json"
    path.write_text(json.dumps(historical), encoding="utf-8")
    context = load_historical_bc_evidence(path)
    proposal = plan_anchor_based_daily_windows(temporal_days(["normal", "positive", "normal"]), context,
                                               case_event=event_for_anchor(), selected_cluster_ids=[0], mode="retrospective")
    assert proposal["evidence_references"]["historical"]["summary_artifact"] == context["summary_artifact"]


def test_planning_calls_no_detector_scientific_pipeline_or_framework_d(historical, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Planning must not execute scientific workflows.")

    import src.temporal_anomaly.temporal_anomaly as temporal_module
    import src.spatial_verification.spatial_anomaly as spatial_module
    import src.workflow.stage2_runner as stage2_module
    import src.workflow.modern_spatial_input_adapter as modern_module
    from examples import reproduce_afghanistan_historical_bc as bc_module

    monkeypatch.setattr(temporal_module, "detect_temporal_anomalies", forbidden)
    monkeypatch.setattr(spatial_module, "compute_spatial_anomalies", forbidden)
    monkeypatch.setattr(stage2_module, "run_stage2", forbidden)
    monkeypatch.setattr(modern_module, "run_spatial_verification_from_modern_gim", forbidden)
    monkeypatch.setattr(bc_module, "_run_bc", forbidden)
    assert report(plan(historical, ["normal", "positive", "normal"]))["status"] == "candidate"
