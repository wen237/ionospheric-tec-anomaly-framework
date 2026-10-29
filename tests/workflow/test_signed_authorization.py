"""Synthetic V1 statements and ephemeral in-memory keys; no real approvals."""

import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.workflow.planning_approval import DecisionRecord, ExecutionIntent, validate_decisions
from src.workflow.signed_authorization import (
    AuthorizationAttestationV1, CANONICAL_PROFILE, DOMAIN_PREFIX, KEY_PURPOSE,
    MAX_DOCUMENT_BYTES, MAX_NESTING_DEPTH,
    TrustedPublicKeyRegistryV1, attestation_signing_bytes, canonical_payload_bytes,
    key_id_for_public_key, sign_attestation, verify_attestation,
)
from tests.workflow.test_planning_approval import declaration, intent, proposal, reseal, review_chain
from tests.workflow.test_planning_evidence import historical


AUTH_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "22222222-2222-4222-8222-222222222222"
STORE_ID = "33333333-3333-4333-8333-333333333333"
NOW = "2001-01-01T02:00:00Z"
IDENTITY = "synthetic-reviewer (unverified)"


def golden_payload():
    """Unsigned serialization vector; digests are synthetic, not source claims."""
    return dict(
        authorization_type="scientific_execution_authorization_attestation", schema_version=1, algorithm="Ed25519",
        canonical_profile=CANONICAL_PROFILE, execution_intent_digest="a" * 64, proposal_digest="b" * 64,
        decision_record_digest="c" * 64, decision_id="synthetic-vector", review_status="pending_review", revision=0,
        supersedes=None, reviewer_key_id="d" * 64, reviewer_identity="合成審查者", key_purpose=KEY_PURPOSE,
        signed_at_utc="2001-01-01T00:00:00Z", expires_at_utc=None,
        authorization_scope="Only the bound spatial analysis; no causality or earthquake precursor identification is authorized.",
        store=dict(store_id=None, sequence=None, previous_entry_digest=None), authorization_id=AUTH_ID,
    )


def test_documented_canonical_utf8_vector_and_domain_prefix():
    expected = (
        '{"algorithm":"Ed25519","authorization_id":"11111111-1111-4111-8111-111111111111",'
        '"authorization_scope":"Only the bound spatial analysis; no causality or earthquake precursor identification is authorized.",'
        '"authorization_type":"scientific_execution_authorization_attestation",'
        '"canonical_profile":"tec-authorization-json-utf8-lf-v1","decision_id":"synthetic-vector",'
        '"decision_record_digest":"' + "c" * 64 + '","execution_intent_digest":"' + "a" * 64 + '",'
        '"expires_at_utc":null,"key_purpose":"scientific_review_decision","proposal_digest":"' + "b" * 64 + '",'
        '"review_status":"pending_review","reviewer_identity":"合成審查者","reviewer_key_id":"' + "d" * 64 + '",'
        '"revision":0,"schema_version":1,"signed_at_utc":"2001-01-01T00:00:00Z",'
        '"store":{"previous_entry_digest":null,"sequence":null,"store_id":null},"supersedes":null}\n'
    ).encode("utf-8")
    assert canonical_payload_bytes(golden_payload()) == expected
    assert attestation_signing_bytes(golden_payload()) == b"ionospheric-tec/authorization-attestation/v1\x00" + expected
    assert b"\r" not in expected and expected[-1:] == b"\n"
    assert len(expected) == 1016
    assert hashlib.sha256(expected).hexdigest() == "b4919e85b3cfe33473877d8e019b53b1c6cf93dcc2402b7738620e78fecd45f0"
    assert hashlib.sha256(attestation_signing_bytes(golden_payload())).hexdigest() == "9614f4ac2c7d0f586faaf98e819b7324d02b23b2fad6264f516d9bde0154b38a"


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()  # never serialized, persisted or printed


@pytest.fixture
def decision(intent):
    return review_chain(intent)[1]


