# Local authorization verification V1 — demonstration only

Checkpoint 3B-2C-1 composes the existing review contracts, Ed25519 verifier and
complete decision-store reader. It determines the local review state for one
exact ExecutionIntent digest. It **does not authenticate a Windows deployment,
prove human presence, grant execution, or invoke Framework D**. A shared Windows
account remains DEMONSTRATION ONLY, even with matching content pins and signatures.

## Fixed interface and bootstrap

```python
verifier = LocalAuthorizationVerifier(
    RESEARCHER_CONFIG_PATH,
    expected_config_sha256=INDEPENDENTLY_PUBLISHED_CONFIG_SHA256,
)
result = verifier.verify(execution_intent_digest)
```

The constructor belongs to a trusted-side deployment/bootstrap, not an Agent API.
Its path is absolute/local and its SHA-256 pin is explicitly supplied; the verifier
does not compute a first-use pin, register keys or discover alternative roots.
The ordinary Python constructor and its arguments do not authenticate themselves.
The expected configuration pin must eventually be protected with the bootstrap
and code, independently of Agent-controlled input. Controlling both a file and
its pin is not source authentication.

Queries accept only a lowercase 64-character intent digest. No per-query paths,
decision subsets, keys, external flags, alternate clock or approval override are
accepted. There is no CLI, key generation, signing, persistence or recovery API.
An invalid bootstrap argument raises a type/value error; unavailable or malformed
configured files produce a structured non-authorizing query result. There is no
cached approved-state fallback after a source becomes unavailable.

## Strict configuration V1

`VerifierConfigurationV1` supports `from_dict/from_json/to_dict/to_json`. It stores
frozen canonical JSON and returns detached copies. Its fields are declarations,
not verified Windows properties. The exact schema is:

```text
{
  configuration_type: "local_authorization_verifier_configuration",
  schema_version: 1,
  configuration_id: canonical UUIDv4,
  store: {store_id: canonical UUIDv4, root: absolute local directory},
  registry: {path: absolute local file, sha256: SHA256 of exact file bytes},
  minimum_checkpoint: {
    path: absolute local file,
    sha256: SHA256 of exact file bytes,
    sequence: nonnegative safe integer,
    entry_digest: null at zero, otherwise lowercase SHA256
  },
  deployment: {
    deployment_id: canonical UUIDv4,
    verifier_code_sha256: declared release/code artifact SHA256,
    dependency_manifest_sha256: declared dependency artifact/manifest SHA256,
    isolation_requirement: "separate_windows_security_identities"
  },
  expected_authorization_scope: exact unchanged ExecutionIntent V1 scope,
  time_source: "local_system_utc_unverified"
}
```

The scope remains:

```text
Only the bound spatial analysis; no causality or earthquake precursor identification is authorized.
```

UUIDs are lowercase canonical UUIDv4; digests are lowercase SHA-256. Sequence is
an exact integer, excluding bool/float. Unknown/missing fields, duplicate keys,
invalid Unicode/BOM, unsupported versions, floats, unsafe integers, nonfinite
JSON and claimed trust flags are rejected using the existing bounded signed-JSON
codec. Configuration transport/canonical content is limited to 16 KiB and the
codec's 16-container depth. Registry retains 64 KiB/16-depth limits; the external
checkpoint is bounded to 4 KiB and retains StoreCheckpointV1 validation. Existing
store history limits remain unchanged. Pins cover **raw file bytes**, including
whitespace, not only equivalent parsed content. No digest/signing format changes.

The code/dependency pins are deployment declarations, not measurements of the
running interpreter, imports or memory. Matching config/registry/checkpoint pins
cannot authenticate the pin's publisher. V1 has no `trust=True`, ACL-verified or
production-mode setting; the isolation requirement states what deployment must
provide, not what this process has established.

## Source acquisition and current review state

For each query the verifier:

1. Reads the fixed configuration as a bounded regular UTF-8 file and matches its
   independently declared bootstrap pin, then validates the strict schema.
