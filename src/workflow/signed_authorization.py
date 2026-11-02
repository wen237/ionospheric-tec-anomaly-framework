"""Signed statements only: no current authorization, storage or execution.

AuthorizationAttestationV1 signs DOMAIN_PREFIX + canonical_payload_bytes.
The profile is sorted-key compact JSON, ensure_ascii=False, allow_nan=False,
strict UTF-8 without BOM, and exactly one trailing LF. Its values are strings,
nonnegative safe integers, booleans or null; schemas further restrict types.
Floats, duplicate keys, invalid Unicode, negative-zero integer spellings and
noncanonical padded STANDARD Base64 are rejected. This is NOT RFC 8785 JCS.
Transport JSON may vary in whitespace/key order; signing bytes are canonical.
Existing ExecutionIntent/DecisionRecord V1 digest algorithms are unchanged.

Resource policy for this module's shared JSON codec: at most 64 KiB per UTF-8
transport document or canonical document (including LF), and 16 nested dict/list
containers (root container counts as one). Native copies share a canonical-byte
budget, so oversized strings, wide collections and cycles fail before unbounded
copying. Decoder/encoder RecursionError is an input validation failure, not a
reason to suppress unrelated errors from signature verification. Accepted V1
canonical/signing bytes are unchanged; these bounds do not verify store state.

Store position is a signed DECLARATION reserved for future store integration:
all three fields null means unassigned; otherwise store_id is a canonical
UUIDv4, sequence >= 1, and previous_entry_digest is null exactly at sequence 1.
No position, history completeness, ID uniqueness, replay, or freshness check
is performed. Authorization IDs are caller-supplied canonical UUIDv4 strings;
reuse across valid signatures cannot be detected by this stateless contract.

The independently supplied registry is an explicit CALLER TRUST ANCHOR, not
an authenticated deployment. Registering a public key object here does not
prove OS isolation, custody, physical reviewer identity, or human interaction.
Envelope-attached public keys are rejected and never used as trust anchors.
Registered-key signature means the statement matches the supplied V1 objects,
key fingerprint, reviewer declaration, purpose and enabled/revoked policy.
Its result is separate from current authorization, which is NEVER VERIFIED.
Execution eligibility is ALWAYS FALSE, even for signed 'approved' statements.

Signing requires an existing Ed25519 private-key object. This module never
generates, loads, writes or logs private keys and provides no signing CLI.
The supplied evaluation time is not a trusted clock. Source data, full proposal
content, decision lineage and revocation beyond the supplied registry are not
independently checked; these belong to future authoritative-store integration.
"""

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from uuid import UUID

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .planning_approval import DecisionRecord, ExecutionIntent


DOMAIN_PREFIX = b"ionospheric-tec/authorization-attestation/v1\x00"
CANONICAL_PROFILE = "tec-authorization-json-utf8-lf-v1"
KEY_PURPOSE = "scientific_review_decision"
MAX_DOCUMENT_BYTES = 64 * 1024
MAX_NESTING_DEPTH = 16
_MAX_INTEGER = 2**53 - 1
_STATUSES = {"pending_review", "approved", "rejected", "revision_requested", "revoked"}


def _native(value, _depth=0, _budget=None):
    if _budget is None:
        _budget = [MAX_DOCUMENT_BYTES - 1]  # reserve the canonical trailing LF

    def charge(size):
        _budget[0] -= size
        if _budget[0] < 0:
            raise ValueError("JSON document exceeds maximum input size.")

    if value is None or type(value) is bool:
        charge(4 if value is None or value is True else 5)
        return value
    if type(value) is str:
        if len(value) > MAX_DOCUMENT_BYTES:
            raise ValueError("JSON string exceeds maximum input size.")
        try:
            encoded = json.dumps(value, ensure_ascii=False).encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("Invalid Unicode.") from exc
        charge(len(encoded))
        return value
    if type(value) is int and 0 <= value <= _MAX_INTEGER:
        charge(len(str(value)))
        return value
    if type(value) in (list, dict):
        if _depth >= MAX_NESTING_DEPTH:
            raise ValueError("JSON input exceeds maximum nesting depth.")
        charge(2 + max(0, len(value) - 1) + (len(value) if type(value) is dict else 0))
        if type(value) is list:
            return [_native(item, _depth + 1, _budget) for item in value]
        if all(type(key) is str for key in value):
            return {_native(key, _depth + 1, _budget): _native(item, _depth + 1, _budget)
                    for key, item in value.items()}
    raise ValueError("Only strict JSON profile values are supported; no floats or unsafe integers.")