def registry_data(key):
    public = key.public_key()
    return dict(registry_type="trusted_reviewer_public_keys", schema_version=1, entries=[dict(
        key_id=key_id_for_public_key(public), public_key_b64=base64.b64encode(public.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii"),
        reviewer_identity=IDENTITY, purpose=KEY_PURPOSE, enabled=True, revoked=False,
    )])


@pytest.fixture
def registry(key):
    return TrustedPublicKeyRegistryV1.from_dict(registry_data(key))


def sign(intent, decision, key, **kwargs):
    arguments = dict(private_key=key, reviewer_key_id=key_id_for_public_key(key.public_key()),
                     authorization_id=AUTH_ID, signed_at_utc="2001-01-01T01:05:00Z", expires_at_utc="2001-01-01T03:00:00Z")
    arguments.update(kwargs)
    return sign_attestation(intent, decision, **arguments)


@pytest.fixture
def attestation(intent, decision, key):
    return sign(intent, decision, key)


def verify(attestation, intent, decision, registry, now=NOW):
    result = verify_attestation(attestation, intent, decision, trusted_keys=registry, now_utc=now)
    assert result["execution_eligible"] is False
    for name in ("current_authorization_state", "decision_history_state", "store_state", "authorization_id_uniqueness"):
        assert result[name] == "not_verified"
    assert result["registry_origin_state"] == "caller_supplied_not_authenticated_here"
    return result


def resign(data, key, domain=DOMAIN_PREFIX):
    data = deepcopy(data)
    raw = key.sign(domain + canonical_payload_bytes(data["payload"]))
    data["signature_b64"] = base64.b64encode(raw).decode("ascii")
    return AuthorizationAttestationV1.from_dict(data)


def test_successful_ed25519_verification_is_not_current_authorization(attestation, intent, decision, registry):
    result = verify(attestation, intent, decision, registry)
    for flag in ("attestation_structurally_valid", "contracts_valid", "bindings_valid", "signature_checked",
                 "cryptographic_signature_valid", "key_registered", "key_policy_valid",
                 "registered_trusted_reviewer_signature", "attestation_time_valid", "signature_verification_passed"):
        assert result[flag] is True
    assert result["reason_codes"] == []
    payload = attestation.to_dict()["payload"]
    assert payload["execution_intent_digest"] == intent.digest
    assert payload["proposal_digest"] == intent.to_dict()["proposal_digest"]
    assert payload["decision_record_digest"] == decision.digest
    assert payload["review_status"] == "approved"
    assert payload["supersedes"] == decision.to_dict()["supersedes"]
    assert decision.to_dict()["trusted_authorization_verification"] == "not_verified"


def test_signing_is_deterministic_for_same_key_and_statement(attestation, intent, decision, key):
    assert sign(intent, decision, key).to_json() == attestation.to_json()
    assert attestation_signing_bytes(attestation.to_dict()["payload"]).startswith(DOMAIN_PREFIX)
    assert canonical_payload_bytes(attestation.to_dict()["payload"]).endswith(b"\n")


@pytest.mark.parametrize("field,value", [
    ("execution_intent_digest", "e" * 64), ("proposal_digest", "e" * 64), ("decision_record_digest", "e" * 64),
    ("decision_id", "synthetic-other"), ("review_status", "rejected"), ("revision", 2),
    ("reviewer_identity", "synthetic-other-reviewer"), ("reviewer_key_id", "e" * 64),
    ("signed_at_utc", "2001-01-01T01:06:00Z"), ("expires_at_utc", "2001-01-01T02:59:00Z"),
    ("authorization_scope", "Other operation, not the bound scope."), ("authorization_id", OTHER_ID),
    ("store", dict(store_id=STORE_ID, sequence=1, previous_entry_digest=None)),
])
def test_modified_signed_fields_cannot_reuse_signature(attestation, intent, decision, registry, field, value):
    data = attestation.to_dict()
    data["payload"][field] = value
    result = verify(data, intent, decision, registry)
    assert result["attestation_structurally_valid"]
    assert not result["cryptographic_signature_valid"] and not result["signature_verification_passed"]


@pytest.mark.parametrize("field", ["execution_intent_digest", "proposal_digest", "decision_record_digest",
                                   "decision_id", "review_status", "revision", "reviewer_identity", "authorization_scope"])
def test_even_resigned_mismatched_statement_is_not_a_binding(attestation, intent, decision, registry, key, field):
    data = attestation.to_dict()
    changes = dict(execution_intent_digest="e" * 64, proposal_digest="e" * 64, decision_record_digest="e" * 64,
                   decision_id="synthetic-other", review_status="rejected", revision=2,
                   reviewer_identity="synthetic-other-reviewer", authorization_scope="Other operation.")
    data["payload"][field] = changes[field]
    result = verify(resign(data, key), intent, decision, registry)
    assert result["cryptographic_signature_valid"] and not result["bindings_valid"]
    assert not result["signature_verification_passed"]
    assert "binding_mismatch:" + field in result["reason_codes"]


@pytest.mark.parametrize("kind", ["intent", "proposal", "decision"])
def test_changed_existing_v1_objects_are_rejected(attestation, intent, decision, registry, kind):
    if kind in ("intent", "proposal"):
        data = intent.to_dict()
        if kind == "intent":
            data["framework_d"]["k"] = 4.0
        else:
            data["proposal_digest"] = "e" * 64
        intent = ExecutionIntent.from_dict(reseal(data, "execution_intent_digest"))
    else:
        data = decision.to_dict()
        data["reason"] = "Changed synthetic review reason."
        decision = DecisionRecord.from_dict(reseal(data, "decision_digest"))
    assert not verify(attestation, intent, decision, registry)["signature_verification_passed"]


@pytest.mark.parametrize("kind", ["missing", "wrong_id", "wrong_digest"])
def test_supersession_reference_is_required_and_bound(attestation, intent, decision, registry, key, kind):
    data = attestation.to_dict()
    if kind == "missing":
        data["payload"]["supersedes"] = None
        result = verify(data, intent, decision, registry)
        assert not result["attestation_structurally_valid"]
    else:
        data["payload"]["supersedes"]["decision_id" if kind == "wrong_id" else "decision_digest"] = (
            "synthetic-other-parent" if kind == "wrong_id" else "e" * 64)
        result = verify(resign(data, key), intent, decision, registry)
        assert result["cryptographic_signature_valid"]
        assert "binding_mismatch:supersedes" in result["reason_codes"]
    assert not result["signature_verification_passed"]


@pytest.mark.parametrize("kind", ["empty", "other_key"])
def test_unknown_or_unregistered_key_has_no_trust(attestation, intent, decision, key, kind):
    data = registry_data(key)
    data["entries"] = [] if kind == "empty" else registry_data(Ed25519PrivateKey.generate())["entries"]
    result = verify(attestation, intent, decision, TrustedPublicKeyRegistryV1.from_dict(data))
    assert not result["key_registered"] and not result["signature_checked"]
    assert "unknown_reviewer_key" in result["reason_codes"]


def test_wrong_private_key_cannot_sign_for_registered_key(attestation, intent, decision, registry):
    wrong_key = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="key ID"):
        sign(intent, decision, wrong_key, reviewer_key_id=registry.to_dict()["entries"][0]["key_id"])
    result = verify(resign(attestation.to_dict(), wrong_key), intent, decision, registry)
    assert result["key_registered"] and result["signature_checked"]
    assert not result["cryptographic_signature_valid"]


