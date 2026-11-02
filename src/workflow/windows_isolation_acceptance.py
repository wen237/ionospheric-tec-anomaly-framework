"""Read-only Windows diagnostics and a NON-EXECUTING acceptance specification.

Standard library only; no authorization/scientific modules are imported. PID
handles request QUERY_LIMITED_INFORMATION, tokens TOKEN_QUERY. Path handles
request READ_CONTROL/READ_ATTRIBUTES, OPEN_EXISTING, never data access. There is
no write/delete/rename/ACL setter, signer, Store API, account provisioning,
cleanup, elevation or execution dispatcher. PASS describes one observed fact or
schema check, NEVER Windows isolation, effective access or human authorization.

All observations are point-in-time, unauthenticated diagnostics. Selected PIDs
do not establish complete Agent capability coverage. No Python object, content
pin or mocked observation establishes a trusted deployment. See
docs/windows_isolation_acceptance.md. Future destructive tests need a separately
reviewed, protected launcher and researcher approval; none is implemented here.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
import ntpath
import os
import re
import sys
from uuid import UUID


MAX_SPEC_BYTES = 64 * 1024
MAX_DEPTH = 16
MAX_TARGETS = 32
MAX_API_BYTES = 1024 * 1024
ACCEPTANCE_PARENT = r"C:\ProgramData\TEC-Authorization-Acceptance"
NATIVE_SOURCE = "native_windows_api"
RESOURCE_LAYOUT = {
    "runtime": (r"release\runtime", "directory"),
    "python_executable": (r"release\runtime\python.exe", "file"),
    "application": (r"release\app", "directory"),
    "dependencies": (r"release\deps", "directory"),
    "registry": (r"anchors\registry.json", "file"),
    "bootstrap": (r"bootstrap\manifest.json", "file"),
    "configuration": (r"anchors\verifier.json", "file"),
    "store_root": (r"authority\store", "directory"),
    "history": (r"authority\store\history.jsonl", "file"),
    "head": (r"authority\store\head.json", "file"),
    "local_checkpoint": (r"authority\store\checkpoint.json", "file"),
    "history_lock": (r"authority\store\history.lock", "file"),
    "independent_checkpoint": (r"anchors\minimum-checkpoint.json", "file"),
    "writer_diagnostics": (r"logs\writer", "directory"),
    "verifier_diagnostics": (r"logs\verifier", "directory"),
}
ACCEPTANCE_CASES = {
    "agent_asset_modification": "A write/replace of code, runtime, dependencies and anchors is denied.",
    "owner_and_dacl": "A WRITE_DAC/WRITE_OWNER is denied; actual owner/SDDL remains unchanged.",
    "parent_replacement": "A DELETE/DELETE_CHILD/rename/reparse parent bypass is denied.",
    "writer_operations": "W performs valid signed synthetic Store operations and permanent locking.",
    "verifier_read_and_lock": "V reads the full Store and opens only the existing lock with r+b; no broad Store writes.",
    "verifier_data_writes": "V cannot modify history, head, local/external checkpoint, registry or bootstrap.",
    "permanent_lock_lifecycle": "A/W/V cannot delete or replace the permanent lock; missing lock is not recreated by readers/appends.",
    "marker_publication": "W temporary-file creation and marker replacement preserve reviewed owner/inherited DACL policy.",
    "revocation": "A later valid revocation prevents fallback to an older approved decision.",
    "rollback_and_interruption": "Rollback below a retained newer floor, conflicting/partial publication and missing anchors fail closed; an old floor alone cannot prove freshness.",
}


def _native(value, depth=0, budget=None):
    if budget is None:
        budget = [MAX_SPEC_BYTES - 1]

    def charge(size):
        budget[0] -= size
        if budget[0] < 0:
            raise ValueError("Specification size limit exceeded.")

    if value is None or type(value) is bool:
        charge(4 if value is None or value is True else 5)
        return value
    if type(value) is str:
        if len(value) > MAX_SPEC_BYTES:
            raise ValueError("Specification string too large.")
        charge(len(json.dumps(value, ensure_ascii=False).encode("utf-8", "strict")))
        return value
    if type(value) is int and 0 <= value <= 2**53 - 1:
        charge(len(str(value)))
        return value
    if type(value) in (dict, list):
        if depth >= MAX_DEPTH:
            raise ValueError("Specification nesting limit exceeded.")
        charge(2 + max(0, len(value) - 1) + (len(value) if type(value) is dict else 0))
        if type(value) is list:
            return [_native(item, depth + 1, budget) for item in value]
        if all(type(key) is str for key in value):
            return {_native(key, depth + 1, budget): _native(item, depth + 1, budget)
                    for key, item in value.items()}
    raise ValueError("Only bounded native JSON, without floats, is supported.")


def _canonical(value):
    try:
        return json.dumps(_native(value), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False) + "\n"
    except RecursionError as exc:
        raise ValueError("Specification encoder nesting exceeded.") from exc


def _load(raw):
    if type(raw) is str:
        if len(raw) > MAX_SPEC_BYTES:
            raise ValueError("Specification too large.")
        raw = raw.encode("utf-8", "strict")
    if type(raw) is not bytes or len(raw) > MAX_SPEC_BYTES:
        raise ValueError("Expected bounded UTF-8 specification.")
    text = raw.decode("utf-8", "strict")
    if text.startswith("\ufeff"):
        raise ValueError("BOM is unsupported.")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate specification field.")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("Unsupported JSON number.")

    def integer(value):
        if value.startswith("-") or len(value) > 16:
            raise ValueError("Unsupported JSON integer.")
        return _native(int(value))

    try:
        return _native(json.loads(text, object_pairs_hook=unique, parse_float=reject,
                                  parse_constant=reject, parse_int=integer))
    except RecursionError as exc:
        raise ValueError("Specification decoder nesting exceeded.") from exc


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("Missing, unexpected or malformed specification fields.")


def _sid(value):
    if type(value) is not str or not re.fullmatch(r"S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}", value):
        raise ValueError("Expected canonical SID notation, not an account name.")
    parts = [int(item) for item in value.split("-")[2:]]
    if parts[0] >= 2**48 or any(item >= 2**32 for item in parts[1:]):
        raise ValueError("SID component out of range.")


def _pid(value):
    if type(value) is not int or not 1 <= value <= 2**32 - 1:
        raise ValueError("Expected an explicit positive Windows PID.")


def _path(value):
    if (type(value) is not str or not 3 <= len(value) <= 1024 or
            not re.match(r"^[A-Za-z]:\\", value) or "/" in value or ":" in value[2:] or
            any(ord(char) < 32 for char in value) or any(char in value for char in '*?"<>|')):
        raise ValueError("Expected explicit absolute local DOS path, without devices/ADS/wildcards.")
    parts = value[3:].split("\\") if len(value) > 3 else []
    for part in parts:
        if (not part or part in (".", "..") or part.endswith((".", " ")) or
                re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", part.split(".")[0], re.I)):
            raise ValueError("Ambiguous/reserved path component.")
    return ntpath.normcase(value)


def _observed_path(value):
    if type(value) is str and value.startswith("\\\\?\\"):
        value = value[4:]
    return _path(value)


def _hash(value):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Expected lowercase SHA-256.")


def _flags():
    return dict(windows_local_isolation="NOT VERIFIED", trusted_human_authorization=False,
                execution_eligible=False, evidence_origin_authenticated=False)


def _unknown(kind, selector, reason, winerror=None):
    return dict(kind=kind, selector=selector, status="UNKNOWN", evidence_source="unavailable",
                reason_codes=[reason], winerror=winerror)


class _WindowsAPI:
    """Query-only Win32 implementation; no process/data/ACL modification handles."""
    evidence_source = NATIVE_SOURCE

    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c, w
        self.k = c.WinDLL("kernel32", use_last_error=True)
        self.a = c.WinDLL("advapi32", use_last_error=True)

        class SA(c.Structure):
            _fields_ = [("sid", w.LPVOID), ("attrs", w.DWORD)]

        class Groups(c.Structure):
            _fields_ = [("count", w.DWORD), ("items", SA * 1)]

        class Luid(c.Structure):
            _fields_ = [("low", w.DWORD), ("high", w.LONG)]

        class Privilege(c.Structure):
            _fields_ = [("luid", Luid), ("attrs", w.DWORD)]

        class Privileges(c.Structure):
            _fields_ = [("count", w.DWORD), ("items", Privilege * 1)]

        class FileInfo(c.Structure):
            _fields_ = [("attrs", w.DWORD), ("creation", w.FILETIME), ("access", w.FILETIME),
                        ("write", w.FILETIME), ("volume", w.DWORD), ("size_high", w.DWORD),
                        ("size_low", w.DWORD), ("links", w.DWORD), ("index_high", w.DWORD), ("index_low", w.DWORD)]

        self.SA, self.Groups, self.Privilege, self.Privileges, self.FileInfo = SA, Groups, Privilege, Privileges, FileInfo
        signatures = {
            "OpenProcess": (w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
            "CloseHandle": (w.BOOL, [w.HANDLE]),
            "LocalFree": (w.LPVOID, [w.LPVOID]),
            "QueryFullProcessImageNameW": (w.BOOL, [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]),
            "GetProcessTimes": (w.BOOL, [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4),
            "GetFileAttributesW": (w.DWORD, [w.LPCWSTR]),
            "CreateFileW": (w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]),
            "GetFileInformationByHandle": (w.BOOL, [w.HANDLE, c.POINTER(FileInfo)]),
            "GetFinalPathNameByHandleW": (w.DWORD, [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD]),
            "GetVolumePathNameW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, w.DWORD]),
            "GetVolumeInformationW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, w.DWORD, c.POINTER(w.DWORD),
                                              c.POINTER(w.DWORD), c.POINTER(w.DWORD), w.LPWSTR, w.DWORD]),
        }
        security = {
            "OpenProcessToken": (w.BOOL, [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]),
            "GetTokenInformation": (w.BOOL, [w.HANDLE, c.c_int, w.LPVOID, w.DWORD, c.POINTER(w.DWORD)]),
            "ConvertSidToStringSidW": (w.BOOL, [w.LPVOID, c.POINTER(w.LPWSTR)]),
            "LookupPrivilegeNameW": (w.BOOL, [w.LPCWSTR, c.POINTER(Luid), w.LPWSTR, c.POINTER(w.DWORD)]),
            "GetSecurityInfo": (w.DWORD, [w.HANDLE, c.c_int, w.DWORD] + [c.POINTER(w.LPVOID)] * 5),
            "GetSecurityDescriptorControl": (w.BOOL, [w.LPVOID, c.POINTER(w.WORD), c.POINTER(w.DWORD)]),
            "GetSecurityDescriptorDacl": (w.BOOL, [w.LPVOID, c.POINTER(w.BOOL), c.POINTER(w.LPVOID), c.POINTER(w.BOOL)]),
            "ConvertSecurityDescriptorToStringSecurityDescriptorW": (w.BOOL, [w.LPVOID, w.DWORD, w.DWORD,
                                                                             c.POINTER(w.LPWSTR), c.POINTER(w.DWORD)]),
        }
        for library, mapping in ((self.k, signatures), (self.a, security)):
            for name, (restype, argtypes) in mapping.items():
                function = getattr(library, name)
                function.restype, function.argtypes = restype, argtypes

    def check(self, success):
        if not success:
            raise self.c.WinError(self.c.get_last_error())

    def sid(self, pointer):
        value = self.w.LPWSTR()
        self.check(self.a.ConvertSidToStringSidW(pointer, self.c.byref(value)))
        try:
            return value.value
        finally:
            self.k.LocalFree(self.c.cast(value, self.w.LPVOID))

    def token_info(self, token, kind):
        size = self.w.DWORD()
        self.a.GetTokenInformation(token, kind, None, 0, self.c.byref(size))
        if not 0 < size.value <= MAX_API_BYTES:
            raise OSError("Unavailable or oversized token information.")
        buf = self.c.create_string_buffer(size.value)
        self.check(self.a.GetTokenInformation(token, kind, buf, size, self.c.byref(size)))
        return buf

    def number(self, token, kind):
        return int.from_bytes(self.token_info(token, kind).raw[:4], "little")

    def groups(self, token, kind):
        buf = self.token_info(token, kind)
        count = self.w.DWORD.from_buffer(buf).value
        if count > 256:
            raise OSError("Group-count resource limit exceeded.")
        if not count:
            return []
        array = (self.SA * count).from_buffer(buf, self.Groups.items.offset)
        return [dict(sid=self.sid(item.sid), attributes=item.attrs, enabled=bool(item.attrs & 4),
                     deny_only=bool(item.attrs & 16)) for item in array]

    def privileges(self, token):
        buf = self.token_info(token, 3)
        count = self.w.DWORD.from_buffer(buf).value
        if count > 128:
            raise OSError("Privilege-count resource limit exceeded.")
        if not count:
            return []
        result = []
        for item in (self.Privilege * count).from_buffer(buf, self.Privileges.items.offset):
            size = self.w.DWORD()
            self.a.LookupPrivilegeNameW(None, self.c.byref(item.luid), None, self.c.byref(size))
            if not 0 < size.value < 1024:
                raise OSError("Unavailable privilege name.")
            text = self.c.create_unicode_buffer(size.value + 1)
            size.value = len(text)
            self.check(self.a.LookupPrivilegeNameW(None, self.c.byref(item.luid), text, self.c.byref(size)))
            result.append(dict(name=text.value, attributes=item.attrs, enabled=bool(item.attrs & 2)))
        return result

    def process(self, pid):
        process = self.k.OpenProcess(0x1000, False, pid)
        self.check(process)
        token = self.w.HANDLE()
        try:
            size = self.w.DWORD(32768)
            image = self.c.create_unicode_buffer(size.value)
            self.check(self.k.QueryFullProcessImageNameW(process, 0, image, self.c.byref(size)))
            times = [self.w.FILETIME() for _ in range(4)]
            self.check(self.k.GetProcessTimes(process, *(self.c.byref(item) for item in times)))
            self.check(self.a.OpenProcessToken(process, 0x0008, self.c.byref(token)))
            user, integrity = self.token_info(token, 1), self.token_info(token, 25)
            return dict(image_path=image.value, creation_filetime=str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime),
                        token_type=self.number(token, 8), primary_sid=self.sid(self.SA.from_buffer(user).sid),
                        integrity_sid=self.sid(self.SA.from_buffer(integrity).sid), elevated=bool(self.number(token, 20)),
                        elevation_type=self.number(token, 18), groups=self.groups(token, 2),
                        restricting_sids=self.groups(token, 11), has_restrictions=bool(self.number(token, 21)),
                        is_app_container=bool(self.number(token, 29)), privileges=self.privileges(token))
        finally:
            if token.value:
                self.k.CloseHandle(token)
            self.k.CloseHandle(process)

    def security(self, handle):
        owner, group, dacl, sacl, sd = [self.w.LPVOID() for _ in range(5)]
        error = self.a.GetSecurityInfo(handle, 1, 5, *(self.c.byref(item) for item in (owner, group, dacl, sacl, sd)))
        if error:
            raise self.c.WinError(error)
        text = self.w.LPWSTR()
        try:
            control, revision = self.w.WORD(), self.w.DWORD()
            self.check(self.a.GetSecurityDescriptorControl(sd, self.c.byref(control), self.c.byref(revision)))
            present, defaulted, acl = self.w.BOOL(), self.w.BOOL(), self.w.LPVOID()
            self.check(self.a.GetSecurityDescriptorDacl(sd, self.c.byref(present), self.c.byref(acl), self.c.byref(defaulted)))
            length = self.w.DWORD()
            self.check(self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, 5, self.c.byref(text), self.c.byref(length)))
            if length.value > 32768:
                raise OSError("SDDL resource limit exceeded.")
            return dict(status="PASS", owner_sid=self.sid(owner), sddl=text.value,
                        dacl_present=bool(present), null_dacl=not bool(acl),
                        inheritance_protected=bool(control.value & 0x1000))
        finally:
            if text:
                self.k.LocalFree(self.c.cast(text, self.w.LPVOID))
            if sd:
                self.k.LocalFree(sd)

    def path(self, path):
        ancestors, current = [], path
        while current:
            ancestors.append(current)
            parent = ntpath.dirname(current)
            if parent == current:
                break
            current = parent
        if len(ancestors) > 32:
            raise ValueError("Path-depth resource limit exceeded.")
        observations = []
        for ancestor in reversed(ancestors):
            attrs = self.k.GetFileAttributesW(ancestor)
            if attrs == 0xffffffff:
                raise self.c.WinError(self.c.get_last_error())
            observations.append(dict(path=ancestor, attributes=attrs, reparse_point=bool(attrs & 0x400)))
            if attrs & 0x400:
                return dict(status="FAIL", ancestors=observations, reason_codes=["reparse_redirection_observed"])
        # OPEN_EXISTING + BACKUP_SEMANTICS + OPEN_REPARSE_POINT, full sharing.
        invalid = self.c.c_void_p(-1).value
        handle = self.k.CreateFileW(path, 0x20080, 7, None, 3, 0x02200000, None)
        if handle == invalid:
            handle = self.k.CreateFileW(path, 0x80, 7, None, 3, 0x02200000, None)
        if handle == invalid:
            raise self.c.WinError(self.c.get_last_error())
        try:
            info = self.FileInfo()
            self.check(self.k.GetFileInformationByHandle(handle, self.c.byref(info)))
            final = self.c.create_unicode_buffer(32768)
            length = self.k.GetFinalPathNameByHandleW(handle, final, len(final), 0)
            self.check(length)
            if length >= len(final):
                raise OSError("Resolved path resource limit exceeded.")
            guid_path = self.c.create_unicode_buffer(32768)
            length = self.k.GetFinalPathNameByHandleW(handle, guid_path, len(guid_path), 1)
            self.check(length)
            if length >= len(guid_path):
                raise OSError("Volume path resource limit exceeded.")
            volume = re.match(r"^(\\\\\?\\Volume\{[^}]+\}\\)", guid_path.value)
            mount, fsname = self.c.create_unicode_buffer(32768), self.c.create_unicode_buffer(256)
            self.check(self.k.GetVolumePathNameW(final.value, mount, len(mount)))
            serial, maxpart, flags = self.w.DWORD(), self.w.DWORD(), self.w.DWORD()
            self.check(self.k.GetVolumeInformationW(mount.value, None, 0, self.c.byref(serial),
                                                   self.c.byref(maxpart), self.c.byref(flags), fsname, len(fsname)))
            try:
                security = self.security(handle)
            except OSError as exc:
                security = dict(status="UNKNOWN", reason_codes=["acl_unavailable"], winerror=getattr(exc, "winerror", None))
            reparse = bool(info.attrs & 0x400)
            return dict(status="FAIL" if reparse else security["status"], ancestors=observations,
                        reason_codes=["reparse_redirection_observed"] if reparse else security.get("reason_codes", []),
                        resolved_path=final.value, attributes=info.attrs,
                        object_type="directory" if info.attrs & 0x10 else "file", reparse_point=reparse,
                        volume_serial=f"{info.volume:08x}", volume_guid=volume.group(1) if volume else None,
                        filesystem=fsname.value, volume_query_matches_handle=(serial.value == info.volume),
                        file_id=f"{info.index_high:08x}{info.index_low:08x}", link_count=info.links, security=security)
        finally:
            self.k.CloseHandle(handle)


def _backend():
    if os.name != "nt":
        raise OSError("Native Windows is required.")
    return _WindowsAPI()


def inspect_process(pid: int) -> dict:
    """Explicit PID primary-token query, never process-owner/parent inference."""
    _pid(pid)
    try:
        backend = _backend()
        return dict(kind="process", selector=pid, status="PASS", reason_codes=[],
                    evidence_source=backend.evidence_source, **backend.process(pid))
    except OSError as exc:
        return _unknown("process", pid, "process_evidence_unavailable", getattr(exc, "winerror", None))


def inspect_path(path: str) -> dict:
    """Read selected path metadata and ancestor reparse attributes; no file bytes.

    DACL SDDL is descriptive, NOT effective access. Handles never request data
    read/write, DELETE, WRITE_DAC/OWNER, or SACL access. No reparse traversal is
    intentionally performed. Ancestor prechecks/handle observations are NOT a
    race-free trusted-open guarantee; no future write action follows these reads.
    """
    _path(path)
    try:
        backend = _backend()
        return dict(kind="path", selector=path, evidence_source=backend.evidence_source, **backend.path(path))
    except OSError as exc:
        reason = "path_missing" if getattr(exc, "winerror", None) in (2, 3) else "path_evidence_unavailable"
        return _unknown("path", path, reason, getattr(exc, "winerror", None))


def inspect_environment(*, process_ids=(), paths=()) -> dict:
    """Inspect selected targets only, never enumerate processes or directories."""
    if (type(process_ids) not in (list, tuple) or type(paths) not in (list, tuple) or
            len(process_ids) > MAX_TARGETS or len(paths) > MAX_TARGETS or not (process_ids or paths)):
        raise ValueError("Explicit bounded selector lists are required.")
    for pid in process_ids:
        _pid(pid)
    for path in paths:
        _path(path)
    processes = [inspect_process(pid) for pid in dict.fromkeys(process_ids)]
    selected_paths = [inspect_path(path) for path in dict.fromkeys(paths)]
    statuses = {item["status"] for item in processes + selected_paths}
    return dict(report_type="windows_read_only_inspection", schema_version=1, mode="inspect",
                status=next((value for value in ("FAIL", "UNKNOWN") if value in statuses), "PASS"),
                processes=processes, paths=selected_paths,
                agent_capability_coverage="NOT ESTABLISHED BY SELECTED PIDS", **_flags())


@dataclass(frozen=True)
class AcceptanceSpecificationV1:
    """Immutable proposed test layout; NOT a researcher-authenticated approval."""
    _json: str

    def __post_init__(self):
        data = _load(self._json)
        _fields(data, ("specification_type", "schema_version", "purpose", "run_id", "deployment_root",
                       "roles", "root_expectations", "resource_expectations"))
        if (data["specification_type"] != "windows_isolation_acceptance_specification" or
                type(data["schema_version"]) is not int or data["schema_version"] != 1 or
                data["purpose"] != "disposable_synthetic_only"):
            raise ValueError("Unsupported acceptance specification.")
        run_id = data["run_id"]
        if type(run_id) is not str or str(UUID(run_id)) != run_id or UUID(run_id).version != 4:
            raise ValueError("A canonical UUIDv4 run ID is required.")
        if _path(data["deployment_root"]) != _path(ntpath.join(ACCEPTANCE_PARENT, run_id)):
            raise ValueError("Root must be the fixed acceptance parent plus this run ID.")
        roles = data["roles"]
        _fields(roles, ("A", "W", "V", "M"))
        assigned, pids = set(), set()
        for role, value in roles.items():
            _fields(value, ("sids", "pids") if role == "A" else ("sid", "pids"))
            sids = value["sids"] if role == "A" else ([] if value["sid"] is None else [value["sid"]])
            if type(sids) is not list or not len(sids) <= MAX_TARGETS:
                raise ValueError("Invalid role SID list.")
            for sid in sids:
                _sid(sid)
                if sid in assigned:
                    raise ValueError("Role identities must be distinct, including every Agent SID.")
                assigned.add(sid)
            if type(value["pids"]) is not list or len(value["pids"]) > 8:
                raise ValueError("Explicit bounded role PID lists are required.")
            for pid in value["pids"]:
                _pid(pid)
                if pid in pids:
                    raise ValueError("A PID cannot serve two roles or occur twice.")
                pids.add(pid)
        if len(pids) > MAX_TARGETS:
            raise ValueError("Too many process selectors.")
        root = data["root_expectations"]
        _fields(root, ("resolved_path", "volume_serial", "volume_guid", "owner_sid", "sddl"))
        if root["resolved_path"] is not None and _path(root["resolved_path"]) != _path(data["deployment_root"]):
            raise ValueError("Expected resolved root must match the exact proposed root.")
        if root["volume_serial"] is not None and (type(root["volume_serial"]) is not str or not re.fullmatch("[0-9a-f]{8}", root["volume_serial"])):
            raise ValueError("Invalid volume serial expectation.")
        if root["volume_guid"] is not None and (type(root["volume_guid"]) is not str or not re.fullmatch(
                r"\\\\\?\\Volume\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}\\", root["volume_guid"])):
            raise ValueError("Invalid volume GUID expectation.")
        _fields(data["resource_expectations"], RESOURCE_LAYOUT)
        for name, expected in [("root", root)] + list(data["resource_expectations"].items()):
            if name != "root":
                _fields(expected, ("owner_sid", "sddl"))
            if expected["owner_sid"] is not None:
                _sid(expected["owner_sid"])
                if expected["owner_sid"] in roles["A"]["sids"]:
                    raise ValueError("Agent ownership is not an acceptable protected-resource expectation.")
            if expected["sddl"] is not None and (type(expected["sddl"]) is not str or not expected["sddl"] or len(expected["sddl"]) > 32768):
                raise ValueError("Expected exact native owner/DACL SDDL or null.")
        object.__setattr__(self, "_json", _canonical(data))

    @classmethod
    def from_dict(cls, data):
        return cls(_canonical(data))

    @classmethod
    def from_json(cls, text):
        return cls(text)

    def to_dict(self):
        return json.loads(self._json)

    def to_json(self):
        return self._json

    @property
    def content_sha256(self):
        return hashlib.sha256(self._json.encode("utf-8")).hexdigest()

    def paths(self):
        root = self.to_dict()["deployment_root"]
        return {name: ntpath.join(root, relative) for name, (relative, _) in RESOURCE_LAYOUT.items()}


def build_acceptance_specification(run_id: str, *, agent_sids=(), agent_pids=()) -> AcceptanceSpecificationV1:
    """Pure incomplete template; creates NO directory, identity, key or approval."""
    return AcceptanceSpecificationV1.from_dict(dict(
        specification_type="windows_isolation_acceptance_specification", schema_version=1,
        purpose="disposable_synthetic_only", run_id=run_id, deployment_root=ntpath.join(ACCEPTANCE_PARENT, run_id),
        roles={"A": dict(sids=list(agent_sids), pids=list(agent_pids)),
               **{role: dict(sid=None, pids=[]) for role in ("W", "V", "M")}},
        root_expectations=dict(resolved_path=None, volume_serial=None, volume_guid=None, owner_sid=None, sddl=None),
        resource_expectations={name: dict(owner_sid=None, sddl=None) for name in RESOURCE_LAYOUT},
    ))


def dry_run(specification, *, expected_manifest_sha256=None) -> dict:
    """Validate declarations and collect metadata; NEVER execute acceptance cases.

    Manifest pin matches canonical spec content, not publisher/researcher identity.
    No option can bypass missing prerequisites or enable effective-access tests.
    All ten cases remain explicitly NOT_RUN, including for invalid input.
    """
    acceptance_cases = [dict(case_id=name, expected_outcome=description, status="NOT_RUN",
                             reason="execution_disabled_in_this_checkpoint")
                        for name, description in ACCEPTANCE_CASES.items()]
    result = dict(report_type="windows_isolation_acceptance_dry_run", schema_version=1, mode="dry_run",
                  status="BLOCKED", specification_valid=False, specification_content_sha256=None,
                  manifest_content_matches_pin=False, researcher_approval_verified=False,
                  prerequisites=[], acceptance_cases=acceptance_cases, inspection=None, **_flags())

    def add(name, status, reason):
        result["prerequisites"].append(dict(check=name, status=status, reason=reason))

    try:
        if isinstance(specification, AcceptanceSpecificationV1):
            specification = AcceptanceSpecificationV1.from_json(specification.to_json())
        elif type(specification) is dict:
            specification = AcceptanceSpecificationV1.from_dict(specification)
        else:
            specification = AcceptanceSpecificationV1.from_json(specification)
        if expected_manifest_sha256 is not None:
            _hash(expected_manifest_sha256)
    except (TypeError, ValueError, OverflowError, RecursionError):
        add("specification", "FAIL", "invalid_specification_or_manifest_pin")
        result["status"] = "FAIL"
        return result
    data = specification.to_dict()
    result.update(specification_valid=True, specification_content_sha256=specification.content_sha256)
    add("specification", "PASS", "strict_schema_and_role_separation_declarations")
    if expected_manifest_sha256 is None:
        add("manifest_content", "BLOCKED", "independent_manifest_pin_not_supplied")
    else:
        matches = expected_manifest_sha256 == specification.content_sha256
        result["manifest_content_matches_pin"] = matches
        add("manifest_content", "PASS" if matches else "FAIL", "content_identity_only_not_approval")
    add("manifest_origin", "UNKNOWN", "researcher_approval_and_bootstrap_custody_not_authenticated_here")
    pids = [pid for role in data["roles"].values() for pid in role["pids"]]
    paths = {"root": data["deployment_root"], **specification.paths()}
    inspected = inspect_environment(process_ids=pids, paths=list(paths.values()))
    result["inspection"] = inspected
    processes = {item["selector"]: item for item in inspected["processes"]}
    observed_paths = {_path(item["selector"]): item for item in inspected["paths"]}
    for role, expected in data["roles"].items():
        sids = expected["sids"] if role == "A" else ([] if expected["sid"] is None else [expected["sid"]])
        if not sids or not expected["pids"]:
            add("role_" + role, "BLOCKED", "identity_or_live_process_not_deployed")
            continue
        observations = [processes[pid] for pid in expected["pids"]]
        if any(item["status"] != "PASS" or item["evidence_source"] != NATIVE_SOURCE for item in observations):
            add("role_" + role, "UNKNOWN", "primary_token_evidence_unavailable_or_synthetic")
        elif any(item["primary_sid"] not in sids or item["token_type"] != 1 for item in observations):
            add("role_" + role, "FAIL", "observed_primary_token_mismatch")
        elif role in ("W", "V") and any(item["elevated"] for item in observations):
            add("role_" + role, "FAIL", "trusted_runtime_must_not_be_elevated")
        else:
            add("role_" + role, "PASS", "selected_primary_sid_fact_only_not_capability_coverage")
    identities = {}
    for name, path in paths.items():
        observation = observed_paths[_path(path)]
        expected = data["root_expectations"] if name == "root" else data["resource_expectations"][name]
        if observation["status"] == "FAIL":
            add("path_" + name, "FAIL", "redirection_observed")
            continue
        if "path_missing" in observation.get("reason_codes", []):
            add("path_" + name, "BLOCKED", "required_path_not_deployed")
            continue
        if observation["status"] != "PASS" or observation["evidence_source"] != NATIVE_SOURCE:
            add("path_" + name, "UNKNOWN", "path_evidence_unavailable_or_synthetic")
            continue
        try:
            same_path = _observed_path(observation["resolved_path"]) == _path(path)
        except ValueError:
            same_path = False
        if not same_path or observation["object_type"] != ("directory" if name == "root" else RESOURCE_LAYOUT[name][1]):
            add("path_" + name, "FAIL", "unexpected_resolved_path_or_object_type")
            continue
        identity = observation["volume_serial"], observation["file_id"]
        if identity in identities:
            add("path_" + name, "FAIL", "protected_resource_file_identity_alias")
            continue
        identities[identity] = name
        security = observation["security"]
        if security["status"] != "PASS":
            add("path_" + name, "UNKNOWN", "owner_or_acl_unreadable")
        elif not security["dacl_present"] or security["null_dacl"]:
            add("path_" + name, "FAIL", "required_dacl_absent_or_null")
        elif security["owner_sid"] in data["roles"]["A"]["sids"]:
            add("path_" + name, "FAIL", "agent_owns_proposed_protected_resource")
        elif expected["owner_sid"] is None or expected["sddl"] is None:
            add("path_" + name, "BLOCKED", "owner_or_exact_sddl_expectation_missing")
        elif security["owner_sid"] != expected["owner_sid"] or security["sddl"] != expected["sddl"]:
            add("path_" + name, "FAIL", "observed_owner_or_exact_sddl_mismatch")
        else:
            add("path_" + name, "PASS", "metadata_identity_only_NOT_effective_access")
        if name == "root":
            fields = ("resolved_path", "volume_serial", "volume_guid")
            if any(expected[key] is None for key in fields):
                add("root_identity", "BLOCKED", "independent_root_identity_expectation_missing")
            elif (not observation["volume_query_matches_handle"] or observation["filesystem"] != "NTFS" or
                  any(observation[key] != expected[key] for key in ("volume_serial", "volume_guid")) or
                  _observed_path(observation["resolved_path"]) != _path(expected["resolved_path"])):
                add("root_identity", "FAIL", "volume_or_resolved_root_identity_mismatch")
            else:
                add("root_identity", "PASS", "observed_root_identity_only_not_future_run_authorization")
    statuses = {item["status"] for item in result["prerequisites"]}
    result["status"] = next((status for status in ("FAIL", "BLOCKED", "UNKNOWN") if status in statuses), "NOT_RUN")
    return result


def main(argv=None):
    """stdout-only CLI; dry-run specification is bounded stdin, never a key file."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    selected = sub.add_parser("inspect")
    selected.add_argument("--pid", type=int, action="append", default=[])
    selected.add_argument("--path", action="append", default=[])
    planned = sub.add_parser("dry-run")
    planned.add_argument("--expected-manifest-sha256")
    args = parser.parse_args(argv)
    try:
        if args.mode == "inspect":
            if not args.pid and not args.path:
                parser.error("Explicit --pid or --path selectors are required.")
            result = inspect_environment(process_ids=args.pid, paths=args.path)
        else:
            raw = sys.stdin.buffer.read(MAX_SPEC_BYTES + 1)
            result = dry_run(raw, expected_manifest_sha256=args.expected_manifest_sha256)
    except (TypeError, ValueError, OverflowError, RecursionError):
        parser.error("Invalid bounded selector/specification; no acceptance action was performed.")
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2))
    # Success is only collection/validation, never an isolation acceptance PASS.
    return 0 if args.mode == "inspect" else 2


if __name__ == "__main__":
    raise SystemExit(main())
