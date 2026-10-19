"""Unit tests for Stage 2 spatial plot export."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.workflow.spatial_plot_export as module

from src.workflow.preparation_manifest import (
    PreparationManifest,
)
from src.workflow.spatial_verification_workflow import (
    SpatialVerificationWorkflowResult,
)
from src.workflow.temporal_window import TemporalWindow


@pytest.fixture
def export_case(tmp_path, monkeypatch):
    manifest = PreparationManifest(
        schema_version=1,
        case_id="synthetic_case",
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
        temporal_plot="temporal/synthetic.png",
        clustering_summary="clustering/synthetic.json",
        analysis_parameters={"reference_days": 3},
        data_sources={"temporal": "synthetic_gim"},
    )

    window = TemporalWindow(
        start_time=datetime(
            2022, 5, 28, 6, tzinfo=timezone.utc
        ),
        end_time=datetime(
            2022, 5, 29, 5, tzinfo=timezone.utc
        ),
        selection_mode="explicit",
    )

    spatial_result = SimpleNamespace(
        marker="synthetic_spatial_result"
    )

    workflow_result = SpatialVerificationWorkflowResult(
        preparation_manifest_path=(
            tmp_path / "preparation_manifest.json"
        ),
        preparation_manifest=manifest,
        window=window,
        spatial_result=spatial_result,
        spatial_dataset_dir=tmp_path / "gim",
        reference_days=3,
        k=3.0,
    )

    calls = []

    def fake_save(
        result,
        *,
        polarity,
        output_path,
        start_time,
        end_time,
        epicenter_latitude,
        epicenter_longitude,
        magnitude,
    ):
        calls.append(
            {
                "result": result,
                "polarity": polarity,
                "output_path": output_path,
                "start_time": start_time,
                "end_time": end_time,
                "latitude": epicenter_latitude,
                "longitude": epicenter_longitude,
                "magnitude": magnitude,
            }
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_bytes(b"synthetic-png")

        return output_path

    monkeypatch.setattr(
        module,
        "save_spatial_anomaly_plot",
        fake_save,
    )

    return {
        "workflow_result": workflow_result,
        "output_dir": tmp_path / "spatial",
        "calls": calls,
        "spatial_result": spatial_result,
    }


def run_export(case, **overrides):
    kwargs = {
        "workflow_result": case["workflow_result"],
        "output_dir": case["output_dir"],
        "epicenter_latitude": 33.020,
        "epicenter_longitude": 69.464,
        "magnitude": 6.0,
    }
    kwargs.update(overrides)

    return module.export_spatial_plots(**kwargs)


def test_export_returns_two_paths(export_case):
    result = run_export(export_case)

    assert result.case_id == "synthetic_case"
    assert result.positive_plot.is_file()
    assert result.negative_plot.is_file()
    assert result.output_dir == (
        export_case["output_dir"].resolve()
    )


def test_filenames_include_explicit_utc_window(export_case):
    result = run_export(export_case)

    assert result.positive_plot.name == (
        "synthetic_case_20220528T0600_"
        "20220529T0500_positive_spatial.png"
    )

    assert result.negative_plot.name == (
        "synthetic_case_20220528T0600_"
        "20220529T0500_negative_spatial.png"
    )


def test_plot_writer_receives_scientific_result(export_case):
    run_export(export_case)

    calls = export_case["calls"]

    assert len(calls) == 2
    assert [call["polarity"] for call in calls] == [
        "positive",
        "negative",
    ]

    for call in calls:
        assert call["result"] is (
            export_case["spatial_result"]
        )
        assert call["latitude"] == 33.020
        assert call["longitude"] == 69.464
        assert call["magnitude"] == 6.0


def test_plot_writer_receives_explicit_window(export_case):
    run_export(export_case)

    window = export_case["workflow_result"].window

    for call in export_case["calls"]:
        assert call["start_time"] == window.start_time
        assert call["end_time"] == window.end_time


def test_existing_output_is_not_overwritten(export_case):
    first = run_export(export_case)

    before_positive = first.positive_plot.read_bytes()
    before_negative = first.negative_plot.read_bytes()

    with pytest.raises(FileExistsError):
        run_export(export_case)

    assert first.positive_plot.read_bytes() == before_positive
    assert first.negative_plot.read_bytes() == before_negative

    assert len(export_case["calls"]) == 2


def test_invalid_epicenter_rejected(export_case):
    with pytest.raises(ValueError):
        run_export(
            export_case,
            epicenter_latitude=100.0,
        )

    assert export_case["calls"] == []


def test_invalid_magnitude_rejected(export_case):
    with pytest.raises(ValueError):
        run_export(
            export_case,
            magnitude=float("nan"),
        )

    assert export_case["calls"] == []


def test_invalid_output_path_type_rejected(export_case):
    with pytest.raises(TypeError):
        run_export(
            export_case,
            output_dir="spatial",
        )

    assert export_case["calls"] == []


def test_invalid_workflow_result_rejected(export_case):
    with pytest.raises(TypeError):
        run_export(
            export_case,
            workflow_result=object(),
        )

    assert export_case["calls"] == []


def test_failed_second_plot_cleans_partial_export(
    export_case,
    monkeypatch,
):
    calls = []

    def failing_writer(
        result,
        *,
        polarity,
        output_path,
        **kwargs,
    ):
        calls.append(polarity)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_bytes(b"partial-png")

        if polarity == "negative":
            raise RuntimeError("Synthetic PNG failure")

        return output_path

    monkeypatch.setattr(
        module,
        "save_spatial_anomaly_plot",
        failing_writer,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic PNG failure",
    ):
        run_export(export_case)

    assert calls == ["positive", "negative"]
    assert list(export_case["output_dir"].glob("*.png")) == []


def test_non_explicit_window_rejected(export_case):
    original = export_case["workflow_result"]

    deterministic_window = TemporalWindow(
        start_time=original.window.start_time,
        end_time=original.window.end_time,
        selection_mode="deterministic",
    )

    export_case["workflow_result"] = (
        SpatialVerificationWorkflowResult(
            preparation_manifest_path=(
                original.preparation_manifest_path
            ),
            preparation_manifest=(
                original.preparation_manifest
            ),
            window=deterministic_window,
            spatial_result=original.spatial_result,
            spatial_dataset_dir=(
                original.spatial_dataset_dir
            ),
            reference_days=original.reference_days,
            k=original.k,
        )
    )

    with pytest.raises(
        ValueError,
        match="explicit",
    ):
        run_export(export_case)

    assert export_case["calls"] == []