2. Resolves the configured source locations. Configuration, registry and external
   checkpoint must be outside the store and distinct. Existing-file identity
   checks reject hard-link aliases to mutable store files or each other. There is
   no fallback to `store/checkpoint.json`, filename inference or Agent attachment.
3. Reads/pin-checks/parses the configured registry snapshot and external checkpoint.
   The latter must match configured store ID, expected sequence and entry digest.
4. Samples system UTC once, then calls `AuthorizationStore.validate()` with the
   required external floor. That existing public method locks and reads the full
   history, verifies signatures/bindings/chain and validates every intent lineage.
5. Rechecks the three fixed source pins after store validation to detect observed
   replacements. It then selects only the exact requested digest from the validated
   result, never a similar UTC window, case name or caller-supplied record subset.
6. Reports the effective status, latest decision ID and current attestation/decision
   time validity. Scientific proposal/intent consistency and scope consistency
   derive from the existing full-store V1 validation, which enforces the fixed
   scope. This is not independent authentication of original research data.

The existing reader now opens an **existing** permanent lock file with `r+b` during
validation instead of creating it with `a+b`. Missing lock fails closed and is
not repaired. This is the only store implementation correction: no V1 schemas,
digest algorithms, history/status rules or writer allocation/publication change.
It requires lock-file read/write access for locking, but writes no lock bytes,
history, markers, configuration or registry. OS-managed access metadata is not
an application history mutation. Store initialization/writing remain separate.

`approved` plus valid time becomes local state `approved_unverified`; it never
becomes permission. Expired approval becomes `expired_approval`. Pending, rejected,
revision-requested and revoked histories keep their non-authorizing statuses.
A later revocation wins through full lineage validation, never through newest
timestamp selection. Corruption, conflicting chains/signatures or incomplete
publication exposes no selected decision/status, never an older approved fallback.
An absent digest is distinguished from an invalid store.

## Result V1

`result_type="local_authorization_verification"`, integer `schema_version=1`:

| Fields | Meaning |
| --- | --- |
| `requested_execution_intent_digest` | Exact validated request, null for malformed input |
| `configuration_valid`, `registry_valid`, `independent_checkpoint_valid` | Parsed source shape/declared position validity |
| `configuration_content_matches_pin`, `registry_content_matches_pin`, `independent_checkpoint_content_matches_pin` | Exact byte identity relative to supplied declarations, not origin proof |
| `store_structurally_valid`, `hash_chain_valid`, `head_consistent`, `checkpoint_consistent`, `entries_signature_valid`, `decision_history_valid` | Existing store validation stages; earlier stages may succeed before a later failure |
| `local_store_valid` | Full local store and source-snapshot checks completed |
| `checkpoint_matches_store` | External floor is present in the validated chain |
| `checkpoint_is_current_head` | Floor position equals the validated head, not proof of global freshness |
| `requested_intent_present`, `proposal_intent_consistent`, `authorization_scope_consistent` | Exact requested intent exists and passes existing V1 consistency/scope rules |
| `effective_review_status`, `effective_decision_id` | Latest local declaration for that exact intent, null when unavailable/invalid/absent |
| `latest_attestation_time_valid` | Latest attestation/decision valid at sampled system UTC; null if not evaluated |
| `local_review_state` | `approved_unverified`, `expired_approval`, non-approved status, `intent_not_found`, or `not_evaluated` |
| `evaluation_time_utc`, `time_source` | Evaluation snapshot and `local_system_utc_unverified` |
| `deployment_mode` | Always `demonstration_only` |
| `trusted_configuration_origin_verified`, `trusted_registry_origin_verified`, `trusted_store_origin_verified`, `independent_checkpoint_verified` | Always false; local file/pin checks cannot establish authenticated origin/protection |
| `deployment_isolation_verified`, `verifier_deployment_identity_verified`, `authoritative_freshness_verified`, `trusted_time_verified` | Always false; no OS/runtime/freshness/secure-time boundary is implemented |
| `trusted_human_authorization` | Always false; signatures alone do not establish human presence or authenticated provenance |
| `current_authorization_state`, `execution_eligible` | Always `not_verified` and false |
| `reason_codes`, `store_reason_codes` | Distinguish unavailable sources, pin/schema mismatch, store failures, missing intent, review status and unverified deployment limits |

