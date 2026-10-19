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
