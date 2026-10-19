"""End-to-end integration tests for Stage 2 spatial plot export.

Real execution path:
Synthetic GIM -> Stage 2 Workflow -> Framework D -> PNG Export.

No monkeypatch is used.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pytest

from src.workflow.preparation_manifest import (
    PreparationManifest,
    save_preparation_manifest,
)
from src.workflow.spatial_verification_workflow import (
    run_spatial_verification_workflow,
)
from src.workflow.spatial_plot_export import (
    export_spatial_plots,
)


START = datetime(2022, 5, 28, 6, tzinfo=timezone.utc)
END = datetime(2022, 5, 29, 5, tzinfo=timezone.utc)

REFERENCE_DAYS = 3
POSITIVE_INDEX = (20, 50)
NEGATIVE_INDEX = (40, 25)


def create_gim_day(
    dataset_prefix: Path,
    day: datetime,
) -> None:
    """Write a 24-hour synthetic GIM file."""

    year = day.year
    doy = day.timetuple().tm_yday

    year_dir = dataset_prefix.parent / (
        f"{dataset_prefix.name}{year}"
    )
    year_dir.mkdir(parents=True, exist_ok=True)

    # GIM stored in 0.1 TECu units.
    gim = np.full(
        (24, 71, 73),
        100.0,
        dtype=float,
    )

    if day.date() == START.date():
        gim[7, POSITIVE_INDEX[0], POSITIVE_INDEX[1]] = 420.0
        gim[18, NEGATIVE_INDEX[0], NEGATIVE_INDEX[1]] = 20.0

    gim_time = np.array(
        [
            [
                day.year,
                day.month,
                day.day,
                hour,
                0,
                0,
            ]
            for hour in range(24)
        ],
        dtype=int,
    )

    np.savez(
        year_dir / f"gim{year}{doy:03d}.npz",
        gim=gim.reshape(24 * 71, 73),
        gim_time=gim_time,
    )


def create_gim_dataset(dataset_prefix: Path) -> None:
    """Create the reference period and target window."""

    first_day = (
        START.replace(tzinfo=None)
        - timedelta(days=REFERENCE_DAYS)
    ).date()

    last_day = END.date()

    day = first_day

    while day <= last_day:
        create_gim_day(
            dataset_prefix,
            datetime(day.year, day.month, day.day),
        )
        day += timedelta(days=1)


@pytest.fixture(scope="module")
def spatial_export_e2e(tmp_path_factory):
    root = tmp_path_factory.mktemp("spatial_export_e2e")

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

    manifest_path = (
        output_root / "preparation_manifest.json"
    )

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

    # Real scientific workflow, no mocking.
    workflow_result = run_spatial_verification_workflow(
        preparation_manifest_path=manifest_path,
        start_time="2022-05-28T06:00:00Z",
        end_time="2022-05-29T05:00:00Z",
        spatial_dataset_dir=dataset_prefix,
        reference_days=REFERENCE_DAYS,
        k=3.0,
    )

    # Real PNG generation, no mocking.
    export_result = export_spatial_plots(
        workflow_result,
        output_dir=output_root / "spatial",
        epicenter_latitude=33.020,
        epicenter_longitude=69.464,
        magnitude=6.0,
    )

    return {
        "workflow": workflow_result,
        "export": export_result,
        "stage_one_files": stage_one_files,
        "stage_one_before": stage_one_before,
    }


def test_e2e_scientific_anomalies(spatial_export_e2e):
    """Check scientific values before plotting."""

    spatial = spatial_export_e2e[
        "workflow"
    ].spatial_result

    assert spatial.window_steps == 24

    assert spatial.positive_counts[
        POSITIVE_INDEX
    ] == 1.0

    assert spatial.negative_counts[
        NEGATIVE_INDEX
    ] == 1.0

    assert spatial.positive_ratio[
        POSITIVE_INDEX
    ] == pytest.approx(100.0 / 24.0)

    assert spatial.negative_ratio[
        NEGATIVE_INDEX
    ] == pytest.approx(100.0 / 24.0)

    assert np.sum(spatial.positive_counts) == 1.0
    assert np.sum(spatial.negative_counts) == 1.0


def test_e2e_both_png_files_exist(spatial_export_e2e):
    exported = spatial_export_e2e["export"]

    assert exported.positive_plot.is_file()
    assert exported.negative_plot.is_file()

    assert exported.positive_plot.stat().st_size > 0
    assert exported.negative_plot.stat().st_size > 0


def test_e2e_png_files_are_readable(spatial_export_e2e):
    exported = spatial_export_e2e["export"]

    for path in (
        exported.positive_plot,
        exported.negative_plot,
    ):
        assert path.read_bytes()[:8] == (
            b"\x89PNG\r\n\x1a\n"
        )

        image = mpimg.imread(path)

        assert image.ndim == 3
        assert image.shape[0] > 100
        assert image.shape[1] > 100
        assert image.shape[2] in (3, 4)


def test_e2e_positive_negative_images_differ(
    spatial_export_e2e,
):
    exported = spatial_export_e2e["export"]

    positive = mpimg.imread(
        exported.positive_plot
    )
    negative = mpimg.imread(
        exported.negative_plot
    )

    assert positive.shape == negative.shape

    # Positive and negative anomalies occur at different
    # locations and the titles also differ.
    assert not np.array_equal(
        positive,
        negative,
    )


def test_e2e_filenames_include_utc_window(
    spatial_export_e2e,
):
    exported = spatial_export_e2e["export"]

    assert exported.positive_plot.name == (
        "synthetic_case_20220528T0600_"
        "20220529T0500_positive_spatial.png"
    )

    assert exported.negative_plot.name == (
        "synthetic_case_20220528T0600_"
        "20220529T0500_negative_spatial.png"
    )


def test_e2e_stage_one_artifacts_unchanged(
    spatial_export_e2e,
):
    for path in spatial_export_e2e["stage_one_files"]:
        assert path.read_bytes() == (
            spatial_export_e2e["stage_one_before"][path]
        )


def test_e2e_scientific_arrays_remain_unchanged(
    spatial_export_e2e,
):
    """Plotting must not change the computed anomaly arrays."""

    spatial = spatial_export_e2e[
        "workflow"
    ].spatial_result

    assert np.count_nonzero(
        spatial.positive_ratio
    ) == 1

    assert np.count_nonzero(
        spatial.negative_ratio
    ) == 1

    assert spatial.positive_ratio[
        POSITIVE_INDEX
    ] == pytest.approx(100.0 / 24.0)

    assert spatial.negative_ratio[
        NEGATIVE_INDEX
    ] == pytest.approx(100.0 / 24.0)


# ============================================================
# S2-4d: Spatial Summary End-to-End Handoff Tests
# ============================================================

from src.workflow.spatial_summary import (
    load_spatial_summary,
)
from src.workflow.spatial_summary_export import (
    export_spatial_summary,
)


@pytest.fixture(scope="module")
def spatial_handoff_e2e(spatial_export_e2e):
    """Extend the existing real PNG integration fixture.

    Executes:
        Synthetic GIM
        -> Framework D
        -> Positive/Negative PNG
        -> Spatial Summary JSON
        -> Reloaded SpatialSummary
    """

    workflow = spatial_export_e2e["workflow"]
    plots = spatial_export_e2e["export"]

    summary_path = export_spatial_summary(
        workflow,
        plots,
        epicenter_latitude=33.020,
        epicenter_longitude=69.464,
        magnitude=6.0,
    )

    loaded_summary = load_spatial_summary(summary_path)

    return {
        **spatial_export_e2e,
        "summary_path": summary_path,
        "summary": loaded_summary,
    }


def test_handoff_summary_json_exists(spatial_handoff_e2e):
    """The complete workflow must produce a JSON file."""

    summary_path = spatial_handoff_e2e["summary_path"]

    assert summary_path.is_file()
    assert summary_path.stat().st_size > 0
    assert summary_path.suffix == ".json"


def test_handoff_metadata_matches_workflow(spatial_handoff_e2e):
    """Summary metadata must match the executed workflow."""

    workflow = spatial_handoff_e2e["workflow"]
    summary = spatial_handoff_e2e["summary"]

    assert summary.schema_version == 1

    assert summary.case_id == (
        workflow.preparation_manifest.case_id
    )

    assert summary.start_time == workflow.window.start_time
    assert summary.end_time == workflow.window.end_time

    assert summary.window_steps == (
        workflow.spatial_result.window_steps
    )

    assert summary.reference_days == workflow.reference_days
    assert summary.k == workflow.k

    assert summary.epicenter_latitude == 33.020
    assert summary.epicenter_longitude == 69.464
    assert summary.magnitude == 6.0


def test_handoff_maximum_ratios_match_framework_d(
    spatial_handoff_e2e,
):
    """Summary maxima must match the actual scientific arrays."""

    workflow = spatial_handoff_e2e["workflow"]
    summary = spatial_handoff_e2e["summary"]

    spatial = workflow.spatial_result

    positive_maximum = float(
        np.max(spatial.positive_ratio)
    )
    negative_maximum = float(
        np.max(spatial.negative_ratio)
    )

    assert summary.spatial_anomalies["positive"][
        "maximum_ratio_percent"
    ] == pytest.approx(positive_maximum)

    assert summary.spatial_anomalies["negative"][
        "maximum_ratio_percent"
    ] == pytest.approx(negative_maximum)

    assert positive_maximum == pytest.approx(100.0 / 24.0)
    assert negative_maximum == pytest.approx(100.0 / 24.0)


def test_handoff_geographic_peak_coordinates(
    spatial_handoff_e2e,
):
    """Verify raw GIM indices become correct geographic points."""

    summary = spatial_handoff_e2e["summary"]

    positive_points = summary.spatial_anomalies["positive"][
        "maximum_grid_points"
    ]
    negative_points = summary.spatial_anomalies["negative"][
        "maximum_grid_points"
    ]

    # Raw GIM (20, 50) -> 37.5 N, 70 E
    assert positive_points == [
        {
            "latitude": 37.5,
            "longitude": 70.0,
        }
    ]

    # Raw GIM (40, 25) -> 12.5 S, 55 W
    assert negative_points == [
        {
            "latitude": -12.5,
            "longitude": -55.0,
        }
    ]


def test_handoff_artifact_paths_resolve(
    spatial_handoff_e2e,
):
    """Every referenced artifact must resolve within the case root."""

    workflow = spatial_handoff_e2e["workflow"]
    plots = spatial_handoff_e2e["export"]
    summary = spatial_handoff_e2e["summary"]

    root = (
        workflow.preparation_manifest_path.resolve().parent
    )

    assert (
        root / summary.preparation_manifest
    ).resolve() == (
        workflow.preparation_manifest_path.resolve()
    )

    assert (
        root / summary.positive_plot
    ).resolve() == plots.positive_plot.resolve()

    assert (
        root / summary.negative_plot
    ).resolve() == plots.negative_plot.resolve()

    for relative_path in (
        summary.preparation_manifest,
        summary.positive_plot,
        summary.negative_plot,
    ):
        resolved = (root / relative_path).resolve()

        assert resolved.is_file()
        assert resolved.is_relative_to(root)


def test_handoff_no_automatic_verification(
    spatial_handoff_e2e,
):
    """The V1 summary must not make an earthquake decision."""

    summary = spatial_handoff_e2e["summary"]
    data = summary.to_dict()

    assert data["window"]["selection_mode"] == "explicit"

    assert data["verification"] == {
        "method": "visual_inspection",
        "automatic_decision": None,
    }


def test_handoff_stage_one_artifacts_unchanged(
    spatial_handoff_e2e,
):
    """The full Stage 2 handoff must preserve Stage 1 files."""

    before = spatial_handoff_e2e["stage_one_before"]

    for path in spatial_handoff_e2e["stage_one_files"]:
        assert path.is_file()
        assert path.read_bytes() == before[path]