Local integrity, signed statements, human authorization and execution eligibility
are separate assertions. No higher trust flags from a store dictionary are
copied into the result. Unexpected programming errors are not broadly suppressed.

## Checkpoint publication and rollback limits

The external checkpoint is a mandatory retained **minimum**, not a trusted clock
or assertion of latest history. An older matching floor is accepted by the
unchanged store validator and reported as `checkpoint_is_only_lower_bound` when
head is ahead. A retained newer checkpoint detects whole-store rollback below
that floor; a conflicting digest at the same sequence detects a fork.

It cannot detect a rollback to a point at/above an old floor that hides a newer,
unwitnessed revocation. Even equal floor/head does not prove that no newer history
has been withheld. All freshness/authenticated-authorization flags therefore stay
false. If the adversary can roll back the external checkpoint, configuration and
bootstrap pin together, content checks cannot establish anti-rollback freshness.

Future trusted-side publication must deliberately retain/advance the floor after
validated commits, publish new pinned configuration/bootstrap metadata, prevent
lowering or replacing them, and document recovery after interrupted publication.
This verifier never copies or updates a checkpoint automatically. Missing,
changed or malformed retained files deny evaluation instead of using a local
marker. Source reads are snapshots; post-read checks do not defeat malicious
swap-and-restore, root replacement, reparse races or changes after verification.
OS isolation and handle-based source acquisition still require separate review.

## Windows deployment architecture — manual review plan, NOT performed

The initial protection model excludes administrators, SYSTEM-equivalent attackers,
kernel compromise and hardware/backup authorities able to replace the complete
protected deployment. It targets a malicious **unprivileged Agent SID**, separate
from a researcher-controlled trusted SID. A second process/folder under the same
SID provides no independent boundary. Standard process creation under the current
user is insufficient; check the actual local primary token. In particular,
`LOGON_NETCREDENTIALS_ONLY` retains the caller's local token and is unsuitable for
local identity separation ([Microsoft process-token documentation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createprocesswithlogonw)).

Proposed manually reviewed layout/rights, on local NTFS:

| Resource | Trusted side | Unprivileged Agent |
| --- | --- | --- |
| Interpreter, installed verifier/package dependencies, bootstrap and configuration | Controlled deployment/update; normal run read/execute | Cannot write, replace, change DACL/owner or redirect imports |
| Registry and independent retained checkpoint, including protected parents | Controlled read/update and monotonic publication | Cannot modify, delete, replace or roll back |
| Store root/history/head/local checkpoint | Writer append/publication; verifier read/lock | No authoritative write/delete/replacement rights |
| Permanent lock file | Reader/writer lock access; no routine replacement | No write/delete/replacement rights |
| Signer private-key capability | Researcher-controlled signer only; verifier does not need it | No key access or arbitrary signing endpoint |
| Agent proposals/requests | Treated as untrusted digest-addressed input | Can propose; cannot supply authority files or executable trusted code |

