"""Real integration tests for the unified Stage 2 runner.

Execution:
    Synthetic GIM
    -> Stage 1 Preparation Manifest
    -> run_stage2()
    -> Framework D
    -> Positive / Negative PNG
    -> Spatial Summary JSON

No scientific workflow functions are mocked.
"""

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pytest

from src.workflow.preparation_manifest import (
    PreparationManifest,
    save_preparation_manifest,
)
from src.workflow.spatial_summary import load_spatial_summary
from src.workflow.stage2_runner import (
    Stage2RunResult,
    run_stage2,
)


START = "2022-05-28T06:00:00Z"
END = "2022-05-29T05:00:00Z"

REFERENCE_DAYS = 3
POSITIVE_INDEX = (20, 50)
NEGATIVE_INDEX = (40, 25)

EPICENTER_LATITUDE = 33.020
EPICENTER_LONGITUDE = 69.464
MAGNITUDE = 6.0


def _load_existing_gim_generator():
    """Reuse the Synthetic GIM generator from S2-3d."""

    source = (
        Path(__file__).resolve().parent
        / "test_spatial_plot_export_integration.py"
    )

    spec = spec_from_file_location(
        "_existing_spatial_gim_test_helpers",
        source,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Cannot load the existing Synthetic GIM generator."
        )

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.create_gim_dataset


create_gim_dataset = _load_existing_gim_generator()


def create_stage_one_case(root: Path) -> dict:
    """Create one independent Stage 1 synthetic case."""

    output_root = root / "outputs"
    dataset_prefix = root / "gim"

    create_gim_dataset(dataset_prefix)

    temporal_plot = (
        output_root / "temporal" / "synthetic_temporal.png"
    )
    clustering_summary = (
        output_root / "clustering" / "synthetic_summary.json"
    )

    temporal_plot.parent.mkdir(parents=True)
    clustering_summary.parent.mkdir(parents=True)

    temporal_plot.write_bytes(b"synthetic-temporal-artifact")
    clustering_summary.write_text(
        '{"case_id": "synthetic_case"}',
        encoding="utf-8",
    )

    manifest = PreparationManifest(
        schema_version=1,
        case_id="synthetic_case",
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
        temporal_plot="temporal/synthetic_temporal.png",
        clustering_summary="clustering/synthetic_summary.json",
        analysis_parameters={
            "reference_days": REFERENCE_DAYS,
            "threshold_multiplier": 3.0,
        },
        data_sources={
            "temporal": "synthetic_gim",
            "historical": "synthetic_tec",
        },
    )

    manifest_path = output_root / "preparation_manifest.json"

    save_preparation_manifest(
        manifest,
        manifest_path,
    )

    stage_one_files = (
        temporal_plot,
        clustering_summary,
        manifest_path,
    )

    stage_one_before = {
        path: path.read_bytes()
        for path in stage_one_files
    }

    return {
        "root": root,
        "output_root": output_root,
        "dataset_prefix": dataset_prefix,
        "manifest_path": manifest_path,
        "stage_one_files": stage_one_files,
        "stage_one_before": stage_one_before,
    }


def execute_stage2(case: dict) -> Stage2RunResult:
    """Execute the real Stage 2 entry point."""

    return run_stage2(
        preparation_manifest_path=case["manifest_path"],
        spatial_dataset_dir=case["dataset_prefix"],
        start_time=START,
        end_time=END,
        epicenter_latitude=EPICENTER_LATITUDE,
        epicenter_longitude=EPICENTER_LONGITUDE,
        magnitude=MAGNITUDE,
        reference_days=REFERENCE_DAYS,
        k=3.0,
    )


@pytest.fixture(scope="module")
def stage2_real_e2e(tmp_path_factory):
    """Run the complete scientific workflow once."""

    root = tmp_path_factory.mktemp("stage2_runner_e2e")

    case = create_stage_one_case(root)
    result = execute_stage2(case)

    summary = load_spatial_summary(result.summary_path)

    return {
        **case,
        "result": result,
        "summary": summary,
    }


def test_runner_e2e_creates_all_artifacts(stage2_real_e2e):
    """Real run_stage2 must create two PNGs and one JSON."""

    result = stage2_real_e2e["result"]

    assert isinstance(result, Stage2RunResult)

    assert result.plot_result.positive_plot.is_file()
    assert result.plot_result.negative_plot.is_file()
    assert result.summary_path.is_file()

    for path in (
        result.plot_result.positive_plot,
        result.plot_result.negative_plot,
        result.summary_path,
    ):
        assert path.stat().st_size > 0

    for path in (
        result.plot_result.positive_plot,
        result.plot_result.negative_plot,
    ):
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

        image = mpimg.imread(path)
        assert image.ndim == 3
        assert image.shape[0] > 100
        assert image.shape[1] > 100


