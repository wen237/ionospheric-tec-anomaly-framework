"""Synthetic integration tests for the fixed historical B+C example CLI."""

import csv
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from examples import reproduce_afghanistan_historical_bc as example


ROOT = Path(__file__).resolve().parents[2]


def run_cli(tec, catalog, output, *extra):
    return subprocess.run(
        [sys.executable, "-B", "-m", "examples.reproduce_afghanistan_historical_bc",
         "--tec", str(tec), "--catalog", str(catalog), "--output-dir", str(output), *extra],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic-historical-bc")
    # Full 1999-2021 coverage: tests do not loosen the production configuration.
    day_indices = np.arange(example.N_DAYS)
    daily = np.repeat((10.0 + (day_indices % 7) * 0.1)[:, None], 24, axis=1)
    daily[day_indices[day_indices % 37 == 0], 9] += 4.0
    daily[day_indices[day_indices % 41 == 0], 19] -= 4.0
    events = [70, 160, 250, 340]
    for index in events:
        daily[index - 8, 4] += 10.0
        daily[index - 22, 16] -= 10.0
        daily[index, 21] += 10.0
        daily[index + 8, 6] += 10.0
        daily[index + 22, 18] -= 10.0
    tec, catalog, legacy = root / "synthetic.npy", root / "synthetic.csv", root / "legacy.npy"
    np.save(tec, daily.reshape(-1, 1))
    dates = [example.START + timedelta(days=index) for index in events]
    with catalog.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["event_id", "time_utc", "magnitude"])
        for i, day in enumerate(dates):
            writer.writerow([f"synthetic-{i}", f"{day.isoformat()}T12:00:00Z", 6.5])
    eqlist = np.zeros((len(dates), 10))
    for row, day in zip(eqlist, dates):
        row[:3] = [day.year, day.month, day.day]
        row[3], row[6], row[7], row[8], row[9] = 12, 70, 30, 10, 6.5
    np.save(legacy, eqlist[::-1])  # Deliberately opposite event order.
    return tec, catalog, legacy


@pytest.fixture(scope="module")
def completed(inputs, tmp_path_factory):
    tec, catalog, legacy = inputs
    output = tmp_path_factory.mktemp("synthetic-historical-bc-output")
    result = run_cli(tec, catalog, output, "--legacy-eqlist", str(legacy))
    assert result.returncode == 0, result.stderr
    path = output / example.OUTPUT_NAME
    return output, path.read_text(encoding="utf-8"), json.loads(path.read_text(encoding="utf-8"))