@pytest.mark.parametrize("field,value,reason", [("revoked", True, "reviewer_key_revoked"),
                                               ("enabled", False, "reviewer_key_disabled"),
                                               ("purpose", "data_export", "reviewer_key_purpose_mismatch"),
                                               ("reviewer_identity", "synthetic-impostor", "reviewer_identity_mismatch")])
def test_registry_key_policy_is_separate_from_signature_math(attestation, intent, decision, registry, field, value, reason):
    data = registry.to_dict()
    data["entries"][0][field] = value
    result = verify(attestation, intent, decision, TrustedPublicKeyRegistryV1.from_dict(data))
    assert result["cryptographic_signature_valid"]
    assert not result["key_policy_valid"] and not result["registered_trusted_reviewer_signature"]
    assert reason in result["reason_codes"]


def test_agent_attached_public_key_is_never_a_trust_anchor(attestation, intent, decision, registry):
    data = attestation.to_dict()
    data["public_key_b64"] = registry.to_dict()["entries"][0]["public_key_b64"]
    assert not verify(data, intent, decision, registry)["attestation_structurally_valid"]
    data = attestation.to_dict()
    data["payload"]["public_key_b64"] = registry.to_dict()["entries"][0]["public_key_b64"]
    assert not verify(data, intent, decision, registry)["attestation_structurally_valid"]
    assert "invalid_trusted_registry" in verify(attestation, intent, decision, None)["reason_codes"]


