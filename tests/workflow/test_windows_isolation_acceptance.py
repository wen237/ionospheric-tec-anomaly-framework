"""Synthetic diagnostic observations only; no keys, Store API or ACL mutations.

Some payloads emulate the native API label to exercise comparison branches.
That string is not authenticated provenance, and no test establishes isolation.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import io
import json
import ntpath
import os
from pathlib import Path
import subprocess
import sys

import pytest

import src.workflow.windows_isolation_acceptance as module
from src.workflow.windows_isolation_acceptance import (
    ACCEPTANCE_CASES, ACCEPTANCE_PARENT, AcceptanceSpecificationV1, RESOURCE_LAYOUT,
    build_acceptance_specification, dry_run, inspect_environment, inspect_path, inspect_process,
)


RUN_ID = "11111111-1111-4111-8111-111111111111"
SIDS = {role: "S-1-5-21-111-222-333-" + str(index) for role, index in zip("AWVM", (1001, 1002, 1003, 1004))}
PIDS = dict(zip("AWVM", (101, 102, 103, 104)))
GUID = "\\\\?\\Volume{22222222-2222-4222-8222-222222222222}\\"
SDDL = "O:" + SIDS["M"] + "D:P(A;;FA;;;SY)"


@pytest.fixture
def specification():
    data = build_acceptance_specification(RUN_ID, agent_sids=[SIDS["A"]], agent_pids=[PIDS["A"]]).to_dict()
    for role in "WVM":
        data["roles"][role] = dict(sid=SIDS[role], pids=[PIDS[role]])
    data["root_expectations"].update(resolved_path=data["deployment_root"], volume_serial="1234abcd",
                                     volume_guid=GUID, owner_sid=SIDS["M"], sddl=SDDL)
    for expected in data["resource_expectations"].values():
        expected.update(owner_sid=SIDS["M"], sddl=SDDL)
    return AcceptanceSpecificationV1.from_dict(data)


class SyntheticAPI:
    # Emulates native records to exercise interpretation. NEVER OS evidence.
    evidence_source = module.NATIVE_SOURCE

    def __init__(self, spec):
        self.spec = spec
        self.data = spec.to_dict()
        self.paths = {module._path(self.data["deployment_root"]): ("root", "directory")}
        self.paths.update({module._path(path): (name, RESOURCE_LAYOUT[name][1]) for name, path in spec.paths().items()})
        self.calls = []

    def process(self, pid):
        self.calls.append(("process", pid))
        role = next(role for role in PIDS if PIDS[role] == pid)
        return dict(image_path="C:\\Synthetic\\test.exe", creation_filetime="100000000000000000",
                    token_type=1, primary_sid=SIDS[role], integrity_sid="S-1-16-8192", elevated=False,
                    elevation_type=1, groups=[], restricting_sids=[], has_restrictions=True,
                    is_app_container=False, privileges=[])

    def path(self, path):
        self.calls.append(("path", path))
        name, kind = self.paths[module._path(path)]
        index = list(self.paths).index(module._path(path))
        return dict(status="PASS", ancestors=[dict(path="C:\\", attributes=16, reparse_point=False)],
                    reason_codes=[], resolved_path="\\\\?\\" + path, attributes=16 if kind == "directory" else 32,
                    object_type=kind, reparse_point=False, volume_serial="1234abcd", volume_guid=GUID,
                    filesystem="NTFS", volume_query_matches_handle=True, file_id=f"{index:016x}", link_count=1,
                    security=dict(status="PASS", owner_sid=SIDS["M"], sddl=SDDL, dacl_present=True,
                                  null_dacl=False, inheritance_protected=True))


@pytest.fixture
def api(specification, monkeypatch):
    backend = SyntheticAPI(specification)
    monkeypatch.setattr(module, "_backend", lambda: backend)
    return backend


def assert_disabled_acceptance(checked):
    expected_ids = (
        "agent_asset_modification", "owner_and_dacl", "parent_replacement", "writer_operations",
        "verifier_read_and_lock", "verifier_data_writes", "permanent_lock_lifecycle",
        "marker_publication", "revocation", "rollback_and_interruption",
    )
    assert tuple(item["case_id"] for item in checked["acceptance_cases"]) == expected_ids
    for item in checked["acceptance_cases"]:
        assert item["status"] == "NOT_RUN"
        assert item["reason"] == "execution_disabled_in_this_checkpoint"
    assert checked["windows_local_isolation"] == "NOT VERIFIED"
    assert checked["trusted_human_authorization"] is False
    assert checked["execution_eligible"] is False
    assert checked["evidence_origin_authenticated"] is False
    assert checked["researcher_approval_verified"] is False


def result(specification):
    checked = dry_run(specification, expected_manifest_sha256=specification.content_sha256)
    assert_disabled_acceptance(checked)
    assert json.loads(json.dumps(checked, allow_nan=False)) == checked
    return checked


def prerequisite(report, name):
    return next(item for item in report["prerequisites"] if item["check"] == name)


def altered(spec, change):
    data = spec.to_dict()
    change(data)
    return AcceptanceSpecificationV1.from_dict(data)


def test_valid_spec_and_deterministic_detached_contract(specification):
    assert AcceptanceSpecificationV1.from_json(specification.to_json()) == specification
    assert AcceptanceSpecificationV1.from_dict(specification.to_dict()).content_sha256 == specification.content_sha256
    assert specification.content_sha256 == hashlib.sha256(specification.to_json().encode("utf-8")).hexdigest()
    with pytest.raises(FrozenInstanceError):
        specification._json = "{}"
    detached = specification.to_dict()
    detached["roles"]["W"]["sid"] = None
    assert specification.to_dict()["roles"]["W"]["sid"] == SIDS["W"]
    assert set(specification.paths()) == set(RESOURCE_LAYOUT)
    assert all(module._path(path).startswith(module._path(specification.to_dict()["deployment_root"]) + "\\")
               for path in specification.paths().values())


def test_matching_diagnostics_are_not_acceptance_or_approval(specification, api):
    checked = result(specification)
    assert checked["status"] == "UNKNOWN"
    assert prerequisite(checked, "role_W")["status"] == "PASS"  # comparison of emulated data only
    assert prerequisite(checked, "manifest_origin")["status"] == "UNKNOWN"
    assert len(checked["acceptance_cases"]) == 10
    assert checked == result(specification)


@pytest.mark.parametrize("role", ["W", "V", "M"])
def test_undeployed_identity_is_blocked(specification, api, role):
    changed = altered(specification, lambda data: data["roles"][role].update(sid=None, pids=[]))
    checked = result(changed)
    assert prerequisite(checked, "role_" + role)["status"] == "BLOCKED"
    assert checked["status"] == "BLOCKED"


@pytest.mark.parametrize("role", ["A", "W", "V", "M"])
def test_declared_sid_without_live_process_is_blocked(specification, api, role):
    changed = altered(specification, lambda data: data["roles"][role].update(pids=[]))
    assert prerequisite(result(changed), "role_" + role)["status"] == "BLOCKED"


@pytest.mark.parametrize("roles", [("A", "W"), ("A", "V"), ("A", "M"), ("W", "V"), ("W", "M"), ("V", "M")])
def test_overlapping_identities_are_rejected(specification, roles):
    data = specification.to_dict()
    first, second = roles
    data["roles"][second]["sid"] = SIDS[first]
    with pytest.raises(ValueError, match="distinct"):
        AcceptanceSpecificationV1.from_dict(data)
    assert dry_run(data)["status"] == "FAIL"


def test_all_agent_sids_participate_in_separation(specification):
    data = specification.to_dict()
    data["roles"]["A"]["sids"].append(SIDS["V"])
    with pytest.raises(ValueError, match="distinct"):
        AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("failure", ["denied", "wrong_sid", "not_primary", "elevated"])
def test_token_evidence_is_not_inferred(specification, api, monkeypatch, failure):
    original = api.process

    def observe(pid):
        if failure == "denied" and pid == PIDS["A"]:
            raise PermissionError("Synthetic TOKEN_QUERY denial")
        data = original(pid)
        if pid == PIDS["V"]:
            data.update({"wrong_sid": dict(primary_sid=SIDS["A"]), "not_primary": dict(token_type=2),
                         "elevated": dict(elevated=True)}.get(failure, {}))
        return data

    monkeypatch.setattr(api, "process", observe)
    checked = result(specification)
    target = "A" if failure == "denied" else "V"
    assert prerequisite(checked, "role_" + target)["status"] == ("UNKNOWN" if failure == "denied" else "FAIL")
    assert checked["inspection"]["agent_capability_coverage"] == "NOT ESTABLISHED BY SELECTED PIDS"


def test_explicit_synthetic_origin_cannot_pass_native_prerequisites(specification, api):
    api.evidence_source = "synthetic"
    checked = result(specification)
    assert prerequisite(checked, "role_W")["status"] == "UNKNOWN"
    assert prerequisite(checked, "path_history")["status"] == "UNKNOWN"


@pytest.mark.parametrize("failure", ["acl_unreadable", "missing", "redirected", "different_path", "wrong_type",
                                    "null_dacl", "owner_mismatch", "sddl_mismatch", "agent_owner", "alias"])
def test_path_evidence_failures_never_count_as_secure(specification, api, monkeypatch, failure):
    original = api.path
    history = module._path(specification.paths()["history"])

    def observe(path):
        data = original(path)
        if module._path(path) != history:
            return data
        if failure == "missing":
            error = OSError("Synthetic missing path")
            error.winerror = 2
            raise error
        if failure == "acl_unreadable":
            data["security"] = dict(status="UNKNOWN")
        elif failure == "redirected":
            data.update(status="FAIL", reparse_point=True, reason_codes=["reparse_redirection_observed"])
        elif failure == "different_path":
            data["resolved_path"] = r"C:\Users\Someone\production.json"
        elif failure == "wrong_type":
            data["object_type"] = "directory"
        elif failure == "null_dacl":
            data["security"]["null_dacl"] = True
        elif failure == "owner_mismatch":
            data["security"]["owner_sid"] = SIDS["W"]
        elif failure == "sddl_mismatch":
            data["security"]["sddl"] += "(A;;FR;;;WD)"
        elif failure == "agent_owner":
            data["security"]["owner_sid"] = SIDS["A"]
        else:
            data["file_id"] = original(specification.paths()["head"])["file_id"]
        return data

    monkeypatch.setattr(api, "path", observe)
    checked = result(specification)
    states = {item["check"]: item["status"] for item in checked["prerequisites"]}
    if failure == "alias":
        assert "FAIL" in (states["path_history"], states["path_head"])
    else:
        assert states["path_history"] == {"missing": "BLOCKED", "acl_unreadable": "UNKNOWN"}.get(failure, "FAIL")


@pytest.mark.parametrize("field,value", [("volume_serial", "ffffffff"), ("volume_guid", "wrong"),
                                        ("filesystem", "FAT32"), ("volume_query_matches_handle", False)])
def test_root_volume_identity_mismatch(specification, api, monkeypatch, field, value):
    original = api.path
    root = specification.to_dict()["deployment_root"]

    def observe(path):
        data = original(path)
        if path == root:
            data[field] = value
        return data

    monkeypatch.setattr(api, "path", observe)
    assert prerequisite(result(specification), "root_identity")["status"] == "FAIL"


def test_missing_root_and_security_expectations_block(specification, api):
    data = specification.to_dict()
    data["root_expectations"] = dict.fromkeys(data["root_expectations"])
    data["resource_expectations"]["runtime"] = dict(owner_sid=None, sddl=None)
    checked = result(AcceptanceSpecificationV1.from_dict(data))
    assert prerequisite(checked, "root_identity")["status"] == "BLOCKED"
    assert prerequisite(checked, "path_runtime")["status"] == "BLOCKED"


@pytest.mark.parametrize("pin", [None, "e" * 64])
def test_pin_is_required_and_does_not_authenticate_approval(specification, api, pin):
    checked = dry_run(specification, expected_manifest_sha256=pin)
    assert prerequisite(checked, "manifest_content")["status"] == ("BLOCKED" if pin is None else "FAIL")
    assert checked["status"] == ("BLOCKED" if pin is None else "FAIL")
    assert_disabled_acceptance(checked)


@pytest.mark.parametrize("failure", ["invalid_json", "missing_field", "malformed_field"])
def test_invalid_specification_retains_disabled_acceptance(specification, monkeypatch, failure):
    invalid = specification.to_dict()
    if failure == "invalid_json":
        invalid = b'{"specification_type":'
    elif failure == "missing_field":
        invalid.pop("roles")
    else:
        invalid["roles"]["W"]["pids"] = "not-a-list"
    monkeypatch.setattr(module, "inspect_environment", lambda **kwargs: pytest.fail("Invalid spec was inspected"))
    checked = dry_run(invalid, expected_manifest_sha256=specification.content_sha256)
    assert checked["status"] == "FAIL"
    assert checked["inspection"] is None
    assert_disabled_acceptance(checked)


@pytest.mark.parametrize("pin", ["", "a" * 63, "A" * 64, "g" * 64, 123])
def test_invalid_manifest_format_retains_disabled_acceptance(specification, monkeypatch, pin):
    monkeypatch.setattr(module, "inspect_environment", lambda **kwargs: pytest.fail("Invalid pin was inspected"))
    checked = dry_run(specification, expected_manifest_sha256=pin)
    assert checked["status"] == "FAIL"
    assert checked["inspection"] is None
    assert_disabled_acceptance(checked)


@pytest.mark.parametrize("root", ["C:\\", r"C:\Users\Researcher", r"C:\Work\repo", r"C:\Work\repo\.venv",
                                 r"C:\Production\store", "C:\\ProgramData\\Other\\" + RUN_ID])
def test_root_cannot_be_selected_arbitrarily(specification, root):
    data = specification.to_dict()
    data["deployment_root"] = root
    with pytest.raises(ValueError):
        AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("path", ["relative", r"C:relative", r"\\server\share\a", r"\\?\C:\a",
                                 "C:\\safe\\..\\other", "C:\\safe\\.\\file", "C:\\safe\\file ",
                                 "C:\\safe\\file.", "C:\\safe\\file:stream", "C:\\safe\\*", r"C:\NUL"])
def test_ambiguous_or_device_inspection_paths_are_rejected(path):
    with pytest.raises(ValueError):
        inspect_path(path)


@pytest.mark.parametrize("pid", [0, -1, True, 1.0, "123", 2**32])
def test_invalid_pid_rejected_before_api_call(pid, monkeypatch):
    monkeypatch.setattr(module, "_backend", lambda: pytest.fail("Invalid PID reached native APIs"))
    with pytest.raises(ValueError):
        inspect_process(pid)


@pytest.mark.parametrize("change", [dict(schema_version=True), dict(schema_version=2), dict(trust=True),
                                   dict(execution_eligible=True), dict(purpose="production"), dict(extra="field")])
def test_unsupported_schema_and_claimed_trust_rejected(specification, change):
    data = specification.to_dict()
    data.update(change)
    with pytest.raises(ValueError):
        AcceptanceSpecificationV1.from_dict(data)


def test_unexpected_resource_path_or_missing_asset_rejected(specification):
    for kind in ("extra_path", "missing_asset"):
        data = specification.to_dict()
        if kind == "extra_path":
            data["resource_expectations"]["registry"]["path"] = r"C:\Other\registry.json"
        else:
            data["resource_expectations"].pop("history_lock")
        with pytest.raises(ValueError):
            AcceptanceSpecificationV1.from_dict(data)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.0}', b'{"a":-0}',
                                b'[' * 5000 + b'null' + b']' * 5000, b' ' * (module.MAX_SPEC_BYTES + 1)],
                         ids=["duplicate", "nan", "float", "negative_zero", "deep", "oversized"])
def test_bounded_strict_json_failure_has_no_inspection(raw, monkeypatch):
    monkeypatch.setattr(module, "inspect_environment", lambda **kwargs: pytest.fail("Invalid spec was inspected"))
    assert dry_run(raw)["status"] == "FAIL"


def test_native_cycle_rejected_without_recursion_escape():
    data = {}
    data["cycle"] = data
    assert dry_run(data)["status"] == "FAIL"


def test_malformed_volume_guid_rejected(specification):
    data = specification.to_dict()
    data["root_expectations"]["volume_guid"] = "\\\\?\\Volume{" + "-" * 36 + "}\\"
    with pytest.raises(ValueError, match="volume GUID"):
        AcceptanceSpecificationV1.from_dict(data)


def test_selector_bounds_and_no_enumeration(specification, api):
    with pytest.raises(ValueError):
        inspect_environment()
    with pytest.raises(ValueError):
        inspect_environment(process_ids=list(range(1, module.MAX_TARGETS + 2)))
    checked = inspect_environment(process_ids=[101, 101], paths=[specification.paths()["history"]])
    assert len(checked["processes"]) == 1
    assert [item[0] for item in api.calls] == ["process", "path"]
    assert checked["execution_eligible"] is False


def test_dry_run_never_mutates_files_or_invokes_external_operations(specification, api, monkeypatch, tmp_path):
    sentinel = tmp_path / "synthetic-sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    before = sentinel.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Dry run attempted mutation/subprocess/content access")

    for name in ("open", "write_text", "write_bytes", "unlink", "rename", "replace", "mkdir", "rmdir"):
        monkeypatch.setattr(Path, name, forbidden)
    for name in ("open", "remove", "unlink", "rename", "replace", "mkdir", "rmdir", "chmod", "system"):
        monkeypatch.setattr(os, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    checked = result(specification)
    assert checked["status"] != "PASS"
    monkeypatch.undo()
    assert sentinel.read_bytes() == before


def test_harness_does_not_import_authorization_science_or_key_libraries():
    script = """
