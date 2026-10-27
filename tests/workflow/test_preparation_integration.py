"""Real synthetic end-to-end integration for Framework A+B+C.

No scientific-stage monkeypatching is used.
"""

import json
from datetime import date, datetime, timedelta

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)
from src.workflow.workflow_config import WorkflowConfig
from src.workflow.preparation_workflow import (
    run_preparation_workflow,
)
from src.workflow.preparation_export import export_preparation
from src.workflow.preparation_manifest import (
    load_preparation_manifest,
)


# ------------------------------------------------------------
# 1. Synthetic GIM: reuse the validated I3-2 file contract.
# ------------------------------------------------------------

def write_gim_day(
    dataset_prefix,
    day,
    *,
    raw_latitude_index,
    longitude_index,
    injections,
):
    year = day.year
    doy = day.timetuple().tm_yday

    year_dir = dataset_prefix.parent / (
        dataset_prefix.name + str(year)
    )
    year_dir.mkdir(parents=True, exist_ok=True)

    # GIM stores TEC in units of 0.1 TECu.
    grid = np.full((24, 71, 73), 100.0, dtype=float)

    for timestamp, value in injections.items():
        if timestamp.date() == day.date():
            grid[
                timestamp.hour,
                raw_latitude_index,
                longitude_index,
            ] = value * 10.0

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


def create_synthetic_gim(
    dataset_prefix,
    start_time,
    end_time,
    reference_days,
):
    raw_latitude_index = 20
    longitude_index = 50

    injections = {
        start_time + timedelta(hours=1): 42.0,
        start_time + timedelta(hours=12): 2.0,
    }

    first_day = (
        start_time - timedelta(days=reference_days)
    ).date()

    last_day = end_time.date()

    current_day = first_day

    while current_day <= last_day:
        write_gim_day(
            dataset_prefix,
            datetime.combine(
                current_day,
                datetime.min.time(),
            ),
            raw_latitude_index=raw_latitude_index,
            longitude_index=longitude_index,
            injections=injections,
        )

        current_day += timedelta(days=1)

    return (
        float(GIM_LATITUDES[70 - raw_latitude_index]),
        float(GIM_LONGITUDES[longitude_index]),
    )


# ------------------------------------------------------------
# 2. Synthetic historical TEC and earthquake catalog.
# ------------------------------------------------------------

def create_synthetic_history():
    start_date = date(2021, 1, 1)
    n_days = 400

    event_indices = [70, 160, 250, 340]

    event_dates = [
        start_date + timedelta(days=index)
        for index in event_indices
    ]

    magnitudes = [6.1, 6.3, 6.5, 6.7]

    daily_tec = np.zeros((n_days, 24), dtype=float)

    for day_index in range(n_days):
        daily_tec[day_index, :] = (
            10.0 + (day_index % 7) * 0.1
        )

        # Sparse non-earthquake anomalies for the
        # historical population null probabilities.
        if day_index % 37 == 0:
            daily_tec[day_index, 9] += 4.0

        if day_index % 41 == 0:
            daily_tec[day_index, 19] -= 4.0

    # Known earthquake-related synthetic signals.
    for event_index in event_indices:
        daily_tec[event_index - 8, 4] += 10.0
        daily_tec[event_index - 22, 16] -= 10.0

    start_datetime = datetime.combine(
        start_date,
        datetime.min.time(),
    )

    epochs = [
        start_datetime + timedelta(hours=index)
        for index in range(n_days * 24)
    ]

    return {
        "epochs": epochs,
        "tec": daily_tec.reshape(-1),
        "start_date": start_date,
        "end_date": start_date + timedelta(days=n_days - 1),
        "event_dates": event_dates,
        "magnitudes": magnitudes,
    }


# ------------------------------------------------------------
# 3. Execute the real complete preparation pipeline once.
# ------------------------------------------------------------

