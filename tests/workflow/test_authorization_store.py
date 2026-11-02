"""Synthetic trusted-writer harness only; no human approvals or persistent keys."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
import subprocess
import sys
from threading import Barrier

import pytest

import src.workflow.authorization_store as module
from src.workflow.authorization_store import (
    AuthorizationStore, ENTRY_DIGEST_PROFILE, ENTRY_DOMAIN_PREFIX, MAX_DOCUMENT_BYTES,
    MAX_HISTORY_BYTES, MAX_MARKER_BYTES, MAX_NESTING_DEPTH,
    StoreCheckpointV1, StoreEntryV1, StoreError, StoreHeadV1, entry_digest,
)
from src.workflow.planning_approval import DecisionRecord, build_execution_intent, validate_decisions
from src.workflow.signed_authorization import (
    AuthorizationAttestationV1, TrustedPublicKeyRegistryV1, key_id_for_public_key, sign_attestation,
)
from tests.workflow.test_planning_approval import config, declaration, intent, proposal, reseal, review_chain
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_signed_authorization import key, registry, registry_data, resign


STORE_ID = "33333333-3333-4333-8333-333333333333"
OTHER_STORE = "44444444-4444-4444-8444-444444444444"
AUTH_ID = "11111111-1111-4111-8111-111111111111"
NOW = "2001-01-01T02:00:00Z"


class TestOnlyTrustedWriterHarness:
    """In-memory capability for tests; NOT OS isolation or proof of human presence."""
    __test__ = False

    def __init__(self, root, key, registry):
        self.root, self.key, self.registry = root, key, registry
        self.store = AuthorizationStore(root, store_id=STORE_ID, trusted_keys=registry)
        self.head = self.store.initialize()

    def signer(self, intent, decision, **allocated):
        return sign_attestation(intent, decision, private_key=self.key,
                                reviewer_key_id=key_id_for_public_key(self.key.public_key()), **allocated)

    def add(self, intent, proposal, decision, **options):
        arguments = dict(expected_head=self.head, signer=self.signer, signed_at_utc=NOW, now_utc=NOW)
        arguments.update(options)
        entry = self.store.append(intent, proposal, decision, **arguments)
        data = entry.to_dict()
        self.head = module._marker(StoreHeadV1, STORE_ID, data["sequence"], data["entry_digest"])
        return entry

    def validate(self, **options):
        result = self.store.validate(now_utc=NOW, **options)
        assert result["execution_eligible"] is False
        assert result["current_authorization_state"] == "not_verified"
        assert result["store_origin_authenticated"] is False
        assert result["registry_origin_authenticated"] is False
        if not result["local_store_valid"]:
            assert result["effective_review_status"] == {}
            assert result["effective_decision_ids"] == {}
            assert result["committed_head"] is None
        return result


@pytest.fixture
def harness(tmp_path, key, registry):
    return TestOnlyTrustedWriterHarness(tmp_path, key, registry)


def add_chain(harness, intent, proposal, revoked=False):
    records = list(review_chain(intent))
    if revoked:
        records.append(declaration(intent, "revoked", previous=records[-1], decision_id="synthetic-revoked",
                                   stamp="2001-01-01T01:30:00Z"))
    entries = [harness.add(intent, proposal, record) for record in records]
    return records, entries


def disk_entries(harness):
    return [json.loads(line) for line in (harness.root / "history.jsonl").read_bytes().splitlines()]


def rewrite(harness, entries, *, rechain=False, markers=True):
    """Adversarial disk editing, NOT a recovery operation offered by production."""
    previous = None
    for entry in entries:
        if rechain:
            entry["previous_entry_digest"] = previous
            entry["entry_digest"] = entry_digest(entry)
        previous = entry["entry_digest"]
    (harness.root / "history.jsonl").write_bytes(b"".join(module._canonical(entry) for entry in entries))
    if markers:
        sequence = len(entries)
        digest = entries[-1]["entry_digest"] if entries else None
        for name, cls in (("head.json", StoreHeadV1), ("checkpoint.json", StoreCheckpointV1)):
            (harness.root / name).write_bytes(module._canonical(module._marker(cls, STORE_ID, sequence, digest).to_dict()))


def test_empty_initialization_and_reinitialization_rejected(harness):
    result = harness.validate()
    assert (harness.root / "history.lock").is_file()
    assert result["local_store_valid"]
    assert all(result[name] for name in ("store_structurally_valid", "hash_chain_valid", "head_consistent",
                                       "checkpoint_consistent", "entries_signature_valid", "decision_history_valid"))
    assert result["committed_head"]["sequence"] == 0
    assert result["checkpoint"]["entry_digest"] is None
    assert result["effective_review_status"] == {}
    with pytest.raises(StoreError, match="store_not_empty"):
        harness.store.initialize()


@pytest.mark.parametrize("revoked,status", [(False, "approved"), (True, "revoked")])
def test_valid_full_history_and_revocation(harness, intent, proposal, revoked, status):
    records, entries = add_chain(harness, intent, proposal, revoked)
    result = harness.validate()
    assert result["local_store_valid"]
    assert result["effective_review_status"] == {intent.digest: status}
    assert result["effective_decision_ids"] == {intent.digest: records[-1].to_dict()["decision_id"]}
    assert result["committed_head"]["sequence"] == len(records)
    for index, entry in enumerate(entries, 1):
        data = entry.to_dict()
        payload = data["attestation"]["payload"]
        assert payload["store"] == dict(store_id=STORE_ID, sequence=index,
                                       previous_entry_digest=None if index == 1 else entries[index - 2].to_dict()["entry_digest"])
        assert data["decision_record"] == records[index - 1].to_dict()


def test_interleaved_intents_use_one_global_sequence(harness, intent, proposal):
    settings = config()
    settings["output"]["identity"] = "synthetic-other-output"
    other = build_execution_intent(proposal, selected_cluster_id=0, framework_d=settings)
    pending, approved = review_chain(intent)
    other_pending = declaration(other, decision_id="synthetic-other-pending")
    other_rejected = declaration(other, "rejected", previous=other_pending, decision_id="synthetic-other-rejected",
                                 stamp="2001-01-01T01:00:00Z")
    for i, d in ((intent, pending), (other, other_pending), (intent, approved), (other, other_rejected)):
        harness.add(i, proposal, d)
    result = harness.validate()
    assert result["local_store_valid"] and result["committed_head"]["sequence"] == 4
    assert result["effective_review_status"] == {intent.digest: "approved", other.digest: "rejected"}


def test_entry_digest_exact_profile_and_determinism(harness, intent, proposal):
    entry = harness.add(intent, proposal, declaration(intent))
    data = entry.to_dict()
    expected = deepcopy(data)
    expected.pop("entry_digest")
    raw = (json.dumps(expected, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    assert data["digest_profile"] == ENTRY_DIGEST_PROFILE
    assert ENTRY_DOMAIN_PREFIX == b"ionospheric-tec/authorization-store-entry/v1\x00"
    assert data["entry_digest"] == hashlib.sha256(ENTRY_DOMAIN_PREFIX + raw).hexdigest()
    assert entry_digest(dict(reversed(list(data.items())))) == data["entry_digest"]
    assert StoreEntryV1.from_json(entry.to_json()) == entry
    with pytest.raises(FrozenInstanceError):
        entry._json = "{}"
    detached = entry.to_dict()
    detached["proposal"]["limitations"].append("synthetic change")
    assert entry_digest(detached) != entry_digest(data)
    assert entry.to_dict() == data


@pytest.mark.parametrize("kind,reason", [
    ("duplicate_authorization", "duplicate_authorization_id"),
    ("duplicate_decision", "duplicate_decision_id"),
    ("duplicate_sequence", "noncontinuous_sequence"),
    ("skipped_sequence", "noncontinuous_sequence"),
    ("wrong_previous", "previous_digest_mismatch"),
    ("wrong_store", "store_id_mismatch"),
    ("entry_tamper", "entry_digest_mismatch"),
    ("signature_tamper", "invalid_entry_signature"),
    ("signed_position", "signed_store_position_mismatch"),
    ("signed_store_id", "signed_store_position_mismatch"),
])
def test_adversarial_history(harness, intent, proposal, kind, reason):
    add_chain(harness, intent, proposal)
    entries = disk_entries(harness)
    entry = entries[-1]
    if kind in ("duplicate_authorization", "signed_position", "signed_store_id"):
        envelope = entry["attestation"]
        if kind == "duplicate_authorization":
            envelope["payload"]["authorization_id"] = entries[0]["attestation"]["payload"]["authorization_id"]
        elif kind == "signed_position":
            envelope["payload"]["store"]["previous_entry_digest"] = "a" * 64
        else:
            envelope["payload"]["store"]["store_id"] = OTHER_STORE
        entry["attestation"] = resign(envelope, harness.key).to_dict()
    elif kind == "duplicate_decision":
        entry["decision_record"] = entries[0]["decision_record"]
    elif kind == "duplicate_sequence":
        entry["sequence"] = 1
        entry["previous_entry_digest"] = None
    elif kind == "skipped_sequence":
        entry["sequence"] += 1
    elif kind == "wrong_previous":
        entry["previous_entry_digest"] = "a" * 64
    elif kind == "wrong_store":
        entry["store_id"] = OTHER_STORE
    elif kind == "entry_tamper":
        entry["proposal"]["limitations"].append("Tampered synthetic content")
    else:
        signature = entry["attestation"]["signature_b64"]
        entry["attestation"]["signature_b64"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    if kind != "entry_tamper":
        entry["entry_digest"] = entry_digest(entry)
    rewrite(harness, entries)
    result = harness.validate()
    assert not result["local_store_valid"] and result["reason_codes"] == [reason]


@pytest.mark.parametrize("policy", ["unknown", "disabled", "revoked", "identity", "purpose"])
def test_current_registry_policy_applies_to_every_archived_signature(harness, intent, proposal, policy):
    add_chain(harness, intent, proposal, True)
    data = registry_data(harness.key)
    if policy == "unknown":
        data["entries"] = []
    elif policy == "disabled":
        data["entries"][0]["enabled"] = False
    elif policy == "revoked":
        data["entries"][0]["revoked"] = True
    else:
        data["entries"][0]["reviewer_identity" if policy == "identity" else "purpose"] = "synthetic-other"
    store = AuthorizationStore(harness.root, store_id=STORE_ID,
                               trusted_keys=TrustedPublicKeyRegistryV1.from_dict(data))
    result = store.validate(now_utc=NOW)
    assert result["reason_codes"] == ["invalid_entry_signature"]
    assert not result["entries_signature_valid"] and not result["execution_eligible"]
    assert result["effective_review_status"] == {}


@pytest.mark.parametrize("kind", ["missing_parent", "branch", "revision", "transition", "cross_intent", "stale_proposal"])
def test_writer_rejects_invalid_lineage_before_signing(harness, intent, proposal, kind):
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)
    if kind == "branch":
        harness.add(intent, proposal, approved)
        changed = declaration(intent, "approved", previous=pending, decision_id="synthetic-branch",
                              stamp="2001-01-01T01:30:00Z")
    else:
        data = approved.to_dict()
        if kind == "missing_parent":
            data["supersedes"]["decision_id"] = "synthetic-absent"
        elif kind == "revision":
            data["revision"] = 5
        elif kind == "transition":
            data["status"] = "revoked"
        elif kind == "cross_intent":
            data["execution_intent_digest"] = "e" * 64
        else:
            proposal = deepcopy(proposal)
            proposal["limitations"].append("Changed proposal must be reviewed again.")
        changed = DecisionRecord.from_dict(reseal(data, "decision_digest"))
    before = (harness.root / "history.jsonl").read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid lineage must not reach signing capability.")

    with pytest.raises(StoreError):
        harness.add(intent, proposal, changed, signer=forbidden)
    assert (harness.root / "history.jsonl").read_bytes() == before


@pytest.mark.parametrize("kind", ["missing_parent", "branch", "revision", "transition", "reverse_order", "stale_proposal"])
def test_reader_independently_checks_lineage_and_proposal(harness, intent, proposal, kind):
    records, _ = add_chain(harness, intent, proposal)
    entries = disk_entries(harness)
    entry = entries[-1]
    data = entry["decision_record"]
    if kind == "missing_parent":
        data["supersedes"]["decision_id"] = "synthetic-absent"
    elif kind == "branch":
        entry = deepcopy(entry)
        entry["sequence"] = 3
        data = entry["decision_record"]
        data["decision_id"] = "synthetic-conflicting-branch"
        entries.append(entry)
    elif kind == "revision":
        data["revision"] += 1
    elif kind == "transition":
        data["status"] = "revoked"
    elif kind == "reverse_order":
        entries.reverse()
    else:
        for candidate in entries:
            candidate["proposal"]["limitations"].append("Synthetic resealed stale proposal")
    if kind not in ("reverse_order", "stale_proposal"):
        entry["decision_record"] = reseal(data, "decision_digest")
    previous = None
    for sequence, candidate in enumerate(entries, 1):
        candidate["sequence"] = sequence
        candidate["previous_entry_digest"] = previous
        decision = DecisionRecord.from_dict(candidate["decision_record"])
        candidate["attestation"] = harness.signer(intent, decision, authorization_id=str(module.uuid4()),
                                                 store=dict(store_id=STORE_ID, sequence=sequence, previous_entry_digest=previous),
                                                 signed_at_utc=NOW, expires_at_utc=None).to_dict()
        candidate["entry_digest"] = entry_digest(candidate)
        previous = candidate["entry_digest"]
    rewrite(harness, entries)
    result = harness.validate()
    assert result["entries_signature_valid"]
    assert not result["decision_history_valid"] and not result["local_store_valid"]


def test_subset_cannot_hide_revocation(harness, intent, proposal):
    records, _ = add_chain(harness, intent, proposal, True)
    subset = validate_decisions(intent, proposal, records[:2], now_utc=NOW)
    assert subset["approved_review_status"]  # stateless 3A cannot detect omissions
    assert harness.validate()["effective_review_status"] == {intent.digest: "revoked"}
    with pytest.raises(TypeError):
        harness.store.validate(now_utc=NOW, entries=records[:2])


@pytest.mark.parametrize("kind,reason", [
    ("delete_revoked", "head_history_mismatch"), ("stale_head", "head_history_mismatch"),
    ("head_ahead", "head_history_mismatch"), ("checkpoint_ahead", "checkpoint_head_mismatch"),
    ("checkpoint_stale", "checkpoint_head_mismatch"), ("checkpoint_fork", "checkpoint_head_mismatch"),
    ("head_fork", "head_history_mismatch"), ("checkpoint_store", "checkpoint_head_mismatch"),
])
def test_history_head_checkpoint_must_agree_exactly(harness, intent, proposal, kind, reason):
    add_chain(harness, intent, proposal, True)
    entries = disk_entries(harness)
    if kind == "delete_revoked":
        rewrite(harness, entries[:-1], markers=False)
    else:
        filename = "head.json" if kind.startswith("head") or kind == "stale_head" else "checkpoint.json"
        path = harness.root / filename
        data = json.loads(path.read_bytes())
        if kind in ("stale_head", "checkpoint_stale"):
            data.update(sequence=2, entry_digest=entries[1]["entry_digest"])
        elif kind.endswith("ahead"):
            data["sequence"] += 1
        elif kind.endswith("store"):
            data["store_id"] = OTHER_STORE
        else:
            data["entry_digest"] = "e" * 64
        path.write_bytes(module._canonical(data))
    result = harness.validate()
    assert not result["local_store_valid"] and result["reason_codes"] == [reason]
    with pytest.raises(StoreError):
        harness.add(intent, proposal, declaration(intent, decision_id="synthetic-no-fallback"))


def test_external_checkpoint_detects_entire_root_rollback(harness, intent, proposal):
    records, _ = add_chain(harness, intent, proposal, True)
    protected = StoreCheckpointV1.from_json((harness.root / "checkpoint.json").read_bytes())
    entries = disk_entries(harness)
    rewrite(harness, entries[:2])  # attacker rolled back ALL mutable state files
    unprotected = harness.validate()
    assert unprotected["local_store_valid"]  # documented residual attack
    assert unprotected["effective_review_status"][intent.digest] == "approved"
    result = harness.validate(minimum_checkpoint=protected)
    assert result["reason_codes"] == ["checkpoint_rollback"]
    with pytest.raises(StoreError, match="checkpoint_rollback"):
        harness.add(intent, proposal, records[-1], minimum_checkpoint=protected)


@pytest.mark.parametrize("kind", ["older_valid", "equal_valid", "same_sequence_fork", "older_fork", "other_store"])
def test_independently_retained_checkpoint_floor(harness, intent, proposal, kind):
    _, entries = add_chain(harness, intent, proposal, True)
    index = 0 if kind.startswith("older") else 2
    entry = entries[index].to_dict()
    floor = module._marker(StoreCheckpointV1, OTHER_STORE if kind == "other_store" else STORE_ID,
                           entry["sequence"], "e" * 64 if "fork" in kind else entry["entry_digest"])
    result = harness.validate(minimum_checkpoint=floor)
    assert result["local_store_valid"] is kind.endswith("valid")
    if "fork" in kind:
        assert result["reason_codes"] == ["checkpoint_fork"]


@pytest.mark.parametrize("filename", ["history.jsonl", "head.json", "checkpoint.json"])
@pytest.mark.parametrize("corruption", ["truncated", "invalid_json", "duplicate_key", "nonfinite", "extra_field", "missing"])
def test_corrupt_or_missing_files_fail_closed(harness, intent, proposal, filename, corruption):
    add_chain(harness, intent, proposal, True)
    path = harness.root / filename
    raw = path.read_bytes()
    if corruption == "missing":
        path.unlink()
    elif corruption == "truncated":
        path.write_bytes(raw[:-5])
    elif corruption == "invalid_json":
        path.write_bytes(b"{broken}\n")
    elif corruption == "duplicate_key":
        path.write_bytes(b'{"a":1,"a":2}\n')
    elif corruption == "nonfinite":
        path.write_bytes(b'{"a":NaN}\n')
    else:
        data = json.loads(raw.splitlines()[0])
        data["extra"] = "synthetic"
        path.write_bytes(module._canonical(data))
    assert not harness.validate()["local_store_valid"]


@pytest.mark.parametrize("stage", ["partial_append", "after_append", "head", "checkpoint", "after_checkpoint"])
def test_interrupted_publication_is_detected_without_automatic_repair(harness, intent, proposal, monkeypatch, stage):
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)
    real_append, real_publish = module._append_history, module._publish

    def append(path, raw):
        if stage == "partial_append":
            with path.open("ab") as handle:
                handle.write(raw[:37])
                module._flush(handle)
            raise OSError("Injected interrupted append")
        real_append(path, raw)
        if stage == "after_append":
            raise OSError("Injected failure after history flush")

    def publish(path, raw):
        if path.name == stage + ".json":
            raise OSError("Injected publication failure")
        real_publish(path, raw)
        if stage == "after_checkpoint" and path.name == "checkpoint.json":
            raise OSError("Injected lost acknowledgement after complete publication")

    monkeypatch.setattr(module, "_append_history", append)
    monkeypatch.setattr(module, "_publish", publish)
    with pytest.raises(StoreError, match="Injected"):
        harness.add(intent, proposal, approved)
    snapshot = {path.name: path.read_bytes() for path in harness.root.iterdir()}
    result = harness.validate()
    if stage == "after_checkpoint":
        # All three files match. A failed caller acknowledgement cannot undo a
        # committed append; retry must re-read state instead of signing twice.
        assert result["local_store_valid"] and result["committed_head"]["sequence"] == 2
        with pytest.raises(StoreError, match="stale_expected_head"):
            harness.add(intent, proposal, approved)
    else:
        assert not result["local_store_valid"]
        with pytest.raises(StoreError):
            harness.add(intent, proposal, approved)
    assert {path.name: path.read_bytes() for path in harness.root.iterdir()} == snapshot


@pytest.mark.parametrize("stage", ["history", "head", "checkpoint"])
def test_flush_failures_do_not_publish_a_new_committed_state(harness, intent, proposal, monkeypatch, stage):
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)
    original = module._flush
    calls = 0

    def flush(handle):
        nonlocal calls
        calls += 1
        if calls == {"history": 1, "head": 2, "checkpoint": 3}[stage]:
            raise OSError("Injected fsync failure")
        return original(handle)

    monkeypatch.setattr(module, "_flush", flush)
    with pytest.raises(StoreError, match="fsync"):
        harness.add(intent, proposal, approved)
    assert not harness.validate()["local_store_valid"]


@pytest.mark.parametrize("target", ["head.json", "checkpoint.json"])
def test_actual_replacement_boundary_failure(harness, intent, proposal, monkeypatch, target):
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)
    original = module.os.replace

    def replace(source, destination):
        if destination.name == target:
            raise OSError("Injected os.replace failure")
        return original(source, destination)

    monkeypatch.setattr(module.os, "replace", replace)
    with pytest.raises(StoreError, match="os.replace"):
        harness.add(intent, proposal, approved)
    assert not harness.validate()["local_store_valid"]


def test_complete_extra_entry_stale_head(harness, intent, proposal):
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)
    old_head = (harness.root / "head.json").read_bytes()
    old_checkpoint = (harness.root / "checkpoint.json").read_bytes()
    harness.add(intent, proposal, approved)
    (harness.root / "head.json").write_bytes(old_head)
    (harness.root / "checkpoint.json").write_bytes(old_checkpoint)
    assert harness.validate()["reason_codes"] == ["head_history_mismatch"]


def test_lock_failure_and_reader_writer_lock_contention(harness, intent, proposal):
    with module._exclusive(harness.root):
        assert harness.validate()["reason_codes"] == ["lock_unavailable"]
        with pytest.raises(StoreError, match="lock"):
            harness.add(intent, proposal, declaration(intent))
    assert harness.validate()["local_store_valid"]


def test_actual_separate_process_cannot_read_while_writer_locked(harness):
    script = """