def test_cross_domain_signature_reuse_is_rejected(attestation, intent, decision, registry, key):
    cross_domain = resign(attestation.to_dict(), key, domain=b"other-application/v1\x00")
    assert "invalid_signature" in verify(cross_domain, intent, decision, registry)["reason_codes"]


@pytest.mark.parametrize("field,value", [("algorithm", "none"), ("algorithm", "Ed25519ctx"),
                                         ("schema_version", 2), ("schema_version", True),
                                         ("authorization_type", "other"), ("canonical_profile", "RFC8785"),
                                         ("key_purpose", "other"), ("review_status", "authorize")])
def test_unsupported_profile_algorithm_and_schema_are_rejected(attestation, intent, decision, registry, field, value):
    data = attestation.to_dict()
    data["payload"][field] = value
    assert not verify(data, intent, decision, registry)["attestation_structurally_valid"]


@pytest.mark.parametrize("kind", ["no_padding", "extra_padding", "whitespace", "urlsafe", "invalid_char",
                                  "short", "long", "nonzero_pad_bits", "non_string"])
def test_noncanonical_signature_encodings_are_rejected(attestation, intent, decision, registry, kind):
    data = attestation.to_dict()
    original = data["signature_b64"]
    if kind == "no_padding":
        modified = original.rstrip("=")
    elif kind == "extra_padding":
        modified = original + "="
    elif kind == "whitespace":
        modified = original + "\n"
    elif kind == "urlsafe":
        modified = base64.urlsafe_b64encode(b"\xfb" * 64).decode("ascii")
    elif kind == "invalid_char":
        modified = "*" + original[1:]
    elif kind in ("short", "long"):
        modified = base64.b64encode(b"\0" * (63 if kind == "short" else 65)).decode("ascii")
    elif kind == "nonzero_pad_bits":
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        modified = original[:-3] + alphabet[alphabet.index(original[-3]) + 1] + "=="
        assert base64.b64decode(modified) == base64.b64decode(original)
    else:
        modified = True
    data["signature_b64"] = modified
    assert not verify(data, intent, decision, registry)["attestation_structurally_valid"]


def test_well_encoded_invalid_signature_is_a_crypto_failure(attestation, intent, decision, registry):
    data = attestation.to_dict()
    data["signature_b64"] = base64.b64encode(b"\0" * 64).decode("ascii")
    result = verify(data, intent, decision, registry)
    assert result["attestation_structurally_valid"] and result["signature_checked"]
    assert not result["cryptographic_signature_valid"]


@pytest.mark.parametrize("text", ['{"payload":{},"payload":{}}', '{"x":NaN}', '{"x":Infinity}',
                                  '{"x":1e999}', '{"x":1.0}', '{"x":-0}', '{"x":9007199254740992}',
                                  '{invalid', '[]', '\ufeff{}', b'\xff'])
