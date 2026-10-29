# Signed authorization statement V1

Checkpoint 3B-2A implements a stateless signed contract. It does **not** implement
current human authorization, authoritative history, replay prevention, a signer
CLI, persistent key storage, Windows isolation, or Framework D execution.
Existing ExecutionIntent V1, DecisionRecord V1 and their digest algorithms remain
unchanged. DecisionRecord's `trusted_authorization_verification` remains
`not_verified`; verification does not rewrite the record.

## Interfaces

- `sign_attestation(intent, decision, *, private_key, reviewer_key_id,
  authorization_id, signed_at_utc, expires_at_utc=None, store=None)` requires an
  explicitly supplied `Ed25519PrivateKey` object. It never generates or loads keys.
- `verify_attestation(attestation, intent, decision, *, trusted_keys, now_utc)`
  accepts an immutable envelope, dictionary, or strict UTF-8 JSON text/bytes.
  `trusted_keys` must be an independently supplied `TrustedPublicKeyRegistryV1`.
- `canonical_payload_bytes(payload)` and `attestation_signing_bytes(payload)`
  expose the exact serialization and domain-separated bytes.
- `key_id_for_public_key(public_key)` fingerprints an Ed25519 public key.
- `AuthorizationAttestationV1` and `TrustedPublicKeyRegistryV1` provide
  `from_dict`, `from_json`, `to_dict`, `to_json`. Objects are frozen; dictionaries
  returned to callers are detached. This is not tamper resistance within a
  malicious Python process.

## Envelope and payload schema

The envelope has exactly two fields: `payload` (the object below) and
`signature_b64` (canonical padded standard Base64 of a 64-byte Ed25519 signature).
It cannot contain a public key or registry. Unknown fields are rejected.

| Payload field | V1 meaning |
| --- | --- |
| `authorization_type` | `scientific_execution_authorization_attestation` |
| `schema_version` | Integer `1`, not boolean or floating point |
| `algorithm` | `Ed25519` only |
| `canonical_profile` | `tec-authorization-json-utf8-lf-v1` |
| `execution_intent_digest` | Exact existing intent digest |
| `proposal_digest` | Exact proposal digest bound by both existing V1 objects |
| `decision_record_digest` | Exact existing decision digest |
| `decision_id`, `review_status`, `revision`, `supersedes` | Exact V1 decision fields; supersession is null or `{decision_id, decision_digest}` |
| `reviewer_key_id` | Lowercase SHA-256 fingerprint of raw 32-byte Ed25519 public key |
| `reviewer_identity` | Exact decision reviewer identity declaration, without normalization |
| `key_purpose` | `scientific_review_decision` |
| `signed_at_utc` | Canonical explicit UTC ISO timestamp ending `Z`, not earlier than decision time |
| `expires_at_utc` | Null or canonical UTC strictly after signing; cannot extend decision expiry |
| `authorization_scope` | Exact scope text from ExecutionIntent, not a precursor/causality finding |
| `store` | Reserved declaration `{store_id, sequence, previous_entry_digest}` |
| `authorization_id` | Caller-supplied canonical lowercase UUIDv4; uniqueness is not verified |

Null expiry inherits the decision expiry when present. If neither supplies an
expiry it remains null; this is **not** a freshness guarantee. Evaluation uses
exclusive expiry (`now >= expiry` is expired). Signing time and `now_utc` are
declarations, not independently authenticated timestamps or trusted clock data.
Old V1 UTC representations are read without rewriting their objects; the new
attestation timestamps use canonical `datetime.isoformat()` UTC with `Z`.

Store fields are either all null (unassigned), or a UUIDv4 `store_id`, integer
`sequence >= 1`, and a previous digest that is null exactly at sequence 1.
For later sequences it is a lowercase SHA-256 digest. These constraints check
only one statement's internal form. No store is read, no sequence allocated,
and no latest head or uniqueness is verified. Multiple correctly signed
statements can claim the same authorization ID or position; detection requires
the future authoritative store. Changing an ID without a new valid signature
is rejected cryptographically. Well-formed re-signing cannot prove uniqueness.

## Canonical bytes and domain separation

The profile uses `json.dumps(..., ensure_ascii=False, allow_nan=False,
sort_keys=True, separators=(",", ":"))`, one trailing LF, and strict UTF-8
without BOM. No Unicode normalization is performed. JSON-native integers must
be nonnegative and at most `2**53-1`; floats are not supported. Schema types
further restrict values (booleans are used only for registry policy flags).
Duplicate keys, lone Unicode surrogates, nonfinite numbers, float/exponent
number encodings, `-0`, and noncanonical signature/public-key Base64 encodings
are rejected. UTF-16/32 and BOM transport are unsupported. Transport JSON may
vary in whitespace, key order, and valid Unicode escapes; the parsed payload
is always re-encoded to the same signing bytes.

This format is **not RFC 8785 JCS**. It does not replace or reinterpret any
existing V1 serialization. Standard Ed25519 signs these bytes directly:

```python
b"ionospheric-tec/authorization-attestation/v1\x00" + canonical_payload_bytes
```

This is an application message prefix, not a custom Ed25519ctx implementation.
Base64 is standard `A-Z a-z 0-9 + /` with required padding; whitespace, URL-safe
alternatives, extra padding and nonzero padding bits are rejected by decoding
and requiring exact standard re-encoding.

