"""Pure proposed deployment records, NOT a launcher or deployment authority.

Only an existing acceptance specification and declared artifact hashes are used.
No OS inspection, file acquisition, UUID/key generation, signing, Store calls or
commands are performed. Unknown identities/hashes remain null. Even complete
declarations produce NO_GO: approval, origin, effective access, runtime integrity
and the lock namespace conflict cannot be established by this preparation code.
See docs/windows_deployment_preparation.md before reviewing any future mutation.
"""

import hashlib
import json
import ntpath
import re

from .windows_isolation_acceptance import (
    ACCEPTANCE_CASES, ACCEPTANCE_PARENT, AcceptanceSpecificationV1, RESOURCE_LAYOUT,
)


# Bundles are reviewed archives; inventories must enumerate installed bytes too.
# Hashes supplied to this module are declarations, NEVER file measurements.
ARTIFACT_LAYOUT = {
    "runtime_bundle": r"release\runtime",
    "application_bundle": r"release\app",
    "dependencies_bundle": r"release\deps",
    "runtime_inventory": r"bootstrap\runtime-files.json",
    "application_inventory": r"bootstrap\application-files.json",
    "dependencies_inventory": r"bootstrap\dependency-files.json",
    "writer_launcher": r"bootstrap\writer-launcher.exe",
    "verifier_launcher": r"bootstrap\verifier-launcher.exe",
    "bootstrap": r"bootstrap\manifest.json",
    "registry": r"anchors\registry.json",
    "configuration": r"anchors\verifier.json",
    "independent_checkpoint": r"anchors\minimum-checkpoint.json",
}

# Candidate rights only. No DACL encoder, setter, AccessCheck or allow decision.
# All masks are object-specific Windows FILE_* masks, not generic shell names.
READ = 0x120089
READ_EXECUTE = 0x1200A9
READ_WRITE = 0x12019F
DELETE = 0x10000
FULL = 0x1F01FF
POLICIES = {
    "container": ("M", {"W": READ_EXECUTE, "V": READ_EXECUTE}),
    "release": ("M", {"W": READ_EXECUTE, "V": READ_EXECUTE}),
    "anchor": ("M", {"W": READ, "V": READ}),
    "store_directory": ("M", {"W": READ_EXECUTE | 0x2, "V": READ_EXECUTE}),
    "history": ("M", {"W": READ_WRITE, "V": READ}),
    "marker": ("W", {"W": READ_WRITE | DELETE, "V": READ}),
    "lock": ("M", {"W": READ_WRITE, "V": READ_WRITE}),
    "writer_logs": ("M", {"W": READ_EXECUTE | 0x2}),
    "verifier_logs": ("M", {"V": READ_EXECUTE | 0x2}),
}
RESOURCE_POLICY = {
    "runtime": "release", "python_executable": "release", "application": "release",
    "dependencies": "release", "registry": "anchor", "bootstrap": "anchor",
    "configuration": "anchor", "store_root": "store_directory", "history": "history",
    "head": "marker", "local_checkpoint": "marker", "history_lock": "lock",
    "independent_checkpoint": "anchor", "writer_diagnostics": "writer_logs",
    "verifier_diagnostics": "verifier_logs",
}
BLOCKERS = {
    "native_identity_coverage": "Independently establish full A host/worker SIDs (including known 1001/1003), all groups/privileges, W/V/M primary tokens and absence of Agent control over them.",
    "parent_namespace": "Verify protected ancestors, exact resolved root/volume, no aliases/reparse, unused RunId and absence of A DELETE_CHILD/replacement/ownership paths.",
    "lock_namespace_conflict": "W needs FILE_ADD_FILE for mkstemp. If history.lock is absent that directory right can recreate its name. ACL on the former file cannot protect a missing name. Required policy/design resolution is NOT implemented.",
    "owner_rights_and_replacement": "Prove inherited OWNER RIGHTS S-1-3-4 policy suppresses implicit WRITE_DAC on W-created files; no CREATOR OWNER FullControl. Measure os.replace result, owner and exact DACL on native Windows.",
    "runtime_and_origin": "Independently review runtime/installed-byte inventories, package/native DLL closure, Python/import/DLL search paths, artifact provenance and external bootstrap-pin custody.",
    "complete_operation_inventory": "Expand reviewed bundle inventories and exact temporary/log/retention filenames into individually approved mutations. Directory-level proposals and hashes are not permission to mutate arbitrary children.",
    "trusted_startup": "A protected W/V launcher with real primary-token checks, fixed paths/pins, controlled environment/CWD and no Agent-controlled executable/config/callback loading is not implemented.",
    "independent_floor": "M must independently validate, retain and publish a newer floor with coordinated config/bootstrap pin updates. A local or old floor cannot establish global freshness.",
    "effective_access": "Real role-token access attempts and interrupted multi-file publication tests require a separately approved sacrificial deployment; mocks/SDDL/pins are insufficient.",
    "researcher_approval": "Approval for exact operations, identities, hashes, root and failure containment must be established outside Agent-controlled code and manifests.",
}


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"


