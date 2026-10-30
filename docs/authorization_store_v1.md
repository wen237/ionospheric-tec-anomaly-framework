# Local authoritative decision store V1 prototype

Checkpoint 3B-2B adds local integrity and complete-history validation around the
existing immutable V1 contracts. It does not authenticate the configured root,
registry origin, researcher identity or human presence. It never grants execution
eligibility, invokes Framework D, or intercepts the existing Stage 2 interfaces.
Windows account/ACL separation remains Checkpoint 3B-2C work.

## Interfaces and trusted-side configuration

`AuthorizationStore(root, *, store_id, trusted_keys)` requires an existing absolute
directory, canonical lowercase UUIDv4 and independently supplied
`TrustedPublicKeyRegistryV1` snapshot. It resolves the configured root once; paths
are not parameters to subsequent reader/writer methods. This is a trusted-side
Python prototype, **not** an Agent-facing path or signing API. Private Python
attributes and callbacks do not create a security boundary within one process.

- `initialize() -> StoreHeadV1` accepts only an empty directory, except for the
  permanent lock file. It refuses to reinitialize damaged or incomplete stores.
- `append(intent, proposal, decision, *, expected_head, signer, signed_at_utc,
  now_utc, expires_at_utc=None, minimum_checkpoint=None) -> StoreEntryV1` allocates
  the position and authorization UUID under the lock. `expected_head` is a
  required `StoreHeadV1` compare-and-append precondition, not a trusted clock.
- `validate(*, now_utc, minimum_checkpoint=None) -> dict` reads the complete
  configured history under the same exclusive lock. No entry subset is accepted.
- `entry_digest(entry)` exposes the independent store digest algorithm.
- `StoreEntryV1`, `StoreHeadV1`, `StoreCheckpointV1` provide frozen JSON content,
  `from_dict/from_json`, `to_dict/to_json`, and detached dictionary copies.

`signer(intent, decision, *, authorization_id, store, signed_at_utc,
expires_at_utc)` must be an explicit existing signing capability supplied by the
trusted side and return `AuthorizationAttestationV1`. There is no default signer,
key generation, key loading, persistent key storage, callable-name deserialization
or signing CLI. Its output is revalidated against the exact allocated UUID,
position, original decision/intent and configured registry before persistence.
The test-only harness holds ephemeral in-memory keys; it does not establish
physical review, OS isolation or researcher authorization.

## Exact on-disk contracts

The root contains `history.jsonl`, `head.json`, `checkpoint.json`, and a permanent
`history.lock`. Failed publications can leave `.publish-*` diagnostic temporary
files, which readers ignore. Temporary files are not history or publication
markers. No paths inside stored proposals/configuration are followed.

Every `history.jsonl` line is one canonical UTF-8 Entry V1 including its final LF:

```text
{
  entry_type: "signed_decision_store_entry",
  schema_version: 1,
  digest_profile: "tec-store-json-utf8-lf-v1",
  store_id: canonical UUIDv4,
  sequence: positive safe integer,
  previous_entry_digest: null at sequence 1, otherwise lowercase SHA256,
  proposal: complete existing daily-window proposal,
  execution_intent: complete immutable ExecutionIntent V1,
  decision_record: complete immutable DecisionRecord V1,
  attestation: complete AuthorizationAttestationV1 envelope,
  entry_digest: lowercase SHA256
}
```

There are no external proposal references to resolve. Full proposal content is
stored in each entry so existing `validate_decisions()` can rebuild and compare
the exact ExecutionIntent. This intentionally small prototype trades some space
for an independently verifiable, self-contained history. Repeated intent and
proposal content must agree exactly within each intent's history.

Head V1 and Checkpoint V1 each have exactly:

```text
{
  document_type: "authorization_store_head" | "authorization_store_checkpoint",
  schema_version: 1,
  store_id: canonical UUIDv4,
  sequence: nonnegative safe integer,
  entry_digest: null at sequence 0, otherwise lowercase SHA256
}
```

An initialized empty store has zero history bytes, sequence 0 and null digest in
both markers. Sequence numbers for entries are global, contiguous from 1, across
all intents. Decision IDs and authorization IDs are unique across the whole
store. Different intents have independent decision lineages; interleaving does
not create a cross-intent parent relationship.

Unknown/missing fields, duplicate JSON keys, unsupported types/versions,
nonfinite values, BOM, invalid UTF-8 and noncanonical on-disk bytes are rejected.
Schema integers must be exact integers, excluding booleans. Native JSON values
support finite floats and signed safe integers for the embedded existing proposal
and intent; this does not change the narrower attestation V1 numeric profile.

