"""Read-only, demonstration-only local verification composition, never a grant.

Fixed configuration and content pins are supplied by a trusted-side bootstrap;
ordinary Python paths/objects do NOT authenticate that bootstrap. No Windows
SID, DACL, ownership, code custody, secure clock or human presence is verified.
Consequently ALL origin/isolation/human-authorization flags remain false, even
when exact local review state is approved. Execution eligibility is always false.

Queries accept only an exact intent digest, not records, paths, keys or trust
flags. Registry/checkpoint snapshots are acquired from pinned configured files,
then AuthorizationStore.validate() reads the complete locked history. No keys,
history, checkpoints or configuration are created/modified. Locking requires
opening the existing permanent lock file read/write, without writing its bytes.
See docs/local_authorization.md for deployment tests and residual races/rollback.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from .authorization_store import AuthorizationStore, StoreCheckpointV1, MAX_MARKER_BYTES
from .planning_approval import _SCOPE
from .signed_authorization import (
    TrustedPublicKeyRegistryV1, MAX_DOCUMENT_BYTES as MAX_REGISTRY_BYTES,
    _canonical, _fields, _hash, _integer, _load, _text, _utc, _uuid,
)


MAX_CONFIGURATION_BYTES = 16 * 1024
_STORE_FLAGS = ("store_structurally_valid", "hash_chain_valid", "head_consistent",
                "checkpoint_consistent", "entries_signature_valid", "decision_history_valid")
_LIMITATIONS = ["deployment_isolation_not_verified", "trusted_source_origin_not_verified",
                "authoritative_freshness_not_verified", "trusted_time_not_verified"]


def _absolute_path(value):
    _text(value)
    path = Path(value)
    if not path.is_absolute() or value.startswith(("\\\\", "//")):
        raise ValueError("An explicit absolute local path is required; no expansion or UNC paths.")
    return path


def _configuration_bytes(text):
    if type(text) is str:
        if len(text) > MAX_CONFIGURATION_BYTES:
            raise ValueError("Configuration size limit exceeded.")
        text = text.encode("utf-8", "strict")
    if type(text) is not bytes or len(text) > MAX_CONFIGURATION_BYTES:
        raise ValueError("Expected bounded UTF-8 configuration.")
    return text


@dataclass(frozen=True)
class VerifierConfigurationV1:
    """Strict immutable DECLARATIONS; parsing does not verify deployment origin.

    SHA-256 pins identify exact file bytes, not owners or authenticated sources.
    Code/dependency hashes are release declarations, NOT runtime measurements.
    No field can assert trusted status, ACL enforcement or permission to execute.
    """
    _json: str

    def __post_init__(self):
        data = _load(_configuration_bytes(self._json))
        _fields(data, ("configuration_type", "schema_version", "configuration_id", "store", "registry",
                       "minimum_checkpoint", "deployment", "expected_authorization_scope", "time_source"))
        if (data["configuration_type"] != "local_authorization_verifier_configuration" or
                type(data["schema_version"]) is not int or data["schema_version"] != 1):
            raise ValueError("Unsupported verifier configuration.")
        _uuid(data["configuration_id"])
        _fields(data["store"], ("store_id", "root"))
        _uuid(data["store"]["store_id"])
        _absolute_path(data["store"]["root"])
        _fields(data["registry"], ("path", "sha256"))
        _absolute_path(data["registry"]["path"])
        _hash(data["registry"]["sha256"])
        checkpoint = data["minimum_checkpoint"]
        _fields(checkpoint, ("path", "sha256", "sequence", "entry_digest"))
        _absolute_path(checkpoint["path"])
        _hash(checkpoint["sha256"])
        _integer(checkpoint["sequence"])
        if checkpoint["sequence"] == 0:
            if checkpoint["entry_digest"] is not None:
                raise ValueError("Empty checkpoint must have null digest.")
        else:
            _hash(checkpoint["entry_digest"])
        deployment = data["deployment"]
        _fields(deployment, ("deployment_id", "verifier_code_sha256", "dependency_manifest_sha256",
                             "isolation_requirement"))
        _uuid(deployment["deployment_id"])
        _hash(deployment["verifier_code_sha256"])
        _hash(deployment["dependency_manifest_sha256"])
        if deployment["isolation_requirement"] != "separate_windows_security_identities":
            raise ValueError("V1 requires independent Windows identities; no self-declared isolation.")
        if data["expected_authorization_scope"] != _SCOPE:
            raise ValueError("Expected scope must match the unchanged ExecutionIntent V1 scope.")
        if data["time_source"] != "local_system_utc_unverified":
            raise ValueError("No authenticated clock is implemented.")
        raw = _canonical(data)
        _configuration_bytes(raw)
        object.__setattr__(self, "_json", raw.decode("utf-8"))

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


class _SourceFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _read_source(path, limit, expected_hash, label):
    """Read one bounded regular file; matching a pin does not authenticate it."""
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise _SourceFailure(label + "_unavailable")
        with path.open("rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise _SourceFailure(label + "_unavailable")
            raw = handle.read(limit + 1)
    except OSError as exc:
        raise _SourceFailure(label + "_unavailable") from exc
    if len(raw) > limit:
        raise _SourceFailure(label + "_too_large")
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise _SourceFailure(label + "_identity_mismatch")
    return raw


def _parse_source(parser, raw, label):
    try:
        return parser(raw)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise _SourceFailure(label + "_invalid") from exc


def _locations(configuration_path, data):
    """Reject obvious store-local/alias anchors; NOT TOCTOU-safe OS enforcement."""
    paths = {"configuration": configuration_path, "registry": Path(data["registry"]["path"]),
             "checkpoint": Path(data["minimum_checkpoint"]["path"])}
    try:
        root = Path(data["store"]["root"]).resolve(strict=True)
        if not root.is_dir():
            raise _SourceFailure("store_unavailable")
    except OSError as exc:
        raise _SourceFailure("store_unavailable") from exc
    except RuntimeError as exc:
        raise _SourceFailure("store_invalid_path") from exc
    resolved = {}
    for label, path in paths.items():
        try:
            resolved[label] = path.resolve(strict=True)
            if resolved[label] == root or root in resolved[label].parents:
                raise _SourceFailure(label + "_path_not_independent")
            for store_file in ("history.jsonl", "head.json", "checkpoint.json", "history.lock"):
                target = root / store_file
                if target.exists() and os.path.samefile(path, target):
                    raise _SourceFailure(label + "_path_not_independent")
            if any(os.path.samefile(path, other) for name, other in paths.items() if name != label and other.exists()):
                raise _SourceFailure("trust_anchor_path_alias")
        except OSError as exc:
            raise _SourceFailure(label + "_unavailable") from exc
        except RuntimeError as exc:
            # pathlib.resolve reports symlink loops as RuntimeError on Python
            # 3.10. Scope this conversion to filesystem path resolution only.
            raise _SourceFailure(label + "_invalid_path") from exc
    return root


def _now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _result(digest):
    return dict(result_type="local_authorization_verification", schema_version=1,
                requested_execution_intent_digest=digest, configuration_valid=False,
                configuration_content_matches_pin=False, registry_content_matches_pin=False,
                registry_valid=False, independent_checkpoint_content_matches_pin=False,
                independent_checkpoint_valid=False, checkpoint_matches_store=False,
                checkpoint_is_current_head=False, local_store_valid=False,
                **{name: False for name in _STORE_FLAGS},
                requested_intent_present=False, proposal_intent_consistent=False, authorization_scope_consistent=False,
                effective_review_status=None, effective_decision_id=None, latest_attestation_time_valid=None,
                local_review_state="not_evaluated", evaluation_time_utc=None,
                time_source="local_system_utc_unverified", deployment_mode="demonstration_only",
                trusted_configuration_origin_verified=False, trusted_registry_origin_verified=False,
                trusted_store_origin_verified=False, independent_checkpoint_verified=False,
                deployment_isolation_verified=False, verifier_deployment_identity_verified=False,
                authoritative_freshness_verified=False, trusted_time_verified=False,
                trusted_human_authorization=False, current_authorization_state="not_verified",
                execution_eligible=False, store_reason_codes=[], reason_codes=list(_LIMITATIONS))


class LocalAuthorizationVerifier:
    """Fixed trusted-side bootstrap declarations, never a verified OS boundary.

    expected_config_sha256 MUST be supplied independently, not derived on first
    use. Matching it detects configuration changes relative to that declaration;
    a caller controlling both values still cannot claim authenticated origin.
    Every query reacquires registry/checkpoint files; no cached approved fallback.
    """

    def __init__(self, configuration_path, *, expected_config_sha256: str):
        self._configuration_path = _absolute_path(os.fspath(configuration_path))
        _hash(expected_config_sha256)
        self._expected_config_sha256 = expected_config_sha256

    def verify(self, execution_intent_digest: str) -> dict:
        """Query a complete-store snapshot by exact digest; never grant execution.

        No per-query paths, records, keys, clock overrides or trusted-status flags
        are accepted. System UTC is sampled once; it is not authenticated time.
        No exception handler suppresses unrelated store/programming failures.
        """
        result = _result(None)
        try:
            _hash(execution_intent_digest)
        except ValueError:
            result["reason_codes"].insert(0, "invalid_execution_intent_digest")
            return result
        result["requested_execution_intent_digest"] = execution_intent_digest
        try:
            configuration_raw = _read_source(self._configuration_path, MAX_CONFIGURATION_BYTES,
                                              self._expected_config_sha256, "configuration")
            result["configuration_content_matches_pin"] = True
            data = _parse_source(VerifierConfigurationV1.from_json, configuration_raw, "configuration").to_dict()
            result["configuration_valid"] = True
            root = _locations(self._configuration_path, data)
            registry_path = Path(data["registry"]["path"])
            registry_raw = _read_source(registry_path, MAX_REGISTRY_BYTES, data["registry"]["sha256"], "registry")
            result["registry_content_matches_pin"] = True
            registry = _parse_source(TrustedPublicKeyRegistryV1.from_json, registry_raw, "registry")
            result["registry_valid"] = True
            checkpoint_path = Path(data["minimum_checkpoint"]["path"])
            checkpoint_raw = _read_source(checkpoint_path, MAX_MARKER_BYTES,
                                           data["minimum_checkpoint"]["sha256"], "checkpoint")
            result["independent_checkpoint_content_matches_pin"] = True
            checkpoint = _parse_source(StoreCheckpointV1.from_json, checkpoint_raw, "checkpoint")
            floor = checkpoint.to_dict()
            expected = data["minimum_checkpoint"]
            if (floor["store_id"] != data["store"]["store_id"] or floor["sequence"] != expected["sequence"] or
                    floor["entry_digest"] != expected["entry_digest"]):
                raise _SourceFailure("checkpoint_position_mismatch")
            result["independent_checkpoint_valid"] = True
            now = _now_utc()
            _utc(now)
            result["evaluation_time_utc"] = now
            # Only this existing public method reconstructs and verifies history.
            try:
                store = AuthorizationStore(root, store_id=data["store"]["store_id"], trusted_keys=registry)
            except (ValueError, OSError) as exc:
                raise _SourceFailure("store_unavailable") from exc
            checked = store.validate(now_utc=now, minimum_checkpoint=checkpoint)
            for name in _STORE_FLAGS:
                result[name] = checked[name]
            result["store_reason_codes"] = list(checked["reason_codes"])
            if not checked["local_store_valid"]:
                raise _SourceFailure("store_invalid")
            # Recheck fixed source identities after the store snapshot. This
            # detects observed replacements, NOT malicious swap-and-restore races.
            _read_source(self._configuration_path, MAX_CONFIGURATION_BYTES, self._expected_config_sha256, "configuration")
            _read_source(registry_path, MAX_REGISTRY_BYTES, data["registry"]["sha256"], "registry")
            _read_source(checkpoint_path, MAX_MARKER_BYTES, expected["sha256"], "checkpoint")
            result.update(local_store_valid=True, checkpoint_matches_store=True,
                          checkpoint_is_current_head=(floor["sequence"] == checked["committed_head"]["sequence"] and
                                                      floor["entry_digest"] == checked["committed_head"]["entry_digest"]))
            if not result["checkpoint_is_current_head"]:
                result["reason_codes"].insert(0, "checkpoint_is_only_lower_bound")
            if execution_intent_digest not in checked["effective_review_status"]:
                result["local_review_state"] = "intent_not_found"
                raise _SourceFailure("requested_intent_not_found")
            status = checked["effective_review_status"][execution_intent_digest]
            time_valid = checked["effective_attestation_time_valid"][execution_intent_digest]
            result.update(requested_intent_present=True, proposal_intent_consistent=True,
                          authorization_scope_consistent=True, effective_review_status=status,
                          effective_decision_id=checked["effective_decision_ids"][execution_intent_digest],
                          latest_attestation_time_valid=time_valid)
            if status == "approved":
                result["local_review_state"] = "approved_unverified" if time_valid else "expired_approval"
            else:
                result["local_review_state"] = status
            result["reason_codes"].insert(0, result["local_review_state"])
            return result
        except _SourceFailure as exc:
            result["reason_codes"].insert(0, exc.code)
            return result
