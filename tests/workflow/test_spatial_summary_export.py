"""Tests for Stage 2 spatial summary export."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from src.spatial_verification.spatial_anomaly import (
    SpatialAnomalyResult,
)
from src.workflow.preparation_manifest import (
    PreparationManifest,
    save_preparation_manifest,
)
from src.workflow.spatial_plot_export import (
    SpatialPlotExportResult,
)
from src.workflow.spatial_summary import (
    load_spatial_summary,
)
from src.workflow.spatial_summary_export import (
    build_spatial_summary,
    export_spatial_summary,
)
from src.workflow.spatial_verification_workflow import (
    SpatialVerificationWorkflowResult,
)
from src.workflow.temporal_window import TemporalWindow


@pytest.fixture
def export_case(tmp_path):
    root = tmp_path / "outputs"
    spatial_dir = root / "spatial"
    spatial_dir.mkdir(parents=True)

    manifest = PreparationManifest(
        schema_version=1,
        case_id="synthetic_case",
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
        temporal_plot="temporal/temporal.png",
        clustering_summary="clustering/summary.json",
        analysis_parameters={"reference_days": 3},
        data_sources={"source": "synthetic"},
    )

    manifest_path = root / "preparation_manifest.json"
    save_preparation_manifest(manifest, manifest_path)

    window = TemporalWindow(
        start_time=datetime(
            2022, 5, 28, 6, tzinfo=timezone.utc
        ),
        end_time=datetime(
            2022, 5, 29, 5, tzinfo=timezone.utc
        ),
        selection_mode="explicit",
    )

    positive = np.zeros((71, 73))
    negative = np.zeros((71, 73))

    positive[20, 50] = 100.0 / 24.0
    negative[40, 25] = 100.0 / 24.0

    spatial = SpatialAnomalyResult(
        positive_counts=np.where(
            positive > 0, 1, 0
        ),
        negative_counts=np.where(
            negative > 0, 1, 0
        ),
        positive_ratio=positive,
        negative_ratio=negative,
        latitudes=np.linspace(-87.5, 87.5, 71),
        longitudes=np.linspace(-180, 180, 73),
        window_steps=24,
    )

    workflow = SpatialVerificationWorkflowResult(
        preparation_manifest_path=manifest_path,
        preparation_manifest=manifest,
        window=window,
        spatial_result=spatial,
        spatial_dataset_dir=tmp_path / "gim",
        reference_days=3,
        k=3.0,
    )

    positive_plot = spatial_dir / "positive.png"
    negative_plot = spatial_dir / "negative.png"

    positive_plot.write_bytes(b"synthetic-positive-png")
    negative_plot.write_bytes(b"synthetic-negative-png")

    plots = SpatialPlotExportResult(
        case_id="synthetic_case",
        output_dir=spatial_dir,
        positive_plot=positive_plot,
        negative_plot=negative_plot,
    )

    return workflow, plots


def build(case):
    workflow, plots = case

    return build_spatial_summary(
        workflow,
        plots,
        epicenter_latitude=33.020,
        epicenter_longitude=69.464,
        magnitude=6.0,
    )


def export(case):
    workflow, plots = case

    return export_spatial_summary(
        workflow,
        plots,
        epicenter_latitude=33.020,
        epicenter_longitude=69.464,
        magnitude=6.0,
    )


def test_positive_maximum_geographic_coordinates(export_case):
    summary = build(export_case)

    positive = summary.spatial_anomalies["positive"]

    assert positive["maximum_ratio_percent"] == pytest.approx(
        100.0 / 24.0
    )
    assert positive["maximum_grid_points"] == [
        {"latitude": 37.5, "longitude": 70.0}
    ]


def test_negative_maximum_geographic_coordinates(export_case):
    summary = build(export_case)

    negative = summary.spatial_anomalies["negative"]

    assert negative["maximum_ratio_percent"] == pytest.approx(
        100.0 / 24.0
    )
    assert negative["maximum_grid_points"] == [
        {"latitude": -12.5, "longitude": -55.0}
    ]


def test_summary_parameters_match_workflow(export_case):
    summary = build(export_case)

    assert summary.case_id == "synthetic_case"
    assert summary.window_steps == 24
    assert summary.reference_days == 3
    assert summary.k == 3.0
    assert summary.magnitude == 6.0


def test_summary_uses_relative_artifact_paths(export_case):
    summary = build(export_case)

    assert summary.preparation_manifest == (
        "preparation_manifest.json"
    )
    assert summary.positive_plot == "spatial/positive.png"
    assert summary.negative_plot == "spatial/negative.png"


def test_export_creates_valid_json(export_case):
    path = export(export_case)

    assert path.is_file()

    loaded = load_spatial_summary(path)

    assert loaded == build(export_case)


def test_export_filename_contains_utc_window(export_case):
    path = export(export_case)

    assert path.name == (
        "synthetic_case_20220528T0600_"
        "20220529T0500_spatial_summary.json"
    )


def test_export_does_not_overwrite(export_case):
    path = export(export_case)
    original = path.read_bytes()

    with pytest.raises(FileExistsError):
        export(export_case)

    assert path.read_bytes() == original


def test_zero_anomaly_map_has_no_peak_points(export_case):
    workflow, plots = export_case

    workflow.spatial_result.negative_ratio[:] = 0.0

    summary = build(export_case)

    negative = summary.spatial_anomalies["negative"]

    assert negative["maximum_ratio_percent"] == 0.0
    assert negative["maximum_grid_points"] == []


def test_tied_maxima_are_preserved(export_case):
    workflow, plots = export_case

    workflow.spatial_result.positive_ratio[21, 50] = (
        100.0 / 24.0
    )

    summary = build(export_case)

    points = summary.spatial_anomalies["positive"][
        "maximum_grid_points"
    ]

    assert points == [
        {"latitude": 35.0, "longitude": 70.0},
        {"latitude": 37.5, "longitude": 70.0},
    ]


def test_scientific_arrays_not_modified(export_case):
    workflow, plots = export_case

    before_positive = (
        workflow.spatial_result.positive_ratio.copy()
    )
    before_negative = (
        workflow.spatial_result.negative_ratio.copy()
    )

    build(export_case)

    np.testing.assert_array_equal(
        workflow.spatial_result.positive_ratio,
        before_positive,
    )
    np.testing.assert_array_equal(
        workflow.spatial_result.negative_ratio,
        before_negative,
    )


def test_missing_png_is_rejected(export_case):
    workflow, plots = export_case
    plots.positive_plot.unlink()

    with pytest.raises(FileNotFoundError):
        build(export_case)


def test_png_outside_output_root_is_rejected(
    export_case,
    tmp_path,
):
    workflow, plots = export_case

    outside = tmp_path / "outside.png"
    outside.write_bytes(b"synthetic-png")

    bad_plots = SpatialPlotExportResult(
        case_id=plots.case_id,
        output_dir=plots.output_dir,
        positive_plot=outside,
        negative_plot=plots.negative_plot,
    )

    with pytest.raises(ValueError, match="output root"):
        build_spatial_summary(
            workflow,
            bad_plots,
            epicenter_latitude=33.020,
            epicenter_longitude=69.464,
            magnitude=6.0,
        )
