"""Tests for preparation manifest export integration."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import src.workflow.preparation_export as module

from src.workflow.preparation_manifest import (
    load_preparation_manifest,
)
from src.workflow.preparation_workflow import (
    PreparationWorkflowRunResult,
)
from src.workflow.workflow_config import WorkflowConfig


def make_result(tmp_path, monkeypatch):
    config = WorkflowConfig(
        case_id="synthetic_case",
        output_dir=tmp_path / "outputs",
        temporal_data_dir=tmp_path / "temporal_data",
        statistical_data_dir=tmp_path / "statistical_data",
        spatial_dataset_dir=tmp_path / "spatial_data",
    )

    plot_path = (
        config.output_dir
        / "temporal"
        / "synthetic_case_temporal_anomaly.png"
    )

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plot_path.write_bytes(b"synthetic-png")

    # The real summary builder is already tested in I3-4c.
    def fake_save_summary(result, output_path):
        output_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        output_path.write_text(
            json.dumps({"case_id": "synthetic_case"}),
            encoding="utf-8",
        )
        return output_path

    monkeypatch.setattr(
        module,
        "save_clustering_summary",
        fake_save_summary,
    )

    result = PreparationWorkflowRunResult(
        preparation=NS(
            config=config,
            temporal_plot_path=plot_path,
        ),
        temporal_workflow=NS(),
        historical=NS(),
        statistical_analysis=NS(),
        statistical_significance=NS(),
        clustering_workflow=NS(),
    )

    return result


def metadata():
    return {
        "analysis_parameters": {
            "reference_days": 15,
            "threshold_multiplier": 3.0,
            "minimum_magnitude": 6.0,
            "critical_z": 1.96,
            "n_clusters": 2,
            "random_state": 42,
        },
        "data_sources": {
            "temporal": "synthetic_gim",
            "historical": "synthetic_hourly_tec",
            "earthquake_catalog": "synthetic_catalog",
        },
    }


def test_export_creates_files(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    exported = module.export_preparation(
        result,
        **metadata(),
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
    )

    assert exported.summary_path.is_file()
    assert exported.manifest_path.is_file()


def test_manifest_roundtrip(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    exported = module.export_preparation(
        result,
        **metadata(),
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
    )

    loaded = load_preparation_manifest(
        exported.manifest_path
    )

    assert loaded == exported.manifest
    assert loaded.schema_version == 1
    assert loaded.case_id == "synthetic_case"


def test_manifest_relative_paths(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    exported = module.export_preparation(
        result,
        **metadata(),
    )

    manifest = exported.manifest

    assert manifest.temporal_plot == (
        "temporal/synthetic_case_temporal_anomaly.png"
    )

    assert manifest.clustering_summary == (
        "clustering/synthetic_case_clustering_summary.json"
    )

    root = result.preparation.config.output_dir

    assert (root / manifest.temporal_plot).is_file()
    assert (root / manifest.clustering_summary).is_file()


def test_manifest_metadata_preserved(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    exported = module.export_preparation(
        result,
        **metadata(),
    )

    assert (
        exported.manifest.analysis_parameters
        == metadata()["analysis_parameters"]
    )

    assert (
        exported.manifest.data_sources
        == metadata()["data_sources"]
    )


def test_default_created_at_is_utc(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    exported = module.export_preparation(
        result,
        **metadata(),
    )

    assert (
        exported.manifest.created_at.utcoffset()
        .total_seconds() == 0
    )


def test_missing_temporal_plot_rejected(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    result.preparation.temporal_plot_path.unlink()

    with pytest.raises(
        FileNotFoundError,
        match="Temporal plot",
    ):
        module.export_preparation(
            result,
            **metadata(),
        )


def test_outside_output_directory_rejected(
    tmp_path, monkeypatch
):
    result = make_result(tmp_path, monkeypatch)

    outside = tmp_path / "outside.png"
    outside.write_bytes(b"synthetic-png")

    result.preparation.temporal_plot_path = outside

    with pytest.raises(
        ValueError,
        match="inside config.output_dir",
    ):
        module.export_preparation(
            result,
            **metadata(),
        )


def test_invalid_metadata_rejected(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    bad = metadata()
    bad["analysis_parameters"]["critical_z"] = float("nan")

    with pytest.raises(ValueError, match="finite"):
        module.export_preparation(
            result,
            **bad,
        )


def test_naive_timestamp_rejected(tmp_path, monkeypatch):
    result = make_result(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="UTC"):
        module.export_preparation(
            result,
            **metadata(),
            created_at=datetime(2022, 6, 1),
        )


def test_invalid_result_type(tmp_path):
    with pytest.raises(
        TypeError,
        match="PreparationWorkflowRunResult",
    ):
        module.export_preparation(
            None,
            **metadata(),
        )


def test_summary_failure_prevents_manifest(
    tmp_path, monkeypatch
):
    result = make_result(tmp_path, monkeypatch)

    def fail_summary(result, output_path):
        raise RuntimeError("Synthetic summary failure")

    monkeypatch.setattr(
        module,
        "save_clustering_summary",
        fail_summary,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic summary failure",
    ):
        module.export_preparation(
            result,
            **metadata(),
        )

    assert not (
        result.preparation.config.output_dir
        / "preparation_manifest.json"
    ).exists()
