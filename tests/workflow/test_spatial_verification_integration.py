"""Real synthetic GIM integration tests for Stage 2.

No monkeypatching of the GIM loader or Framework D.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.spatial_verification.spatial_anomaly import (
    SpatialAnomalyResult,
)
from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)
from src.workflow.preparation_manifest import (
    PreparationManifest,
    save_preparation_manifest,
)
from src.workflow.spatial_verification_workflow import (
    run_spatial_verification_workflow,
)


START_TIME = datetime(2022, 5, 28, 6)
END_TIME = datetime(2022, 5, 29, 5)
REFERENCE_DAYS = 3

POSITIVE_INDEX = (20, 50)
NEGATIVE_INDEX = (40, 25)


def write_gim_day(dataset_prefix, day, injections):
    """Write a synthetic GIM file using the validated format."""

    year = day.year
    doy = day.timetuple().tm_yday

    year_dir = dataset_prefix.parent / (
        dataset_prefix.name + str(year)
    )
    year_dir.mkdir(parents=True, exist_ok=True)

    # Raw GIM data are stored in units of 0.1 TECu.
    grid = np.full(
        (24, 71, 73),
        100.0,
        dtype=float,
    )

    for timestamp, raw_index, tecu in injections:
        if timestamp.date() == day.date():
            grid[
                timestamp.hour,
                raw_index[0],
                raw_index[1],
            ] = tecu * 10.0

    gim = grid.reshape(24 * 71, 73)

    gim_time = np.array(
        [
            [
                (day + timedelta(hours=h)).year,
                (day + timedelta(hours=h)).month,
                (day + timedelta(hours=h)).day,
                (day + timedelta(hours=h)).hour,
                0,
                0,
            ]
            for h in range(24)
        ],
        dtype=int,
    )

    np.savez(
        year_dir / f"gim{year}{doy:03d}.npz",
        gim=gim,
        gim_time=gim_time,
    )


def create_synthetic_spatial_gim(dataset_prefix):
    """Create reference and target GIM files."""

    injections = [
        (
            datetime(2022, 5, 28, 7),
            POSITIVE_INDEX,
            42.0,
        ),
        (
            datetime(2022, 5, 28, 18),
            NEGATIVE_INDEX,
            2.0,
        ),
    ]

    first_day = (
        START_TIME - timedelta(days=REFERENCE_DAYS)
    ).date()

    last_day = END_TIME.date()

    current_day = first_day

    while current_day <= last_day:
        write_gim_day(
            dataset_prefix,
            datetime.combine(
                current_day,
                datetime.min.time(),
            ),
            injections,
        )

        current_day += timedelta(days=1)


@pytest.fixture(scope="module")
def spatial_e2e_case(tmp_path_factory):
    root = tmp_path_factory.mktemp("spatial_e2e")

    output_dir = root / "outputs"
    dataset_prefix = root / "gim"

    create_synthetic_spatial_gim(dataset_prefix)

    # Stage 1 artifacts are synthetic but real files.
    # The manifest is saved and loaded by the real code.
    temporal_plot = (
        output_dir / "temporal" / "synthetic_temporal.png"
    )
    clustering_summary = (
        output_dir / "clustering" / "synthetic_summary.json"
    )

    temporal_plot.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    clustering_summary.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporal_plot.write_bytes(b"synthetic-stage-one-png")
    clustering_summary.write_text(
        '{"case_id": "synthetic_spatial"}\n',
        encoding="utf-8",
    )

    manifest = PreparationManifest(
        schema_version=1,
        case_id="synthetic_spatial",
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
        temporal_plot=(
            "temporal/synthetic_temporal.png"
        ),
        clustering_summary=(
            "clustering/synthetic_summary.json"
        ),
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
        output_dir / "preparation_manifest.json"
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

    before = {
        path: path.read_bytes()
        for path in stage_one_files
    }

    # This invokes the real Stage 2 orchestrator,
    # GIM loader, and Framework D scientific core.
    result = run_spatial_verification_workflow(
        preparation_manifest_path=manifest_path,
        start_time="2022-05-28T06:00:00Z",
        end_time="2022-05-29T05:00:00Z",
        spatial_dataset_dir=dataset_prefix,
        reference_days=REFERENCE_DAYS,
        k=3.0,
    )

    return {
        "result": result,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "dataset_prefix": dataset_prefix,
        "stage_one_files": stage_one_files,
        "before": before,
    }


def test_spatial_e2e_real_workflow(spatial_e2e_case):
    result = spatial_e2e_case["result"]

    assert isinstance(
        result.spatial_result,
        SpatialAnomalyResult,
    )

    assert result.preparation_manifest == (
        spatial_e2e_case["manifest"]
    )

    assert result.window.selection_mode == "explicit"

    assert result.window.start_time == datetime(
        2022, 5, 28, 6, tzinfo=timezone.utc
    )

    assert result.window.end_time == datetime(
        2022, 5, 29, 5, tzinfo=timezone.utc
    )

    assert result.reference_days == REFERENCE_DAYS
    assert result.k == 3.0


def test_spatial_e2e_positive_anomaly(spatial_e2e_case):
    spatial = spatial_e2e_case[
        "result"
    ].spatial_result

    assert spatial.window_steps == 24

    assert spatial.positive_counts[
        POSITIVE_INDEX
    ] == 1.0

    assert spatial.negative_counts[
        POSITIVE_INDEX
    ] == 0.0

    assert spatial.positive_ratio[
        POSITIVE_INDEX
    ] == pytest.approx(100.0 / 24.0)


def test_spatial_e2e_negative_anomaly(spatial_e2e_case):
    spatial = spatial_e2e_case[
        "result"
    ].spatial_result

    assert spatial.negative_counts[
        NEGATIVE_INDEX
    ] == 1.0

    assert spatial.positive_counts[
        NEGATIVE_INDEX
    ] == 0.0

    assert spatial.negative_ratio[
        NEGATIVE_INDEX
    ] == pytest.approx(100.0 / 24.0)


def test_spatial_e2e_grid_shape_and_orientation(
    spatial_e2e_case,
):
    spatial = spatial_e2e_case[
        "result"
    ].spatial_result

    expected_shape = (
        len(GIM_LATITUDES),
        len(GIM_LONGITUDES),
    )

    assert expected_shape == (71, 73)

    for array in (
        spatial.positive_counts,
        spatial.negative_counts,
        spatial.positive_ratio,
        spatial.negative_ratio,
    ):
        assert array.shape == expected_shape

    np.testing.assert_array_equal(
        spatial.latitudes,
        GIM_LATITUDES,
    )

    np.testing.assert_array_equal(
        spatial.longitudes,
        GIM_LONGITUDES,
    )

    # The anomaly counts must remain at the raw GIM
    # flattened-grid indices used by Framework D.
    assert np.count_nonzero(
        spatial.positive_counts
    ) == 1

    assert np.count_nonzero(
        spatial.negative_counts
    ) == 1

    assert np.sum(
        spatial.positive_counts
    ) == 1.0

    assert np.sum(
        spatial.negative_counts
    ) == 1.0


def test_spatial_e2e_reproducibility(spatial_e2e_case):
    original = spatial_e2e_case[
        "result"
    ].spatial_result

    repeated = run_spatial_verification_workflow(
        preparation_manifest_path=(
            spatial_e2e_case["manifest_path"]
        ),
        start_time="2022-05-28T06:00:00Z",
        end_time="2022-05-29T05:00:00Z",
        spatial_dataset_dir=(
            spatial_e2e_case["dataset_prefix"]
        ),
        reference_days=REFERENCE_DAYS,
        k=3.0,
    ).spatial_result

    for field in (
        "positive_counts",
        "negative_counts",
        "positive_ratio",
        "negative_ratio",
        "latitudes",
        "longitudes",
    ):
        np.testing.assert_array_equal(
            getattr(original, field),
            getattr(repeated, field),
        )

    assert original.window_steps == repeated.window_steps


def test_spatial_e2e_stage_one_unchanged(
    spatial_e2e_case,
):
    for path in spatial_e2e_case["stage_one_files"]:
        assert path.read_bytes() == (
            spatial_e2e_case["before"][path]
        )