## Entry digest profile and signed positions

To compute `entry_digest`, copy the complete entry, remove **only** its own
`entry_digest` field, and encode:

```python
canonical = (json.dumps(content, ensure_ascii=False, allow_nan=False,
                        sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
entry_digest = sha256(b"ionospheric-tec/authorization-store-entry/v1\x00" + canonical).hexdigest()
```

There is no Unicode normalization or BOM, and exactly one trailing LF. This is
the Python JSON profile above, **not RFC 8785 JCS**. The digest covers all embedded
V1 objects, the signature, store ID, sequence, predecessor and profile label.
Existing ExecutionIntent/DecisionRecord digests, Ed25519 domain prefix, payload
fields, canonical signing bytes and golden vectors are unchanged.

The writer first chooses `(store_id, sequence, previous_entry_digest)`, then
signs the DecisionRecord with that exact position and a new authorization UUID.
It then computes the entry digest over the completed signed envelope. The
attestation binds its predecessor, not its own entry digest, so no circular hash
exists. A valid signature with a different position is not a valid store entry.
The underlying stateless `verify_attestation()` still treats store positions as
declarations; only this full-history reader checks their relationship to entries.

## Locking, publication and the committed-state invariant

All initialization, reads and appends take one nonblocking exclusive lock on the
permanent `history.lock`; lock contention fails closed rather than waiting or
reading an intermediate publication. The file is never replaced/unlinked by
this module. Windows uses `msvcrt.locking(..., LK_NBLCK, 1)` at offset zero (a
region beyond EOF is supported). The POSIX fallback uses `flock(LOCK_EX|LOCK_NB)`.
See [Python msvcrt locking](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking).

Append order under that lock:

1. Read and validate the entire history, head and checkpoint, plus any supplied
   independent checkpoint floor. Compare the required expected head.
2. Reject duplicate decision IDs; validate the next declared lineage and exact
   proposal/intent binding before invoking the signing capability.
3. Allocate the next global sequence, predecessor digest and UUIDv4; reject a
   UUID collision rather than accepting or silently reusing it.
4. Obtain and verify the signed attestation, including actual position/UUID,
   registry policy and time at append; construct and digest the entry.
5. Append one canonical line to history, check the write count, flush and fsync.
6. Write a same-directory temporary head, flush/fsync, then `os.replace` head.
7. Write a same-directory temporary checkpoint, flush/fsync, then replace it.
8. Re-read and validate the complete state before returning; release the lock.

**A valid committed local state requires history EOF, Head V1 and Checkpoint V1
to have identical store ID, sequence and entry digest, with every history entry
valid.** Empty history is the explicitly initialized sequence-zero state.
An extra complete line with stale markers is an error, not a committed prefix.
No existing history entry is overwritten by the writer.

These are separate writes, not a multi-file atomic transaction. Readers sharing
the lock avoid normal intermediate states; crashes can leave an inconsistent
state that later readers reject. Every cooperating writer must use this same
lock protocol. Neither POSIX advisory locks nor Windows range locks defend
against deletion/replacement of the root/lock file by a privileged writer.
No network filesystem, SMB, cloud-sync directory or distributed locking
guarantee is made.