import json, sys
from src.workflow.authorization_store import AuthorizationStore
from src.workflow.signed_authorization import TrustedPublicKeyRegistryV1
store = AuthorizationStore(sys.argv[1], store_id=sys.argv[2],
    trusted_keys=TrustedPublicKeyRegistryV1.from_json(sys.argv[3]))
result = store.validate(now_utc=sys.argv[4])
print(json.dumps(result['reason_codes']))
"""
    with module._exclusive(harness.root):
        process = subprocess.run([sys.executable, "-B", "-c", script, str(harness.root), STORE_ID,
                                  harness.registry.to_json(), NOW], capture_output=True, text=True, timeout=20)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == ["lock_unavailable"]


def test_concurrent_writers_one_commits_other_fails(harness, intent, proposal):
    barrier = Barrier(2)
    expected = harness.head

    def write(index):
        record = declaration(intent, decision_id="synthetic-concurrent-" + str(index))
        barrier.wait(timeout=10)
        try:
            return harness.store.append(intent, proposal, record, expected_head=expected,
                                         signer=harness.signer, signed_at_utc=NOW, now_utc=NOW)
        except StoreError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, (1, 2)))
    assert sum(isinstance(item, StoreEntryV1) for item in results) == 1
    assert next(item for item in results if type(item) is str) in ("lock_unavailable", "stale_expected_head")
    assert harness.validate()["committed_head"]["sequence"] == 1


@pytest.mark.parametrize("kind", ["wrong_position", "wrong_authorization_id", "changed_status", "wrong_type", "unknown_key"])
def test_capability_result_cannot_override_writer_allocations_or_decision(harness, intent, proposal, kind):
    record = declaration(intent)

    def signer(i, d, **allocated):
        if kind == "wrong_type":
            return {}
        if kind == "wrong_position":
            allocated["store"]["store_id"] = OTHER_STORE
        elif kind == "wrong_authorization_id":
            allocated["authorization_id"] = AUTH_ID
        elif kind == "changed_status":
            d = declaration(i, "approved")
        if kind == "unknown_key":
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            other = Ed25519PrivateKey.generate()
            return sign_attestation(i, d, private_key=other, reviewer_key_id=key_id_for_public_key(other.public_key()), **allocated)
        return harness.signer(i, d, **allocated)

    with pytest.raises(StoreError):
        harness.add(intent, proposal, record, signer=signer)
    assert harness.validate()["committed_head"]["sequence"] == 0


def test_capability_exception_propagates_without_writing(harness, intent, proposal):
    def signer(*args, **kwargs):
        raise RuntimeError("Unrelated signer programming error")

    with pytest.raises(RuntimeError, match="programming"):
        harness.add(intent, proposal, declaration(intent), signer=signer)
    assert harness.validate()["committed_head"]["sequence"] == 0


def test_writer_detects_duplicate_decision_and_generated_authorization_id(harness, intent, proposal, monkeypatch):
    pending, approved = review_chain(intent)
    first = harness.add(intent, proposal, pending)
    with pytest.raises(StoreError, match="duplicate_decision_id"):
        harness.add(intent, proposal, pending)
    monkeypatch.setattr(module, "uuid4", lambda: first.to_dict()["attestation"]["payload"]["authorization_id"])
    with pytest.raises(StoreError, match="duplicate_authorization_id"):
        harness.add(intent, proposal, approved)
    assert harness.validate()["committed_head"]["sequence"] == 1


@pytest.mark.parametrize("filename,limit", [("history.jsonl", MAX_HISTORY_BYTES), ("head.json", MAX_MARKER_BYTES),
                                           ("checkpoint.json", MAX_MARKER_BYTES)])
def test_file_resource_limits(harness, filename, limit):
    (harness.root / filename).write_bytes(b" " * (limit + 1))
    assert harness.validate()["reason_codes"] == ["resource_limit"]


@pytest.mark.parametrize("kind", ["deep_dict", "deep_text", "wide", "oversized", "nan", "infinity", "cycle"])
def test_bounded_contract_parsing(kind):
    if kind == "deep_text":
        with pytest.raises(ValueError):
            StoreEntryV1.from_json("[" * 5000 + "null" + "]" * 5000)
        return
    value = {}
    if kind == "deep_dict":
        for _ in range(5000):
            value = {"nested": value}
    elif kind == "cycle":
        value["self"] = value
    elif kind == "wide":
        value = [None] * MAX_DOCUMENT_BYTES
    else:
        value = {"bad": {"oversized": "x" * MAX_DOCUMENT_BYTES, "nan": float("nan"), "infinity": float("inf")}[kind]}
    with pytest.raises(ValueError):
        StoreEntryV1.from_dict(value)


def test_entry_count_bound_on_reader_and_writer(harness, intent, proposal, monkeypatch):
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)
    monkeypatch.setattr(module, "MAX_ENTRIES", 1)
    with pytest.raises(StoreError, match="resource_limit"):
        harness.add(intent, proposal, approved)
    raw = (harness.root / "history.jsonl").read_bytes()
    (harness.root / "history.jsonl").write_bytes(raw + raw)
    assert harness.validate()["reason_codes"] == ["resource_limit"]


def test_expired_ancestor_does_not_hide_revocation(harness, intent, proposal):
    pending = declaration(intent, expires="2001-01-01T00:30:00Z")
    approved = declaration(intent, "approved", previous=pending, decision_id="synthetic-expiring-approved",
                           stamp="2001-01-01T00:10:00Z", expires="2001-01-01T00:30:00Z")
    revoked = declaration(intent, "revoked", previous=approved, decision_id="synthetic-later-revocation",
                          stamp="2001-01-01T01:00:00Z")
    harness.add(intent, proposal, pending, signed_at_utc="2001-01-01T00:01:00Z", now_utc="2001-01-01T00:01:00Z")
    harness.add(intent, proposal, approved, signed_at_utc="2001-01-01T00:11:00Z", now_utc="2001-01-01T00:11:00Z")
    assert harness.validate()["effective_attestation_time_valid"] == {intent.digest: False}
    harness.add(intent, proposal, revoked)
    result = harness.validate()
    assert result["local_store_valid"] and result["effective_review_status"] == {intent.digest: "revoked"}


@pytest.mark.parametrize("kind", ["future", "expired"])
def test_new_entry_must_be_time_valid_at_append(harness, intent, proposal, kind):
    pending = declaration(intent)
    options = dict(signed_at_utc="2001-01-01T03:00:00Z") if kind == "future" else dict(
        signed_at_utc="2001-01-01T00:01:00Z", expires_at_utc="2001-01-01T00:30:00Z")
    with pytest.raises(StoreError, match="invalid_new_signature"):
        harness.add(intent, proposal, pending, **options)
    assert harness.validate()["committed_head"]["sequence"] == 0


@pytest.mark.parametrize("name,cls", [("head.json", StoreHeadV1), ("checkpoint.json", StoreCheckpointV1)])
@pytest.mark.parametrize("field,value", [("schema_version", True), ("schema_version", 2), ("sequence", True),
                                         ("sequence", -1), ("store_id", "bad"), ("entry_digest", "a" * 64)])
def test_marker_schema_is_strict(harness, name, cls, field, value):
    data = json.loads((harness.root / name).read_bytes())
    data[field] = value
    with pytest.raises(ValueError):
        cls.from_dict(data)


def test_configured_root_and_identity_are_explicit(tmp_path, registry):
    for root in ("relative-store", tmp_path / "missing"):
        with pytest.raises(ValueError):
            AuthorizationStore(root, store_id=STORE_ID, trusted_keys=registry)
    with pytest.raises(TypeError):
        AuthorizationStore(tmp_path, store_id=STORE_ID, trusted_keys={})
    with pytest.raises(ValueError):
        AuthorizationStore(tmp_path, store_id="not-uuid", trusted_keys=registry)


def test_missing_store_does_not_initialize_itself(tmp_path, registry):
    store = AuthorizationStore(tmp_path, store_id=STORE_ID, trusted_keys=registry)
    assert store.validate(now_utc=NOW)["reason_codes"] == ["lock_unavailable"]
    assert not (tmp_path / "head.json").exists()
    assert not (tmp_path / "history.lock").exists()


@pytest.mark.parametrize("operation", ["validate", "append"])
def test_initialized_store_missing_lock_never_recreates_or_mutates_files(harness, intent, proposal, operation):
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)  # ordinary initialized-store append succeeds
    (harness.root / "history.lock").unlink()
    before = {path.name: path.read_bytes() for path in harness.root.iterdir()}
    assert set(before) == {"history.jsonl", "head.json", "checkpoint.json"}

    def forbidden(*args, **kwargs):
        raise AssertionError("Missing permanent lock must fail before signing.")

    if operation == "validate":
        result = harness.validate()
        assert result["reason_codes"] == ["lock_unavailable"]
        assert not result["local_store_valid"]
    else:
        with pytest.raises(StoreError) as caught:
            harness.add(intent, proposal, approved, signer=forbidden)
        assert caught.value.code == "lock_unavailable"
    assert not (harness.root / "history.lock").exists()
    assert {path.name: path.read_bytes() for path in harness.root.iterdir()} == before


def test_lock_helper_defaults_to_not_creating_files(tmp_path):
    with pytest.raises(StoreError) as caught:
        with module._exclusive(tmp_path):
            raise AssertionError("Missing lock must prevent entering the critical section.")
    assert caught.value.code == "lock_unavailable"
    assert list(tmp_path.iterdir()) == []


def test_different_configured_store_rejects_replay(harness, intent, proposal):
    add_chain(harness, intent, proposal)
    other = AuthorizationStore(harness.root, store_id=OTHER_STORE, trusted_keys=harness.registry)
    result = other.validate(now_utc=NOW)
    assert result["reason_codes"] == ["store_id_mismatch"]


def test_no_mutation_of_existing_v1_records(harness, intent, proposal):
    records = review_chain(intent)
    before = deepcopy(proposal), intent.to_json(), [record.to_json() for record in records], harness.registry.to_json()
    for record in records:
        harness.add(intent, proposal, record)
    harness.validate()
    assert before == (proposal, intent.to_json(), [record.to_json() for record in records], harness.registry.to_json())
    assert records[-1].to_dict()["trusted_authorization_verification"] == "not_verified"


def test_store_never_calls_scientific_frameworks(harness, intent, proposal, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Store must not execute scientific code or Stage 2.")

    import src.temporal_anomaly.temporal_anomaly as temporal
    import src.workflow.statistical_analysis_adapter as statistical
    import src.workflow.statistical_significance_adapter as significance
    import src.workflow.clustering_adapter as clustering
    import src.spatial_verification.spatial_anomaly as spatial
    import src.workflow.stage2_runner as runner
    import src.workflow.stage2_cli as cli

    for target, name in ((temporal, "detect_temporal_anomalies"), (statistical, "run_statistical_analysis"),
                         (significance, "run_statistical_significance"), (clustering, "run_clustering_workflow"),
                         (spatial, "compute_spatial_anomalies"), (runner, "run_stage2"), (cli, "main")):
        monkeypatch.setattr(target, name, forbidden)
    add_chain(harness, intent, proposal, True)
    assert harness.validate()["local_store_valid"]


def test_no_agent_controlled_trust_or_execution_switch(harness):
    for option in (dict(trust=True), dict(execution_eligible=True), dict(root="agent-selected")):
        with pytest.raises(TypeError):
            harness.store.validate(now_utc=NOW, **option)


@pytest.mark.parametrize("status", ["rejected", "revoked"])
def test_writer_never_promotes_denied_state_directly_to_approval(harness, intent, proposal, status):
    if status == "revoked":
        records, _ = add_chain(harness, intent, proposal, True)
    else:
        records = list(review_chain(intent, "rejected"))
        for record in records:
            harness.add(intent, proposal, record)
    changed = declaration(intent, "approved", previous=records[-1], decision_id="synthetic-invalid-promotion",
                          stamp="2001-01-01T01:45:00Z")
    before = (harness.root / "history.jsonl").read_bytes()
    with pytest.raises(StoreError, match="invalid_decision_history"):
        harness.add(intent, proposal, changed)
    assert (harness.root / "history.jsonl").read_bytes() == before
    assert harness.validate()["effective_review_status"][intent.digest] == status


def test_stale_expected_head_prevents_signer_invocation(harness, intent, proposal):
    stale = harness.head
    pending, approved = review_chain(intent)
    harness.add(intent, proposal, pending)

    def forbidden(*args, **kwargs):
        raise AssertionError("Stale compare-and-append must fail before signing.")

    with pytest.raises(StoreError, match="stale_expected_head"):
        harness.add(intent, proposal, approved, expected_head=stale, signer=forbidden)


@pytest.mark.parametrize("depth,valid", [(MAX_NESTING_DEPTH, True), (MAX_NESTING_DEPTH + 1, False)])
def test_exact_codec_depth_boundary(depth, valid):
    value = None
    for _ in range(depth):
        value = [value]
    if valid:
        assert module._load(module._canonical(value)) == value
    else:
        with pytest.raises(ValueError, match="nesting"):
            module._canonical(value)


def test_exact_codec_byte_boundary_and_large_integer():
    value = "x" * (MAX_DOCUMENT_BYTES - 3)  # two quotes and one LF
    assert len(module._canonical(value)) == MAX_DOCUMENT_BYTES
    with pytest.raises(ValueError, match="size"):
        module._canonical(value + "x")
    with pytest.raises(ValueError):
        module._load(b" " * (MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(ValueError, match="integer"):
        module._load(b"1" * 10000)


@pytest.mark.parametrize("field,value", [("schema_version", True), ("schema_version", 2),
                                         ("sequence", True), ("digest_profile", "other"),
                                         ("entry_type", "other"), ("proposal", None)])
def test_entry_schema_versions_and_types(harness, intent, proposal, field, value):
    data = harness.add(intent, proposal, declaration(intent)).to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        StoreEntryV1.from_dict(data)


@pytest.mark.parametrize("raw", [b'{"nested":' * 5000 + b'null' + b'}' * 5000,
                                 b'{"oversized":"' + b'x' * MAX_DOCUMENT_BYTES + b'"}\n'],
                         ids=["deep_json", "oversized_json"])
def test_deep_or_oversized_stored_entry_returns_structured_failure(harness, raw):
    (harness.root / "history.jsonl").write_bytes(raw + (b"" if raw.endswith(b"\n") else b"\n"))
    result = harness.validate()
    assert not result["store_structurally_valid"]
    assert result["reason_codes"] == ["invalid_store_document"]


@pytest.mark.parametrize("target", ["head.json", "checkpoint.json"])
def test_interrupted_initialization_is_not_automatically_reinitialized(tmp_path, key, registry, monkeypatch, target):
    store = AuthorizationStore(tmp_path, store_id=STORE_ID, trusted_keys=registry)
    original = module._publish

    def publish(path, raw):
        if path.name == target:
            raise OSError("Injected initialization publication failure")
        return original(path, raw)

    monkeypatch.setattr(module, "_publish", publish)
    with pytest.raises(StoreError):
        store.initialize()
    assert not store.validate(now_utc=NOW)["local_store_valid"]
    with pytest.raises(StoreError, match="store_not_empty"):
        store.initialize()


@pytest.mark.parametrize("value", [True, 1.0])
def test_each_embedded_proposal_requires_exact_json_content(harness, intent, proposal, value):
    add_chain(harness, intent, proposal)
    entries = disk_entries(harness)
    entries[-1]["proposal"]["schema_version"] = value
    assert entries[-1]["proposal"] == entries[0]["proposal"]  # Python equality is insufficient
    entries[-1]["entry_digest"] = entry_digest(entries[-1])
    rewrite(harness, entries)
    result = harness.validate()
    assert result["entries_signature_valid"]
    assert result["reason_codes"] == ["conflicting_intent_content"]
