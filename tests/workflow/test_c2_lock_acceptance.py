"""Pure C2 declaration tests; no OS evidence, files, ACLs, keys or Store calls."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import builtins
import hashlib
import json
import os

import pytest

from src.workflow import windows_isolation_acceptance as v1
from src.workflow.c2_lock_acceptance import (
    ARTIFACT_KEYS, BLOCKERS, C2_LAYOUT, C2AcceptanceSpecificationV1,
    DELETE, FULL, IDENTITY_FIELDS, LAYOUT_VERSION, READ, READ_EXECUTE, READ_WRITE, TRAVERSE,
    build_c2_acceptance_specification, build_c2_e1_plan,
)


RUN_ID = "11111111-1111-4111-8111-111111111111"
STORE_ID = "22222222-2222-4222-8222-222222222222"
GUID = "\\\\?\\Volume{33333333-3333-4333-8333-333333333333}\\"


@pytest.fixture
def specification():
    data = build_c2_acceptance_specification(RUN_ID, STORE_ID).to_dict()
    data["roles"]["A"] = dict(sids=["S-1-5-21-9-8-7-1001", "S-1-5-21-9-8-7-1003"], pids=[101, 103])
    for role, rid in (("W", 9002), ("V", 9003), ("M", 9004)):
        data["roles"][role] = dict(sid=f"S-1-5-21-9-8-7-{rid}", pids=[rid])
    return C2AcceptanceSpecificationV1.from_dict(data)


def assert_non_executing(report):
    assert report["status"] == "BLOCKED" and report["deployment_decision"] == "NO_GO"
    assert report["execution_enabled"] is False
    assert report["windows_local_isolation"] == "NOT VERIFIED"
    assert report["trusted_human_authorization"] is False and report["execution_eligible"] is False
    assert report["researcher_approval_verified"] is False and report["evidence_origin_authenticated"] is False
    assert len(report["cases"]) == 18
    assert len({item["case_id"] for item in report["cases"]}) == 18
    assert all(item["status"] == "NOT_RUN" and item["enabled"] is False and
               item["reason"] == "execution_disabled_in_this_checkpoint" for item in report["cases"])
    assert {item["blocker_id"] for item in report["blockers"]} == set(BLOCKERS)
    assert all(item["status"] == "BLOCKED" for item in report["blockers"])
    assert all(item["status"] == "NOT_VERIFIED" for item in report["approval_checklist"])
    assert all(item["actual_effective_access"] == "UNKNOWN" and item["actual_sddl"] is None
               for item in report["rights_matrix"].values())
    assert report["environment_requirements"] == dict(platform="NATIVE_WINDOWS", filesystem="NTFS",
        same_local_volume=True, no_reparse=True, lock_link_count=1,
        lock_region=dict(offset=0, length=1, nonblocking=True), actual_state="UNKNOWN")


def test_independent_type_and_layout_without_v1_mutation(specification):
    before = deepcopy(v1.RESOURCE_LAYOUT)
    old = v1.build_acceptance_specification(RUN_ID)
    report = build_c2_e1_plan(specification)
    assert_non_executing(report)
    assert report["layout_version"] == LAYOUT_VERSION
    assert specification.paths()["history_lock"].endswith("coordination\\" + STORE_ID + "\\history.lock")
    assert not specification.paths()["history_lock"].startswith(specification.paths()["data_store"] + "\\")
    assert old.paths()["history_lock"].endswith(r"store\history.lock")
    assert v1.RESOURCE_LAYOUT == before
    with pytest.raises(ValueError):
        C2AcceptanceSpecificationV1.from_json(old.to_json())
    with pytest.raises(ValueError):
        v1.AcceptanceSpecificationV1.from_json(specification.to_json())


def test_detached_immutable_deterministic_contract(specification):
    before = specification.to_dict()
    assert C2AcceptanceSpecificationV1.from_json(specification.to_json()) == specification
    assert specification.content_sha256 == hashlib.sha256(specification.to_json().encode("utf-8")).hexdigest()
    with pytest.raises(FrozenInstanceError):
        specification._json = "{}"
    report = build_c2_e1_plan(specification)
    assert report == build_c2_e1_plan(before)
    report["cases"][0]["enabled"] = True
    assert specification.to_dict() == before
    assert_non_executing(build_c2_e1_plan(specification))
    assert json.loads(json.dumps(build_c2_e1_plan(specification), allow_nan=False)) == build_c2_e1_plan(specification)


def test_complete_declarations_never_become_native_evidence(specification):
    data = specification.to_dict()
    data["artifact_sha256"] = dict.fromkeys(ARTIFACT_KEYS, "a" * 64)
    for index, (key, expected) in enumerate(data["identity_expectations"].items()):
        expected.update(resolved_path=specification.paths()[key], volume_guid=GUID,
                        volume_serial="1234abcd", file_id=f"{index:016x}",
                        owner_sid=data["roles"]["M"]["sid"], sddl="SYNTHETIC DECLARATION ONLY")
    assert_non_executing(build_c2_e1_plan(data))


def test_incomplete_template_keeps_unknown_provenance():
    spec = build_c2_acceptance_specification(RUN_ID, STORE_ID)
    data = spec.to_dict()
    assert data["roles"]["A"]["sids"] == []
    assert all(data["roles"][role]["sid"] is None for role in "WVM")
    assert all(value is None for item in data["identity_expectations"].values() for value in item.values())
    assert all(value is None for value in data["artifact_sha256"].values())
    assert_non_executing(build_c2_e1_plan(spec))


def test_rights_separate_directory_creation_file_writes_and_lock_exception(specification):
    matrix = build_c2_e1_plan(specification)["rights_matrix"]
    data = matrix["data_store"]
    assert data["proposed_allow_masks"]["W"] == READ_EXECUTE | 0x2
    assert data["required_individual_denials"]["W"] == {
        "FILE_ADD_SUBDIRECTORY": 4, "DELETE_CHILD": 64, "DELETE": DELETE, "WRITE_DAC": 0x40000, "WRITE_OWNER": 0x80000}
    for key in ("coordination", "lock_parent", "authority", "root"):
        assert matrix[key]["proposed_allow_masks"]["W"] == READ_EXECUTE
        assert matrix[key]["proposed_allow_masks"]["A"] == TRAVERSE
        assert matrix[key]["required_individual_denials"]["W"]["FILE_ADD_FILE"] == 2
    lock = matrix["history_lock"]
    assert lock["lock_RW_exception"] is True and lock["owner_role"] == "M"
    for role in "WV":
        assert lock["proposed_allow_masks"][role] == READ_WRITE
        assert "WRITE_DATA" not in lock["required_individual_denials"][role]
        assert lock["required_individual_denials"][role]["DELETE"] == DELETE
    assert matrix["head"]["proposed_allow_masks"]["W"] == READ_WRITE | DELETE
    assert matrix["history"]["proposed_allow_masks"]["W"] == READ_WRITE
    assert matrix["history"]["protected_dacl"] and lock["protected_dacl"]
    for key in ("history", "head", "registry", "configuration", "bootstrap", "independent_checkpoint"):
        assert matrix[key]["proposed_allow_masks"]["V"] == READ
    for key in C2_LAYOUT:
        assert matrix[key]["proposed_allow_masks"]["M"] == FULL
    child = data["child_file_policy"]
    assert child["rights_by_role"]["W"] == READ_WRITE | DELETE
    assert child["rights_by_role"]["V"] == READ
    assert child["rights_by_role"]["OWNER_RIGHTS"] == 0x20000
    assert child["parent_ace_flags"] == ["OBJECT_INHERIT", "INHERIT_ONLY"]
    assert child["protected_named_files_override"] is True


def test_control_sources_and_global_ancestors_are_explicit(specification):
    matrix = build_c2_e1_plan(specification)["rights_matrix"]
    for role in "AWV":
        assert matrix["control_" + role]["proposed_allow_masks"][role] == READ_EXECUTE | 2
        assert matrix["control_source_" + role]["proposed_allow_masks"][role] == READ_WRITE | DELETE
    for key in ("volume_root", "program_data", "acceptance_parent"):
        assert matrix[key]["proposed_allow_masks"] is None
        assert matrix[key]["policy_id"] == "EXISTING_ANCESTOR_REVIEW_ONLY"


def test_case_outcomes_do_not_conflate_missing_open_with_acl_denial(specification):
    cases = {item["case_id"]: item for item in build_c2_e1_plan(specification)["cases"]}
    assert cases["missing_lock_existing_open"]["expected_outcome"] == "MISSING_OPEN_WITHOUT_CREATION"
    assert cases["missing_lock_name_recreation"]["expected_outcome"] == "NATIVE_ACCESS_DENIED"
    assert cases["existing_lock_reparse"]["expected_outcome"] == "DENIAL_REQUIRED_OR_STOP"
    assert cases["hardlink_alias_outside_coordination"]["expected_outcome"] == "DENIAL_REQUIRED_OR_STOP"
    assert cases["cross_process_locking"]["roles"] == ["W", "V"]


@pytest.mark.parametrize("change", [dict(schema_version=True), dict(schema_version=2),
    dict(specification_type="windows_isolation_acceptance_specification"), dict(layout_version="v1"),
    dict(purpose="production"), dict(approved=True), dict(execution_eligible=True), dict(paths={"lock": "elsewhere"})])
def test_unknown_schema_and_authority_fields_rejected(specification, change):
    with pytest.raises(ValueError):
        C2AcceptanceSpecificationV1.from_dict({**specification.to_dict(), **change})


@pytest.mark.parametrize("role", list("WVM"))
def test_role_overlap_rejected(specification, role):
    data = specification.to_dict()
    data["roles"][role]["sid"] = data["roles"]["A"]["sids"][1]
    with pytest.raises(ValueError, match="distinct"):
        build_c2_e1_plan(data)


def test_duplicate_pid_rejected(specification):
    data = specification.to_dict()
    data["roles"]["W"]["pids"] = data["roles"]["A"]["pids"][:1]
    with pytest.raises(ValueError, match="PID"):
        C2AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("path", [r"C:\Users\Researcher", r"C:\Production", r"\\server\share", r"C:relative"])
def test_arbitrary_root_rejected(specification, path):
    data = specification.to_dict()
    data["deployment_root"] = path
    with pytest.raises(ValueError):
        build_c2_e1_plan(data)


def test_v1_lock_fallback_and_physical_alias_rejected(specification):
    data = specification.to_dict()
    data["identity_expectations"]["history_lock"]["resolved_path"] = v1.build_acceptance_specification(RUN_ID).paths()["history_lock"]
    with pytest.raises(ValueError, match="path"):
        C2AcceptanceSpecificationV1.from_dict(data)
    data = specification.to_dict()
    for key in ("root", "history_lock"):
        data["identity_expectations"][key].update(volume_guid=GUID, file_id="a" * 16)
    with pytest.raises(ValueError, match="alias"):
        C2AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("role", ["A", "W"])
def test_protected_identity_owner_cannot_be_agent_or_writer(specification, role):
    data = specification.to_dict()
    data["identity_expectations"]["history_lock"]["owner_sid"] = (
        data["roles"]["A"]["sids"][0] if role == "A" else data["roles"][role]["sid"])
    with pytest.raises(ValueError, match="ownership|owner"):
        C2AcceptanceSpecificationV1.from_dict(data)


def test_declared_cross_volume_e1_rejected(specification):
    data = specification.to_dict()
    data["identity_expectations"]["root"]["volume_serial"] = "1234abcd"
    data["identity_expectations"]["history_lock"]["volume_serial"] = "1234abce"
    with pytest.raises(ValueError, match="volume"):
        C2AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("digest", ["A" * 64, "g" * 64, "a" * 63, True])
def test_artifact_digest_is_a_strict_declaration(specification, digest):
    data = specification.to_dict()
    data["artifact_sha256"]["runtime"] = digest
    with pytest.raises(ValueError):
        C2AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("field,value", [("file_id", "x" * 16), ("volume_serial", 123),
    ("volume_guid", "unknown"), ("sddl", ""), ("owner_sid", "1001")])
def test_malformed_identity_declaration_rejected(specification, field, value):
    data = specification.to_dict()
    data["identity_expectations"]["history_lock"][field] = value
    with pytest.raises(ValueError):
        C2AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.0}', b'not json',
    b'[' * 5000 + b'null' + b']' * 5000, b' ' * (64 * 1024 + 1)],
    ids=["duplicate", "nonfinite", "float", "invalid-json", "deep", "oversized"])
def test_invalid_or_excessive_json_fails_without_probe(raw):
    with pytest.raises(ValueError):
        build_c2_e1_plan(raw)


def test_preparation_never_inspects_or_opens_files(specification, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("C2 preparation attempted filesystem/native operation")

    monkeypatch.setattr(builtins, "open", forbidden)
    for name in ("open", "stat", "mkdir", "remove", "rename", "replace", "chmod", "system"):
        monkeypatch.setattr(os, name, forbidden)
    monkeypatch.setattr(v1, "_backend", forbidden)
    monkeypatch.setattr(v1, "inspect_environment", forbidden)
    assert_non_executing(build_c2_e1_plan(specification))


@pytest.mark.parametrize("keyword", ["execute", "approve", "cleanup", "trust", "probe"])
def test_no_enable_switch(specification, keyword):
    with pytest.raises(TypeError):
        build_c2_e1_plan(specification, **{keyword: True})