`flush()` plus `os.fsync()` is requested for file content; Python maps Windows
fsync to `_commit()` ([Python os.fsync](https://docs.python.org/3/library/os.html#os.fsync)).
The prototype does not flush directory metadata or implement Windows volume/
hardware durability barriers. It cannot promise persistence across power loss,
controller/cache failure, or filesystem behavior beyond the OS calls. Successful
re-reading is a local consistency check, not a physical durability proof.

## Crash, recovery and acknowledgement rules

Partial JSONL, corrupt/truncated documents, missing files, complete extra entries,
head ahead of or behind history, checkpoint ahead/behind head or with a different
digest, failed history flush and failed marker publication all prevent a valid
store result. A lock failure also denies access. Effective statuses are empty on
any validation error; the reader never searches backward for an approved record.
Appends revalidate under the lock and reject the same ambiguous state.

There is no automatic truncation, repair, initialization of missing files, or
fallback to old approval. An operator must stop writers, preserve the damaged
root and diagnostic temporaries, compare independent checkpoints/backups and
complete signed chains, and explicitly authorize a separately reviewed recovery.
This checkpoint provides no recovery command. Do not delete a newer revocation
to make an older approval readable. If completeness cannot be established, keep
the store unavailable and require a new trusted review/recovery process.

If all three files have been published and match but the caller loses the return
value (or an error occurs after the last replacement), the entry is already
locally committed. A failed call is not proof of non-commit. Re-read complete
state before retrying; stale expected-head and duplicate-decision checks prevent
an unnoticed second append. No destructive rollback is attempted after failure.

## History, expiry and revocation

The reader checks every entry's digest/position/signature, global UUID/decision-ID
uniqueness and current registry key policy. A currently unknown, disabled or
revoked key makes the store fail closed, even if that key signed a past record.
An archived attestation's time bounds are checked at its declared signing time;
signing in the future relative to `now_utc` is rejected. This permits reading an
expired ancestor followed by a later valid revocation. It does not authenticate
the signing timestamp or prove the key's historical custody.

For each intent, the reader checks that each parent is the preceding decision in
global store order for that intent, then reuses the existing full-history
`validate_decisions()` checks: exactly one pending root, allowed transitions,
revision increments, parent ID/digest, timestamps and exact bindings. No newest
timestamp heuristic or branch selection is used. Latest attestation/decision
expiry is checked again at `now_utc` and reported separately. An expired latest
approval is an expired declaration, never current authorization. A later revoked
record makes the effective local review status `revoked`, never `approved`.

## Checkpoints, origin and residual rollback attacks

The local checkpoint must equal head on every read. It detects deleting a newest
revocation, reverting head, or changing a same-sequence digest **while the newer
checkpoint remains intact**. A separately retained `minimum_checkpoint` can also
detect rollback of all local files below that floor, or a fork at that sequence.
Older floors are accepted only if their digest matches the chain at their exact
sequence. The caller must retain/advance and protect this floor independently;
the Python object does not authenticate its own origin.

Without ACL isolation, an attacker can replace history, head and checkpoint with
an internally valid old snapshot. That whole-root rollback is not detectable
without an independent newer floor. Root path configuration, hashes, fsync and
valid signatures cannot prove store freshness, completeness outside the supplied
root, physical researcher identity, registry origin or human presence. Same-user
code can change files, configuration, callbacks, runtime or verifier code, and
can bypass this non-executing prototype. Symlink/reparse-point and root replacement
protection, registry custody, secure clock and Windows code/runtime isolation are
deployment responsibilities. No ACL installation or privilege escalation occurs.

## Validation result

`authorization_store_validation` schema V1 includes:

| Field | Meaning |
| --- | --- |
| `store_structurally_valid` | All required files/entry schemas parsed within bounds |
| `hash_chain_valid` | Configured store ID, continuous sequence, predecessor/digest chain |
| `head_consistent` | Head equals complete history EOF |
| `checkpoint_consistent` | Checkpoint equals head; supplied independent floor matches |
| `entries_signature_valid` | Every archived signature/binding passes current registry policy |
| `decision_history_valid` | All per-intent histories pass existing V1 semantics and global order |
| `local_store_valid` | All local checks completed successfully |
| `effective_review_status` | Map from intent digest to latest local review status; empty on failure |
| `effective_decision_ids` | Corresponding latest decision IDs; empty on failure |
| `effective_attestation_time_valid` | Latest attestation/decision time validity at caller's `now_utc` |
| `committed_head`, `checkpoint` | Detached validated markers; null on failure |
| `current_authorization_state` | Always `not_verified` |
| `store_origin_authenticated`, `registry_origin_authenticated` | Always false |
| `execution_eligible` | Always false |
| `reason_codes` | Failure code, or explicit unauthenticated-origin limitations on local success |

Earlier validation flags can remain true if a later stage fails; only
`local_store_valid` indicates completion of all local checks. Neither it nor an
`approved` status is an execution token or independently trusted authorization.

## Resource limits and verification scope

- Each entry/native document: at most 1 MiB of transport/canonical UTF-8 including
  LF; at most 32 nested dict/list containers, with root counted as one.
- Markers: at most 4 KiB each.
- Whole history: at most 16 MiB and 256 entries; this is a small review prototype,
  not an unbounded production ledger or retention/compaction implementation.
- Native copies share a canonical-byte budget to bound width, strings and cycles;
  decoder recursion exhaustion becomes an input validation error.
- Embedded attestations/registry retain their existing 64 KiB/16-depth limits.

Tests use temporary directories and ephemeral keys only. Failure tests edit
synthetic files or inject errors at append, flush, replacement and publication
boundaries. Lock contention is exercised with both competing threads/writers and
a separate Python process. These tests simulate interrupted states and lost
acknowledgements; they are not power-cut, filesystem-corruption, OS ACL or
hardware-durability qualification. Scientific inputs and golden vectors are
untouched; no Framework A/B/C/D computation or real approval is performed by
the store.
