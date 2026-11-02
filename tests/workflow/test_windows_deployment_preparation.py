"""Pure proposed-manifest validation; no Windows mutations, science or keys."""

from copy import deepcopy
import builtins
import hashlib
import json
import os
from pathlib import Path

import pytest

from src.workflow import windows_isolation_acceptance as inspector
from src.workflow.windows_deployment_preparation import (
    ARTIFACT_LAYOUT, BLOCKERS, DELETE, FULL, READ, READ_EXECUTE, READ_WRITE, RESOURCE_POLICY,
    build_deployment_preparation,
)


RUN_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def specification():
    # Fictional SID domain, not evidence about the researcher's accounts.
    data = inspector.build_acceptance_specification(RUN_ID, agent_sids=["S-1-5-21-9-8-7-1001", "S-1-5-21-9-8-7-1003"]).to_dict()
    for role, rid in (("W", 9002), ("V", 9003), ("M", 9004)):
        data["roles"][role]["sid"] = f"S-1-5-21-9-8-7-{rid}"
    return data


def assert_disabled(report):
    assert report["status"] == "BLOCKED" and report["deployment_decision"] == "NO_GO"
    assert report["execution_enabled"] is False
    assert report["researcher_approval_verified"] is False
    assert report["artifact_origin_verified"] is False
    assert report["windows_local_isolation"] == "NOT VERIFIED"
    assert report["trusted_human_authorization"] is False and report["execution_eligible"] is False
    assert all(item["enabled"] is False and item["status"] == "NOT_RUN" for item in report["operations"])
    assert set(BLOCKERS).issubset({item["blocker_id"] for item in report["blockers"]})
    assert all(item["status"] == "BLOCKED" for item in report["blockers"])
    assert "lock_namespace_conflict" in {item["blocker_id"] for item in report["blockers"]}
    assert len(report["acceptance_cases"]) == 10
    assert tuple(item["case_id"] for item in report["acceptance_cases"]) == tuple(inspector.ACCEPTANCE_CASES)
    assert all(item["status"] == "NOT_RUN" and item["reason"] == "execution_disabled_in_this_checkpoint"
               for item in report["acceptance_cases"])


def test_deterministic_detached_manifest_and_digest(specification):
    before = deepcopy(specification)
    report = build_deployment_preparation(specification)
    assert_disabled(report)
    assert specification == before
    assert report == build_deployment_preparation(inspector.AcceptanceSpecificationV1.from_dict(specification).to_json())
    data = deepcopy(report)
    digest = data.pop("content_sha256")
    canonical = json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
    assert digest == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    report["operations"][0]["enabled"] = True
    assert_disabled(build_deployment_preparation(specification))


def test_incomplete_template_preserves_unknowns():
    report = build_deployment_preparation(inspector.build_acceptance_specification(RUN_ID))
    assert_disabled(report)
    assert all(report["roles"][role]["sid"] is None for role in "WVM")
    assert len(report["operations"]) == 36 and len(report["blockers"]) == 26
    assert all(item["declared_sha256"] is None for item in report["artifacts"].values())
    assert all(report["resources"][name]["policy"]["owner_sid"] is None for name in report["resources"])
    assert {"missing_sid_" + role for role in "AWVM"}.issubset({item["blocker_id"] for item in report["blockers"]})
    accounts = [item for item in report["operations"] if item["operation"] == "propose_dedicated_account"]
    assert all(len(item["target"]["proposed_name"]) <= 20 for item in accounts)


def test_documented_template_is_incomplete_not_deployed():
    path = Path(__file__).resolve().parents[2] / "docs" / "windows_deployment_preparation.example.json"
    report = build_deployment_preparation(path.read_text(encoding="utf-8"))
    assert_disabled(report)
    assert report["roles"]["A"]["sids"] == []
    assert all(report["roles"][role]["sid"] is None for role in "WVM")
    assert len(report["operations"]) == 36 and len(report["blockers"]) == 26


def test_complete_hash_declarations_do_not_authorize_or_measure(specification):
    hashes = dict.fromkeys(ARTIFACT_LAYOUT, "a" * 64)
    report = build_deployment_preparation(specification, artifact_sha256=hashes)
    assert_disabled(report)
    assert all(not item["origin_verified"] and not item["installed_bytes_verified"] for item in report["artifacts"].values())
    assert not any(item["blocker_id"].startswith("missing_hash_") for item in report["blockers"])
    assert {"native_identity_coverage", "trusted_startup", "lock_namespace_conflict", "complete_operation_inventory", "researcher_approval"}.issubset(
        {item["blocker_id"] for item in report["blockers"]})
    hashes["runtime_bundle"] = "b" * 64
    assert build_deployment_preparation(specification, artifact_sha256=hashes)["content_sha256"] != report["content_sha256"]


