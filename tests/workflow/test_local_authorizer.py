"""Synthetic local composition only; NO genuine Windows isolation/human approval."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path

import pytest

import src.workflow.local_authorizer as module
from src.workflow.authorization_store import AuthorizationStore
from src.workflow.local_authorizer import LocalAuthorizationVerifier, VerifierConfigurationV1
from src.workflow.planning_approval import build_execution_intent, validate_decisions
from tests.workflow.test_authorization_store import (
    STORE_ID, OTHER_STORE, NOW, TestOnlyTrustedWriterHarness, add_chain, disk_entries, rewrite,
)
from tests.workflow.test_planning_approval import config, declaration, intent, proposal, review_chain
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_signed_authorization import key, registry, registry_data


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class DemonstrationDeployment:
    """Test-only bootstrap/publisher with ephemeral keys; not an OS trust boundary."""

    def __init__(self, root, key, registry):
        self.store_root = root / "store"
        self.anchors = root / "anchors"
        self.store_root.mkdir()
        self.anchors.mkdir()
        self.writer = TestOnlyTrustedWriterHarness(self.store_root, key, registry)
        self.configuration_path = self.anchors / "verifier.json"
        self.registry_path = self.anchors / "reviewers.json"
        self.checkpoint_path = self.anchors / "retained-checkpoint.json"
        self.registry_path.write_bytes(registry.to_json().encode("utf-8"))
        self.pin_current()

    def pin_current(self):
        # EXPLICIT test-side retained snapshot and config publication, not a
        # verifier operation, TOFU, OS protection or real researcher action.
        raw = (self.store_root / "checkpoint.json").read_bytes()
        self.checkpoint_path.write_bytes(raw)
        floor = json.loads(raw)
        data = dict(
            configuration_type="local_authorization_verifier_configuration", schema_version=1,
            configuration_id="11111111-1111-4111-8111-111111111111",
            store=dict(store_id=STORE_ID, root=str(self.store_root)),
            registry=dict(path=str(self.registry_path), sha256=sha(self.registry_path.read_bytes())),
            minimum_checkpoint=dict(path=str(self.checkpoint_path), sha256=sha(raw),
                                    sequence=floor["sequence"], entry_digest=floor["entry_digest"]),
            deployment=dict(deployment_id="22222222-2222-4222-8222-222222222222",
                            verifier_code_sha256="a" * 64, dependency_manifest_sha256="b" * 64,
                            isolation_requirement="separate_windows_security_identities"),
            expected_authorization_scope=module._SCOPE, time_source="local_system_utc_unverified",
        )
        self.publish(data)

    def publish(self, data):
        raw = (json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        self.publish_raw(raw)

    def publish_raw(self, raw):
        self.configuration_path.write_bytes(raw)
        self.verifier = LocalAuthorizationVerifier(self.configuration_path, expected_config_sha256=sha(raw))

    def data(self):
        return json.loads(self.configuration_path.read_bytes())

    def verify(self, digest):
        result = self.verifier.verify(digest)
        for field in ("trusted_configuration_origin_verified", "trusted_registry_origin_verified",
                      "trusted_store_origin_verified", "independent_checkpoint_verified",
                      "deployment_isolation_verified", "verifier_deployment_identity_verified",
                      "authoritative_freshness_verified", "trusted_time_verified",
                      "trusted_human_authorization", "execution_eligible"):
            assert result[field] is False
        assert result["current_authorization_state"] == "not_verified"
        assert result["deployment_mode"] == "demonstration_only"
        assert json.loads(json.dumps(result, allow_nan=False)) == result
        return result


@pytest.fixture
def deployment(tmp_path, key, registry, monkeypatch):
    # Test clock substitution is not a public time override or secure-clock test.
    monkeypatch.setattr(module, "_now_utc", lambda: NOW)
    return DemonstrationDeployment(tmp_path, key, registry)


def approved(deployment, intent, proposal):
    records, entries = add_chain(deployment.writer, intent, proposal)
    deployment.pin_current()
    return records, entries


def test_approved_is_exact_local_state_without_authorization(deployment, intent, proposal):
    records, _ = approved(deployment, intent, proposal)
    result = deployment.verify(intent.digest)
    assert result["result_type"] == "local_authorization_verification" and result["schema_version"] == 1
    assert result["local_store_valid"] and result["requested_intent_present"]
    assert result["proposal_intent_consistent"] and result["authorization_scope_consistent"]
    assert result["entries_signature_valid"] and result["decision_history_valid"]
    assert result["effective_review_status"] == "approved"
    assert result["effective_decision_id"] == records[-1].to_dict()["decision_id"]
    assert result["local_review_state"] == "approved_unverified"
    assert result["latest_attestation_time_valid"] is True
    assert result["checkpoint_matches_store"] and result["checkpoint_is_current_head"]
    assert result["reason_codes"][0] == "approved_unverified"


@pytest.mark.parametrize("status", ["pending_review", "rejected", "revision_requested", "revoked"])
def test_nonapproved_effective_states(deployment, intent, proposal, status):
    if status == "revoked":
        records, _ = add_chain(deployment.writer, intent, proposal, True)
    else:
        records = [declaration(intent)] if status == "pending_review" else list(review_chain(intent, status))
        for record in records:
            deployment.writer.add(intent, proposal, record)
    deployment.pin_current()
    result = deployment.verify(intent.digest)
    assert result["local_store_valid"]
    assert result["effective_review_status"] == status and result["local_review_state"] == status
    assert result["effective_decision_id"] == records[-1].to_dict()["decision_id"]


@pytest.mark.parametrize("expiry_kind", ["decision", "attestation"])
def test_expired_approval_remains_non_authorizing(deployment, intent, proposal, monkeypatch, expiry_kind):
    records = review_chain(intent, expires="2001-01-01T03:00:00Z" if expiry_kind == "decision" else None)
    for record in records:
        options = {} if expiry_kind == "decision" else dict(expires_at_utc="2001-01-01T03:00:00Z")
        deployment.writer.add(intent, proposal, record, **options)
    deployment.pin_current()
    monkeypatch.setattr(module, "_now_utc", lambda: "2001-01-01T03:00:00Z")
    result = deployment.verify(intent.digest)
    assert result["local_store_valid"] and result["entries_signature_valid"]
    assert result["effective_review_status"] == "approved"
    assert result["latest_attestation_time_valid"] is False
    assert result["local_review_state"] == "expired_approval"


def test_intent_absent_and_same_window_is_not_same_intent(deployment, intent, proposal):
    approved(deployment, intent, proposal)
    settings = config()
    settings["output"]["identity"] = "synthetic-other-output"
    other = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    assert other.to_dict()["window"] == intent.to_dict()["window"] and other.digest != intent.digest
    for digest in ("e" * 64, other.digest):
        result = deployment.verify(digest)
        assert result["local_store_valid"] and not result["requested_intent_present"]
        assert result["effective_review_status"] is None and result["effective_decision_id"] is None
        assert result["reason_codes"][0] == "requested_intent_not_found"


def test_interleaved_intents_are_selected_by_exact_digest(deployment, intent, proposal):
    settings = config()
    settings["k"] = 4.0  # synthetic configuration binding only, never a scientific run
    other = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    first = review_chain(intent)
    second_pending = declaration(other, decision_id="synthetic-other-pending")
    second_rejected = declaration(other, "rejected", previous=second_pending, decision_id="synthetic-other-rejected",
                                  stamp="2001-01-01T01:00:00Z")
    for i, d in ((intent, first[0]), (other, second_pending), (intent, first[1]), (other, second_rejected)):
        deployment.writer.add(i, proposal, d)
    deployment.pin_current()
    assert deployment.verify(intent.digest)["effective_review_status"] == "approved"
    assert deployment.verify(other.digest)["effective_review_status"] == "rejected"


@pytest.mark.parametrize("change", ["tamper", "whitespace", "missing", "wrong_pin", "invalid_schema"])
def test_registry_acquisition_and_identity(deployment, intent, proposal, change):
    approved(deployment, intent, proposal)
    data = deployment.data()
    if change == "missing":
        deployment.registry_path.unlink()
    elif change == "wrong_pin":
        data["registry"]["sha256"] = "e" * 64
        deployment.publish(data)
    elif change == "whitespace":
        deployment.registry_path.write_bytes(deployment.registry_path.read_bytes() + b" ")
    else:
        registry = registry_data(deployment.writer.key)
        registry["entries"][0]["reviewer_identity"] = "synthetic-tamper"
        if change == "invalid_schema":
            registry["claimed_trusted"] = True
        raw = json.dumps(registry).encode("utf-8")
        deployment.registry_path.write_bytes(raw)
        if change == "invalid_schema":
            data["registry"]["sha256"] = sha(raw)
            deployment.publish(data)
    result = deployment.verify(intent.digest)
    expected = "registry_unavailable" if change == "missing" else (
        "registry_invalid" if change == "invalid_schema" else "registry_identity_mismatch")
    assert result["reason_codes"][0] == expected
    assert not result["local_store_valid"] and result["effective_review_status"] is None


@pytest.mark.parametrize("policy", ["unknown", "disabled", "revoked"])
def test_pinned_registry_policy_is_still_enforced(deployment, intent, proposal, policy):
    approved(deployment, intent, proposal)
    registry = registry_data(deployment.writer.key)
    if policy == "unknown":
        registry["entries"] = []
    elif policy == "disabled":
        registry["entries"][0]["enabled"] = False
    else:
        registry["entries"][0]["revoked"] = True
    deployment.registry_path.write_bytes(json.dumps(registry).encode("utf-8"))
    data = deployment.data()
    data["registry"]["sha256"] = sha(deployment.registry_path.read_bytes())
    deployment.publish(data)
    result = deployment.verify(intent.digest)
    assert result["registry_valid"] and result["registry_content_matches_pin"]
    assert result["reason_codes"][0] == "store_invalid"
    assert result["store_reason_codes"] == ["invalid_entry_signature"]


@pytest.mark.parametrize("change", ["missing", "replaced", "invalid", "wrong_store", "wrong_sequence", "wrong_digest"])
def test_required_retained_checkpoint(deployment, intent, proposal, change):
    initial = deployment.checkpoint_path.read_bytes()
    approved(deployment, intent, proposal)
    data = deployment.data()
    if change == "missing":
        deployment.checkpoint_path.unlink()
    elif change == "replaced":
        deployment.checkpoint_path.write_bytes(initial)
    else:
        floor = json.loads(deployment.checkpoint_path.read_bytes())
        if change == "invalid":
            floor["extra"] = True
        elif change == "wrong_store":
            floor["store_id"] = OTHER_STORE
        elif change == "wrong_sequence":
            floor["sequence"] += 1
        else:
            floor["entry_digest"] = "e" * 64
        raw = json.dumps(floor).encode("utf-8")
        deployment.checkpoint_path.write_bytes(raw)
        data["minimum_checkpoint"]["sha256"] = sha(raw)  # explicit test pin; keep expected position
        deployment.publish(data)
    result = deployment.verify(intent.digest)
    expected = {"missing": "checkpoint_unavailable", "replaced": "checkpoint_identity_mismatch",
                "invalid": "checkpoint_invalid"}.get(change, "checkpoint_position_mismatch")
    assert result["reason_codes"][0] == expected and not result["local_store_valid"]


def test_whole_root_rollback_is_detected_by_independent_newer_floor(deployment, intent, proposal):
    add_chain(deployment.writer, intent, proposal, True)
    deployment.pin_current()
    entries = disk_entries(deployment.writer)
    rewrite(deployment.writer, entries[:2])
    assert deployment.writer.validate()["effective_review_status"] == {intent.digest: "approved"}
    result = deployment.verify(intent.digest)
    assert result["reason_codes"][0] == "store_invalid"
    assert result["store_reason_codes"] == ["checkpoint_rollback"]
    assert result["effective_review_status"] is None


def test_old_floor_is_only_a_lower_bound_not_freshness(deployment, intent, proposal):
    approved(deployment, intent, proposal)
    entries = disk_entries(deployment.writer)
    parent = review_chain(intent)[-1]
    revoked = declaration(intent, "revoked", previous=parent, decision_id="synthetic-later-revoked",
                          stamp="2001-01-01T01:30:00Z")
    deployment.writer.add(intent, proposal, revoked)
    result = deployment.verify(intent.digest)
    assert result["effective_review_status"] == "revoked" and result["checkpoint_matches_store"]
    assert not result["checkpoint_is_current_head"]
    assert "checkpoint_is_only_lower_bound" in result["reason_codes"]
    rewrite(deployment.writer, entries)  # floor itself cannot detect unseen newer history
    assert deployment.verify(intent.digest)["local_review_state"] == "approved_unverified"


@pytest.mark.parametrize("filename", ["history.jsonl", "head.json", "checkpoint.json", "history.lock"])
def test_incomplete_store_never_falls_back_to_old_approval(deployment, intent, proposal, filename):
    add_chain(deployment.writer, intent, proposal, True)
    deployment.pin_current()
    path = deployment.store_root / filename
    if filename == "history.lock":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes()[:-11])
    before = {file.name: file.read_bytes() for file in deployment.store_root.iterdir()}
    result = deployment.verify(intent.digest)
    assert result["reason_codes"][0] == "store_invalid"
    assert result["effective_review_status"] is None
    assert {file.name: file.read_bytes() for file in deployment.store_root.iterdir()} == before


@pytest.mark.parametrize("source", ["store", "registry", "checkpoint"])
def test_wrong_fixed_source_path(deployment, intent, source):
    data = deployment.data()
    if source == "store":
        data["store"]["root"] = str(deployment.anchors / "missing-store")
    else:
        data["registry" if source == "registry" else "minimum_checkpoint"]["path"] = str(deployment.anchors / "missing-file")
    deployment.publish(data)
    assert deployment.verify(intent.digest)["reason_codes"][0] == source + "_unavailable"


def test_unexpected_configured_store_identity(deployment, intent):
    data = deployment.data()
    data["store"]["store_id"] = OTHER_STORE
    deployment.publish(data)
    result = deployment.verify(intent.digest)
    assert result["reason_codes"][0] == "checkpoint_position_mismatch"


@pytest.mark.parametrize("source", ["configuration", "registry", "checkpoint"])
def test_trust_anchors_cannot_live_inside_store(deployment, intent, source):
    data = deployment.data()
    if source == "configuration":
        old = deployment.configuration_path
        deployment.configuration_path = deployment.store_root / "verifier.json"
        deployment.publish(data)
        old.unlink()
    else:
        field = "registry" if source == "registry" else "minimum_checkpoint"
        destination = deployment.store_root / (source + "-copy.json")
        destination.write_bytes(Path(data[field]["path"]).read_bytes())
        data[field]["path"] = str(destination)
        deployment.publish(data)
    assert deployment.verify(intent.digest)["reason_codes"][0] == source + "_path_not_independent"


def test_checkpoint_outside_store_but_hardlinked_to_mutable_marker_is_rejected(deployment, intent):
    deployment.checkpoint_path.unlink()
    os.link(deployment.store_root / "checkpoint.json", deployment.checkpoint_path)
    result = deployment.verify(intent.digest)
    assert result["reason_codes"][0] == "checkpoint_path_not_independent"


@pytest.mark.parametrize("change", ["missing", "tamper", "wrong_pin", "malformed", "missing_field"])
def test_missing_or_invalid_configuration(deployment, intent, change):
    if change == "missing":
        deployment.configuration_path.unlink()
    elif change == "tamper":
        deployment.configuration_path.write_bytes(deployment.configuration_path.read_bytes() + b" ")
    elif change == "wrong_pin":
        deployment.verifier = LocalAuthorizationVerifier(deployment.configuration_path, expected_config_sha256="e" * 64)
    elif change == "malformed":
        deployment.publish_raw(b'{"broken":')
    else:
        data = deployment.data()
        data.pop("minimum_checkpoint")
        deployment.publish(data)
    expected = "configuration_unavailable" if change == "missing" else (
        "configuration_invalid" if change in ("malformed", "missing_field") else "configuration_identity_mismatch")
    assert deployment.verify(intent.digest)["reason_codes"][0] == expected


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 2), ("trust", True), ("execution_eligible", True),
    ("trusted_human_authorization", True), ("effective_review_status", "approved"),
    ("time_source", "trusted"), ("expected_authorization_scope", "Execute anything"),
])
def test_configuration_cannot_self_attest_trust_or_approval(deployment, intent, field, value):
    data = deployment.data()
    data[field] = value
    deployment.publish(data)
    result = deployment.verify(intent.digest)
    assert result["reason_codes"][0] == "configuration_invalid"


@pytest.mark.parametrize("field", ["store", "registry", "minimum_checkpoint", "deployment"])
def test_nested_configuration_claims_are_rejected(deployment, intent, field):
    data = deployment.data()
    data[field]["verified"] = True
    deployment.publish(data)
    assert deployment.verify(intent.digest)["reason_codes"][0] == "configuration_invalid"


@pytest.mark.parametrize("options", [dict(trust=True), dict(assume_authorized=True), dict(records=[]),
                                     dict(registry_path="agent-selected"), dict(store_root="other"),
                                     dict(minimum_checkpoint={}), dict(now_utc=NOW)])
def test_no_query_time_trust_paths_records_or_clock_overrides(deployment, intent, options):
    with pytest.raises(TypeError):
        deployment.verifier.verify(intent.digest, **options)


def test_subset_cannot_change_revoked_state(deployment, intent, proposal):
    records, _ = add_chain(deployment.writer, intent, proposal, True)
    deployment.pin_current()
    assert validate_decisions(intent, proposal, records[:2], now_utc=NOW)["approved_review_status"]
    assert deployment.verify(intent.digest)["effective_review_status"] == "revoked"
    with pytest.raises(TypeError):
        deployment.verifier.verify(intent.digest, decisions=records[:2])


def test_shared_user_even_with_matching_pins_is_demonstration_only(deployment, intent, proposal):
    approved(deployment, intent, proposal)
    result = deployment.verify(intent.digest)
    assert result["configuration_content_matches_pin"] and result["registry_content_matches_pin"]
    assert result["independent_checkpoint_content_matches_pin"] and result["checkpoint_matches_store"]
    assert "deployment_isolation_not_verified" in result["reason_codes"]
    data = deployment.data()
    data["deployment"]["isolation_requirement"] = "verified_windows_acl"
    deployment.publish(data)
    assert deployment.verify(intent.digest)["reason_codes"][0] == "configuration_invalid"


@pytest.mark.parametrize("digest", [None, True, 123, "a" * 63, "A" * 64, {"claimed_digest": "a" * 64}])
def test_invalid_request_digest_returns_strict_fail_closed_result(deployment, digest):
    result = deployment.verify(digest)
    assert result["requested_execution_intent_digest"] is None
    assert result["reason_codes"][0] == "invalid_execution_intent_digest"


@pytest.mark.parametrize("source,limit", [("configuration", module.MAX_CONFIGURATION_BYTES),
                                        ("registry", module.MAX_REGISTRY_BYTES), ("checkpoint", module.MAX_MARKER_BYTES)])
def test_source_byte_limits(deployment, intent, source, limit):
    data = deployment.data()
    raw = b" " * (limit + 1)
    if source == "configuration":
        deployment.publish_raw(raw)
    else:
        path = deployment.registry_path if source == "registry" else deployment.checkpoint_path
        path.write_bytes(raw)
        data["registry" if source == "registry" else "minimum_checkpoint"]["sha256"] = sha(raw)
        deployment.publish(data)
    assert deployment.verify(intent.digest)["reason_codes"][0] == source + "_too_large"


@pytest.mark.parametrize("raw", [b'[' * 5000 + b'null' + b']' * 5000, b'{"a":1,"a":2}', b'{"a":NaN}'],
                         ids=["deep", "duplicate_keys", "nonfinite"])
def test_strict_bounded_configuration_parsing(deployment, intent, raw):
    deployment.publish_raw(raw)
    assert deployment.verify(intent.digest)["reason_codes"][0] == "configuration_invalid"


def test_configuration_is_immutable_and_serialization_is_deterministic(deployment):
    data = deployment.data()
    configuration = VerifierConfigurationV1.from_dict(data)
    assert VerifierConfigurationV1.from_json(configuration.to_json()) == configuration
    assert VerifierConfigurationV1.from_dict(deepcopy(data)).to_json() == configuration.to_json()
    with pytest.raises(FrozenInstanceError):
        configuration._json = "{}"
    detached = configuration.to_dict()
    detached["store"]["store_id"] = OTHER_STORE
    assert configuration.to_dict() == data


def test_query_does_not_mutate_any_file_or_existing_v1_object(deployment, intent, proposal):
    records, entries = approved(deployment, intent, proposal)
    snapshot = {str(path): path.read_bytes() for directory in (deployment.store_root, deployment.anchors)
                for path in directory.iterdir()}
    content = deepcopy(proposal), intent.to_json(), [record.to_json() for record in records], [entry.to_json() for entry in entries]
    first = deployment.verify(intent.digest)
    assert deployment.verify(intent.digest) == first
    assert snapshot == {str(path): path.read_bytes() for directory in (deployment.store_root, deployment.anchors)
                        for path in directory.iterdir()}
    assert content == (proposal, intent.to_json(), [record.to_json() for record in records], [entry.to_json() for entry in entries])


@pytest.mark.parametrize("source", ["configuration", "registry", "checkpoint"])
def test_source_replacement_during_store_validation_is_rejected(deployment, intent, proposal, monkeypatch, source):
    approved(deployment, intent, proposal)
    original = AuthorizationStore.validate

    def replace_source(store, **kwargs):
        result = original(store, **kwargs)
        path = {"configuration": deployment.configuration_path, "registry": deployment.registry_path,
                "checkpoint": deployment.checkpoint_path}[source]
        path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(AuthorizationStore, "validate", replace_source)
    result = deployment.verify(intent.digest)
    assert result["reason_codes"][0] == source + "_identity_mismatch"
    assert not result["local_store_valid"] and result["effective_review_status"] is None


def test_store_claimed_trust_flags_cannot_promote_result(deployment, intent, proposal, monkeypatch):
    approved(deployment, intent, proposal)
    original = AuthorizationStore.validate

    def injected_claims(store, **kwargs):
        return {**original(store, **kwargs), "execution_eligible": True, "trusted_human_authorization": True,
                "store_origin_authenticated": True, "registry_origin_authenticated": True}

    monkeypatch.setattr(AuthorizationStore, "validate", injected_claims)
    assert deployment.verify(intent.digest)["local_review_state"] == "approved_unverified"


@pytest.mark.parametrize("error_type", [RuntimeError, RecursionError])
def test_unrelated_store_programming_errors_are_not_suppressed(deployment, intent, monkeypatch, error_type):
    def broken(*args, **kwargs):
        raise error_type("Unrelated verifier programming error")

    monkeypatch.setattr(AuthorizationStore, "validate", broken)
    with pytest.raises(error_type, match="programming"):
        deployment.verifier.verify(intent.digest)


def test_no_scientific_framework_stage2_signing_or_key_generation(deployment, intent, proposal, monkeypatch):
    approved(deployment, intent, proposal)

    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only verification must not execute/sign/generate keys.")

    import src.temporal_anomaly.temporal_anomaly as temporal
    import src.workflow.statistical_analysis_adapter as statistical
    import src.workflow.statistical_significance_adapter as significance
    import src.workflow.clustering_adapter as clustering
    import src.spatial_verification.spatial_anomaly as spatial
    import src.workflow.stage2_runner as runner
    import src.workflow.stage2_cli as cli
    import src.workflow.signed_authorization as signing
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    for target, name in ((temporal, "detect_temporal_anomalies"), (statistical, "run_statistical_analysis"),
                         (significance, "run_statistical_significance"), (clustering, "run_clustering_workflow"),
                         (spatial, "compute_spatial_anomalies"), (runner, "run_stage2"), (cli, "main"),
                         (signing, "sign_attestation"), (Ed25519PrivateKey, "generate"),
                         (AuthorizationStore, "append"), (AuthorizationStore, "initialize")):
        monkeypatch.setattr(target, name, forbidden)
    assert deployment.verify(intent.digest)["local_store_valid"]


def test_lock_contention_denies_query_without_fallback(deployment, intent, proposal):
    approved(deployment, intent, proposal)
    from src.workflow.authorization_store import _exclusive

    with _exclusive(deployment.store_root):
        result = deployment.verify(intent.digest)
    assert result["reason_codes"][0] == "store_invalid"
    assert result["store_reason_codes"] == ["lock_unavailable"]
    assert result["effective_review_status"] is None


def test_directory_is_not_a_registry_file(deployment, intent):
    data = deployment.data()
    data["registry"]["path"] = str(deployment.anchors)
    deployment.publish(data)
    assert deployment.verify(intent.digest)["reason_codes"][0] == "registry_unavailable"


@pytest.mark.parametrize("case", ["relative", "none_path", "none_pin", "bool_pin", "uppercase_pin", "unc", "missing_pin"])
def test_bootstrap_requires_explicit_valid_local_path_and_pin(deployment, case):
    path, pin = deployment.configuration_path, "a" * 64
    if case == "relative":
        path = "relative.json"
    elif case == "none_path":
        path = None
    elif case == "none_pin":
        pin = None
    elif case == "bool_pin":
        pin = True
    elif case == "uppercase_pin":
        pin = "A" * 64
    elif case == "unc":
        path = "\\\\example.invalid\\share\\verifier.json"
    with pytest.raises((TypeError, ValueError)):
        if case == "missing_pin":
            LocalAuthorizationVerifier(path)
        else:
            LocalAuthorizationVerifier(path, expected_config_sha256=pin)


@pytest.mark.parametrize("source", ["configuration", "registry", "checkpoint"])
def test_read_permission_errors_are_structured_but_do_not_prove_acl_enforcement(deployment, intent, monkeypatch, source):
    path = {"configuration": deployment.configuration_path, "registry": deployment.registry_path,
            "checkpoint": deployment.checkpoint_path}[source]
    original = Path.open

    def deny_access(candidate, *args, **kwargs):
        if candidate == path:
            raise PermissionError("Synthetic access error, NOT an OS isolation test")
        return original(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_access)
    assert deployment.verify(intent.digest)["reason_codes"][0] == source + "_unavailable"