def test_strict_json_rejects_duplicates_numbers_and_ambiguous_transport(text):
    for parser in (AuthorizationAttestationV1.from_json, TrustedPublicKeyRegistryV1.from_json):
        with pytest.raises(ValueError):
            parser(text)


def test_invalid_unicode_and_utf16_transport_are_rejected(attestation):
    data = attestation.to_dict()
    with pytest.raises(ValueError):
        AuthorizationAttestationV1.from_json(attestation.to_json().encode("utf-16"))
    data["payload"]["reviewer_identity"] = "\ud800"
    with pytest.raises(ValueError):
        AuthorizationAttestationV1.from_dict(data)
    with pytest.raises(ValueError):
        AuthorizationAttestationV1.from_json(json.dumps(data, ensure_ascii=True))


@pytest.mark.parametrize("stamp", ["2001-01-01", "2001-01-01T01:05:00", "2001-01-01T01:05:00+00:00",
                                    "2001-01-01T01:05:00+08:00", "2001-01-01T01:05:00.1Z", "bad"])
def test_attestation_timestamps_require_canonical_explicit_utc(intent, decision, key, stamp):
    with pytest.raises(ValueError):
        sign(intent, decision, key, signed_at_utc=stamp)


def test_expiration_inherits_or_shortens_decision_without_mutating_v1(intent, key):
    decision = review_chain(intent, expires="2001-01-01T02:30:00+00:00")[1]
    original = decision.to_json()
    inherited = sign(intent, decision, key, expires_at_utc=None)
    shortened = sign(intent, decision, key, expires_at_utc="2001-01-01T02:00:00Z")
    assert inherited.to_dict()["payload"]["expires_at_utc"] == "2001-01-01T02:30:00Z"
    assert shortened.to_dict()["payload"]["expires_at_utc"] == "2001-01-01T02:00:00Z"
    assert decision.to_json() == original
    with pytest.raises(ValueError, match="expiry_extended"):
        sign(intent, decision, key, expires_at_utc="2001-01-01T02:30:01Z")
    with pytest.raises(ValueError):
        sign(intent, decision, key, expires_at_utc="2001-01-01T01:05:00Z")


@pytest.mark.parametrize("expiry", [None, "2001-01-01T03:00:00Z"])
def test_even_correct_signature_cannot_extend_decision_expiry(intent, key, registry, expiry):
    decision = review_chain(intent, expires="2001-01-01T02:30:00Z")[1]
    data = sign(intent, decision, key, expires_at_utc=None).to_dict()
    data["payload"]["expires_at_utc"] = expiry
    result = verify(resign(data, key), intent, decision, registry)
    assert result["cryptographic_signature_valid"] and not result["bindings_valid"]
    assert "decision_expiry_extended" in result["reason_codes"]


@pytest.mark.parametrize("now,valid", [("2001-01-01T01:04:59Z", False), (NOW, True),
                                      ("2001-01-01T03:00:00Z", False), ("2001-01-02T00:00:00Z", False)])
def test_time_validity_is_separate_from_signature_math(attestation, intent, decision, registry, now, valid):
    result = verify(attestation, intent, decision, registry, now)
    assert result["cryptographic_signature_valid"] and result["registered_trusted_reviewer_signature"]
    assert result["attestation_time_valid"] is valid
    assert result["signature_verification_passed"] is valid


def test_signing_before_decision_is_rejected_even_when_resigned(attestation, intent, decision, registry, key):
    with pytest.raises(ValueError, match="signing_before_decision"):
        sign(intent, decision, key, signed_at_utc="2001-01-01T00:59:59Z")
    data = attestation.to_dict()
    data["payload"]["signed_at_utc"] = "2001-01-01T00:59:59Z"
    result = verify(resign(data, key), intent, decision, registry)
    assert result["cryptographic_signature_valid"] and not result["signature_verification_passed"]


def test_null_expiry_is_allowed_when_no_decision_expiry_and_is_not_freshness(intent, decision, key, registry):
    attestation = sign(intent, decision, key, expires_at_utc=None)
    assert attestation.to_dict()["payload"]["expires_at_utc"] is None
    assert verify(attestation, intent, decision, registry)["signature_verification_passed"]