Review effective NTFS DACLs, inheritance and ownership on **every protected file
and parent**. File read-only attributes, absolute paths or ownership by the current
user do not prove protection. Check write, append, delete, parent delete-child,
rename/replacement, WRITE_DAC/WRITE_OWNER and privileged group memberships. The
Agent must not own protected objects or control their parent directories. ACL
decisions concern actual token trustees, not a display name ([Microsoft ACL model](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-lists)).
Ownership can confer DACL control; review it independently of current read/write
access ([Microsoft object ownership](https://learn.microsoft.com/en-us/windows/win32/secauthz/owner-of-a-new-object)).

Check ancestors, junctions, mount points, symbolic links, hard links and other
reparse redirection. A protected leaf in an Agent-replaceable parent is inadequate.
Path resolution and `samefile()` here reject obvious aliases but are not an atomic
trusted-open primitive ([Microsoft reparse-point behavior](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points)).

Install reviewed code and a fixed interpreter/dependency environment outside the
Agent workspace. Record release artifact hashes and actual imported module/DLL
locations. Review startup environment, working directory, PATH/DLL search,
PYTHONPATH/PYTHONHOME, user site packages, `.pth`/sitecustomize hooks and writable
virtual-environment directories. Python `-I` removes script/current and user-site
paths and ignores PYTHON* variables; it does not protect a writable interpreter,
installed site packages or system hooks. A reviewed installed package/bootstrap
is needed; do not append the Agent repo to sys.path to make isolated launch work
([Python 3.10 isolated mode](https://docs.python.org/3.10/using/cmdline.html#cmdoption-I)).

Manually execute and retain evidence for Checkpoint 3B-2C-2:

1. Record both actual local process SIDs, token groups/integrity/elevation and
   effective privileges (`whoami /user`, `whoami /groups`, `whoami /priv` are
   read-only inspection examples). Confirm alternate-user launch changes the local
   token, not merely network credentials. Do not record credentials in commands.
2. Review `Get-Acl`/`icacls` output and ownership for files/ancestors, including
   inherited write/delete rights and replacement paths. Approve intended rights
   manually before any ACL changes in the separate deployment checkpoint.
3. Under the real Agent token, attempt creating/replacing/deleting/renaming
   authoritative files and their parents, lowering checkpoints, replacing the
   config/bootstrap pin, changing DACL/owner, and linking/junction redirection.
   Required outcome: denial without altering protected original bytes. Use
   sacrificial deployment copies and compare hashes, never research artifacts.
4. Under the trusted token, verify only the intended signer/store writer can
   sign/publish; confirm reader locking succeeds on the existing lock without
   directory creation rights. A verifier does not need signer access; missing
   signer must not trigger key creation or substitute unsigned approval.
5. Plant fake modules, `.pth`/startup hooks and DLL candidates in Agent-writable
   locations; verify trusted startup/imports do not load them. Test protected code,
   interpreter/dependencies, environment and parent directories together.
6. Inject revoked/latest-corrupt histories, checkpoint/root rollback and source
   unavailability; confirm no previous approved fallback. Audit backup restoration
   and independent checkpoint/config-pin monotonicity separately from live DACLs.
7. Test clock rollback/forward, time-service configuration and decision expiry.
   Local UTC is not a cryptographically trusted clock; this implementation offers
   no time rollback protection. Retain explicit time-source limitations.
8. Test concurrent writer contention and denial of service (lock held, full disk,
   missing source, denied access). Availability failure must deny authorization;
   it must not enable a bypass, automatic repair or alternate authority root.

These tests have **not** been executed under separate Windows accounts in this
checkpoint. Temporary-file tests, mocked reads and matching hashes are not SID,
DACL, owner, code-custody or trusted-human-presence evidence. No account creation,
ACL modification, privilege escalation or persistent signer provisioning occurs.

## Future runner responsibilities and scientific limits

A future controlled Framework D runner must independently authenticate deployment,
registry/store/checkpoint provenance, exact current intent/proposal and scientific
input bindings, latest revocation/expiry and trusted time, then revalidate at the
protected execution boundary. It must address check-to-execution races and any
one-time-use semantics, restrict output/input access and executable code, and keep
the researcher in authority. A JSON result from this verifier is not a bearer
token, execution grant or durable authorization; old Stage 2 entry points remain
unchanged and are not gated by this prototype.

No original TEC/catalog data, source hashes, detector thresholds, historical
anchors, UTC windows, scientific causality or precursor interpretation are
revalidated or changed. Synthetic test decisions are not real research approvals.