def test_existing_owner_expectations_preserved_and_conflicts_blocked(specification):
    specification["resource_expectations"]["head"]["owner_sid"] = specification["roles"]["M"]["sid"]
    before = deepcopy(specification)
    report = build_deployment_preparation(specification)
    assert_disabled(report)
    assert specification == before
    head = report["resources"]["head"]
    assert head["acceptance_expectation"]["owner_sid"] == specification["roles"]["M"]["sid"]
    assert head["policy"]["owner_sid"] == specification["roles"]["W"]["sid"]
    assert "owner_expectation_conflict_head" in {item["blocker_id"] for item in report["blockers"]}


@pytest.mark.parametrize("hashes", [{"unknown_file": "a" * 64}, {"runtime_bundle": "A" * 64},
                                  {"runtime_bundle": "g" * 64}, {"runtime_bundle": "a" * 63},
                                  {"runtime_bundle": 123}, {"runtime_bundle": True}, [], "trusted"])
def test_invalid_artifact_declarations_rejected(specification, hashes):
    with pytest.raises(ValueError):
        build_deployment_preparation(specification, artifact_sha256=hashes)


@pytest.mark.parametrize("role", ["W", "V", "M"])
def test_agent_role_overlap_rejected(specification, role):
    specification["roles"][role]["sid"] = specification["roles"]["A"]["sids"][1]
    with pytest.raises(ValueError, match="distinct"):
        build_deployment_preparation(specification)


def test_arbitrary_root_and_claimed_approval_rejected(specification):
    for change in ({"deployment_root": r"C:\Users\Researcher\Production"}, {"approved": True}):
        bad = {**specification, **change}
        with pytest.raises(ValueError):
            build_deployment_preparation(bad)


def test_permission_proposals_are_specific_and_preserve_lock_exception(specification):
    report = build_deployment_preparation(specification)
    resources = report["resources"]
    assert set(RESOURCE_POLICY) == set(inspector.RESOURCE_LAYOUT)
    for item in resources.values():
        rights = item["policy"]["rights_by_role"]
        assert rights["A"] == 0
        assert all(rights.get(role, 0) != FULL for role in "WV")
        assert item["policy"]["owner_rights_sid"] == "S-1-3-4"
        assert item["policy"]["owner_rights_mask"] == 0x20000
        assert item["policy"]["exact_sddl"] is None  # no fabricated native evidence
    lock = resources["history_lock"]["policy"]
    assert lock["rights_by_role"]["V"] == READ_WRITE
    assert not lock["rights_by_role"]["W"] & DELETE
    assert resources["history"]["policy"]["rights_by_role"]["V"] == READ
    assert resources["head"]["policy"]["rights_by_role"]["W"] & DELETE
    assert resources["head"]["policy"]["owner_role"] == "W"
    assert resources["store_root"]["policy"]["rights_by_role"]["W"] & 0x2
    assert not resources["store_root"]["policy"]["rights_by_role"]["W"] & 0x40
    children = resources["store_root"]["policy"]["directory_child_inheritance"]["child_files"]["rights_by_role"]
    assert children["W"] == READ_WRITE | DELETE
    assert children["V"] == READ and children["OWNER_RIGHTS"] == 0x20000


@pytest.mark.parametrize("resource", ["root", "runtime", "registry", "store_root", "writer_diagnostics", "verifier_diagnostics"])
def test_directory_self_and_child_inheritance_are_distinct(specification, resource):
    report = build_deployment_preparation(specification)
    assert_disabled(report)
    policy = report["resources"][resource]["policy"]
    inheritance = policy["directory_child_inheritance"]
    assert inheritance["declared_on"] == "PARENT_DIRECTORY"
    assert "applies_to" not in inheritance and "scope" not in inheritance
    assert inheritance["directory_self"]["ace_flags"] == []
    for role, mask in policy["rights_by_role"].items():
        assert inheritance["directory_self"]["rights_by_role"][role] == mask
    assert inheritance["child_files"]["inherit_only"] is False
    for ace in inheritance["inheritable_aces"]:
        flags, role = set(ace["ace_flags"]), ace["role"]
        assert {"OBJECT_INHERIT", "INHERIT_ONLY"}.issubset(flags)
        assert inheritance["child_files"]["rights_by_role"][role] == ace["mask"]
        if "CONTAINER_INHERIT" in flags:
            assert inheritance["child_directories"]["rights_by_role"][role] == ace["mask"]
            assert role not in inheritance["child_directories"]["inherit_only_rights_by_role"]
        else:
            assert role not in inheritance["child_directories"]["rights_by_role"]
            assert inheritance["child_directories"]["inherit_only_rights_by_role"][role] == ace["mask"]