def build_deployment_preparation(specification, *, artifact_sha256=None) -> dict:
    """Return a deterministic, detached, non-executing proposed operation manifest.

    Accepted input is the existing V1 object, dictionary or bounded JSON. Hashes
    may name only ARTIFACT_LAYOUT keys; absent/null means unknown, not a default
    or an inferred measurement. Supplied paths, digests and SIDs never authorize
    an operation. There is deliberately no execute/approve/cleanup parameter.
    content_sha256 covers the canonical result EXCLUDING that digest field;
    it authenticates neither the researcher nor the original files.
    """
    if isinstance(specification, AcceptanceSpecificationV1):
        spec = AcceptanceSpecificationV1.from_json(specification.to_json())
    elif type(specification) is dict:
        spec = AcceptanceSpecificationV1.from_dict(specification)
    else:
        spec = AcceptanceSpecificationV1.from_json(specification)
    declared = {} if artifact_sha256 is None else artifact_sha256
    if type(declared) is not dict or not set(declared).issubset(ARTIFACT_LAYOUT):
        raise ValueError("Only fixed deployment artifact hash declarations are supported.")
    for value in declared.values():
        if value is not None and (type(value) is not str or len(value) != 64 or not re.fullmatch("[0-9a-f]{64}", value)):
            raise ValueError("Expected lowercase SHA-256 or null, never an artifact path.")
    data, paths = spec.to_dict(), spec.paths()
    root, roles = data["deployment_root"], data["roles"]
    sids = {role: roles[role]["sid"] for role in "WVM"}
    blockers = [dict(blocker_id=name, status="BLOCKED", reason=reason) for name, reason in BLOCKERS.items()]
    for role in "AWVM":
        if not (roles[role]["sids"] if role == "A" else roles[role]["sid"]):
            blockers.append(dict(blocker_id="missing_sid_" + role, status="BLOCKED", reason="Full independently verified SID assignment is unavailable; suffix/account name is insufficient."))

    def policy(profile):
        owner_role, access = POLICIES[profile]
        children = {"M": FULL, "SYSTEM": FULL, "OWNER_RIGHTS": 0x20000}
        if profile in ("release", "anchor"):
            children.update(access)
        elif profile in ("store_directory", "writer_logs", "verifier_logs"):
            children.update({role: READ_WRITE | DELETE for role in ("W", "V")
                             if role in access and (profile != "store_directory" or role == "W")})
            if profile == "store_directory":
                children["V"] = READ
        # Separate self-only ACEs from inheritance-only ACEs declared on a
        # directory. OI without CI becomes an IO carrier on child directories,
        # not a directory access grant. These are proposals, not an ACL engine.
        file_only = profile in ("store_directory", "writer_logs", "verifier_logs")
        directory_rights = {role: mask for role, mask in children.items()
                            if not file_only or role in ("M", "SYSTEM")}
        carrier_rights = {role: mask for role, mask in children.items() if role not in directory_rights}
        return dict(policy_id=profile, owner_role=owner_role, owner_sid=sids[owner_role],
                    rights_by_role={"A": 0, "M": FULL, "SYSTEM": FULL, **access},
                    owner_rights_sid="S-1-3-4", owner_rights_mask=0x20000,
                    directory_child_inheritance=dict(declared_on="PARENT_DIRECTORY",
                        directory_self=dict(rights_by_role={"A": 0, "M": FULL, "SYSTEM": FULL,
                                                            **access, "OWNER_RIGHTS": 0x20000}, ace_flags=[]),
                        inheritable_aces=[dict(role=role, mask=mask,
                            ace_flags=["OBJECT_INHERIT", "INHERIT_ONLY"] +
                                      (["CONTAINER_INHERIT"] if role in directory_rights else []))
                            for role, mask in children.items()],
                        child_files=dict(rights_by_role=children, inherit_only=False),
                        child_directories=dict(rights_by_role=directory_rights,
                                               inherit_only_rights_by_role=carrier_rights)),
                    dacl_protected=profile != "marker", exact_sddl=None,
                    status="PROPOSED_NOT_APPLIED")

    resources = {"root": dict(path=root, object_type="directory", policy=policy("container"))}
    resources.update({name: dict(path=path, object_type=RESOURCE_LAYOUT[name][1], policy=policy(RESOURCE_POLICY[name]))
                      for name, path in paths.items()})
    for name, item in resources.items():
        expected = data["root_expectations"] if name == "root" else data["resource_expectations"][name]
        item["acceptance_expectation"] = expected
        if expected["owner_sid"] is not None and expected["owner_sid"] != item["policy"]["owner_sid"]:
            blockers.append(dict(blocker_id="owner_expectation_conflict_" + name, status="BLOCKED",
                                 reason="Existing acceptance owner declaration conflicts with the candidate deployment policy; no declaration is overwritten."))
    artifacts = {name: dict(target_path=ntpath.join(root, relative), declared_sha256=declared.get(name),
                            origin_verified=False, installed_bytes_verified=False)
                 for name, relative in ARTIFACT_LAYOUT.items()}
    for name, item in artifacts.items():
        if item["declared_sha256"] is None:
            blockers.append(dict(blocker_id="missing_hash_" + name, status="BLOCKED", reason="Reviewed exact artifact hash is not supplied."))
    directories = {root, ntpath.join(root, r"anchors\retained-checkpoints")}
    for item in resources.values():
        current = item["path"] if item["object_type"] == "directory" else ntpath.dirname(item["path"])
        while current != root:
            directories.add(current)
            current = ntpath.dirname(current)
    for item in artifacts.values():
        directories.add(ntpath.dirname(item["target_path"]))

    operations = []

    def operation(kind, target, privilege, before, after, why, verification, approval):
        operations.append(dict(operation_id=f"op-{len(operations) + 1:03d}", operation=kind, target=target,
                               enabled=False, status="NOT_RUN", approval_gate=approval,
                               required_privilege=privilege, expected_before=before, expected_after=after,
                               rationale=why, failure_conditions=["Any prerequisite/approval/token/path/owner/DACL/hash mismatch", "Unexpected existing target, alias, partial publication or unavailable evidence"],
                               verification=verification,
                               containment="Stop W/V; retain exact synthetic root and diagnostics. No retry/repair, rollback or recursive cleanup. M separately reviews recovery."))

    absent = dict(existence="ABSENT_REQUIRED", owner_sid=None, dacl=None)
    unknown = dict(existence="PREVIOUS_STAGE_REQUIRED", owner_sid=None, dacl="UNKNOWN_REQUIRES_NATIVE_SNAPSHOT")
    for role in "WV":
        operation("propose_dedicated_account", dict(role=role, existing_sid=sids[role],
                  proposed_name="TECA-" + role + "-" + data["run_id"].replace("-", "")[:12] if sids[role] is None else None),
                  "Independently authorized local administrator; no automatic elevation",
                  dict(account="ABSENT_OR_INDEPENDENTLY_REVIEWED", owner_sid=None, dacl="NOT_APPLICABLE"),
                  dict(primary_sid=sids[role], owner_sid=None, dacl="NOT_APPLICABLE", membership="Dedicated standard user; credentials never available to A"),
                  "Separate role identity; names are proposals, not SID measurements.",
                  "Independent SID/account collision/group/privilege review and real primary-token inspection; no use of RID inference.", "G1_PRINCIPALS")
    operation("create_acceptance_parent_only_if_absent", ACCEPTANCE_PARENT, "M; administrator only if required and separately approved",
              absent, policy("container"), "Protect acceptance namespace without changing C:\\ or C:\\ProgramData ACLs.",
              "If parent exists, do not recreate/overwrite it: separately attest its owner/DACL and namespace protection. No ancestor mutation is authorized.", "G2_NAMESPACE")
    for path in sorted(directories, key=lambda value: (value.count("\\"), value)):
        matched = next((item for item in resources.values() if item["path"] == path), None)
        after = matched["policy"] if matched else policy("container")
        operation("create_new_directory_with_initial_policy", path, "M; privilege needed for owner assignment must be separately reviewed", absent, after,
                  "Create only this named disposable directory with restrictive initial policy; do not expose a permissive staging interval.",
                  "Native path/volume/file-ID/reparse, owner and effective DACL snapshot; abort on pre-existing run root or child.", "G2_NAMESPACE")
    for name, artifact in artifacts.items():
        profile = "release" if name.endswith(("_bundle", "_launcher")) else "anchor"
        before = dict(existence="NEW_EMPTY_DIRECTORY_FROM_THIS_RUN", policy=policy(profile)) if name.endswith("_bundle") else absent
        gate = "G4_SYNTHETIC_STORE" if name == "registry" else (
            "G6_CHECKPOINT_AND_PINS" if name in ("bootstrap", "configuration", "independent_checkpoint") else "G3_RUNTIME_AND_ORIGIN")
        operation("stage_reviewed_artifact", artifact["target_path"], "M, from independently verified offline release custody", before,
                  dict(policy=policy(profile), declared_sha256=artifact["declared_sha256"], artifact_id=name),
                  "Install/copy only a new reviewed artifact or synthetic anchor; no development .venv reuse or in-place upgrade.",
                  "Authenticate publisher/release outside this manifest; match archive hash AND installed-file inventory/owner/DACL; reject missing or extra files and DLLs.", gate)
    operation("create_permanent_empty_lock", paths["history_lock"], "M; no W/V activity", absent,
              dict(policy=policy("lock"), content="EMPTY", immutable_file_identity_required=True),
              "Pre-create a single permanent lock before initialization; no DELETE or parent DELETE_CHILD for W/V/A.",
              "Record file ID, link count, owner/SDDL; later validate/append must use the same file. Missing-lock namespace conflict must first be resolved.", "G4_SYNTHETIC_STORE")
    operation("create_ephemeral_synthetic_signing_capability", dict(role="W", sid=sids["W"], storage="PROCESS_MEMORY_ONLY"),
              "W under reviewed startup; no persistent key storage", dict(key="ABSENT", owner_sid=None, dacl="NOT_APPLICABLE"),
              dict(key="EPHEMERAL_SYNTHETIC_ONLY", owner_sid=None, dacl="NOT_APPLICABLE"),
              "Later signed synthetic Store tests require an explicitly approved signing capability; none is generated by this tool.",
              "Separate human approval and key-custody review; no logs/export, no production keys, no key from Agent inputs.", "G4_SYNTHETIC_STORE")
    operation("initialize_existing_v1_store_once", paths["store_root"], "W through a separately reviewed trusted adapter",
              dict(policy=policy("store_directory"), children=["history.lock"], lock_policy=policy("lock")),
              dict(files={name: dict(path=paths[name], policy=policy("marker")) for name in ("history", "head", "local_checkpoint")},
                   sequence=0, intermediate_history_owner="W; M sealing required before runtime starts", published=False),
              "Use unchanged AuthorizationStore.initialize on an otherwise empty root; never reset or fabricate V1 bytes.",
              "Validate actual V1 files, sequence zero and unchanged permanent lock file ID; withhold publication on partial failure.", "G4_SYNTHETIC_STORE")
    operation("seal_initial_history_owner_and_dacl", paths["history"], "M; W/V stopped", unknown, policy("history"),
              "Fix initial W-created history ownership while retaining required W read/write and V read access.",
              "Native owner/DACL/effective-access tests; history bytes unchanged; no per-append ACL repair.", "G4_SYNTHETIC_STORE")
    operation("writer_append_and_marker_replacement", paths["store_root"], "W; exact reviewed synthetic decisions only", unknown,
              dict(history=policy("history"), markers=policy("marker"), temporary_files="W-owned, inherited object-only W RW+DELETE / V R / M+SYSTEM full / OWNER RIGHTS RC; no CREATOR OWNER FullControl"),
              "Existing mkstemp + os.replace requires new file creation and per-file DELETE, not directory DELETE_CHILD.",
              "Native W operations, resulting marker owner/DACL, permanent lock identity, full V1 chain/revocation and interrupted publication checks. No Framework execution.", "G5_EFFECTIVE_ACCESS_AND_STORE")
    operation("write_role_diagnostics", {role: paths[name] for role, name in (("W", "writer_diagnostics"), ("V", "verifier_diagnostics"))},
              "Corresponding W/V only; M can inspect", unknown,
              dict(writer_directory=policy("writer_logs"), verifier_directory=policy("verifier_logs"),
                   children="Own-role RW, M/SYSTEM full, OWNER RIGHTS RC; no other-role write"),
              "Separate non-authoritative diagnostics; never executable input, trust anchor or key material.",
              "Record exact created child names before approving a real run; inspect inheritance/owner and cross-role denial. Dynamic names are not authorized by this proposal.", "G5_EFFECTIVE_ACCESS_AND_STORE")
    operation("publish_and_retain_independent_floor", paths["independent_checkpoint"], "M independently of W", unknown,
              dict(policy=policy("anchor"), retained_directory=ntpath.join(root, r"anchors\retained-checkpoints"),
                   pin_updates=[paths["configuration"], paths["bootstrap"]]),
              "Retain validated newer floors outside mutable Store; coordinate verifier config and independently held bootstrap pins.",
              "Approve exact retention filenames/bytes first; validate chain membership, monotonic floor and raw hashes; old floor is not a freshness proof. Quiesce W/V during multi-file publication.", "G6_CHECKPOINT_AND_PINS")
    operation("retire_exact_disposable_run_only", root, "M; separately approved cleanup with no recursive implementation here", unknown,
              dict(existence="ABSENT_AFTER_SEPARATELY_REVIEWED_CLEANUP", owner_sid=None, dacl=None),
              "Future retirement requires an exact approved inventory; never delete a root inferred from Agent input.",
              "Revalidate approved root/RunId/volume/owner/SDDL/no-reparse, stop all role processes, retain evidence; no wildcard or parent cleanup.", "G7_RETIREMENT")
    report = dict(manifest_type="windows_synthetic_deployment_preparation", schema_version=1,
                  status="BLOCKED", deployment_decision="NO_GO", mode="non_executing_preparation",
                  run_id=data["run_id"], deployment_root=root, acceptance_specification=data,
                  specification_content_sha256=spec.content_sha256, roles=roles, resources=resources,
                  artifacts=artifacts, operations=operations, blockers=blockers,
                  acceptance_cases=[dict(case_id=name, expected_outcome=description, status="NOT_RUN",
                                         reason="execution_disabled_in_this_checkpoint") for name, description in ACCEPTANCE_CASES.items()],
                  execution_enabled=False, researcher_approval_verified=False, artifact_origin_verified=False,
                  windows_local_isolation="NOT VERIFIED", trusted_human_authorization=False, execution_eligible=False)
    report["content_sha256"] = hashlib.sha256(_canonical(report).encode("utf-8")).hexdigest()
    return report
