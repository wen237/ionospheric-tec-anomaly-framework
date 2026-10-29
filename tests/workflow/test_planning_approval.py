"""Synthetic declarations only: no actual human approvals or scientific runs."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime
import hashlib
import json

import pytest

from src.workflow.planning_approval import (
    DecisionRecord,
    ExecutionIntent,
    build_decision_record,
    build_execution_intent,
    validate_decisions,
)
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_window_planning import plan


NOW = "2001-01-01T02:00:00Z"


def config(mode="modern"):
    return dict(input_mode=mode, dataset=dict(identity="synthetic-dataset", version="fixture-v1", sha256="a" * 64),
                reference_days=15, k=3.0, epicenter=dict(latitude=33.02, longitude=69.46, magnitude=6.0),
                case_id="synthetic_case", manifest=None if mode == "modern" else dict(
                    identity="synthetic-case/preparation_manifest.json", sha256="b" * 64),
                output=dict(identity="synthetic-case/spatial"))


@pytest.fixture
def proposal(historical):
    return plan(historical, ["normal", "positive", "positive", "normal"])


@pytest.fixture
def intent(proposal):
    return build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())


def declaration(intent, status="pending_review", *, previous=None, decision_id="synthetic-pending",
                stamp="2001-01-01T00:00:00Z", expires=None, reviewer="synthetic-reviewer (unverified)"):
    return build_decision_record(intent, decision_id=decision_id, status=status,
                                 reviewer_identity_declaration=reviewer, decision_time_utc=stamp,
                                 reason="Synthetic test declaration; never actual authorization.",
                                 expires_at_utc=expires, supersedes=previous)


def review_chain(intent, status="approved", *, expires=None):
    pending = declaration(intent)
    reviewed = declaration(intent, status, previous=pending, decision_id="synthetic-reviewed",
                           stamp="2001-01-01T01:00:00Z", expires=expires)
    return pending, reviewed


def reseal(data, field):
    data = deepcopy(data)
    data.pop(field, None)
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
    data[field] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return data


def validate(intent, proposal, records, now=NOW):
    result = validate_decisions(intent, proposal, records, now_utc=now)
    assert result["execution_eligible"] is False
    assert result["trusted_human_authorization"] is False
    assert result["authorization_verification_status"] == "not_configured"
    assert "trusted_authorizer_not_configured" in result["reasons"]
    return result


@pytest.mark.parametrize("mode", ["legacy", "modern"])
def test_one_selected_candidate_binds_exact_window_policy_and_configuration(proposal, mode):
    settings = config(mode)
    original = deepcopy((proposal, settings))
    intent = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    data = intent.to_dict()
    assert data["intent_type"] == "framework_d_execution_intent" and data["schema_version"] == 1
    assert data["window"] == proposal["anchor_reports"][0]["candidate_window"]
    assert data["candidate"]["cluster_id"] == 0 and len(data["candidate"]["candidate_id"]) == 64
    assert data["policy"]["name"] == "anchor_based_daily_expansion_v1"
    assert data["framework_d"] == settings
    assert data["source_hash_verification"] == "declared_not_verified"
    assert "no causality" in data["authorization_scope"]
    assert (proposal, settings) == original


def test_multiple_candidates_require_explicit_unambiguous_selection(historical):
    profiles = ["normal"] * 25
    profiles[7], profiles[21] = "negative", "positive"
    event = dict(case_id="synthetic_case", event_id="synthetic-event", time_utc="2000-12-30T05:06:07Z",
                 source_reference="synthetic-catalog#synthetic-event")
    proposal = plan(historical, profiles, start=datetime(2000, 12, 1), event=event, selected=[0, 1])
    first = build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())
    second = build_execution_intent(proposal, selected_cluster_id=1, framework_d=config())
    assert first.digest != second.digest
    assert first.to_dict()["candidate"]["candidate_id"] != second.to_dict()["candidate"]["candidate_id"]
    with pytest.raises(TypeError):
        build_execution_intent(proposal, framework_d=config())
    with pytest.raises(ValueError):
        build_execution_intent(proposal, selected_cluster_id=[0, 1], framework_d=config())


@pytest.mark.parametrize("cluster_id", [1, 99, None, True, 0.0])
def test_invalid_or_unselected_candidate_is_rejected(proposal, cluster_id):
    with pytest.raises(ValueError):
        build_execution_intent(proposal, selected_cluster_id=cluster_id, framework_d=config())


def test_invalid_anchor_no_candidate_and_empty_selection_are_rejected(historical):
    for profiles, selection in ((["normal"] * 3, [0]), (["positive"] * 3, [])):
        proposal = plan(historical, profiles, selected=selection)
        with pytest.raises(ValueError, match="selected candidate"):
            build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())


@pytest.mark.parametrize("kind", ["schema", "policy", "missing_window", "bad_hours", "naive_bounds",
                                  "non_utc_bounds", "nonhourly_bounds", "bad_anchor_date", "duplicate_anchor",
                                  "daily_counts", "missing_day", "quality_flags", "stopping_reason",
                                  "source_digest", "candidate_not_selected", "wrong_included_days"])
def test_malformed_or_internally_inconsistent_proposal_is_rejected(proposal, kind):
    candidate = proposal["anchor_reports"][0]
    window = candidate["candidate_window"]
    if kind == "schema":
        proposal["schema_version"] = True
    elif kind == "policy":
        proposal["policy_name"] = "unapproved_other_policy"
    elif kind == "missing_window":
        candidate["candidate_window"] = None
    elif kind == "bad_hours":
        window["inclusive_hours"] -= 1
    elif kind == "naive_bounds":
        window["start_utc"] = window["start_utc"].removesuffix("Z")
    elif kind == "non_utc_bounds":
        window["end_utc"] = window["end_utc"].replace("Z", "+08:00")
    elif kind == "nonhourly_bounds":
        window["end_utc"] = window["end_utc"].replace("23:00", "23:30")
    elif kind == "bad_anchor_date":
        candidate["anchor_date_utc"] = "2000-12-22"
    elif kind == "duplicate_anchor":
        proposal["anchor_reports"].append(deepcopy(candidate))
    elif kind == "daily_counts":
        proposal["daily_evidence"][0]["valid_normal"] = 25
    elif kind == "missing_day":
        proposal["daily_evidence"].pop(1)
    elif kind == "quality_flags":
        candidate["anchor_day_evidence"]["quality_complete"] = False
    elif kind == "stopping_reason":
        candidate["forward_stop"]["reason"] = "invented"
    elif kind == "source_digest":
        candidate["anchor_source_reference"]["content_sha256"] = "c" * 64
    elif kind == "candidate_not_selected":
        candidate["selected"] = False
    else:
        candidate["included_days"] = ["2000-12-21"]
    with pytest.raises(ValueError):
        build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())


def test_complete_proposal_digest_covers_evidence_and_unselected_context(proposal, intent):
    for field in ("evidence", "context", "limitations"):
        changed = deepcopy(proposal)
        if field == "evidence":
            changed["evidence_references"]["temporal"]["content_sha256"] = "c" * 64
        elif field == "context":
            changed["anchor_reports"][1]["anchor"]["hour"] = 7
        else:
            changed["limitations"].append("Additional retrospective limitation, requiring fresh review.")
        replacement = build_execution_intent(changed, selected_cluster_id=0, framework_d=config())
        assert replacement.digest != intent.digest
        assert replacement.to_dict()["proposal_digest"] != intent.to_dict()["proposal_digest"]
        result = validate(intent, changed, review_chain(intent))
        assert "invalid_or_stale_intent" in result["reasons"]


def test_changed_selected_anchor_or_event_changes_candidate_identity(proposal, intent):
    for field in ("anchor", "event"):
        changed = deepcopy(proposal)
        if field == "anchor":
            changed["anchor_reports"][0]["anchor"]["hour"] = 12
        else:
            changed["case_event"]["time_utc"] = changed["case_event"]["time_utc"].replace("10:30", "11:30")
        replacement = build_execution_intent(changed, selected_cluster_id=0, framework_d=config())
        assert replacement.digest != intent.digest
        assert replacement.to_dict()["candidate"]["candidate_id"] != intent.to_dict()["candidate"]["candidate_id"]
        assert replacement.to_dict()["window"] == intent.to_dict()["window"]


@pytest.mark.parametrize("pointer", ["/historical_summary/clustering/temporal_anchors/99",
                                    "/historical_summary/clustering/temporal_anchors/00"])
def test_invalid_anchor_pointer_cannot_supply_stable_candidate_identity(proposal, pointer):
    proposal["anchor_reports"][0]["anchor_source_reference"]["json_pointer"] = pointer
    with pytest.raises(ValueError):
        build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())


@pytest.mark.parametrize("field,value", [("reference_days", 14), ("k", 4.0), ("dataset_version", "fixture-v2"),
                                         ("dataset_hash", "c" * 64), ("dataset_identity", "other-dataset"),
                                         ("latitude", 30.0), ("longitude", 70.0), ("magnitude", 6.5),
                                         ("output", "other/output"), ("manifest", "c" * 64)])
def test_d_parameter_or_dataset_change_requires_new_digest_and_review(proposal, field, value):
    settings = config("legacy")
    original = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    records = review_chain(original)
    if field.startswith("dataset_"):
        settings["dataset"][field.removeprefix("dataset_").replace("hash", "sha256")] = value
    elif field in ("latitude", "longitude", "magnitude"):
        settings["epicenter"][field] = value
    elif field == "output":
        settings["output"]["identity"] = value
    elif field == "manifest":
        settings["manifest"]["sha256"] = value
    else:
        settings[field] = value
    changed = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    assert changed.digest != original.digest
    assert changed.to_dict()["proposal_digest"] == original.to_dict()["proposal_digest"]
    assert "mismatched_decision_binding" in validate(changed, proposal, records)["reasons"]
    with pytest.raises(ValueError, match="new review"):
        declaration(changed, previous=records[-1], decision_id="synthetic-invalid-carryover")


@pytest.mark.parametrize("field,value", [("input_mode", "auto"), ("reference_days", True), ("reference_days", 0),
                                         ("k", -1), ("k", float("nan")), ("case_id", "other"),
                                         ("manifest", None), ("verified", True)])
def test_invalid_d_configuration_and_trust_claims_are_rejected(proposal, field, value):
    settings = config("legacy")
    settings[field] = value
    with pytest.raises(ValueError):
        build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)


def test_dataset_must_declare_version_or_hash(proposal):
    settings = config()
    settings["dataset"].update(version=None, sha256=None)
    with pytest.raises(ValueError, match="version or hash"):
        build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)


def test_input_mode_change_also_changes_intent_digest(proposal):
    settings = config("legacy")
    legacy = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    settings["input_mode"] = "modern"  # retain the same optional manifest to isolate mode binding
    modern = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    assert legacy.digest != modern.digest


def test_intent_and_record_are_immutable_and_deterministically_serialized(proposal, intent):
    rebuilt = build_execution_intent(deepcopy(proposal), selected_cluster_id=0, framework_d=config())
    assert rebuilt.to_json() == intent.to_json() and rebuilt.digest == intent.digest
    assert ExecutionIntent.from_json(intent.to_json()) == intent
    pending = declaration(intent)
    assert DecisionRecord.from_json(pending.to_json()) == pending
    assert declaration(intent).to_json() == pending.to_json()
    for record in (intent, pending):
        with pytest.raises(FrozenInstanceError):
            record._json = "{}"
        detached = record.to_dict()
        detached["schema_version"] = 99
        assert record.to_dict()["schema_version"] == 1
        assert json.loads(record.to_json()) == record.to_dict()


@pytest.mark.parametrize("record_type", ["intent", "decision"])
def test_modified_payload_with_stale_record_digest_is_rejected(intent, record_type):
    data = intent.to_dict() if record_type == "intent" else declaration(intent).to_dict()
    if record_type == "intent":
        data["framework_d"]["k"] = 4.0
        parser = ExecutionIntent.from_dict
    else:
        data["reason"] = "Modified after review"
        parser = DecisionRecord.from_dict
    with pytest.raises(ValueError, match="digest"):
        parser(data)


def test_resealed_forged_candidate_identity_is_rejected_against_proposal(intent, proposal):
    data = intent.to_dict()
    data["candidate"]["candidate_id"] = "c" * 64
    altered = ExecutionIntent.from_dict(reseal(data, "execution_intent_digest"))
    assert "invalid_or_stale_intent" in validate(altered, proposal, review_chain(altered))["reasons"]


def test_forged_source_verification_claim_is_not_accepted(intent):
    data = intent.to_dict()
    data["source_hash_verification"] = "verified"
    with pytest.raises(ValueError, match="cannot be elevated"):
        ExecutionIntent.from_dict(reseal(data, "execution_intent_digest"))


@pytest.mark.parametrize("record_type", ["intent", "decision"])
@pytest.mark.parametrize("change", [dict(schema_version=True), dict(schema_version=2), dict(extra="field")])
def test_unsupported_record_schema_is_rejected(intent, record_type, change):
    record = intent if record_type == "intent" else declaration(intent)
    field = "execution_intent_digest" if record_type == "intent" else "decision_digest"
    parser = ExecutionIntent.from_dict if record_type == "intent" else DecisionRecord.from_dict
    data = record.to_dict()
    data.update(change)
    with pytest.raises(ValueError):
        parser(reseal(data, field))


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"value":NaN}', '{"value":Infinity}', '{"value":1e999}', '[]'])
def test_strict_json_parsers_reject_malformed_records(text):
    for parser in (ExecutionIntent.from_json, DecisionRecord.from_json):
        with pytest.raises(ValueError):
            parser(text)


def test_valid_approved_declaration_chain_is_not_trusted_authorization(intent, proposal):
    records = review_chain(intent)
    result = validate(intent, proposal, records)
    assert result["intent_valid"] and result["records_structurally_valid"] and result["decision_history_valid"]
    assert result["review_status"] == "approved" and result["approved_review_status"] is True
    assert result["reasons"] == ["trusted_authorizer_not_configured"]
    assert validate(intent.to_dict(), proposal, [record.to_dict() for record in reversed(records)]) == result


@pytest.mark.parametrize("records", [None, []])
def test_missing_decision_fails_closed(intent, proposal, records):
    result = validate(intent, proposal, records)
    assert "missing_decision" in result["reasons"] and not result["approved_review_status"]


@pytest.mark.parametrize("status", ["pending_review", "rejected", "revision_requested", "revoked"])
def test_nonapproved_status_is_denied(intent, proposal, status):
    if status == "pending_review":
        records = [declaration(intent)]
    elif status == "revoked":
        records = list(review_chain(intent))
        records.append(declaration(intent, "revoked", previous=records[-1], decision_id="synthetic-revoked",
                                   stamp="2001-01-01T01:30:00Z"))
    else:
        records = review_chain(intent, status)
    result = validate(intent, proposal, records)
    assert result["decision_history_valid"] and not result["approved_review_status"]
    assert result["review_status"] == status and "review_status:" + status in result["reasons"]


@pytest.mark.parametrize("initial", ["rejected", "revision_requested", "revoked"])
def test_rereview_requires_new_pending_then_approved(intent, proposal, initial):
    records = list(review_chain(intent, initial if initial != "revoked" else "approved"))
    if initial == "revoked":
        records.append(declaration(intent, "revoked", previous=records[-1], decision_id="synthetic-revoked",
                                   stamp="2001-01-01T01:05:00Z"))
    records.append(declaration(intent, previous=records[-1], decision_id="synthetic-new-pending",
                               stamp="2001-01-01T01:10:00Z"))
    records.append(declaration(intent, "approved", previous=records[-1], decision_id="synthetic-new-approved",
                               stamp="2001-01-01T01:20:00Z"))
    result = validate(intent, proposal, records)
    assert result["approved_review_status"] and result["decision_history_valid"]


@pytest.mark.parametrize("status", ["yes", "approve", "", True])
def test_invalid_status_is_rejected(intent, status):
    with pytest.raises(ValueError):
        declaration(intent, status)


@pytest.mark.parametrize("root_status", ["approved", "rejected", "revision_requested", "revoked"])
def test_initial_record_must_be_pending_review(intent, proposal, root_status):
    result = validate(intent, proposal, [declaration(intent, root_status)])
    assert result["records_structurally_valid"] and not result["decision_history_valid"]
    assert "invalid_initial_state" in result["reasons"]


@pytest.mark.parametrize("parent_status,child_status", [("pending_review", "revoked"),
                                                        ("approved", "rejected"),
                                                        ("rejected", "approved"),
                                                        ("revision_requested", "approved")])
def test_invalid_state_transitions_are_rejected(intent, proposal, parent_status, child_status):
    records = [declaration(intent)] if parent_status == "pending_review" else list(review_chain(intent, parent_status))
    records.append(declaration(intent, child_status, previous=records[-1], decision_id="synthetic-invalid-transition",
                               stamp="2001-01-01T01:30:00Z"))
    assert "invalid_state_transition" in validate(intent, proposal, records)["reasons"]


def test_conflicting_approvals_do_not_choose_latest_timestamp_or_input_position(intent, proposal):
    pending, approved = review_chain(intent)
    competing = declaration(intent, "approved", previous=pending, decision_id="synthetic-competing",
                            stamp="2001-01-01T01:50:00Z")
    first = validate(intent, proposal, [pending, approved, competing])
    second = validate(intent, proposal, [competing, pending, approved])
    assert first == second and "conflicting_decision_branches" in first["reasons"]


def test_multiple_roots_and_duplicate_ids_are_ambiguous(intent, proposal):
    pending = declaration(intent)
    assert "duplicate_or_conflicting_decision_id" in validate(intent, proposal, [pending, pending])["reasons"]
    other = declaration(intent, decision_id="synthetic-other-root")
    assert "missing_or_ambiguous_decision_root" in validate(intent, proposal, [pending, other])["reasons"]


@pytest.mark.parametrize("kind", ["missing_parent", "wrong_parent_digest", "wrong_revision", "reverse_time"])
def test_invalid_supersession_and_revision_consistency(intent, proposal, kind):
    pending, approved = review_chain(intent)
    data = approved.to_dict()
    if kind == "missing_parent":
        data["supersedes"]["decision_id"] = "synthetic-absent"
    elif kind == "wrong_parent_digest":
        data["supersedes"]["decision_digest"] = "c" * 64
    elif kind == "wrong_revision":
        data["revision"] += 1
    else:
        data["decision_time_utc"] = "2000-12-31T23:59:59Z"
    altered = DecisionRecord.from_dict(reseal(data, "decision_digest"))
    result = validate(intent, proposal, [pending, altered])
    expected = {"missing_parent": "missing_superseded_decision", "wrong_parent_digest": "supersession_digest_mismatch",
                "wrong_revision": "inconsistent_decision_revision", "reverse_time": "reversed_decision_timestamps"}
    assert expected[kind] in result["reasons"]


@pytest.mark.parametrize("now,expired", [("2001-01-01T01:59:59Z", False), (NOW, True), ("2001-01-02T00:00:00Z", True)])
def test_expiry_is_exclusive_and_always_denied_without_trust(intent, proposal, now, expired):
    result = validate(intent, proposal, review_chain(intent, expires=NOW), now)
    assert result["approved_review_status"] and result["decision_history_valid"]
    assert ("expired_decision" in result["reasons"]) is expired


@pytest.mark.parametrize("stamp", ["2001-01-01", "2001-01-01T00:00:00", "2001-01-01T00:00:00+08:00", "bad"])
def test_invalid_utc_decision_timestamps_are_rejected(intent, stamp):
    with pytest.raises(ValueError):
        declaration(intent, stamp=stamp)


def test_invalid_expiry_and_future_timestamp_are_denied(intent, proposal):
    with pytest.raises(ValueError, match="Expiration"):
        declaration(intent, expires="2000-12-31T23:59:59Z")
    records = review_chain(intent)
    result = validate(intent, proposal, records, now="2000-12-31T23:59:59Z")
    assert "future_decision_timestamp" in result["reasons"]


def test_spoofed_identity_in_untrusted_approved_json_cannot_authorize(intent, proposal):
    pending = declaration(intent, reviewer="CLAIMED administrator (synthetic spoof)")
    approved = declaration(intent, "approved", previous=pending, decision_id="synthetic-spoofed-approved",
                           stamp="2001-01-01T01:00:00Z", reviewer="CLAIMED principal investigator (synthetic spoof)")
    records = [json.loads(record.to_json()) for record in (pending, approved)]
    result = validate(intent, proposal, records)
    assert result["records_structurally_valid"] and result["approved_review_status"]
    assert approved.to_dict()["trusted_authorization_verification"] == "not_verified"


@pytest.mark.parametrize("claim", ["verified", True, dict(status="verified")])
def test_json_cannot_promote_itself_to_trusted_verification(intent, proposal, claim):
    pending, approved = review_chain(intent)
    data = approved.to_dict()
    data["trusted_authorization_verification"] = claim
    result = validate(intent, proposal, [pending.to_dict(), reseal(data, "decision_digest")])
    assert not result["records_structurally_valid"] and "invalid_decision_record" in result["reasons"]


def test_no_agent_controlled_trust_switch(intent, proposal):
    with pytest.raises(TypeError):
        validate_decisions(intent, proposal, review_chain(intent), now_utc=NOW, trust=True)


def test_no_mutation_of_evidence_proposal_intent_or_decisions(historical):
    before_history = deepcopy(historical)
    proposal = plan(historical, ["normal", "positive", "normal"])
    before_proposal = deepcopy(proposal)
    settings = config()
    before_settings = deepcopy(settings)
    intent = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    records = [record.to_dict() for record in review_chain(intent)]
    before_records = deepcopy(records)
    validate(intent, proposal, records)
    assert historical == before_history and proposal == before_proposal
    assert settings == before_settings and records == before_records


def test_contract_operations_do_not_execute_frameworks_or_stage2(proposal, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Review contracts must not execute scientific workflows.")

    import src.temporal_anomaly.temporal_anomaly as temporal_module
    import src.workflow.statistical_analysis_adapter as analysis_module
    import src.workflow.statistical_significance_adapter as significance_module
    import src.workflow.clustering_adapter as clustering_module
    import src.spatial_verification.spatial_anomaly as spatial_module
    import src.workflow.stage2_runner as runner_module
    import src.workflow.stage2_cli as cli_module

    for module, name in ((temporal_module, "detect_temporal_anomalies"), (analysis_module, "run_statistical_analysis"),
                         (significance_module, "run_statistical_significance"), (clustering_module, "run_clustering_workflow"),
                         (spatial_module, "compute_spatial_anomalies"), (runner_module, "run_stage2"), (cli_module, "main")):
        monkeypatch.setattr(module, name, forbidden)
    intent = build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())
    assert validate(intent, proposal, review_chain(intent))["approved_review_status"]
