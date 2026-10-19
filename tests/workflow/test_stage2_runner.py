"""Unit tests for the unified Stage 2 runner."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.workflow.stage2_runner as runner
from src.workflow.preparation_manifest import (
    PreparationManifest,
    save_preparation_manifest,
)
from src.workflow.spatial_plot_export import SpatialPlotExportResult


START = "2022-05-28T06:00:00Z"
END = "2022-05-29T05:00:00Z"


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / "outputs"
    root.mkdir()

    manifest = PreparationManifest(
        schema_version=1,
        case_id="synthetic_case",
        created_at=datetime(2022, 6, 1, tzinfo=timezone.utc),
        temporal_plot="temporal/plot.png",
        clustering_summary="clustering/summary.json",
        analysis_parameters={"reference_days": 3},
        data_sources={"source": "synthetic"},
    )

    manifest_path = root / "preparation_manifest.json"
    save_preparation_manifest(manifest, manifest_path)

    temporal = root / "temporal" / "plot.png"
    clustering = root / "clustering" / "summary.json"

    temporal.parent.mkdir()
    clustering.parent.mkdir()

    temporal.write_bytes(b"stage-one-temporal")
    clustering.write_text("{}", encoding="utf-8")

    before = {
        path: path.read_bytes()
        for path in (manifest_path, temporal, clustering)
    }

    calls = []
    workflow_result = SimpleNamespace(
        preparation_manifest=manifest,
        preparation_manifest_path=manifest_path,
    )

    def fake_workflow(**kwargs):
        calls.append("workflow")
        return workflow_result

    def fake_plots(workflow, **kwargs):
        calls.append("plots")
        directory = kwargs["output_dir"]
        directory.mkdir(parents=True, exist_ok=True)

        prefix = (
            "synthetic_case_"
            "20220528T0600_20220529T0500"
        )

        positive = directory / f"{prefix}_positive_spatial.png"
        negative = directory / f"{prefix}_negative_spatial.png"

        positive.write_bytes(b"positive-png")
        negative.write_bytes(b"negative-png")

        return SpatialPlotExportResult(
            case_id="synthetic_case",
            output_dir=directory,
            positive_plot=positive,
            negative_plot=negative,
        )

    def fake_summary(workflow, plots, **kwargs):
        calls.append("summary")

        path = plots.output_dir / (
            "synthetic_case_"
            "20220528T0600_20220529T0500"
            "_spatial_summary.json"
        )
        path.write_text('{"schema_version": 1}', encoding="utf-8")
        return path

    monkeypatch.setattr(
        runner, "run_spatial_verification_workflow", fake_workflow
    )
    monkeypatch.setattr(
        runner, "export_spatial_plots", fake_plots
    )
    monkeypatch.setattr(
        runner, "export_spatial_summary", fake_summary
    )

    return {
        "root": root,
        "manifest_path": manifest_path,
        "dataset": tmp_path / "synthetic_gim",
        "calls": calls,
        "before": before,
    }


def execute(case, **overrides):
    arguments = {
        "spatial_dataset_dir": case["dataset"],
        "start_time": START,
        "end_time": END,
        "epicenter_latitude": 33.020,
        "epicenter_longitude": 69.464,
        "magnitude": 6.0,
        "reference_days": 3,
        "k": 3.0,
    }
    arguments.update(overrides)

    return runner.run_stage2(
        case["manifest_path"],
        **arguments,
    )


def test_runner_executes_all_stages_in_order(case):
    execute(case)

    assert case["calls"] == [
        "workflow",
        "plots",
        "summary",
    ]


def test_runner_returns_all_outputs(case):
    result = execute(case)

    assert isinstance(result, runner.Stage2RunResult)
    assert result.plot_result.positive_plot.is_file()
    assert result.plot_result.negative_plot.is_file()
    assert result.summary_path.is_file()


def test_runner_default_output_directory(case):
    result = execute(case)

    assert result.plot_result.output_dir == (
        case["root"] / "spatial"
    )


def test_runner_rejects_existing_output(case):
    execute(case)
    case["calls"].clear()

    with pytest.raises(FileExistsError):
        execute(case)

    assert case["calls"] == []


def test_runner_rejects_existing_summary_before_workflow(case):
    spatial_dir = case["root"] / "spatial"
    spatial_dir.mkdir()

    summary_path = spatial_dir / (
        "synthetic_case_"
        "20220528T0600_20220529T0500"
        "_spatial_summary.json"
    )
    summary_path.write_text("existing-result", encoding="utf-8")

    with pytest.raises(FileExistsError):
        execute(case)

    assert summary_path.read_text(encoding="utf-8") == (
        "existing-result"
    )
    assert case["calls"] == []


def test_runner_rejects_invalid_utc_window(case):
    with pytest.raises(ValueError):
        execute(
            case,
            start_time="2022-05-28T06:00:00",
        )

    assert case["calls"] == []


def test_runner_rejects_output_outside_case_root(case, tmp_path):
    with pytest.raises(ValueError, match="output_dir"):
        execute(
            case,
            output_dir=tmp_path / "outside",
        )

    assert case["calls"] == []


def test_runner_rejects_invalid_earthquake_parameters(case):
    with pytest.raises(ValueError):
        execute(case, magnitude=-1.0)

    assert case["calls"] == []


def test_runner_rejects_invalid_analysis_parameters(case):
    with pytest.raises(ValueError):
        execute(case, reference_days=0)

    assert case["calls"] == []


def test_summary_failure_cleans_new_outputs(
    case,
    monkeypatch,
):
    def failing_summary(workflow, plots, **kwargs):
        case["calls"].append("summary")

        # Simulate a partially written summary.
        partial = plots.output_dir / (
            "synthetic_case_"
            "20220528T0600_20220529T0500"
            "_spatial_summary.json"
        )
        partial.write_text('{"incomplete":', encoding="utf-8")

        raise RuntimeError("Simulated summary write failure")

    monkeypatch.setattr(
        runner,
        "export_spatial_summary",
        failing_summary,
    )

    with pytest.raises(RuntimeError, match="Simulated"):
        execute(case)

    spatial_dir = case["root"] / "spatial"

    assert not list(spatial_dir.glob("*.png"))
    assert not list(spatial_dir.glob("*.json"))


def test_plot_failure_does_not_run_summary(
    case,
    monkeypatch,
):
    def failing_plots(workflow, **kwargs):
        case["calls"].append("plots")
        raise RuntimeError("Simulated plot failure")

    monkeypatch.setattr(
        runner,
        "export_spatial_plots",
        failing_plots,
    )

    with pytest.raises(RuntimeError, match="plot failure"):
        execute(case)

    assert case["calls"] == ["workflow", "plots"]


def test_stage_one_artifacts_remain_unchanged(case):
    execute(case)

    for path, original in case["before"].items():
        assert path.read_bytes() == original


# ============================================================
# S2-5c-1: Export Path Integrity Tests
# ============================================================

def test_runner_rejects_wrong_plot_case_id(
    case,
    monkeypatch,
):
    """A plot result must belong to the same Stage 1 case."""

    def wrong_case_plots(workflow, **kwargs):
        directory = kwargs["output_dir"]
        directory.mkdir(parents=True, exist_ok=True)

        prefix = (
            "synthetic_case_"
            "20220528T0600_20220529T0500"
        )

        positive = directory / f"{prefix}_positive_spatial.png"
        negative = directory / f"{prefix}_negative_spatial.png"

        positive.write_bytes(b"positive")
        negative.write_bytes(b"negative")

        return SpatialPlotExportResult(
            case_id="another_case",
            output_dir=directory,
            positive_plot=positive,
            negative_plot=negative,
        )

    monkeypatch.setattr(
        runner,
        "export_spatial_plots",
        wrong_case_plots,
    )

    with pytest.raises(ValueError, match="case_id"):
        execute(case)

    assert not list((case["root"] / "spatial").glob("*.png"))


def test_runner_rejects_wrong_summary_path(
    case,
    monkeypatch,
):
    """The summary exporter must return the planned JSON path."""

    def wrong_summary(workflow, plots, **kwargs):
        case["calls"].append("summary")

        wrong_path = plots.output_dir / "wrong_summary.json"
        wrong_path.write_text("{}", encoding="utf-8")

        return wrong_path

    monkeypatch.setattr(
        runner,
        "export_spatial_summary",
        wrong_summary,
    )

    with pytest.raises(ValueError, match="unexpected path"):
        execute(case)

    directory = case["root"] / "spatial"

    assert not list(directory.glob("*.png"))

    # The runner must not delete a file outside its planned
    # transaction merely because an exporter returned that path.
    assert (directory / "wrong_summary.json").is_file()


def test_runner_rejects_missing_summary_file(
    case,
    monkeypatch,
):
    """A returned summary path must refer to an existing file."""

    def missing_summary(workflow, plots, **kwargs):
        return plots.output_dir / (
            "synthetic_case_"
            "20220528T0600_20220529T0500"
            "_spatial_summary.json"
        )

    monkeypatch.setattr(
        runner,
        "export_spatial_summary",
        missing_summary,
    )

    with pytest.raises(FileNotFoundError):
        execute(case)

    directory = case["root"] / "spatial"

    assert not list(directory.glob("*.png"))
    assert not list(directory.glob("*.json"))


# ============================================================
# S2-5c-3b: Cleanup Failure Injection Tests
# ============================================================

def test_cleanup_continues_after_permission_error(
    tmp_path,
    monkeypatch,
):
    """One failed deletion must not block other cleanup."""

    protected = tmp_path / "protected.png"
    removable = tmp_path / "removable.png"

    protected.write_bytes(b"protected")
    removable.write_bytes(b"removable")

    original_unlink = Path.unlink

    def simulated_unlink(self, *args, **kwargs):
        if self == protected:
            raise PermissionError("Simulated locked file")

        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(
        Path,
        "unlink",
        simulated_unlink,
    )

    with pytest.warns(RuntimeWarning, match="Could not clean up"):
        runner._remove_created_files(
            (protected, removable)
        )

    assert protected.read_bytes() == b"protected"
    assert not removable.exists()


def test_summary_error_preserved_when_cleanup_fails(
    case,
    monkeypatch,
):
    """The original summary failure must remain visible."""

    def failing_summary(workflow, plots, **kwargs):
        raise RuntimeError("Original summary export failure")

    def failing_cleanup(paths):
        raise PermissionError("Simulated cleanup failure")

    monkeypatch.setattr(
        runner,
        "export_spatial_summary",
        failing_summary,
    )

    monkeypatch.setattr(
        runner,
        "_remove_created_files",
        failing_cleanup,
    )

    with pytest.raises(
        RuntimeError,
        match="Original summary export failure",
    ):
        execute(case)
