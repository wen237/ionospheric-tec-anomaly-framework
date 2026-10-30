"""C2 declarations and a NON-EXECUTING E1 plan, independent of layout V1.

Pure standard-library data processing; no OS inspection, file acquisition,
AccessCheck, SDDL generation, keys, Store, probes, provisioning or dispatcher.
The shared V1 bounded JSON/scalar validators are reused WITHOUT changing V1.
Every E1 case remains NOT_RUN; complete declarations never authorize deployment.
See docs/c2_lock_acceptance.md for evidence requirements and approval gates.
"""

from dataclasses import dataclass
import hashlib
import json
import ntpath
import re
from uuid import UUID

from .windows_isolation_acceptance import (
    ACCEPTANCE_PARENT, _canonical, _fields, _hash, _load, _path, _pid, _sid,
)


SPECIFICATION_TYPE = "c2_lock_namespace_acceptance_specification"
LAYOUT_VERSION = "c2_separate_coordination_v1"
READ, READ_EXECUTE, READ_WRITE = 0x120089, 0x1200A9, 0x12019F
TRAVERSE, DELETE, FULL, OWNER_RC = 0x20, 0x10000, 0x1F01FF, 0x20000
# Relative paths are fixed; only validated UUIDs may be substituted.
C2_LAYOUT = {
    "root": ("", "directory", "container"),
    "authority": ("authority", "directory", "container"),
    "data_store": (r"authority\store", "directory", "data"),
    "history": (r"authority\store\history.jsonl", "file", "history"),
    "head": (r"authority\store\head.json", "file", "marker"),
    "local_checkpoint": (r"authority\store\checkpoint.json", "file", "marker"),
    "publication_temporary": (r"authority\store\e1-publication.tmp", "file", "marker"),
    "coordination": (r"authority\coordination", "directory", "container"),
    "lock_parent": (r"authority\coordination\{store_id}", "directory", "container"),
    "history_lock": (r"authority\coordination\{store_id}\history.lock", "file", "lock"),
    "release": ("release", "directory", "container"),
    "runtime": (r"release\runtime", "directory", "container"),
    "python_executable": (r"release\runtime\python.exe", "file", "code"),
    "application": (r"release\app", "directory", "container"),
    "dependencies": (r"release\deps", "directory", "container"),
    "anchors": ("anchors", "directory", "container"),
    "registry": (r"anchors\registry.json", "file", "anchor"),
    "configuration": (r"anchors\verifier.json", "file", "anchor"),
    "independent_checkpoint": (r"anchors\minimum-checkpoint.json", "file", "anchor"),
    "bootstrap_directory": ("bootstrap", "directory", "container"),
    "bootstrap": (r"bootstrap\manifest.json", "file", "anchor"),
    **{f"control_{role}": (rf"e1-control-{role}", "directory", f"control_{role}") for role in "AWV"},
    **{f"control_source_{role}": (rf"e1-control-{role}\source.tmp", "file", f"source_{role}") for role in "AWV"},
}
IDENTITY_KEYS = ("acceptance_parent", "root", "authority", "data_store", "coordination", "lock_parent", "history_lock")
IDENTITY_FIELDS = ("resolved_path", "volume_guid", "volume_serial", "file_id", "owner_sid", "sddl")
ARTIFACT_KEYS = ("runtime", "application", "dependencies", "bootstrap", "configuration", "registry", "independent_checkpoint")
DIRECTORY_CHECKS = {"FILE_ADD_FILE": 0x2, "FILE_ADD_SUBDIRECTORY": 0x4,
                    "DELETE_CHILD": 0x40, "DELETE": DELETE, "WRITE_DAC": 0x40000, "WRITE_OWNER": 0x80000}
FILE_CHECKS = {"READ_DATA": 0x1, "WRITE_DATA": 0x2, "APPEND_DATA": 0x4,
               "WRITE_EA": 0x10, "EXECUTE": 0x20, "WRITE_ATTRIBUTES": 0x100,
               "DELETE": DELETE, "WRITE_DAC": 0x40000, "WRITE_OWNER": 0x80000}