@pytest.fixture(scope="module")
def completed_preparation(tmp_path_factory):
    root = tmp_path_factory.mktemp(
        "preparation_e2e"
    )

    config = WorkflowConfig(
        case_id="synthetic_e2e",
        output_dir=root / "outputs",
        temporal_data_dir=root / "gim",
        statistical_data_dir=root / "historical",
        spatial_dataset_dir=root / "spatial",
    )

    temporal_start = datetime(2022, 5, 28, 6)
    temporal_end = datetime(2022, 5, 29, 5)

    reference_days = 15

    latitude, longitude = create_synthetic_gim(
        config.temporal_data_dir,
        temporal_start,
        temporal_end,
        reference_days,
    )

    historical = create_synthetic_history()

    result = run_preparation_workflow(
        config=config,
        temporal_start_time=temporal_start,
        temporal_end_time=temporal_end,
        latitude=latitude,
        longitude=longitude,
        historical_epochs=historical["epochs"],
        historical_tec=historical["tec"],
        historical_start_date=historical["start_date"],
        historical_end_date=historical["end_date"],
        earthquake_dates=historical["event_dates"],
        earthquake_magnitudes=historical["magnitudes"],
        observation_days=30,
        reference_days=reference_days,
        threshold_multiplier=3.0,
        minimum_magnitude=6.0,
        critical_z=1.96,
        n_clusters=2,
        random_state=42,
        allow_historical_interpolation=False,
        min_reference_samples=15,
    )

    analysis_parameters = {
        "temporal_start_time": temporal_start.isoformat(),
        "temporal_end_time": temporal_end.isoformat(),
        "latitude": latitude,
        "longitude": longitude,
        "observation_days": 30,
        "reference_days": reference_days,
        "threshold_multiplier": 3.0,
        "minimum_magnitude": 6.0,
        "critical_z": 1.96,
        "n_clusters": 2,
        "random_state": 42,
        "allow_historical_interpolation": False,
        "min_reference_samples": 15,
    }

    data_sources = {
        "temporal": "synthetic_gim_npz",
        "historical": "synthetic_400_day_hourly_tec",
        "earthquake_catalog": "synthetic_four_events",
    }

    exported = export_preparation(
        result,
        analysis_parameters=analysis_parameters,
        data_sources=data_sources,
        created_at=datetime.fromisoformat(
            "2022-06-01T00:00:00+00:00"
        ),
    )

    with exported.summary_path.open(
        "r", encoding="utf-8"
    ) as file:
        summary = json.load(file)

    return {
        "result": result,
        "exported": exported,
        "summary": summary,
        "historical": historical,
        "analysis_parameters": analysis_parameters,
        "data_sources": data_sources,
    }


# ------------------------------------------------------------
# 4. Real end-to-end verification.
# ------------------------------------------------------------

def test_e2e_temporal_anomalies_and_png(
    completed_preparation,
):
    result = completed_preparation["result"]

    anomaly = result.temporal_workflow.anomaly_result

    expected = np.zeros(24, dtype=int)
    expected[1] = 1
    expected[12] = -1

    np.testing.assert_array_equal(
        anomaly.anomaly,
        expected,
    )

    np.testing.assert_allclose(
        anomaly.median,
        np.full(24, 10.0),
    )

    plot_path = result.preparation.temporal_plot_path

    assert plot_path.is_file()
    assert plot_path.stat().st_size > 0
    assert plot_path.read_bytes()[:8] == (
        b"\x89PNG\r\n\x1a\n"
    )

    assert plt.get_fignums() == []


