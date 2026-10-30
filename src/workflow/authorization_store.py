"""Local signed history prototype, NOT an authenticated authorization service.

Only a configured root is read, always in full and under an exclusive lock.
history EOF == head == checkpoint is required; interrupted publication requires
explicit trusted recovery. Three fsynced files are NOT a multi-file transaction.
The checkpoint's protection and registry/root origin are deployment assumptions,
not established here. Whole-root rollback remains possible without an external
protected checkpoint. All results deny execution, including signed approvals.

No keys are generated/persisted, no human presence is inferred from a callback,
and no scientific framework or Stage 2 entry point is invoked. See
docs/authorization_store_v1.md for schemas, resource bounds and recovery limits.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from uuid import UUID, uuid4

from .planning_approval import DecisionRecord, ExecutionIntent, validate_decisions
from .signed_authorization import (
    AuthorizationAttestationV1, TrustedPublicKeyRegistryV1, verify_attestation,
    _utc,
)


ENTRY_DOMAIN_PREFIX = b"ionospheric-tec/authorization-store-entry/v1\x00"
ENTRY_DIGEST_PROFILE = "tec-store-json-utf8-lf-v1"
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_MARKER_BYTES = 4096
MAX_HISTORY_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 256
MAX_NESTING_DEPTH = 32
_MAX_INTEGER = 2**53 - 1


class StoreError(ValueError):
    """A rejected local state/write; callers must not fall back to old approval."""

    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(code + (": " + detail if detail else ""))


def _copy(value, depth=0, budget=None):
    """Bound native traversal before copying; finite floats preserve V1 proposals."""
    if budget is None:
        budget = [MAX_DOCUMENT_BYTES - 1]

    def charge(size):
        budget[0] -= size
        if budget[0] < 0:
            raise ValueError("Store document size limit exceeded.")

    if value is None or type(value) is bool:
        charge(4 if value is None or value is True else 5)
        return value
    if type(value) is str:
        if len(value) > MAX_DOCUMENT_BYTES:
            raise ValueError("Store string size limit exceeded.")
        charge(len(json.dumps(value, ensure_ascii=False).encode("utf-8", "strict")))
        return value
    if ((type(value) is int and abs(value) <= _MAX_INTEGER) or
            (type(value) is float and math.isfinite(value))):
        charge(len(json.dumps(value, allow_nan=False)))
        return value
    if type(value) in (dict, list):
        if depth >= MAX_NESTING_DEPTH:
            raise ValueError("Store document nesting limit exceeded.")
        charge(2 + max(0, len(value) - 1) + (len(value) if type(value) is dict else 0))
        if type(value) is list:
            return [_copy(item, depth + 1, budget) for item in value]
        if all(type(key) is str for key in value):
            return {_copy(key, depth + 1, budget): _copy(item, depth + 1, budget)
                    for key, item in value.items()}
    raise ValueError("Only bounded, finite native JSON values are supported.")


def _canonical(value):
    try:
        return (json.dumps(_copy(value), ensure_ascii=False, allow_nan=False,
                           sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    except RecursionError as exc:
        raise ValueError("Store JSON encoder nesting exceeded.") from exc


def _load(raw):
    if type(raw) is str:
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError("Store document size limit exceeded.")
        raw = raw.encode("utf-8", "strict")
    if type(raw) is not bytes or len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("Expected bounded UTF-8 store JSON.")
    text = raw.decode("utf-8", "strict")
    if text.startswith("\ufeff"):
        raise ValueError("Store JSON must not contain a BOM.")

    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("Duplicate JSON key.")
            data[key] = value
        return data

    def reject(value):
        raise ValueError("Nonfinite JSON constant.")

    def integer(value):
        if len(value.lstrip("-")) > 16:
            raise ValueError("Oversized store integer encoding.")
        parsed = int(value)
        if abs(parsed) > _MAX_INTEGER:
            raise ValueError("Unsafe store integer.")
        return parsed

    try:
        return _copy(json.loads(text, object_pairs_hook=unique, parse_constant=reject, parse_int=integer))
    except RecursionError as exc:
        raise ValueError("Store JSON decoder nesting exceeded.") from exc


def _fields(data, names):
    if type(data) is not dict or set(data) != set(names):
        raise ValueError("Missing, extra or malformed store fields.")


def _uuid(value):
    if type(value) is not str:
        raise ValueError("Expected canonical UUIDv4.")
    parsed = UUID(value)
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("Expected canonical UUIDv4.")


def _hash(value):
    if (type(value) is not str or len(value) != 64 or
            any(char not in "0123456789abcdef" for char in value)):
        raise ValueError("Expected lowercase SHA-256 digest.")


def _sequence(value, minimum=0):
    if type(value) is not int or not minimum <= value <= _MAX_INTEGER:
        raise ValueError("Expected nonnegative safe integer sequence.")


def entry_digest(entry: dict) -> str:
    """SHA256(domain + canonical entry excluding ONLY its own entry_digest).

    Profile: sorted compact JSON, finite native numbers, strict UTF-8, no BOM,
    no Unicode normalization, one final LF. This is not RFC 8785 JCS. Existing
    V1 signing/digest profiles are unchanged. Signature precedes entry hashing;
    its store position binds only the predecessor, so there is no circular hash.
    """
    entry = _copy(entry)
    if type(entry) is not dict:
        raise ValueError("Expected store entry object.")
    entry.pop("entry_digest", None)
    return hashlib.sha256(ENTRY_DOMAIN_PREFIX + _canonical(entry)).hexdigest()


@dataclass(frozen=True)
class _Document:
    _json: str

    def __post_init__(self):
        data = _load(self._json)
        self._shape(data)
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


class StoreEntryV1(_Document):
    """Detached immutable entry; shape parsing does not authenticate its contents."""

    def _shape(self, data):
        _fields(data, ("entry_type", "schema_version", "digest_profile", "store_id", "sequence",
                       "previous_entry_digest", "proposal", "execution_intent", "decision_record",
                       "attestation", "entry_digest"))
        if (data["entry_type"] != "signed_decision_store_entry" or
                type(data["schema_version"]) is not int or data["schema_version"] != 1 or
                data["digest_profile"] != ENTRY_DIGEST_PROFILE):
            raise ValueError("Unsupported store entry contract.")
        _uuid(data["store_id"])
        _sequence(data["sequence"], 1)
        if data["sequence"] == 1:
            if data["previous_entry_digest"] is not None:
                raise ValueError("First entry must have null predecessor.")
        else:
            _hash(data["previous_entry_digest"])
        _hash(data["entry_digest"])
        for field in ("proposal", "execution_intent", "decision_record", "attestation"):
            if type(data[field]) is not dict:
                raise ValueError("Complete V1 objects are required in every entry.")


class _Marker(_Document):
    def _shape(self, data):
        _fields(data, ("document_type", "schema_version", "store_id", "sequence", "entry_digest"))
        if (data["document_type"] != self.document_type or
                type(data["schema_version"]) is not int or data["schema_version"] != 1):
            raise ValueError("Unsupported store marker contract.")
        _uuid(data["store_id"])
        _sequence(data["sequence"])
        if data["sequence"] == 0:
            if data["entry_digest"] is not None:
                raise ValueError("Empty store must have null digest.")
        else:
            _hash(data["entry_digest"])
        if len(_canonical(data)) > MAX_MARKER_BYTES:
            raise ValueError("Store marker size limit exceeded.")


class StoreHeadV1(_Marker):
    """Publication pointer; alone does not establish a committed state."""
    document_type = "authorization_store_head"


class StoreCheckpointV1(_Marker):
    """High-water claim; OS/external protection is NOT provided by this object."""
    document_type = "authorization_store_checkpoint"


def _marker(cls, store_id, sequence, digest):
    return cls.from_dict(dict(document_type=cls.document_type, schema_version=1,
                              store_id=store_id, sequence=sequence, entry_digest=digest))


def _position(data):
    return data["store_id"], data["sequence"], data["entry_digest"]


def _result():
    return dict(result_type="authorization_store_validation", schema_version=1,
                store_structurally_valid=False, hash_chain_valid=False, head_consistent=False,
                checkpoint_consistent=False, entries_signature_valid=False, decision_history_valid=False,
                local_store_valid=False, effective_review_status={}, effective_decision_ids={},
                effective_attestation_time_valid={}, committed_head=None, checkpoint=None,
                current_authorization_state="not_verified", store_origin_authenticated=False,
                registry_origin_authenticated=False, execution_eligible=False, reason_codes=[])


def _acquire(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    elif os.name == "posix":
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        raise StoreError("unsupported_lock_platform")


def _release(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _exclusive(root, *, create=False):
    # Lock file is permanent, never replaced/unlinked. Lock beyond EOF works on
    # Windows; no pre-lock write is needed. Closing also releases a process lock.
    # Only initialization opts into creating the initial permanent lock file.
    try:
        handle = (root / "history.lock").open("a+b" if create else "r+b")
    except OSError as exc:
        raise StoreError("lock_unavailable", str(exc)) from exc
    try:
        try:
            _acquire(handle)
        except OSError as exc:
            raise StoreError("lock_unavailable", str(exc)) from exc
        try:
            yield
        finally:
            _release(handle)
    finally:
        handle.close()


def _flush(handle):
    handle.flush()
    os.fsync(handle.fileno())


def _publish(path, raw):
    # Same-directory replacement is one publication, NOT a cross-file commit.
    # On failure retain any temporary file for explicit trusted investigation.
    descriptor, temporary = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    with os.fdopen(descriptor, "wb") as handle:
        if handle.write(raw) != len(raw):
            raise OSError("Short marker write.")
        _flush(handle)
    os.replace(temporary, path)


def _append_history(path, raw):
    with path.open("ab") as handle:
        if handle.write(raw) != len(raw):
            raise OSError("Short history write.")
        _flush(handle)


def _read(path, limit):
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise StoreError("resource_limit", "Store file exceeds its byte limit.")
    return raw


def _parse(cls, raw):
    try:
        document = cls.from_json(raw)
        if document.to_json().encode("utf-8") != raw:
            raise ValueError("Stored JSON must use exact canonical bytes and final LF.")
        return document
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise StoreError("invalid_store_document", str(exc)) from exc


def _contracts(entry):
    try:
        intent = ExecutionIntent.from_dict(entry["execution_intent"])
        decision = DecisionRecord.from_dict(entry["decision_record"])
        attestation = AuthorizationAttestationV1.from_dict(entry["attestation"])
        return intent, decision, attestation
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise StoreError("invalid_bound_contract", str(exc)) from exc


def _lineages(entries, now_utc):
    """Full per-intent V1 semantics plus predecessor-before-child store order."""
    groups = {}
    for entry in entries:
        intent, decision, attestation = _contracts(entry)
        data = decision.to_dict()
        group = groups.setdefault(intent.digest, dict(intent=intent, proposal=entry["proposal"],
                                                       records=[], latest_attestation=attestation))
        # Python equality conflates 1, 1.0 and True; proposal bindings are exact
        # canonical JSON content, not numeric-equivalence comparisons.
        if _canonical(group["proposal"]) != _canonical(entry["proposal"]) or group["intent"] != intent:
            raise StoreError("conflicting_intent_content")
        expected = None if not group["records"] else dict(
            decision_id=group["records"][-1].to_dict()["decision_id"],
            decision_digest=group["records"][-1].digest)
        if data["supersedes"] != expected:
            raise StoreError("nonlinear_or_out_of_order_decision")
        group["records"].append(decision)
        group["latest_attestation"] = attestation
    for group in groups.values():
        validation = validate_decisions(group["intent"], group["proposal"], group["records"], now_utc=now_utc)
        if not validation["decision_history_valid"]:
            raise StoreError("invalid_decision_history", ", ".join(validation["reasons"]))
        group["validation"] = validation
    return groups


class AuthorizationStore:
    """Trusted-side prototype configured with a fixed root, store ID and registry.

    This constructor is NOT an Agent-facing path-selection interface or an OS
    boundary. All methods take the same nonblocking exclusive lock. append()
    accepts an explicit existing signing capability; a Python callable alone
    proves neither human presence nor key isolation. No repair API is provided.
    """

    def __init__(self, root, *, store_id: str, trusted_keys: TrustedPublicKeyRegistryV1):
        root = Path(root)
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("Configure an existing absolute trusted store directory.")
        _uuid(store_id)
        if not isinstance(trusted_keys, TrustedPublicKeyRegistryV1):
            raise TypeError("An independently configured registry snapshot is required.")
        self._root = root.resolve()
        self._store_id = store_id
        self._registry = TrustedPublicKeyRegistryV1.from_json(trusted_keys.to_json())

    def initialize(self) -> StoreHeadV1:
        """Initialize ONLY an empty root; never reset missing or damaged history."""
        try:
            with _exclusive(self._root, create=True):
                if any(path.name != "history.lock" for path in self._root.iterdir()):
                    raise StoreError("store_not_empty")
                head = _marker(StoreHeadV1, self._store_id, 0, None)
                checkpoint = _marker(StoreCheckpointV1, self._store_id, 0, None)
                with (self._root / "history.jsonl").open("xb") as handle:
                    _flush(handle)
                _publish(self._root / "head.json", head.to_json().encode("utf-8"))
                _publish(self._root / "checkpoint.json", checkpoint.to_json().encode("utf-8"))
                return head
        except OSError as exc:
            raise StoreError("store_io_failure", str(exc)) from exc

    def _state(self, result, now_utc, minimum_checkpoint):
        try:
            now = _utc(now_utc)
        except (TypeError, ValueError, OverflowError) as exc:
            raise StoreError("invalid_evaluation_time", str(exc)) from exc
        head = _parse(StoreHeadV1, _read(self._root / "head.json", MAX_MARKER_BYTES))
        checkpoint = _parse(StoreCheckpointV1, _read(self._root / "checkpoint.json", MAX_MARKER_BYTES))
        history = _read(self._root / "history.jsonl", MAX_HISTORY_BYTES)
        if history and not history.endswith(b"\n"):
            raise StoreError("incomplete_history_write")
        lines = history.splitlines(keepends=True)
        if len(lines) > MAX_ENTRIES:
            raise StoreError("resource_limit", "Store entry count limit exceeded.")
        entries = [_parse(StoreEntryV1, line).to_dict() for line in lines]
        result["store_structurally_valid"] = True
        previous = None
        ids, decisions = set(), set()
        for sequence, entry in enumerate(entries, 1):
            if entry["store_id"] != self._store_id:
                raise StoreError("store_id_mismatch")
            if entry["sequence"] != sequence:
                raise StoreError("noncontinuous_sequence")
            if entry["previous_entry_digest"] != previous:
                raise StoreError("previous_digest_mismatch")
            if entry_digest(entry) != entry["entry_digest"]:
                raise StoreError("entry_digest_mismatch")
            previous = entry["entry_digest"]
        result["hash_chain_valid"] = True
        expected = self._store_id, len(entries), previous
        if _position(head.to_dict()) != expected:
            raise StoreError("head_history_mismatch")
        result["head_consistent"] = True
        if _position(checkpoint.to_dict()) != expected:
            raise StoreError("checkpoint_head_mismatch")
        if minimum_checkpoint is not None:
            if not isinstance(minimum_checkpoint, StoreCheckpointV1):
                raise StoreError("invalid_minimum_checkpoint")
            floor = _parse(StoreCheckpointV1, minimum_checkpoint.to_json().encode("utf-8")).to_dict()
            if floor["store_id"] != self._store_id or floor["sequence"] > len(entries):
                raise StoreError("checkpoint_rollback")
            digest = None if floor["sequence"] == 0 else entries[floor["sequence"] - 1]["entry_digest"]
            if floor["entry_digest"] != digest:
                raise StoreError("checkpoint_fork")
        result["checkpoint_consistent"] = True
        for entry in entries:
            intent, decision, attestation = _contracts(entry)
            payload = attestation.to_dict()["payload"]
            position = dict(store_id=self._store_id, sequence=entry["sequence"],
                            previous_entry_digest=entry["previous_entry_digest"])
            if payload["store"] != position:
                raise StoreError("signed_store_position_mismatch")
            if payload["authorization_id"] in ids:
                raise StoreError("duplicate_authorization_id")
            if decision.to_dict()["decision_id"] in decisions:
                raise StoreError("duplicate_decision_id")
            ids.add(payload["authorization_id"])
            decisions.add(decision.to_dict()["decision_id"])
            # Archive signatures are checked at signing, using CURRENT registry
            # policy. Expired ancestors do not erase a later signed revocation.
            verified = verify_attestation(attestation, intent, decision, trusted_keys=self._registry,
                                          now_utc=payload["signed_at_utc"])
            if not verified["signature_verification_passed"]:
                raise StoreError("invalid_entry_signature", ", ".join(verified["reason_codes"]))
            if _utc(payload["signed_at_utc"]) > now:
                raise StoreError("future_entry_signature")
        result["entries_signature_valid"] = True
        groups = _lineages(entries, now_utc)
        result["decision_history_valid"] = True
        statuses, decision_ids, times = {}, {}, {}
        for digest, group in groups.items():
            checked = group["validation"]
            statuses[digest] = checked["review_status"]
            decision_ids[digest] = checked["effective_decision_id"]
            current = verify_attestation(group["latest_attestation"], group["intent"], group["records"][-1],
                                         trusted_keys=self._registry, now_utc=now_utc)
            times[digest] = current["attestation_time_valid"]
        result.update(local_store_valid=True, effective_review_status=statuses, effective_decision_ids=decision_ids,
                      effective_attestation_time_valid=times, committed_head=head.to_dict(),
                      checkpoint=checkpoint.to_dict(),
                      reason_codes=["store_origin_not_authenticated", "registry_origin_not_authenticated"])
        return entries, head

    def validate(self, *, now_utc: str, minimum_checkpoint: StoreCheckpointV1 | None = None) -> dict:
        """Read the FULL configured history; never accept a caller's entry subset.

        Optional minimum_checkpoint must come from an independently protected
        trusted side. It is a consistency floor, not proof of its own origin.
        Any failure exposes no effective statuses, never an older approval.
        Validation opens only the existing lock; a missing lock is not created.
        """
        result = _result()
        try:
            with _exclusive(self._root, create=False):
                self._state(result, now_utc, minimum_checkpoint)
        except StoreError as exc:
            result.update(reason_codes=[exc.code], detail=str(exc))
        except OSError as exc:
            result.update(reason_codes=["store_io_failure"], detail=str(exc))
        if result["reason_codes"] != ["store_origin_not_authenticated", "registry_origin_not_authenticated"]:
            result.update(local_store_valid=False, effective_review_status={}, effective_decision_ids={},
                          effective_attestation_time_valid={}, committed_head=None, checkpoint=None)
        return result

    def append(self, intent: ExecutionIntent, proposal: dict, decision: DecisionRecord, *,
               expected_head: StoreHeadV1, signer, signed_at_utc: str, now_utc: str,
               expires_at_utc: str | None = None,
               minimum_checkpoint: StoreCheckpointV1 | None = None) -> StoreEntryV1:
        """Trusted-side compare-and-append; caller cannot allocate signed position/ID.

        signer(intent, decision, *, authorization_id, store, signed_at_utc,
        expires_at_utc) must return AuthorizationAttestationV1. It is an explicit
        capability supplied from the trusted side, never a stored callback name.
        Exceptions from the capability propagate; no persistence precedes it.
        Failure after persistence is ambiguous and requires trusted recovery.
        The permanent lock must already exist; append never recreates it.
        """
        if not callable(signer) or not isinstance(expected_head, StoreHeadV1):
            raise TypeError("Explicit signer capability and expected StoreHeadV1 are required.")
        # Snapshot caller content before locking/signing; never modify V1 inputs.
        draft = _copy(dict(proposal=proposal, execution_intent=intent.to_dict(),
                           decision_record=decision.to_dict(), attestation={}))
        checked_intent = ExecutionIntent.from_dict(draft["execution_intent"])
        checked_decision = DecisionRecord.from_dict(draft["decision_record"])
        try:
            with _exclusive(self._root, create=False):
                entries, head = self._state(_result(), now_utc, minimum_checkpoint)
                if head != StoreHeadV1.from_json(expected_head.to_json()):
                    raise StoreError("stale_expected_head")
                if len(entries) >= MAX_ENTRIES:
                    raise StoreError("resource_limit")
                if any(entry["decision_record"]["decision_id"] == draft["decision_record"]["decision_id"]
                       for entry in entries):
                    raise StoreError("duplicate_decision_id")
                # Validate declarations before invoking the signing capability.
                self._validate_next(entries, draft, checked_intent, checked_decision, now_utc)
                position = dict(store_id=self._store_id, sequence=len(entries) + 1,
                                previous_entry_digest=head.to_dict()["entry_digest"])
                authorization_id = str(uuid4())
                if any(entry["attestation"]["payload"]["authorization_id"] == authorization_id for entry in entries):
                    raise StoreError("duplicate_authorization_id")
                attestation = signer(checked_intent, checked_decision, authorization_id=authorization_id,
                                     store=dict(position), signed_at_utc=signed_at_utc, expires_at_utc=expires_at_utc)
                if not isinstance(attestation, AuthorizationAttestationV1):
                    raise StoreError("invalid_signer_result")
                attestation = AuthorizationAttestationV1.from_json(attestation.to_json())
                payload = attestation.to_dict()["payload"]
                if payload["authorization_id"] != authorization_id or payload["store"] != position:
                    raise StoreError("signer_changed_allocated_position_or_id")
                verified = verify_attestation(attestation, checked_intent, checked_decision,
                                              trusted_keys=self._registry, now_utc=now_utc)
                if not verified["signature_verification_passed"]:
                    raise StoreError("invalid_new_signature", ", ".join(verified["reason_codes"]))
                data = dict(entry_type="signed_decision_store_entry", schema_version=1,
                            digest_profile=ENTRY_DIGEST_PROFILE, **position,
                            proposal=draft["proposal"], execution_intent=draft["execution_intent"],
                            decision_record=draft["decision_record"], attestation=attestation.to_dict())
                data["entry_digest"] = entry_digest(data)
                entry = StoreEntryV1.from_dict(data)
                raw = entry.to_json().encode("utf-8")
                if sum(len(_canonical(old)) for old in entries) + len(raw) > MAX_HISTORY_BYTES:
                    raise StoreError("resource_limit")
                _append_history(self._root / "history.jsonl", raw)
                new_head = _marker(StoreHeadV1, self._store_id, position["sequence"], data["entry_digest"])
                _publish(self._root / "head.json", new_head.to_json().encode("utf-8"))
                checkpoint = _marker(StoreCheckpointV1, self._store_id, position["sequence"], data["entry_digest"])
                _publish(self._root / "checkpoint.json", checkpoint.to_json().encode("utf-8"))
                # Re-read exact on-disk state under the lock before success.
                self._state(_result(), now_utc, minimum_checkpoint)
                return entry
        except OSError as exc:
            raise StoreError("store_io_failure", str(exc)) from exc

    @staticmethod
    def _validate_next(entries, draft, intent, decision, now_utc):
        records = [entry["decision_record"] for entry in entries
                   if entry["execution_intent"]["execution_intent_digest"] == intent.digest]
        expected = None if not records else dict(decision_id=records[-1]["decision_id"],
                                                 decision_digest=records[-1]["decision_digest"])
        if decision.to_dict()["supersedes"] != expected:
            raise StoreError("nonlinear_or_out_of_order_decision")
        validation = validate_decisions(intent, draft["proposal"], records + [decision], now_utc=now_utc)
        if not validation["decision_history_valid"]:
            raise StoreError("invalid_decision_history", ", ".join(validation["reasons"]))