@pytest.mark.parametrize("store", [dict(store_id=STORE_ID, sequence=1, previous_entry_digest=None),
                                   dict(store_id=STORE_ID, sequence=2, previous_entry_digest="a" * 64)])
def test_assigned_store_position_is_signed_but_not_verified(intent, decision, key, registry, store):
    attestation = sign(intent, decision, key, store=store)
    assert attestation.to_dict()["payload"]["store"] == store
    assert verify(attestation, intent, decision, registry)["signature_verification_passed"]


@pytest.mark.parametrize("store", [dict(store_id=None, sequence=1, previous_entry_digest=None),
                                   dict(store_id=STORE_ID, sequence=0, previous_entry_digest=None),
                                   dict(store_id=STORE_ID, sequence=True, previous_entry_digest=None),
                                   dict(store_id=STORE_ID, sequence=1, previous_entry_digest="a" * 64),
                                   dict(store_id=STORE_ID, sequence=2, previous_entry_digest=None)])
def test_malformed_reserved_store_position_is_rejected(intent, decision, key, store):
    with pytest.raises(ValueError):
        sign(intent, decision, key, store=store)


@pytest.mark.parametrize("authorization_id", ["", "not-uuid", "11111111111141118111111111111111",
                                              "11111111-1111-1111-8111-111111111111", True])
def test_malformed_authorization_ids_are_rejected(intent, decision, key, authorization_id):
    with pytest.raises(ValueError):
        sign(intent, decision, key, authorization_id=authorization_id)


def test_repeated_and_resigned_ids_require_a_future_authoritative_store(attestation, intent, decision, key, registry):
    first = verify(attestation, intent, decision, registry)
    assert verify(attestation, intent, decision, registry) == first
    data = attestation.to_dict()
    data["payload"]["signed_at_utc"] = "2001-01-01T01:06:00Z"  # same ID, different valid signed statement
    reused = resign(data, key)
    assert reused.to_dict()["payload"]["authorization_id"] == AUTH_ID
    assert verify(reused, intent, decision, registry)["signature_verification_passed"]
    data["payload"]["authorization_id"] = OTHER_ID
    assert verify(resign(data, key), intent, decision, registry)["signature_verification_passed"]


@pytest.mark.parametrize("kind", ["version", "bool_version", "duplicate", "wrong_fingerprint", "bad_public_encoding",
                                  "bad_identity", "bad_purpose", "bad_flag", "attached_trust_flag"])
def test_invalid_public_registry_contract_is_rejected(key, kind):
    data = registry_data(key)
    entry = data["entries"][0]
    if kind == "version":
        data["schema_version"] = 2
    elif kind == "bool_version":
        data["schema_version"] = True
    elif kind == "duplicate":
        data["entries"].append(deepcopy(entry))
    elif kind == "wrong_fingerprint":
        entry["key_id"] = "e" * 64
    elif kind == "bad_public_encoding":
        entry["public_key_b64"] += "="
    elif kind == "bad_identity":
        entry["reviewer_identity"] = "\ud800"
    elif kind == "bad_purpose":
        entry["purpose"] = ""
    elif kind == "bad_flag":
        entry["enabled"] = 1
    else:
        data["trust"] = True
    with pytest.raises(ValueError):
        TrustedPublicKeyRegistryV1.from_dict(data)


def test_registry_is_only_a_caller_supplied_anchor_not_deployment_identity(intent, decision):
    self_selected_key = Ed25519PrivateKey.generate()
    self_selected_registry = TrustedPublicKeyRegistryV1.from_dict(registry_data(self_selected_key))
    result = verify(sign(intent, decision, self_selected_key), intent, decision, self_selected_registry)
    assert result["signature_verification_passed"]
    assert result["registry_origin_state"] == "caller_supplied_not_authenticated_here"