def _canonical(value):
    try:
        return (json.dumps(_native(value), ensure_ascii=False, allow_nan=False,
                           sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    except RecursionError as exc:
        raise ValueError("JSON input exceeds encoder recursion capacity.") from exc


def _load(text):
    if type(text) is bytes:
        if len(text) > MAX_DOCUMENT_BYTES:
            raise ValueError("JSON transport exceeds maximum input size.")
        try:
            text = text.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("Transport must be strict UTF-8.") from exc
    if type(text) is not str or text.startswith("\ufeff"):
        raise ValueError("Transport must be UTF-8 without BOM.")
    if len(text) > MAX_DOCUMENT_BYTES:
        raise ValueError("JSON transport exceeds maximum input size.")
    try:
        if len(text.encode("utf-8", errors="strict")) > MAX_DOCUMENT_BYTES:
            raise ValueError("JSON transport exceeds maximum input size.")
    except UnicodeError as exc:
        raise ValueError("Invalid Unicode.") from exc

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key.")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("Nonfinite/float JSON numbers are unsupported.")

    def integer(value):
        if value.startswith("-") or len(value) > 16:
            raise ValueError("Negative or oversized integer encodings are unsupported.")
        return _native(int(value))

    try:
        parsed = json.loads(text, object_pairs_hook=unique, parse_constant=reject,
                            parse_float=reject, parse_int=integer)
    except RecursionError as exc:
        raise ValueError("JSON input exceeds decoder recursion capacity.") from exc
    return _native(parsed)


def _fields(data, names):
    if type(data) is not dict or set(data) != set(names):
        raise ValueError("Missing, extra or malformed contract fields.")


def _text(value):
    if type(value) is not str or not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Expected a nonempty text identity without control characters.")
    _native(value)


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 digest.")


def _integer(value, low=0):
    if type(value) is not int or not low <= value <= _MAX_INTEGER:
        raise ValueError("Invalid nonnegative safe integer.")


def _uuid(value):
    if type(value) is not str:
        raise ValueError("Expected canonical UUIDv4 string.")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError("Expected canonical UUIDv4 string.") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("Expected canonical UUIDv4 string.")


def _utc(value, *, canonical=False):
    if type(value) is not str:
        raise ValueError("Expected explicit UTC ISO timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid UTC timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must explicitly use UTC.")
    parsed = parsed.astimezone(timezone.utc)
    if canonical and value != _iso(parsed):
        raise ValueError("Attestation timestamps require canonical ISO UTC ending Z.")
    return parsed


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def _decode64(text, length):
    if type(text) is not str:
        raise ValueError("Expected canonical padded standard Base64.")
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except (UnicodeError, binascii.Error, ValueError) as exc:
        raise ValueError("Invalid standard Base64.") from exc
    if len(raw) != length or base64.b64encode(raw).decode("ascii") != text:
        raise ValueError("Noncanonical Base64 or incorrect byte length.")
    return raw


def key_id_for_public_key(public_key: Ed25519PublicKey) -> str:
    """SHA-256 fingerprint of the raw 32-byte public key, not identity proof."""
    if not isinstance(public_key, Ed25519PublicKey):
        raise TypeError("An Ed25519 public-key object is required.")
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def _store(position):
    _fields(position, ("store_id", "sequence", "previous_entry_digest"))
    if all(value is None for value in position.values()):
        return
    _uuid(position["store_id"])
    _integer(position["sequence"], 1)
    if position["sequence"] == 1:
        if position["previous_entry_digest"] is not None:
            raise ValueError("Sequence 1 must have a null previous-entry digest.")
    else:
        _hash(position["previous_entry_digest"])


def _payload_shape(payload):
    _fields(payload, ("authorization_type", "schema_version", "algorithm", "canonical_profile", "execution_intent_digest",
                      "proposal_digest", "decision_record_digest", "decision_id", "review_status", "revision", "supersedes",
                      "reviewer_key_id", "reviewer_identity", "key_purpose", "signed_at_utc", "expires_at_utc",
                      "authorization_scope", "store", "authorization_id"))
    if (payload["authorization_type"] != "scientific_execution_authorization_attestation" or
            type(payload["schema_version"]) is not int or payload["schema_version"] != 1 or
            payload["algorithm"] != "Ed25519" or payload["canonical_profile"] != CANONICAL_PROFILE):
        raise ValueError("Unsupported attestation type/version/algorithm/profile.")
    for name in ("execution_intent_digest", "proposal_digest", "decision_record_digest", "reviewer_key_id"):
        _hash(payload[name])
    for name in ("decision_id", "reviewer_identity", "authorization_scope"):
        _text(payload[name])
    if type(payload["review_status"]) is not str or payload["review_status"] not in _STATUSES:
        raise ValueError("Invalid review status.")
    if payload["key_purpose"] != KEY_PURPOSE:
        raise ValueError("Unsupported signing purpose.")
    _integer(payload["revision"])
    previous = payload["supersedes"]
    if previous is None:
        if payload["revision"] != 0:
            raise ValueError("Missing supersession reference.")
    else:
        _fields(previous, ("decision_id", "decision_digest"))
        _text(previous["decision_id"])
        _hash(previous["decision_digest"])
        if payload["revision"] == 0 or previous["decision_id"] == payload["decision_id"]:
            raise ValueError("Invalid supersession reference.")
    signed = _utc(payload["signed_at_utc"], canonical=True)
    if payload["expires_at_utc"] is not None and _utc(payload["expires_at_utc"], canonical=True) <= signed:
        raise ValueError("Attestation expiry must be after signing.")
    _store(payload["store"])
    _uuid(payload["authorization_id"])


def canonical_payload_bytes(payload: dict) -> bytes:
    """Validate the V1 payload and encode its exact documented UTF-8/LF profile."""
    payload = _native(payload)
    _payload_shape(payload)
    return _canonical(payload)


def attestation_signing_bytes(payload: dict) -> bytes:
    """Fixed application domain plus canonical payload; standard Ed25519, not Ed25519ctx."""
    return DOMAIN_PREFIX + canonical_payload_bytes(payload)


@dataclass(frozen=True)
class AuthorizationAttestationV1:
    """Immutable signed envelope; parsing validates shape/encoding, NOT its signature."""
    _json: str

    def __post_init__(self):
        data = _load(self._json)
        _fields(data, ("payload", "signature_b64"))
        canonical_payload_bytes(data["payload"])
        _decode64(data["signature_b64"], 64)
        object.__setattr__(self, "_json", _canonical(data).decode("utf-8"))

    @classmethod
    def from_dict(cls, data):
        return cls(_canonical(data).decode("utf-8"))

    @classmethod
    def from_json(cls, text):
        return cls(text)

    def to_dict(self):
        return json.loads(self._json)

    def to_json(self):
        return self._json


@dataclass(frozen=True)
class TrustedPublicKeyRegistryV1:
    """Caller-supplied trust-anchor snapshot; no persistence or origin authentication.

    Exact schema: registry_type='trusted_reviewer_public_keys', schema_version=1,
    entries=[{key_id, public_key_b64, reviewer_identity, purpose, enabled, revoked}].
    key_id is the raw Ed25519 public-key SHA-256 fingerprint. Empty registries
    are allowed but cannot verify a registered reviewer signature. Multiple
    entries with the same fingerprint are rejected, never resolved by ordering.
    """
    _json: str

    def __post_init__(self):
        data = _load(self._json)
        _fields(data, ("registry_type", "schema_version", "entries"))
        if (data["registry_type"] != "trusted_reviewer_public_keys" or
                type(data["schema_version"]) is not int or data["schema_version"] != 1 or
                type(data["entries"]) is not list):
            raise ValueError("Unsupported public-key registry contract.")
        ids = set()
        for entry in data["entries"]:
            _fields(entry, ("key_id", "public_key_b64", "reviewer_identity", "purpose", "enabled", "revoked"))
            _hash(entry["key_id"])
            raw = _decode64(entry["public_key_b64"], 32)
            if entry["key_id"] != hashlib.sha256(raw).hexdigest() or entry["key_id"] in ids:
                raise ValueError("Public-key fingerprint mismatch or duplicate registry entry.")
            ids.add(entry["key_id"])
            _text(entry["reviewer_identity"])
            _text(entry["purpose"])
            if type(entry["enabled"]) is not bool or type(entry["revoked"]) is not bool:
                raise ValueError("Key enabled/revoked flags must be booleans.")
        object.__setattr__(self, "_json", _canonical(data).decode("utf-8"))

    @classmethod
    def from_dict(cls, data):
        return cls(_canonical(data).decode("utf-8"))

    @classmethod
    def from_json(cls, text):
        return cls(text)

    def to_dict(self):
        return json.loads(self._json)

    def to_json(self):
        return self._json


def _inputs(intent, decision):
    if not isinstance(intent, ExecutionIntent) or not isinstance(decision, DecisionRecord):
        raise TypeError("Validated ExecutionIntent and DecisionRecord objects are required.")
    intent = ExecutionIntent.from_dict(intent.to_dict())
    decision = DecisionRecord.from_dict(decision.to_dict())
    i, d = intent.to_dict(), decision.to_dict()
    if d["execution_intent_digest"] != intent.digest or d["proposal_digest"] != i["proposal_digest"]:
        raise ValueError("DecisionRecord does not bind this ExecutionIntent/proposal.")
    return intent, decision, i, d


def _binding_errors(payload, intent, decision, i, d):
    expected = dict(execution_intent_digest=intent.digest, proposal_digest=i["proposal_digest"],
                    decision_record_digest=decision.digest, decision_id=d["decision_id"], review_status=d["status"],
                    revision=d["revision"], supersedes=d["supersedes"], reviewer_identity=d["reviewer_identity_declaration"],
                    authorization_scope=i["authorization_scope"])
    errors = ["binding_mismatch:" + key for key, value in expected.items() if _canonical(payload[key]) != _canonical(value)]
    if _utc(payload["signed_at_utc"]) < _utc(d["decision_time_utc"]):
        errors.append("signing_before_decision")
    if d["expires_at_utc"] is not None and (payload["expires_at_utc"] is None or
            _utc(payload["expires_at_utc"]) > _utc(d["expires_at_utc"])):
        errors.append("decision_expiry_extended")
    return errors


def sign_attestation(
    intent: ExecutionIntent, decision: DecisionRecord, *, private_key: Ed25519PrivateKey,
    reviewer_key_id: str, authorization_id: str, signed_at_utc: str,
    expires_at_utc: str | None = None, store: dict | None = None,
) -> AuthorizationAttestationV1:
    """Sign a bound statement with an explicitly supplied key; never grant execution.

    A null expiry inherits the DecisionRecord expiry when present, otherwise
    remains null. Explicit expiry may shorten but never extend that deadline.
    No registry, ID allocator, decision history or human presence is consulted.
    """
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("An explicitly supplied Ed25519 private-key object is required.")
    if reviewer_key_id != key_id_for_public_key(private_key.public_key()):
        raise ValueError("Signing key does not match the declared reviewer key ID.")
    intent, decision, i, d = _inputs(intent, decision)
    expiry = expires_at_utc
    if expiry is None and d["expires_at_utc"] is not None:
        expiry = _iso(_utc(d["expires_at_utc"]))
    payload = dict(
        authorization_type="scientific_execution_authorization_attestation", schema_version=1,
        algorithm="Ed25519", canonical_profile=CANONICAL_PROFILE,
        execution_intent_digest=intent.digest, proposal_digest=i["proposal_digest"], decision_record_digest=decision.digest,
        decision_id=d["decision_id"], review_status=d["status"], revision=d["revision"], supersedes=d["supersedes"],
        reviewer_key_id=reviewer_key_id, reviewer_identity=d["reviewer_identity_declaration"], key_purpose=KEY_PURPOSE,
        signed_at_utc=signed_at_utc, expires_at_utc=expiry, authorization_scope=i["authorization_scope"],
        store=dict(store_id=None, sequence=None, previous_entry_digest=None) if store is None else _native(store),
        authorization_id=authorization_id,
    )
    signing_bytes = attestation_signing_bytes(payload)
    errors = _binding_errors(payload, intent, decision, i, d)
    if errors:
        raise ValueError("Invalid signed binding: " + ", ".join(errors))
    signature = private_key.sign(signing_bytes)
    return AuthorizationAttestationV1.from_dict(dict(payload=payload, signature_b64=base64.b64encode(signature).decode("ascii")))


def verify_attestation(
    attestation, intent: ExecutionIntent, decision: DecisionRecord, *,
    trusted_keys: TrustedPublicKeyRegistryV1, now_utc: str,
) -> dict:
    """Separate shape, signature, registered-key policy, and time checks.

    trusted_keys must be supplied independently by the enclosing verifier, not
    extracted from the attestation. This function cannot authenticate its origin.
    now_utc is an explicit evaluation-time declaration, not secure time evidence.
    signature_verification_passed concerns ONLY this stateless statement. Even
    success never verifies current authorization or allows Framework D execution.
    """
    result = dict(
        attestation_structurally_valid=False, contracts_valid=False, bindings_valid=False,
        signature_checked=False, cryptographic_signature_valid=False, key_registered=False, key_policy_valid=False,
        registered_trusted_reviewer_signature=False, attestation_time_valid=False, signature_verification_passed=False,
        current_authorization_state="not_verified", decision_history_state="not_verified", store_state="not_verified",
        authorization_id_uniqueness="not_verified", registry_origin_state="caller_supplied_not_authenticated_here",
        execution_eligible=False, reason_codes=[],
    )
    try:
        if isinstance(attestation, AuthorizationAttestationV1):
            attestation = AuthorizationAttestationV1.from_json(attestation.to_json())
        elif type(attestation) is dict:
            attestation = AuthorizationAttestationV1.from_dict(attestation)
        else:
            attestation = AuthorizationAttestationV1.from_json(attestation)
        envelope = attestation.to_dict()
        payload = envelope["payload"]
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        return {**result, "reason_codes": ["invalid_attestation"], "detail": str(exc)}
    result["attestation_structurally_valid"] = True
    try:
        intent, decision, i, d = _inputs(intent, decision)
        result["contracts_valid"] = True
        errors = _binding_errors(payload, intent, decision, i, d)
        result["bindings_valid"] = not errors
        result["reason_codes"].extend(errors)
        now = _utc(now_utc)
        time_errors = []
        if _utc(payload["signed_at_utc"]) > now:
            time_errors.append("signing_time_in_future")
        if payload["expires_at_utc"] is not None and now >= _utc(payload["expires_at_utc"]):
            time_errors.append("attestation_expired")
        if d["expires_at_utc"] is not None and now >= _utc(d["expires_at_utc"]):
            time_errors.append("decision_expired")
        result["reason_codes"].extend(time_errors)
        result["attestation_time_valid"] = not time_errors
    except (TypeError, ValueError, OverflowError) as exc:
        return {**result, "reason_codes": result["reason_codes"] + ["invalid_bound_contract_or_evaluation_time"], "detail": str(exc)}
    try:
        if not isinstance(trusted_keys, TrustedPublicKeyRegistryV1):
            raise TypeError("An independently supplied public-key registry object is required.")
        registry = TrustedPublicKeyRegistryV1.from_json(trusted_keys.to_json()).to_dict()
    except (TypeError, ValueError) as exc:
        return {**result, "reason_codes": result["reason_codes"] + ["invalid_trusted_registry"], "detail": str(exc)}
    entry = next((item for item in registry["entries"] if item["key_id"] == payload["reviewer_key_id"]), None)
    if entry is None:
        return {**result, "reason_codes": result["reason_codes"] + ["unknown_reviewer_key"]}
    result["key_registered"] = True
    policy_errors = []
    if not entry["enabled"]:
        policy_errors.append("reviewer_key_disabled")
    if entry["revoked"]:
        policy_errors.append("reviewer_key_revoked")
    if entry["purpose"] != payload["key_purpose"]:
        policy_errors.append("reviewer_key_purpose_mismatch")
    if entry["reviewer_identity"] != payload["reviewer_identity"] or entry["reviewer_identity"] != d["reviewer_identity_declaration"]:
        policy_errors.append("reviewer_identity_mismatch")
    result["reason_codes"].extend(policy_errors)
    result["key_policy_valid"] = not policy_errors
    try:
        key = Ed25519PublicKey.from_public_bytes(_decode64(entry["public_key_b64"], 32))
        result["signature_checked"] = True
        key.verify(_decode64(envelope["signature_b64"], 64), attestation_signing_bytes(payload))
        result["cryptographic_signature_valid"] = True
    except InvalidSignature:
        result["reason_codes"].append("invalid_signature")
    except (ValueError, UnsupportedAlgorithm):
        result["reason_codes"].append("unsupported_or_invalid_crypto_key")
    result["registered_trusted_reviewer_signature"] = (
        result["bindings_valid"] and result["key_policy_valid"] and result["cryptographic_signature_valid"])
    result["signature_verification_passed"] = result["registered_trusted_reviewer_signature"] and result["attestation_time_valid"]
    return result
