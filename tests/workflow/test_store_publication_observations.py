"""Same-token Windows mechanics in pytest-created disposable directories ONLY.

No Store/authentication/scientific modules, V1 records, keys, ACL setters or role
impersonation. These observations neither test SID isolation nor implement the
recommended layout. Fault injection is not a power-loss/durability experiment.
"""

import os
from pathlib import Path
import tempfile

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Native Windows filesystem/CRT observations required.")


def identity(path):
    info = path.stat()
    if not info.st_ino:
        pytest.skip("Filesystem does not expose a usable file identity through stat.")
    return info.st_dev, info.st_ino


def flushed_temporary(directory):
    descriptor, name = tempfile.mkstemp(prefix=".synthetic-publication-", dir=directory)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(b"synthetic-new\n")
        handle.flush()
        os.fsync(handle.fileno())
    return Path(name)


def test_existing_only_open_does_not_remove_same_token_creation_capability(tmp_path):
    # An ordinary, unisolated fixture. This is not an ACL/effective-rights test.
    lock = tmp_path / "synthetic.lock"
    with pytest.raises(FileNotFoundError):
        lock.open("r+b")
    assert not lock.exists()
    assert list(tmp_path.iterdir()) == []
    with lock.open("xb"):
        pass
    assert lock.read_bytes() == b""


@pytest.mark.parametrize("separate_staging", [False, True], ids=["same-directory", "same-volume-other-directory"])
def test_replace_observes_source_identity_not_a_namespace_policy(tmp_path, separate_staging):
    data = tmp_path / "data"
    data.mkdir()
    staging = tmp_path / "staging" if separate_staging else data
    if separate_staging:
        staging.mkdir()
    marker = data / "synthetic-marker.bin"
    marker.write_bytes(b"synthetic-old\n")
    old_id = identity(marker)
    temporary = flushed_temporary(staging)
    temporary_id = identity(temporary)
    if temporary_id[0] != old_id[0]:
        pytest.skip("Fixture directories are not on the same volume.")
    assert temporary_id != old_id  # both files still exist, so no ID reuse
    os.replace(temporary, marker)
    assert marker.read_bytes() == b"synthetic-new\n"
    assert identity(marker) == temporary_id
    assert not temporary.exists()
    # No owner/DACL inference; this token already has ordinary fixture access.


def test_injected_replace_failure_keeps_temporary_for_investigation(tmp_path, monkeypatch):
    marker = tmp_path / "synthetic-marker.bin"
    marker.write_bytes(b"synthetic-old\n")
    temporary = flushed_temporary(tmp_path)
    before = identity(marker)

    def stop(*args, **kwargs):
        raise OSError("Synthetic failure before replace; not a native access denial")

    monkeypatch.setattr(os, "replace", stop)
    with pytest.raises(OSError, match="Synthetic failure"):
        os.replace(temporary, marker)
    assert marker.read_bytes() == b"synthetic-old\n" and identity(marker) == before
    assert temporary.read_bytes() == b"synthetic-new\n"


@pytest.mark.parametrize("stop_after", [1, 2, 3], ids=["history", "first-marker", "second-marker"])
def test_separate_publications_can_leave_mixed_generations(tmp_path, stop_after):
    # Plain synthetic bytes, NOT AuthorizationStore data or a replacement reader.
    history, head, checkpoint = [tmp_path / name for name in ("synthetic-history.bin", "synthetic-head.bin", "synthetic-checkpoint.bin")]
    for path in (history, head, checkpoint):
        path.write_bytes(b"synthetic-old\n")

    class StopObservation(Exception):
        pass

    with pytest.raises(StopObservation):
        with history.open("ab") as handle:
            handle.write(b"synthetic-new\n")
            handle.flush()
            os.fsync(handle.fileno())
        if stop_after == 1:
            raise StopObservation()
        os.replace(flushed_temporary(tmp_path), head)
        if stop_after == 2:
            raise StopObservation()
        os.replace(flushed_temporary(tmp_path), checkpoint)
        raise StopObservation()  # models lost acknowledgement after all writes
    assert history.read_bytes() == b"synthetic-old\nsynthetic-new\n"
    assert head.read_bytes() == (b"synthetic-old\n" if stop_after == 1 else b"synthetic-new\n")
    assert checkpoint.read_bytes() == (b"synthetic-new\n" if stop_after == 3 else b"synthetic-old\n")


def test_empty_file_byte_range_lock_contends_without_writing_bytes(tmp_path):
    msvcrt = pytest.importorskip("msvcrt", reason="Windows CRT locking unavailable.")
    lock = tmp_path / "synthetic.lock"
    with lock.open("xb"):
        pass
    before = identity(lock)
    with lock.open("r+b") as first, lock.open("r+b") as second:
        first.seek(0)
        msvcrt.locking(first.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            second.seek(0)
            with pytest.raises(OSError):
                msvcrt.locking(second.fileno(), msvcrt.LK_NBLCK, 1)
        finally:
            first.seek(0)
            msvcrt.locking(first.fileno(), msvcrt.LK_UNLCK, 1)
        second.seek(0)
        msvcrt.locking(second.fileno(), msvcrt.LK_NBLCK, 1)
        second.seek(0)
        msvcrt.locking(second.fileno(), msvcrt.LK_UNLCK, 1)
    assert identity(lock) == before and lock.read_bytes() == b""