import runpy, sys
runpy.run_path(sys.argv[1], run_name='inspection_import_only')
for name in sys.modules:
    assert not name.startswith(('numpy', 'cryptography', 'src.workflow.planning_',
        'src.workflow.signed_authorization', 'src.workflow.authorization_store',
        'src.workflow.local_authorizer', 'src.workflow.stage2', 'src.spatial_verification'))
"""
    completed = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, module.__file__],
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr


def test_unrelated_programming_error_is_not_suppressed(monkeypatch):
    class Broken:
        evidence_source = module.NATIVE_SOURCE

        def process(self, pid):
            raise RuntimeError("Programming defect")

    monkeypatch.setattr(module, "_backend", Broken)
    with pytest.raises(RuntimeError, match="Programming"):
        inspect_process(123)


@pytest.mark.parametrize("option", ["--execute", "--cleanup", "--root", "--trust", "--assume-authorized"])
def test_cli_has_no_execution_or_bypass_options(option):
    with pytest.raises(SystemExit) as caught:
        module.main(["inspect", option])
    assert caught.value.code == 2


def test_cli_dry_run_stdin_only_and_never_success_acceptance(specification, api, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(specification.to_json().encode("utf-8"))))
    assert module.main(["dry-run", "--expected-manifest-sha256", specification.content_sha256]) == 2
    checked = json.loads(capsys.readouterr().out)
    assert checked["mode"] == "dry_run" and checked["execution_eligible"] is False


@pytest.mark.skipif(os.name != "nt", reason="Requires native Windows TOKEN_QUERY APIs.")
def test_native_current_process_query_only_smoke(monkeypatch):
    backend = module._backend()
    process_open, token_open = backend.k.OpenProcess, backend.a.OpenProcessToken
    accesses = []

    def query_process(access, inherit, pid):
        assert access == 0x1000 and not inherit and pid == os.getpid()
        accesses.append("QUERY_LIMITED_INFORMATION")
        return process_open(access, inherit, pid)

    def query_token(process, access, token):
        assert access == 0x8
        accesses.append("TOKEN_QUERY")
        return token_open(process, access, token)

    monkeypatch.setattr(backend.k, "OpenProcess", query_process)
    monkeypatch.setattr(backend.a, "OpenProcessToken", query_token)
    monkeypatch.setattr(module, "_backend", lambda: backend)
    checked = inspect_process(os.getpid())
    if checked["status"] == "UNKNOWN":
        pytest.skip("Current process token unavailable to read-only diagnostic.")
    assert checked["status"] == "PASS" and checked["token_type"] == 1
    assert checked["primary_sid"].startswith("S-1-")
    assert type(checked["elevated"]) is bool
    assert isinstance(checked["restricting_sids"], list)
    assert "command_line" not in checked and "environment" not in checked
    assert accesses == ["QUERY_LIMITED_INFORMATION", "TOKEN_QUERY"]


@pytest.mark.skipif(os.name != "nt", reason="Requires native Windows metadata/READ_CONTROL APIs.")
def test_native_source_metadata_no_content_read_smoke(monkeypatch):
    backend = module._backend()
    file_open = backend.k.CreateFileW
    selected = str(Path(module.__file__).resolve())
    accesses = []

    def metadata_open(path, access, sharing, security, disposition, flags, template):
        assert path == selected and access in (0x20080, 0x80)
        assert sharing == 7 and security is None and disposition == 3
        assert flags == 0x02200000 and template is None
        accesses.append(access)
        return file_open(path, access, sharing, security, disposition, flags, template)

    monkeypatch.setattr(backend.k, "CreateFileW", metadata_open)
    monkeypatch.setattr(module, "_backend", lambda: backend)
    checked = inspect_path(selected)
    if checked["status"] == "UNKNOWN":
        pytest.skip("Source metadata or ACL unavailable under this token.")
    if checked["status"] == "FAIL":
        pytest.skip("Source path has reparse redirection; no direct-path smoke environment.")
    assert checked["status"] == "PASS"
    assert checked["object_type"] == "file" and not checked["reparse_point"]
    assert checked["security"]["status"] == "PASS"
    assert checked["volume_guid"] is not None
    assert "content" not in checked
    assert accesses == [0x20080]