BLOCKERS = (
    "independent_sacrificial_deployment_approval_missing",
    "all_agent_and_WVM_primary_tokens_not_established",
    "native_ancestor_owner_DACL_and_identity_not_established",
    "protected_runtime_artifact_origin_and_pin_custody_not_verified",
    "native_probe_controls_and_evidence_collector_not_implemented",
    "no_follow_handle_identity_protocol_not_implemented",
    "lock_RW_reparse_and_hardlink_capabilities_unresolved",
    "cross_process_role_locking_not_observed",
    "existing_Store_and_Inspector_V1_do_not_implement_C2",
    "all_E1_native_cases_not_run",
)
APPROVAL_CHECKLIST = (
    "Exact fresh RunId/store_id/root; no reuse of repository, .venv, profile, production or unknown existing targets.",
    "Independent full A host/worker SID and W/V/M separation, token/group/privilege/session review; no RID inference.",
    "Resolved local NTFS volume/file identities, all ancestors, owner/exact observed SDDL and no reparse/alias; no global ancestor ACL changes.",
    "Per-resource before/after policies, exact synthetic fixture bytes/names and control-source rights; no keys or V1 Store initialization.",
    "Separately reviewed native probe/collector, per-bit rights, caller primary token, controls, API flags and raw errors; no arbitrary paths/commands.",
    "Explicit approval of destructive attempts, quiesced M-only missing-lock injection, reparse/hardlink cases and cross-process schedule.",
    "Protected code/runtime/DLL/import paths and independently retained manifest/pins/evidence; hash equality is not researcher authentication.",
    "STOP/NO_GO on unexpected success, inconclusive failure, token/identity/policy drift or unavailable evidence; no retries, repair, rollback or auto cleanup.",
    "M containment/retention and separately approved retirement; E1 results never grant human authorization or Framework execution.",
)


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value or UUID(value).version != 4:
        raise ValueError("Expected canonical UUIDv4 declaration.")


def _paths(data):
    root = data["deployment_root"]
    return {"volume_root": "C:\\", "program_data": r"C:\ProgramData", "acceptance_parent": ACCEPTANCE_PARENT,
            **{key: ntpath.join(root, relative.format(store_id=data["store_id"])) if relative else root
               for key, (relative, _, _) in C2_LAYOUT.items()}}