def test_e2e_statistical_significance(
    completed_preparation,
):
    result = completed_preparation["result"]

    analysis = result.statistical_analysis
    significance = result.statistical_significance

    assert analysis.n_events == 4
    assert significance.n_events == 4

    relative_days = np.asarray(
        significance.relative_days
    )

    assert relative_days[0] == -30
    assert relative_days[-1] == 30

    # The injected signals occur at:
    # Day -8, 04 UT: positive.
    # Day -22, 16 UT: negative.
    positive_index = int(
        np.flatnonzero(relative_days == -8)[0]
    )

    negative_index = int(
        np.flatnonzero(relative_days == -22)[0]
    )

    assert significance.significance_mask[
        positive_index, 4
    ] == 1

    assert significance.significance_mask[
        negative_index, 16
    ] == -1

    assert (
        result.clustering_workflow.n_significant_cells
        == np.count_nonzero(
            significance.significance_mask[relative_days <= 0]
        )
    )

    clustering = result.clustering_workflow
    np.testing.assert_array_equal(clustering.clustering_relative_days, np.arange(-30, 1))
    np.testing.assert_array_equal(
        clustering.clustering_mask, significance.significance_mask[relative_days <= 0]
    )
    assert clustering.significance is significance


def test_e2e_summary_matches_scientific_results(
    completed_preparation,
):
    result = completed_preparation["result"]
    summary = completed_preparation["summary"]

    significance = result.statistical_significance
    clustering = result.clustering_workflow

    stats = summary["statistical_significance"]
    cluster_info = summary["clustering"]

    assert summary["schema_version"] == 2
    assert summary["case_id"] == "synthetic_e2e"

    assert (
        summary["earthquake_selection"]["n_selected_events"]
        == result.statistical_analysis.n_events
    )

    assert stats["overlap_count"] == (
        significance.overlap_count
    )

    assert stats["positive_mask_count"] == int(
        np.count_nonzero(
            significance.significance_mask == 1
        )
    )

    assert stats["negative_mask_count"] == int(
        np.count_nonzero(
            significance.significance_mask == -1
        )
    )

    assert cluster_info["n_clusters"] == 2
    assert cluster_info["random_state"] == 42
    assert (stats["relative_day_start"], stats["relative_day_end"]) == (-30, 30)
    assert (cluster_info["relative_day_start"], cluster_info["relative_day_end"]) == (-30, 0)

    assert cluster_info["n_significant_cells"] == (
        clustering.n_significant_cells
    )


def test_e2e_manifest_roundtrip_and_paths(
    completed_preparation,
):
    result = completed_preparation["result"]
    exported = completed_preparation["exported"]

    manifest = load_preparation_manifest(
        exported.manifest_path
    )

    root = result.preparation.config.output_dir

    assert manifest == exported.manifest
    assert manifest.schema_version == 1
    assert manifest.case_id == "synthetic_e2e"

    assert (root / manifest.temporal_plot).is_file()
    assert (root / manifest.clustering_summary).is_file()

    assert manifest.analysis_parameters == (
        completed_preparation["analysis_parameters"]
    )

    assert manifest.data_sources == (
        completed_preparation["data_sources"]
    )

    assert exported.summary_path == (
        root / manifest.clustering_summary
    )


def test_e2e_temporal_anchors_consistency(
    completed_preparation,
):
    result = completed_preparation["result"]
    summary = completed_preparation["summary"]

    original_anchors = (
        result.clustering_workflow
        .clustering.temporal_anchors
    )

    saved_anchors = (
        summary["clustering"]["temporal_anchors"]
    )

    assert len(original_anchors) == 2
    assert len(saved_anchors) == 2

    original_by_id = {
        int(anchor.cluster_id): anchor
        for anchor in original_anchors
    }

    saved_by_id = {
        anchor["cluster_id"]: anchor
        for anchor in saved_anchors
    }

    assert set(original_by_id) == set(saved_by_id)

    for cluster_id, original in original_by_id.items():
        saved = saved_by_id[cluster_id]

        assert saved["rounded_day"] == int(
            original.rounded_day
        )

        assert saved["hour"] == int(original.hour)

        assert saved["dominant_polarity"] == int(
            original.dominant_polarity
        )

        assert saved["n_members"] == int(
            original.n_members
        )