def test_runner_e2e_metadata_consistency(stage2_real_e2e):
    """Summary metadata must match the real workflow."""

    workflow = stage2_real_e2e["result"].workflow_result
    summary = stage2_real_e2e["summary"]

    assert summary.case_id == "synthetic_case"
    assert summary.schema_version == 1

    assert summary.start_time == workflow.window.start_time
    assert summary.end_time == workflow.window.end_time

    assert summary.window_steps == 24
    assert summary.window_steps == (
        workflow.spatial_result.window_steps
    )

    assert summary.reference_days == REFERENCE_DAYS
    assert summary.k == 3.0

    assert summary.epicenter_latitude == EPICENTER_LATITUDE
    assert summary.epicenter_longitude == EPICENTER_LONGITUDE
    assert summary.magnitude == MAGNITUDE

    assert summary.to_dict()["window"][
        "selection_mode"
    ] == "explicit"

    assert summary.to_dict()["verification"] == {
        "method": "visual_inspection",
        "automatic_decision": None,
    }


def test_runner_e2e_scientific_maxima(stage2_real_e2e):
    """JSON maxima must match actual Framework D results."""

    spatial = (
        stage2_real_e2e["result"]
        .workflow_result.spatial_result
    )
    summary = stage2_real_e2e["summary"]

    assert spatial.positive_counts[POSITIVE_INDEX] == 1.0
    assert spatial.negative_counts[NEGATIVE_INDEX] == 1.0

    assert np.sum(spatial.positive_counts) == 1.0
    assert np.sum(spatial.negative_counts) == 1.0

    expected = 100.0 / 24.0

    assert spatial.positive_ratio[
        POSITIVE_INDEX
    ] == pytest.approx(expected)

    assert spatial.negative_ratio[
        NEGATIVE_INDEX
    ] == pytest.approx(expected)

    assert summary.spatial_anomalies["positive"][
        "maximum_ratio_percent"
    ] == pytest.approx(
        float(np.max(spatial.positive_ratio))
    )

    assert summary.spatial_anomalies["negative"][
        "maximum_ratio_percent"
    ] == pytest.approx(
        float(np.max(spatial.negative_ratio))
    )


def test_runner_e2e_geographic_coordinates(stage2_real_e2e):
    """Raw GIM indices must map to correct coordinates."""

    summary = stage2_real_e2e["summary"]

    assert summary.spatial_anomalies["positive"][
        "maximum_grid_points"
    ] == [
        {"latitude": 37.5, "longitude": 70.0}
    ]

    assert summary.spatial_anomalies["negative"][
        "maximum_grid_points"
    ] == [
        {"latitude": -12.5, "longitude": -55.0}
    ]


def test_runner_e2e_artifact_paths(stage2_real_e2e):
    """All relative artifact paths must resolve correctly."""

    case = stage2_real_e2e
    result = case["result"]
    summary = case["summary"]

    root = case["output_root"].resolve()

    expected = {
        summary.preparation_manifest:
            case["manifest_path"].resolve(),
        summary.positive_plot:
            result.plot_result.positive_plot.resolve(),
        summary.negative_plot:
            result.plot_result.negative_plot.resolve(),
    }

    for relative_path, expected_path in expected.items():
        resolved = (root / relative_path).resolve()

        assert resolved == expected_path
        assert resolved.is_relative_to(root)
        assert resolved.is_file()


def test_runner_e2e_repeated_execution_protected(
    stage2_real_e2e,
):
    """Second execution must not overwrite existing results."""

    case = stage2_real_e2e
    result = case["result"]

    artifacts = (
        result.plot_result.positive_plot,
        result.plot_result.negative_plot,
        result.summary_path,
    )

    before = {
        path: path.read_bytes()
        for path in artifacts
    }

    with pytest.raises(FileExistsError):
        execute_stage2(case)

    for path, original in before.items():
        assert path.read_bytes() == original


def test_runner_e2e_independent_reproducibility(
    stage2_real_e2e,
    tmp_path,
):
    """Independent cases must produce identical science results."""

    second_case = create_stage_one_case(
        tmp_path / "independent_case"
    )

    second_result = execute_stage2(second_case)
    second_summary = load_spatial_summary(
        second_result.summary_path
    )

    first_result = stage2_real_e2e["result"]
    first_summary = stage2_real_e2e["summary"]

    first_spatial = first_result.workflow_result.spatial_result
    second_spatial = second_result.workflow_result.spatial_result

    for name in (
        "positive_counts",
        "negative_counts",
        "positive_ratio",
        "negative_ratio",
        "latitudes",
        "longitudes",
    ):
        np.testing.assert_array_equal(
            getattr(first_spatial, name),
            getattr(second_spatial, name),
        )

    assert first_spatial.window_steps == (
        second_spatial.window_steps
    )

    # Both cases have identical relative artifact paths and
    # a fixed synthetic Stage 1 manifest timestamp.
    assert first_summary.to_dict() == second_summary.to_dict()

    # The second run must produce its own independent files.
    assert second_result.summary_path != first_result.summary_path
    assert second_result.plot_result.positive_plot.is_file()
    assert second_result.plot_result.negative_plot.is_file()


def test_runner_e2e_stage_one_unchanged(stage2_real_e2e):
    """Stage 2 must not modify any Stage 1 artifact."""

    for path in stage2_real_e2e["stage_one_files"]:
        assert path.is_file()
        assert path.read_bytes() == (
            stage2_real_e2e["stage_one_before"][path]
        )