@dataclass(frozen=True)
class C2AcceptanceSpecificationV1:
    """Strict immutable C2 declarations; not V1 layout or an approval artifact.

    JSON uses the existing 64-KiB/16-container strict codec. Unknown baselines
    remain null. Raw SDDL may be declared for later comparison, never generated,
    interpreted as effective access, or applied. Invalid input raises ValueError.
    """
    _json: str

    def __post_init__(self):
        data = _load(self._json)
        _fields(data, ("specification_type", "schema_version", "layout_version", "purpose", "run_id",
                       "store_id", "deployment_root", "roles", "identity_expectations", "artifact_sha256"))
        if (data["specification_type"] != SPECIFICATION_TYPE or type(data["schema_version"]) is not int or
                data["schema_version"] != 1 or data["layout_version"] != LAYOUT_VERSION or
                data["purpose"] != "synthetic_E1_only"):
            raise ValueError("Unsupported C2 specification or layout version.")
        _uuid(data["run_id"])
        _uuid(data["store_id"])
        if _path(data["deployment_root"]) != _path(ntpath.join(ACCEPTANCE_PARENT, data["run_id"])):
            raise ValueError("C2 requires the fixed acceptance parent and exact RunId.")
        roles = data["roles"]
        _fields(roles, "AWVM")
        seen_sids, seen_pids = set(), set()
        for role, assignment in roles.items():
            _fields(assignment, ("sids", "pids") if role == "A" else ("sid", "pids"))
            sids = assignment["sids"] if role == "A" else ([] if assignment["sid"] is None else [assignment["sid"]])
            if type(sids) is not list or len(sids) > 32:
                raise ValueError("Expected bounded full SID assignments.")
            for sid in sids:
                _sid(sid)
                if sid in seen_sids:
                    raise ValueError("All role SIDs, including every Agent SID, must be distinct.")
                seen_sids.add(sid)
            if type(assignment["pids"]) is not list or len(assignment["pids"]) > 8:
                raise ValueError("Expected bounded explicit PID declarations.")
            for pid in assignment["pids"]:
                _pid(pid)
                if pid in seen_pids:
                    raise ValueError("Duplicate or cross-role PID.")
                seen_pids.add(pid)
        paths = _paths(data)
        _fields(data["identity_expectations"], IDENTITY_KEYS)
        identities = set()
        volumes, serials = set(), set()
        for key, expected in data["identity_expectations"].items():
            _fields(expected, IDENTITY_FIELDS)
            if expected["resolved_path"] is not None and _path(expected["resolved_path"]) != _path(paths[key]):
                raise ValueError("Unexpected resolved C2 identity path; no V1 lock fallback.")
            for field, pattern in (("volume_guid", r"\\\\\?\\Volume\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}\\"),
                                   ("volume_serial", r"[0-9a-f]{8}"), ("file_id", r"[0-9a-f]{16}")):
                if expected[field] is not None and (type(expected[field]) is not str or not re.fullmatch(pattern, expected[field])):
                    raise ValueError("Malformed physical identity declaration.")
            if expected["owner_sid"] is not None:
                _sid(expected["owner_sid"])
                if expected["owner_sid"] in roles["A"]["sids"]:
                    raise ValueError("Agent ownership of protected namespaces is unsupported.")
                if roles["M"]["sid"] is not None and expected["owner_sid"] != roles["M"]["sid"]:
                    raise ValueError("Immutable C2 namespace/lock owner must match the declared M SID.")
            if expected["sddl"] is not None and (type(expected["sddl"]) is not str or not expected["sddl"] or len(expected["sddl"]) > 32768):
                raise ValueError("Expected bounded observed SDDL declaration or null.")
            if expected["volume_guid"] is not None and expected["file_id"] is not None:
                identity = expected["volume_guid"].lower(), expected["file_id"]
                if identity in identities:
                    raise ValueError("Declared namespace/lock file identities alias.")
                identities.add(identity)
            if expected["volume_guid"] is not None:
                volumes.add(expected["volume_guid"].lower())
            if expected["volume_serial"] is not None:
                serials.add(expected["volume_serial"])
        if len(volumes) > 1 or len(serials) > 1:
            raise ValueError("C2 E1 requires one independently verified local NTFS volume.")
        _fields(data["artifact_sha256"], ARTIFACT_KEYS)
        for digest in data["artifact_sha256"].values():
            if digest is not None:
                _hash(digest)
        object.__setattr__(self, "_json", _canonical(data))

    @classmethod
    def from_dict(cls, data):
        return cls(_canonical(data))

    @classmethod
    def from_json(cls, raw):
        return cls(raw)

    def to_dict(self):
        return json.loads(self._json)

    def to_json(self):
        return self._json

    def paths(self):
        return _paths(self.to_dict())

    @property
    def content_sha256(self):
        return hashlib.sha256(self._json.encode("utf-8")).hexdigest()


def build_c2_acceptance_specification(run_id, store_id) -> C2AcceptanceSpecificationV1:
    """Pure incomplete template; no RunId generation, probing or deployment."""
    _uuid(run_id)
    _uuid(store_id)
    return C2AcceptanceSpecificationV1.from_dict(dict(
        specification_type=SPECIFICATION_TYPE, schema_version=1, layout_version=LAYOUT_VERSION,
        purpose="synthetic_E1_only", run_id=run_id, store_id=store_id,
        deployment_root=ntpath.join(ACCEPTANCE_PARENT, run_id),
        roles={"A": dict(sids=[], pids=[]), **{role: dict(sid=None, pids=[]) for role in "WVM"}},
        identity_expectations={key: dict.fromkeys(IDENTITY_FIELDS) for key in IDENTITY_KEYS},
        artifact_sha256=dict.fromkeys(ARTIFACT_KEYS),
    ))