def test_private_key_object_is_required(intent, decision, key):
    for invalid in (None, "not-a-key", key.public_key(), X25519PrivateKey.generate()):
        with pytest.raises(TypeError):
            sign_attestation(intent, decision, private_key=invalid,
                             reviewer_key_id=key_id_for_public_key(key.public_key()),
                             authorization_id=AUTH_ID, signed_at_utc="2001-01-01T01:05:00Z")


def test_no_mutation_and_existing_v1_validator_remains_fail_closed(attestation, intent, decision, registry, proposal):
    before = (attestation.to_json(), intent.to_json(), decision.to_json(), registry.to_json(), deepcopy(proposal))
    verify(attestation, intent, decision, registry)
    root, approved = review_chain(intent)
    assert not validate_decisions(intent, proposal, [root, approved], now_utc=NOW)["execution_eligible"]
    assert (attestation.to_json(), intent.to_json(), decision.to_json(), registry.to_json(), proposal) == before
    for record in (attestation, registry):
        with pytest.raises(FrozenInstanceError):
            record._json = "{}"
        detached = record.to_dict()
        detached.clear()
        assert record.to_dict()


def test_transport_key_order_and_whitespace_do_not_change_signing_bytes(attestation, intent, decision, registry):
    transport = json.dumps(attestation.to_dict(), ensure_ascii=True, indent=4)
    parsed = AuthorizationAttestationV1.from_json(transport.encode("utf-8"))
    assert parsed.to_json() == attestation.to_json()
    assert verify(parsed, intent, decision, registry)["signature_verification_passed"]


def test_no_agent_controlled_trust_or_authorization_switch(attestation, intent, decision, registry):
    for name in ("trust", "authorized", "skip_verification"):
        with pytest.raises(TypeError):
            verify_attestation(attestation, intent, decision, trusted_keys=registry, now_utc=NOW, **{name: True})