def test_anchor_file_read_rights_explicit_and_consistent(specification):
    report = build_deployment_preparation(specification)
    for resource in ("registry", "configuration", "independent_checkpoint", "bootstrap"):
        policy = report["resources"][resource]["policy"]
        assert policy["dacl_protected"] is True
        for role in "WV":
            assert policy["rights_by_role"][role] == READ
            assert policy["directory_child_inheritance"]["child_files"]["rights_by_role"][role] == READ
    for operation in report["operations"]:
        if operation["operation"] == "stage_reviewed_artifact" and operation["expected_after"]["policy"]["policy_id"] == "anchor":
            policy = operation["expected_after"]["policy"]
            assert policy["dacl_protected"] is True
            assert all(policy["rights_by_role"][role] == READ for role in "WV")


def test_store_file_only_inheritance_does_not_grant_directory_delete(specification):
    resources = build_deployment_preparation(specification)["resources"]
    store = resources["store_root"]["policy"]["directory_child_inheritance"]
    assert store["directory_self"]["rights_by_role"]["W"] & 0x2
    assert not store["directory_self"]["rights_by_role"]["W"] & 0x40
    for role, mask in (("W", READ_WRITE | DELETE), ("V", READ), ("OWNER_RIGHTS", 0x20000)):
        ace = next(item for item in store["inheritable_aces"] if item["role"] == role)
        assert ace["mask"] == mask and set(ace["ace_flags"]) == {"OBJECT_INHERIT", "INHERIT_ONLY"}
        assert store["child_directories"]["inherit_only_rights_by_role"][role] == mask
        assert role not in store["child_directories"]["rights_by_role"]
    for name in ("history", "history_lock"):
        policy = resources[name]["policy"]
        assert policy["dacl_protected"] is True
        assert not policy["rights_by_role"]["W"] & DELETE
    for name in ("head", "local_checkpoint"):
        policy = resources[name]["policy"]
        assert policy["dacl_protected"] is False
        assert policy["rights_by_role"]["W"] == store["child_files"]["rights_by_role"]["W"]
        assert policy["rights_by_role"]["V"] == store["child_files"]["rights_by_role"]["V"]


def test_operation_manifest_has_review_and_containment_fields(specification):
    report = build_deployment_preparation(specification)
    operations = report["operations"]
    assert len({item["operation_id"] for item in operations}) == len(operations)
    for item in operations:
        for name in ("target", "required_privilege", "expected_before", "expected_after", "rationale", "failure_conditions", "verification", "containment", "approval_gate"):
            assert item[name]
        if isinstance(item["target"], str):
            assert item["target"] == inspector.ACCEPTANCE_PARENT or item["target"].startswith(report["deployment_root"])
    assert report["resources"]["root"]["path"] == report["deployment_root"]
    for name in ("writer_launcher", "verifier_launcher"):
        staged = next(item for item in operations if item["operation"] == "stage_reviewed_artifact"
                      and item["expected_after"]["artifact_id"] == name)
        assert staged["expected_after"]["policy"]["rights_by_role"]["V"] == READ_EXECUTE


def test_preparation_never_acquires_files_processes_or_security_handles(specification, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Pure preparation attempted IO or native inspection")

    monkeypatch.setattr(builtins, "open", forbidden)
    for name in ("open", "stat", "mkdir", "remove", "unlink", "rename", "replace", "chmod", "system"):
        monkeypatch.setattr(os, name, forbidden)
    monkeypatch.setattr(inspector, "_backend", forbidden)
    monkeypatch.setattr(inspector, "inspect_environment", forbidden)
    assert_disabled(build_deployment_preparation(specification))


@pytest.mark.parametrize("keyword", ["execute", "approve", "cleanup", "trust"])
def test_no_execution_or_approval_switch(specification, keyword):
    with pytest.raises(TypeError):
        build_deployment_preparation(specification, **{keyword: True})