def build_c2_e1_plan(specification) -> dict:
    """Return proposed rights/cases only. NEVER ingest results or assign PASS.

    The plan does not authenticate a supplied SID, PID, SDDL, digest or approval.
    No clause, switch or complete declaration can enable an operation. Numerical
    masks are intent, not computed effective access or automatically emitted ACEs.
    """
    if isinstance(specification, C2AcceptanceSpecificationV1):
        spec = C2AcceptanceSpecificationV1.from_json(specification.to_json())
    elif type(specification) is dict:
        spec = C2AcceptanceSpecificationV1.from_dict(specification)
    else:
        spec = C2AcceptanceSpecificationV1.from_json(specification)
    data, paths = spec.to_dict(), spec.paths()
    matrix = {}
    for key, (_, kind, profile) in C2_LAYOUT.items():
        access = {"A": TRAVERSE, "W": READ_EXECUTE, "V": READ_EXECUTE} if kind == "directory" else {"A": 0, "W": READ, "V": READ}
        if profile == "data":
            access["W"] |= 0x2
        elif profile in ("history", "marker", "lock"):
            access["W"] = READ_WRITE | (DELETE if profile == "marker" else 0)
            if profile == "lock":
                access["V"] = READ_WRITE
        elif profile == "code":
            access.update(W=READ_EXECUTE, V=READ_EXECUTE)
        elif profile.startswith("control_"):
            access = dict.fromkeys("AWV", TRAVERSE)
            access[profile[-1]] = READ_EXECUTE | 0x2
        elif profile.startswith("source_"):
            access = dict.fromkeys("AWV", 0)
            access[profile[-1]] = READ_WRITE | DELETE
        checks = DIRECTORY_CHECKS if kind == "directory" else FILE_CHECKS
        matrix[key] = dict(path=paths[key], object_type=kind, policy_id=profile,
            owner_role="W_AFTER_CREATION_OR_REPLACEMENT" if profile == "marker" else "M",
            proposed_allow_masks={**access, "M": FULL, "SYSTEM": FULL},
            required_individual_denials={role: {name: mask for name, mask in checks.items() if not access[role] & mask} for role in "AWV"},
            protected_dacl=profile != "marker", owner_rights_sid="S-1-3-4", owner_rights_mask=OWNER_RC,
            file_policy_source="REVIEWED_DATA_FILE_INHERITANCE" if profile == "marker" else "EXPLICIT_PROTECTED_PER_RESOURCE_POLICY",
            lock_RW_exception=(profile == "lock"), actual_effective_access="UNKNOWN", actual_sddl=None)
        if kind == "directory":
            child = {"M": FULL, "SYSTEM": FULL, "OWNER_RIGHTS": OWNER_RC}
            if profile == "data":
                child.update(W=READ_WRITE | DELETE, V=READ)
            elif profile.startswith("control_"):
                child[profile[-1]] = READ_WRITE | DELETE
            matrix[key]["child_file_policy"] = dict(rights_by_role=child,
                parent_ace_flags=["OBJECT_INHERIT", "INHERIT_ONLY"],
                child_directory_effect="INHERIT_ONLY_CARRIER_NOT_DIRECTORY_WRITE_GRANT",
                protected_named_files_override=True)
    # Actual existing global ancestor ACLs are observations, never proposed edits.
    for key in ("volume_root", "program_data", "acceptance_parent"):
        matrix[key] = dict(path=paths[key], policy_id="EXISTING_ANCESTOR_REVIEW_ONLY",
                           proposed_allow_masks=None, actual_effective_access="UNKNOWN", actual_sddl=None)

    cases = []

    def case(name, roles, targets, operation, expected):
        cases.append(dict(case_id=name, roles=list(roles), targets=[paths[key] for key in targets],
                          operation=operation, expected_outcome=expected, enabled=False, status="NOT_RUN",
                          reason="execution_disabled_in_this_checkpoint"))

    case("native_primary_tokens", "AWVM", ("root",), "Independently bind each process handle/PID/creation time to its actual primary token; all A variants, no owner/parent inference.", "NATIVE_IDENTITY_EVIDENCE_REQUIRED")
    case("ancestor_namespace", "AWV", ("volume_root", "program_data", "acceptance_parent", "root", "authority", "coordination", "lock_parent"), "Per-bit namespace/owner/DACL checks plus controlled ancestor rename/substitution attempts; preserve global ancestor ACLs.", "NATIVE_ACCESS_DENIED_FOR_SUBSTITUTION_OR_STOP")
    case("runtime_anchor_read", "WV", ("python_executable", "registry", "configuration", "bootstrap", "independent_checkpoint"), "Open code RX/anchors R under each actual token; validate independent source custody.", "NATIVE_SUCCESS")
    case("individual_rights", "AWV", tuple(C2_LAYOUT), "Expand every matrix required_individual_denials entry into a separate one-bit access request; validate matching positive controls.", "NATIVE_ACCESS_DENIED")
    case("writer_publication", "W", ("data_store", "publication_temporary", "head", "local_checkpoint"), "Create fixed synthetic temp, write/flush, close, replace fixed synthetic markers; no Store/signature API.", "NATIVE_SUCCESS")
    case("owner_inheritance_after_replace", "W", ("publication_temporary", "head", "local_checkpoint"), "Record before/after owner/DACL/inheritance/file identity; new W-owned files must not acquire implicit WRITE_DAC or broad creator-owner grants.", "NATIVE_POLICY_MATCH_OR_STOP")
    case("existing_lock_RW", "WV", ("history_lock",), "Open existing r+b-compatible RW handles without writes; observe the single-file write-capability exception.", "NATIVE_SUCCESS_WITH_STABLE_LOCK_BYTES")
    case("cross_process_locking", "WV", ("history_lock",), "Distinct W/V processes contend at offset 0 length 1 on same file ID; nonblocking conflict, then acquisition after release/exit; time-bounded.", "CONTENTION_THEN_SUCCESS")
    case("existing_lock_delete_replace", "AWV", ("history_lock", "lock_parent", "control_source_A", "control_source_W", "control_source_V"), "Check individual DELETE and parent rights, then separately approved delete/rename/replace with same-token known-good control source.", "NATIVE_ACCESS_DENIED")
    case("M_quiesced_missing_lock_injection", "M", ("history_lock",), "Separate approval to remove ONLY the sacrificial lock after all processes/handles stop; never auto-recreate or repair.", "M_APPROVED_FAULT_INJECTION_ONLY")
    case("missing_lock_existing_open", "WV", ("history_lock",), "Existing-only open fails on missing file; preserve bytes/namespace. NOT an ACL-denial result.", "MISSING_OPEN_WITHOUT_CREATION")
    case("missing_lock_name_recreation", "AWV", ("history_lock", "lock_parent"), "Direct CREATE_NEW, copy, rename and hard-link insertion into missing name; parent must exist and control sources must be usable.", "NATIVE_ACCESS_DENIED")
    case("lock_parent_new_names", "AWV", ("coordination", "lock_parent"), "Separate FILE_ADD_FILE/ADD_SUBDIRECTORY checks and approved new-name attempts; no prefix assumptions.", "NATIVE_ACCESS_DENIED")
    case("existing_lock_reparse", "AWV", ("history_lock",), "Separately approved set/remove reparse capability observation under actual RW/privilege state; native denial required, otherwise STOP for policy review.", "DENIAL_REQUIRED_OR_STOP")
    case("hardlink_alias_outside_coordination", "AWV", ("history_lock", "control_A", "control_W", "control_V"), "Attempt approved alias to the existing lock in the role's writable control; if allowed or unobservable STOP, never count application rejection as OS denial.", "DENIAL_REQUIRED_OR_STOP")
    case("handle_identity_and_no_follow", "WV", ("root", "coordination", "lock_parent", "history_lock"), "Check actual handles/volume/file ID/link count=1/no reparse before and after locking; no V1 fallback, no accepting a newly replaced lock.", "STABLE_NATIVE_IDENTITY_OR_STOP")
    case("verifier_data_unchanged", "V", ("history", "head", "local_checkpoint", "registry", "configuration", "bootstrap", "independent_checkpoint"), "Compare before/after bytes/identity/security; all write/delete/replace and create attempts denied outside explicit control fixtures.", "NATIVE_ACCESS_DENIED_AND_UNCHANGED")
    case("independent_evidence_and_stop", "M", ("bootstrap", "independent_checkpoint"), "Independently retain raw per-operation evidence and approval provenance; stop on mismatches; no cleanup, fallback, old approval or trust promotion.", "INDEPENDENT_REVIEW_REQUIRED")
    return dict(plan_type="c2_lock_namespace_E1_plan", schema_version=1, layout_version=LAYOUT_VERSION,
                specification_content_sha256=spec.content_sha256, specification=data, paths=paths,
                rights_matrix=matrix, cases=cases,
                environment_requirements=dict(platform="NATIVE_WINDOWS", filesystem="NTFS",
                    same_local_volume=True, no_reparse=True, lock_link_count=1,
                    lock_region=dict(offset=0, length=1, nonblocking=True), actual_state="UNKNOWN"),
                blockers=[dict(blocker_id=key, status="BLOCKED") for key in BLOCKERS],
                approval_checklist=[dict(requirement=value, status="NOT_VERIFIED") for value in APPROVAL_CHECKLIST],
                mode="non_executing_specification", status="BLOCKED", deployment_decision="NO_GO",
                execution_enabled=False,
                researcher_approval_verified=False, evidence_origin_authenticated=False,
                windows_local_isolation="NOT VERIFIED", trusted_human_authorization=False, execution_eligible=False)