### Input resource limits

The shared attestation/registry JSON codec accepts at most **64 KiB (65,536
bytes)** of UTF-8 transport, and at most 64 KiB of canonical JSON including its
final LF. It accepts at most **16 nested object/array containers**, counting the
root as one. These are input-processing limits, not scientific thresholds or a
new serialization profile. Accepted V1 signing bytes and the vectors below are
unchanged. Whitespace-heavy transport is also subject to the transport bound.

Dictionary/list copying shares an exact canonical-size budget, including JSON
escaping, UTF-8, punctuation and LF. Oversized strings and wide collections are
bounded; excessive nesting and cycles are rejected without following them to
Python's recursion limit. JSON decoder/encoder recursion exhaustion becomes an
input `ValueError`, which the existing verification parse boundary reports as
`invalid_attestation`. Its structural-validity, signature-verification-passed
and execution-eligibility flags remain false. The initial attestation parse
boundary also handles any residual `RecursionError` from its parsing calls.
No general exception handler is
added around cryptographic verification; unrelated programming errors propagate.

These limits bound this codec's traversal/copying, not the memory already used
by a caller to construct input or total host-process resource consumption.
They do not authenticate store position, history, identity or current approval.

## Independent public-key registry contract

```text
{
  registry_type: "trusted_reviewer_public_keys",
  schema_version: 1,
  entries: [{
    key_id, public_key_b64, reviewer_identity, purpose, enabled, revoked
  }]
}
```

`public_key_b64` encodes the raw 32-byte Ed25519 public key, and its SHA-256 must
equal `key_id`. Duplicate IDs are rejected. Identity and purpose are nonempty
text; enabled/revoked are exact booleans. Registries may include keys for other
purposes, but only enabled, nonrevoked keys with purpose
`scientific_review_decision` and the exact signed reviewer identity pass policy.
Empty registries cannot verify any registered reviewer signature.

The registry is a **caller-supplied trust anchor**, not an OS-authenticated
registry. The enclosing verifier must eventually obtain it outside the Agent's
control. If an attacker controls both the registry and signer, they can satisfy
these local signature checks; that is not independent human authorization.
No attached key is automatically registered, and there is no trust/authorized/
skip-verification switch. Persistent registration and ACLs are out of scope.

## Verification levels

The result separates:

1. `attestation_structurally_valid` from existing-contract and binding validity.
2. `signature_checked` and `cryptographic_signature_valid`. Unknown keys are not
   checked; a known revoked key can still have a mathematically valid signature.
3. `key_registered`, `key_policy_valid`, `registered_trusted_reviewer_signature`.
   The last flag additionally requires the exact V1-object bindings to match.
4. `attestation_time_valid`, evaluated at the explicitly supplied `now_utc`.
5. `signature_verification_passed`, the conjunction of those local checks.

Even success preserves `current_authorization_state`, `decision_history_state`,
`store_state` and `authorization_id_uniqueness` as `not_verified` and always sets
`execution_eligible=False`. `registry_origin_state` states that its origin was
not authenticated here. Review status `approved` is simply signed content.
Supersession is bound to the supplied decision, but the complete parent chain
is not loaded or checked. Source files and the full original proposal are not
opened or authenticated. Existing `validate_decisions()` remains fail closed.

## Serialization test vector (unsigned, synthetic)

This is a public format vector, not research evidence, a registered key, or a
signed approval. All repeated digests are placeholders. No private key exists
in the vector. Apply the canonical profile to this payload:

```json
{
  "authorization_type": "scientific_execution_authorization_attestation",
  "schema_version": 1,
  "algorithm": "Ed25519",
  "canonical_profile": "tec-authorization-json-utf8-lf-v1",
  "execution_intent_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "proposal_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "decision_record_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "decision_id": "synthetic-vector",
  "review_status": "pending_review",
  "revision": 0,
  "supersedes": null,
  "reviewer_key_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "reviewer_identity": "合成審查者",
  "key_purpose": "scientific_review_decision",
  "signed_at_utc": "2001-01-01T00:00:00Z",
  "expires_at_utc": null,
  "authorization_scope": "Only the bound spatial analysis; no causality or earthquake precursor identification is authorized.",
  "store": {"store_id": null, "sequence": null, "previous_entry_digest": null},
  "authorization_id": "11111111-1111-4111-8111-111111111111"
}
```

- Canonical payload length (including LF): `1016` bytes.
- Payload SHA-256: `b4919e85b3cfe33473877d8e019b53b1c6cf93dcc2402b7738620e78fecd45f0`.
- Domain-prefixed signing bytes SHA-256: `9614f4ac2c7d0f586faaf98e819b7324d02b23b2fad6264f516d9bde0154b38a`.

The focused tests also sign the same payload twice with the same ephemeral
in-memory key and compare signatures. Keys are generated only within synthetic tests;
no private key bytes, PEM, real reviewer credentials or persistent registry are
committed. This vector does not prescribe a permanent cryptographic test key.

## Optional dependency

Install `requirements-authorization.txt` into the project virtual environment.
It pins `cryptography==50.0.2`, tested with Python 3.10.6 on Windows x64. The
scientific requirements are unchanged. Missing crypto support is an explicit
dependency/import error, never a successful signature check or crypto fallback.