def test_no_scientific_computation_stage2_or_key_generation_in_contract_operations(intent, decision, key, registry, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Signed-contract operations must not execute scientific workflows or generate keys.")

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
    monkeypatch.setattr(Ed25519PrivateKey, "generate", forbidden)
    assert verify(sign(intent, decision, key), intent, decision, registry)["signature_verification_passed"]


@pytest.mark.parametrize("container", ["object", "array"])
@pytest.mark.parametrize("transport", ["dict", "text", "bytes"])
def test_excessive_nesting_returns_structured_failure(attestation, intent, decision, registry, container, transport):
    depth = 5000  # beyond Python's normal recursion limit; construct iteratively
    if transport == "dict":
        nested = None
        for _ in range(depth):
            nested = {"x": nested} if container == "object" else [nested]
        data = attestation.to_dict()
        data["payload"] = nested
    else:
        opening, closing = ('{"x":', '}') if container == "object" else ('[', ']')
        data = '{"payload":' + opening * depth + 'null' + closing * depth + ',"signature_b64":"invalid"}'
        assert len(data.encode("utf-8")) < MAX_DOCUMENT_BYTES  # exercise depth, not size rejection
        if transport == "bytes":
            data = data.encode("utf-8")
    result = verify(data, intent, decision, registry)
    assert result["attestation_structurally_valid"] is False
    assert result["signature_verification_passed"] is False
    assert result["execution_eligible"] is False
    assert result["reason_codes"] == ["invalid_attestation"]
    assert not result["signature_checked"]


@pytest.mark.parametrize("container", ["object", "array"])
def test_cyclic_dictionary_input_is_rejected_without_recursion_escape(attestation, intent, decision, registry, container):
    cycle = {} if container == "object" else []
    if container == "object":
        cycle["self"] = cycle
    else:
        cycle.append(cycle)
    data = attestation.to_dict()
    data["payload"] = cycle
    result = verify(data, intent, decision, registry)
    assert not result["attestation_structurally_valid"]
    assert "nesting" in result["detail"]


def test_documented_depth_limit_precedes_interpreter_recursion_limit(intent, decision, registry):
    text = '[' * (MAX_NESTING_DEPTH + 1) + 'null' + ']' * (MAX_NESTING_DEPTH + 1)
    result = verify(text, intent, decision, registry)
    assert result["reason_codes"] == ["invalid_attestation"]
    assert "maximum nesting depth" in result["detail"]


@pytest.mark.parametrize("transport", ["text", "bytes"])
@pytest.mark.parametrize("excess", [0, 1])
def test_utf8_transport_size_boundary(attestation, intent, decision, registry, transport, excess):
    wire = attestation.to_json().encode("utf-8").ljust(MAX_DOCUMENT_BYTES + excess, b" ")
    data = wire.decode("utf-8") if transport == "text" else wire
    result = verify(data, intent, decision, registry)
    if excess:
        assert not result["attestation_structurally_valid"]
        assert "maximum input size" in result["detail"]
    else:
        assert result["signature_verification_passed"]  # whitespace does not change signed bytes


def test_transport_limit_counts_utf8_bytes_not_characters(intent, decision, registry):
    text = '{"payload":"' + '合' * (MAX_DOCUMENT_BYTES // 3) + '","signature_b64":"invalid"}'
    assert len(text) < MAX_DOCUMENT_BYTES < len(text.encode("utf-8"))
    result = verify(text, intent, decision, registry)
    assert not result["attestation_structurally_valid"]
    assert "maximum input size" in result["detail"]


@pytest.mark.parametrize("excess", [0, 1])
def test_native_dictionary_canonical_size_boundary(attestation, intent, decision, registry, excess):
    data = attestation.to_dict()
    data["payload"]["reviewer_identity"] = "x"
    original_size = len((json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    data["payload"]["reviewer_identity"] = "x" * (1 + MAX_DOCUMENT_BYTES - original_size + excess)
    actual_size = len((json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    assert actual_size == MAX_DOCUMENT_BYTES + excess
    result = verify(data, intent, decision, registry)
    assert result["attestation_structurally_valid"] is (not excess)
    assert not result["signature_verification_passed"]  # identity was changed without signing
    if excess:
        assert "maximum input size" in result["detail"]


@pytest.mark.parametrize("kind", ["large_string", "wide_collection", "aggregate_strings"])
def test_native_input_budget_bounds_oversized_copying(attestation, intent, decision, registry, kind):
    data = attestation.to_dict()
    if kind == "large_string":
        data["payload"] = "x" * (MAX_DOCUMENT_BYTES + 1)
    elif kind == "wide_collection":
        data["payload"] = [None] * MAX_DOCUMENT_BYTES
    else:
        data["payload"] = ["x" * 1000] * 100  # each string fits, combined content does not
    result = verify(data, intent, decision, registry)
    assert not result["attestation_structurally_valid"]
    assert "maximum input size" in result["detail"]


@pytest.mark.parametrize("error_type", [RuntimeError, RecursionError])
def test_input_handling_does_not_suppress_unrelated_crypto_errors(attestation, intent, decision, registry, monkeypatch, error_type):
    import src.workflow.signed_authorization as signed_module

    def programming_error(payload):
        raise error_type("Synthetic verifier programming error")

    monkeypatch.setattr(signed_module, "attestation_signing_bytes", programming_error)
    with pytest.raises(error_type, match="Synthetic verifier programming error"):
        verify(attestation, intent, decision, registry)


def test_initial_parse_boundary_handles_recursion_exhaustion(attestation, intent, decision, registry, monkeypatch):
    data = attestation.to_dict()

    def parser_exhausted(cls, value):
        raise RecursionError("Synthetic parser recursion exhaustion")

    monkeypatch.setattr(AuthorizationAttestationV1, "from_dict", classmethod(parser_exhausted))
    result = verify(data, intent, decision, registry)
    assert not result["attestation_structurally_valid"]
    assert not result["signature_verification_passed"]
    assert result["reason_codes"] == ["invalid_attestation"]