def test_valid_cli_summary_and_input_integrity(inputs, completed):
    _, _, summary = completed
    assert summary["summary_type"] == "afghanistan_historical_bc_reproduction"
    assert summary["schema_version"] == 1
    historical = summary["historical_data"]
    assert historical["daily_shape"] == [8401, 24]
    assert historical["input_shape"] == [201624, 1]
    assert historical["interpolated_count"] == 0
    assert historical["values_unchanged"] is True
    assert historical["assigned_start_utc"] == "1999-01-01T00:00:00Z"
    assert historical["assigned_end_utc"] == "2021-12-31T23:00:00Z"
    assert summary["input_integrity_verified_after_run"] is True
    for name, path in zip(("tec", "usgs_catalog", "legacy_catalog"), inputs):
        assert summary["inputs"][name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert summary["inputs"][name]["path"] == str(path.resolve())
    assert summary["earthquake_selection"]["n_selected_events"] == 4
    assert summary["population_baseline"]["valid_sample_count"] == (8401 - 15) * 24
    assert 0 < summary["population_baseline"]["positive_probability"] < 1
    assert 0 < summary["population_baseline"]["negative_probability"] < 1
    assert summary["environment"]["kmeans_n_init"]
    # The real-data reference is evaluated, not forced onto synthetic data.
    assert summary["reference_comparison"]["checks"]["selected_events"] == {
        "expected": 74, "actual": 4, "matches": False,
    }
    assert summary["reference_comparison"]["all_match"] is False


def test_pre_event_selection_keeps_day_zero_and_excludes_post_event(completed):
    summary = completed[2]
    full = summary["statistical_significance"]["full_window"]
    pre = summary["statistical_significance"]["pre_event"]
    cells = lambda window: {(c["hour_utc"], c["relative_day"], c["polarity"])
                            for c in window["significant_cells"]}
    assert full["shape"] == [61, 24]
    assert pre["shape"] == [31, 24]
    assert (6, 8, 1) in cells(full)
    assert (18, 22, -1) in cells(full)
    assert (21, 0, 1) in cells(pre)
    assert (4, -8, 1) in cells(pre)
    assert (16, -22, -1) in cells(pre)
    clustering = summary["clustering"]
    assert clustering["relative_days"] == list(range(-30, 1))
    assert {tuple(row) for row in clustering["raw_features"]} == cells(pre)
    assert all(row[1] <= 0 for row in clustering["raw_features"])
    assert clustering["n_significant_cells"] == pre["nonzero_mask_count"]


def test_legacy_comparison_aligns_utc_dates(completed):
    comparison = completed[2]["legacy_comparison"]
    assert comparison["all_match"] is True
    assert comparison["first_difference"] is None
    assert comparison["event_alignment"] == "UTC calendar date"
    assert comparison["checks"]["subset.delta_tec"]["max_abs_difference"] == 0


def test_repeat_execution_is_byte_deterministic(inputs, completed, tmp_path):
    tec, catalog, legacy = inputs
    path = example.reproduce(tec, catalog, tmp_path, legacy_path=legacy)
    assert path.read_text(encoding="utf-8") == completed[1]


def test_existing_output_protected_and_explicit_overwrite(inputs, completed):
    tec, catalog, legacy = inputs
    output, original, _ = completed
    result = run_cli(tec, catalog, output)
    assert result.returncode == 3
    assert "Output conflict" in result.stderr
    path = output / example.OUTPUT_NAME
    assert path.read_text(encoding="utf-8") == original
    result = run_cli(tec, catalog, output, "--legacy-eqlist", str(legacy), "--overwrite")
    assert result.returncode == 0, result.stderr
    assert path.read_text(encoding="utf-8") == original


def test_optional_legacy_catalog(inputs, tmp_path):
    tec, catalog, _ = inputs
    path = example.reproduce(tec, catalog, tmp_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["legacy_comparison"] is None
    assert "legacy_catalog" not in summary["inputs"]


def test_legacy_difference_is_reported_without_adjusting_science(inputs, tmp_path):
    tec, catalog, original_legacy = inputs
    legacy = tmp_path / "different_legacy.npy"
    eqlist = np.load(original_legacy, allow_pickle=False)
    eqlist[0, -1] = 5.5  # Explicitly exclude one synthetic event.
    np.save(legacy, eqlist)
    path = example.reproduce(tec, catalog, tmp_path / "output", legacy_path=legacy)
    summary = json.loads(path.read_text(encoding="utf-8"))
    comparison = summary["legacy_comparison"]
    assert summary["earthquake_selection"]["n_selected_events"] == 4
    assert comparison["n_selected_events"] == 3
    assert comparison["all_match"] is False
    assert comparison["first_difference"] == "all_catalog_date_magnitude_pairs"
    assert comparison["checks"]["subset.delta_tec"]["equal"] is None
    assert comparison["checks"]["z_test.positive_z"]["max_abs_difference"] > 0


@pytest.mark.parametrize("kind", [
    "short", "transposed", "nan", "infinite", "precision_loss", "object", "not_npy",
])
def test_rejects_invalid_tec_without_output(kind, inputs, tmp_path):
    _, catalog, _ = inputs
    tec = tmp_path / "invalid.npy"
    if kind == "not_npy":
        tec.write_text("not an NPY file", encoding="utf-8")
    else:
        values = np.full(example.N_HOURS, 10.0)
        if kind == "short":
            values = values[:-1]
        elif kind == "transposed":
            values = values.reshape(24, example.N_DAYS)
        elif kind == "nan":
            values[100] = np.nan  # Internal gap must not be silently filled.
        elif kind == "infinite":
            values[100] = np.inf
        elif kind == "precision_loss":
            values = values.astype(np.uint64)
            values[100] = 2**53 + 1  # Not exactly representable as float64.
        elif kind == "object":
            values = np.array([{"untrusted": True}], dtype=object)
        np.save(tec, values)
    before = tec.read_bytes()
    result = run_cli(tec, catalog, tmp_path / "output")
    assert result.returncode == 2
    assert not (tmp_path / "output").exists()
    assert tec.read_bytes() == before


@pytest.mark.parametrize("kind", ["missing", "bad_csv", "duplicate_day", "no_eligible_events"])
def test_rejects_invalid_catalog(kind, inputs, tmp_path):
    tec, _, _ = inputs
    catalog = tmp_path / "invalid.csv"
    if kind == "bad_csv":
        catalog.write_text("unrelated,column\na,b\n", encoding="utf-8")
    elif kind != "missing":
        rows = "event_id,time_utc,magnitude\na,1999-06-01T12:00:00Z,5.5\n"
        if kind == "duplicate_day":
            rows += "b,1999-06-01T13:00:00Z,6.5\n"
        catalog.write_text(rows, encoding="utf-8")
    result = run_cli(tec, catalog, tmp_path / "output")
    assert result.returncode == 2
    assert not (tmp_path / "output").exists()


def test_invalid_legacy_catalog_does_not_create_output(inputs, tmp_path):
    tec, catalog, _ = inputs
    legacy = tmp_path / "invalid_legacy.npy"
    np.save(legacy, np.zeros((2, 3)))
    result = run_cli(tec, catalog, tmp_path / "output", "--legacy-eqlist", str(legacy))
    assert result.returncode == 2
    assert not (tmp_path / "output").exists()


def test_output_cannot_replace_input_even_with_overwrite(inputs, tmp_path):
    _, catalog, _ = inputs
    tec = tmp_path / example.OUTPUT_NAME
    with tec.open("wb") as handle:
        np.save(handle, np.full(example.N_HOURS, 10.0))
    before = tec.read_bytes()
    result = run_cli(tec, catalog, tmp_path, "--overwrite")
    assert result.returncode == 2
    assert "must not replace an input" in result.stderr
    assert tec.read_bytes() == before


@pytest.mark.parametrize("overwrite", [False, True])
def test_atomic_partial_write_failure_never_publishes(inputs, tmp_path, monkeypatch, overwrite):
    output = tmp_path / example.OUTPUT_NAME
    previous = b'{"previous": "valid summary"}\n'
    if overwrite:
        output.write_bytes(previous)
    create_temporary = example.tempfile.NamedTemporaryFile

    def failing_temporary(*args, **kwargs):
        handle = create_temporary(*args, **kwargs)
        assert Path(handle.name).parent == output.parent
        write = handle.write

        def partial_write(text):
            write(text[:len(text) // 2])
            handle.flush()
            raise OSError("Injected partial write failure")

        handle.write = partial_write
        return handle

    monkeypatch.setattr(example.tempfile, "NamedTemporaryFile", failing_temporary)
    with pytest.raises(OSError, match="Injected partial write failure"):
        example._write_summary_atomic(output, '{"new": "complete summary"}\n', overwrite=overwrite)
    if overwrite:
        assert output.read_bytes() == previous
    else:
        assert not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if overwrite else [])


@pytest.mark.parametrize("overwrite", [False, True])
def test_atomic_publication_failure_cleans_temporary(tmp_path, monkeypatch, overwrite):
    output = tmp_path / example.OUTPUT_NAME
    previous = b'{"previous": "valid summary"}\n'
    text = '{"new": "complete summary"}\n'
    if overwrite:
        output.write_bytes(previous)

    def fail_publication(source, destination):
        assert Path(source).read_text(encoding="utf-8") == text
        assert Path(source).parent == Path(destination).parent
        raise OSError("Injected publication failure")

    monkeypatch.setattr(example.os, "replace" if overwrite else "link", fail_publication)
    with pytest.raises(OSError, match="Injected publication failure"):
        example._write_summary_atomic(output, text, overwrite=overwrite)
    if overwrite:
        assert output.read_bytes() == previous
    else:
        assert not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if overwrite else [])


@pytest.mark.parametrize("overwrite", [False, True])
def test_atomic_success_leaves_only_complete_summary(tmp_path, overwrite):
    output = tmp_path / example.OUTPUT_NAME
    if overwrite:
        output.write_text('{"previous": "valid summary"}\n', encoding="utf-8")
    text = json.dumps({"scientific_summary": "完整結果"}, ensure_ascii=False) + "\n"
    example._write_summary_atomic(output, text, overwrite=overwrite)
    assert output.read_text(encoding="utf-8") == text
    assert list(tmp_path.iterdir()) == [output]


def test_cli_concurrent_destination_creation_preserves_winner(inputs, tmp_path, monkeypatch):
    tec, catalog, _ = inputs
    output = tmp_path / example.OUTPUT_NAME
    winner = b'{"concurrent_writer": "complete summary"}\n'
    link = example.os.link

    def concurrent_creation(source, destination):
        # A complete temporary JSON exists, but the final name is still free.
        json.loads(Path(source).read_text(encoding="utf-8"))
        assert not output.exists()
        output.write_bytes(winner)
        return link(source, destination)  # Must fail atomically with EEXIST.

    monkeypatch.setattr(example.os, "link", concurrent_creation)
    with pytest.raises(SystemExit) as error:
        example.main(["--tec", str(tec), "--catalog", str(catalog), "--output-dir", str(tmp_path)])
    assert error.value.code == 3
    assert output.read_bytes() == winner
    assert list(tmp_path.iterdir()) == [output]


def test_cli_sync_failure_preserves_existing_summary_and_exit_code(inputs, tmp_path, monkeypatch):
    tec, catalog, _ = inputs
    output = tmp_path / example.OUTPUT_NAME
    previous = b'{"previous": "valid summary"}\n'
    output.write_bytes(previous)
    before_inputs = [path.read_bytes() for path in inputs]

    def fail_sync(descriptor):
        raise OSError("Injected sync failure")

    monkeypatch.setattr(example.os, "fsync", fail_sync)
    with pytest.raises(SystemExit) as error:
        example.main(["--tec", str(tec), "--catalog", str(catalog),
                      "--output-dir", str(tmp_path), "--overwrite"])
    assert error.value.code == 2
    assert output.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [output]
    assert [path.read_bytes() for path in inputs] == before_inputs
