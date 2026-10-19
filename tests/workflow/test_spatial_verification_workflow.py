"""Unit tests for Stage 2 spatial verification orchestration."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.workflow.spatial_verification_workflow as module

from src.workflow.preparation_manifest import (
    PreparationManifest,
    save_preparation_manifest,
)


@pytest.fixture
def workflow_case(tmp_path, monkeypatch):
    root = tmp_path / "outputs"

    temporal = root / "temporal" / "case_temporal.png"
    summary = root / "clustering" / "case_summary.json"

    temporal.parent.mkdir(parents=True)
    summary.parent.mkdir(parents=True)

    temporal.write_bytes(b"synthetic-png")
    summary.write_text("{}", encoding="utf-8")

    manifest = PreparationManifest(
        schema_version=1,
        case_id="synthetic_case",
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
        temporal_plot="temporal/case_temporal.png",
        clustering_summary="clustering/case_summary.json",
        analysis_parameters={
            "reference_days": 15,
            "threshold_multiplier": 3.0,
        },
        data_sources={
            "temporal": "synthetic_gim",
            "historical": "synthetic_tec",
        },
    )

    manifest_path = root / "preparation_manifest.json"
    save_preparation_manifest(manifest, manifest_path)

    calls = []
    fake_spatial_result = SimpleNamespace(
        marker="synthetic-spatial-result"
    )

    def fake_spatial_adapter(
        window,
        dataset_dir,
        *,
        reference_days,
        k,
    ):
        calls.append({
            "window": window,
            "dataset_dir": dataset_dir,
            "reference_days": reference_days,
            "k": k,
        })
        return fake_spatial_result

    monkeypatch.setattr(
        module,
        "run_spatial_verification",
        fake_spatial_adapter,
    )

    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "temporal": temporal,
        "summary": summary,
        "dataset_dir": tmp_path / "spatial_data",
        "calls": calls,
        "spatial_result": fake_spatial_result,
    }


def run_case(case, **overrides):
    arguments = {
        "preparation_manifest_path": case["manifest_path"],
        "start_time": "2022-05-28T06:00:00Z",
        "end_time": "2022-05-29T05:00:00+00:00",
        "spatial_dataset_dir": case["dataset_dir"],
        "reference_days": 15,
        "k": 3.0,
    }

    arguments.update(overrides)

    return module.run_spatial_verification_workflow(
        **arguments
    )


def test_workflow_returns_packaged_result(workflow_case):
    result = run_case(workflow_case)

    assert isinstance(
        result,
        module.SpatialVerificationWorkflowResult,
    )
    assert result.preparation_manifest == (
        workflow_case["manifest"]
    )
    assert result.spatial_result is (
        workflow_case["spatial_result"]
    )
    assert result.window.selection_mode == "explicit"


def test_explicit_utc_window_preserved(workflow_case):
    result = run_case(workflow_case)

    assert result.window.start_time == datetime(
        2022, 5, 28, 6, tzinfo=timezone.utc
    )
    assert result.window.end_time == datetime(
        2022, 5, 29, 5, tzinfo=timezone.utc
    )


def test_adapter_called_once_with_parameters(workflow_case):
    result = run_case(
        workflow_case,
        reference_days=7,
        k=1.5,
    )

    calls = workflow_case["calls"]

    assert len(calls) == 1
    assert calls[0]["window"] is result.window
    assert calls[0]["dataset_dir"] == (
        workflow_case["dataset_dir"]
    )
    assert calls[0]["reference_days"] == 7
    assert calls[0]["k"] == 1.5

    assert result.reference_days == 7
    assert result.k == 1.5


def test_missing_manifest_rejected(workflow_case):
    missing = (
        workflow_case["manifest_path"].parent
        / "missing_manifest.json"
    )

    with pytest.raises(FileNotFoundError):
        run_case(
            workflow_case,
            preparation_manifest_path=missing,
        )

    assert workflow_case["calls"] == []


def test_missing_temporal_artifact_rejected(workflow_case):
    workflow_case["temporal"].unlink()

    with pytest.raises(FileNotFoundError):
        run_case(workflow_case)

    assert workflow_case["calls"] == []


def test_missing_clustering_artifact_rejected(workflow_case):
    workflow_case["summary"].unlink()

    with pytest.raises(FileNotFoundError):
        run_case(workflow_case)

    assert workflow_case["calls"] == []


@pytest.mark.parametrize(
    "start_time,end_time",
    [
        (
            "2022-05-28T06:00:00",
            "2022-05-29T05:00:00Z",
        ),
        (
            "2022-05-28T06:30:00Z",
            "2022-05-29T05:00:00Z",
        ),
        (
            "2022-05-29T06:00:00Z",
            "2022-05-28T05:00:00Z",
        ),
        (
            "2022-05-28T06:00:00+08:00",
            "2022-05-29T05:00:00Z",
        ),
    ],
)
def test_invalid_utc_windows_rejected(
    workflow_case,
    start_time,
    end_time,
):
    with pytest.raises(ValueError):
        run_case(
            workflow_case,
            start_time=start_time,
            end_time=end_time,
        )

    assert workflow_case["calls"] == []


@pytest.mark.parametrize(
    "reference_days",
    [0, -1, True, 1.5, "15"],
)
def test_invalid_reference_days_rejected(
    workflow_case,
    reference_days,
):
    with pytest.raises(ValueError):
        run_case(
            workflow_case,
            reference_days=reference_days,
        )

    assert workflow_case["calls"] == []


@pytest.mark.parametrize(
    "k,exception",
    [
        (-1.0, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (True, TypeError),
        ("3.0", TypeError),
    ],
)
def test_invalid_k_rejected(
    workflow_case,
    k,
    exception,
):
    with pytest.raises(exception):
        run_case(workflow_case, k=k)

    assert workflow_case["calls"] == []


def test_stage_one_files_unchanged(workflow_case):
    paths = [
        workflow_case["manifest_path"],
        workflow_case["temporal"],
        workflow_case["summary"],
    ]

    before = {
        path: path.read_bytes()
        for path in paths
    }

    run_case(workflow_case)

    for path in paths:
        assert path.read_bytes() == before[path]


def test_wrong_path_types_rejected(workflow_case):
    with pytest.raises(TypeError):
        run_case(
            workflow_case,
            preparation_manifest_path="manifest.json",
        )

    with pytest.raises(TypeError):
        run_case(
            workflow_case,
            spatial_dataset_dir="spatial_data",
        )

    assert workflow_case["calls"] == []
