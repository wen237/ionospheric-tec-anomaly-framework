from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
import pytest

from src.spatial_verification.gim_loader import SpatialTECData
from src.spatial_verification.spatial_anomaly import SpatialAnomalyResult
from src.workflow.spatial_adapter import run_spatial_verification
from src.workflow.temporal_window import TemporalWindow


def make_window():
    return TemporalWindow(
        start_time=datetime(2022, 5, 28, 0, tzinfo=timezone.utc),
        end_time=datetime(2022, 5, 28, 2, tzinfo=timezone.utc),
        selection_mode="explicit",
    )


def make_spatial_data(window_steps=3, reference_days=15):
    start_time = datetime(2022, 5, 28, 0)

    reference_start = start_time - timedelta(
        days=reference_days
    )

    total_steps = reference_days * 24 + window_steps

    timestamps = tuple(
        reference_start + timedelta(hours=i)
        for i in range(total_steps)
    )

    return SpatialTECData(
        tec=np.ones((total_steps, 71 * 73)),
        timestamps=timestamps,
        samples_per_day=24,
        reference_days=reference_days,
        window_steps=window_steps,
    )


@patch("src.workflow.spatial_adapter.compute_spatial_anomalies")
@patch("src.workflow.spatial_adapter.load_spatial_tec")
def test_spatial_adapter_calls_validated_core(
    mock_load,
    mock_compute,
):
    mock_load.return_value = make_spatial_data()

    mock_compute.return_value = SpatialAnomalyResult(
        positive_counts=np.zeros((71, 73)),
        negative_counts=np.zeros((71, 73)),
        positive_ratio=np.zeros((71, 73)),
        negative_ratio=np.zeros((71, 73)),
        latitudes=np.linspace(-87.5, 87.5, 71),
        longitudes=np.linspace(-180, 180, 73),
        window_steps=3,
    )

    result = run_spatial_verification(
        window=make_window(),
        dataset_dir="dummy/",
    )

    assert result is mock_compute.return_value

    mock_load.assert_called_once_with(
        dataset_dir="dummy/",
        start_time=datetime(2022, 5, 28, 0),
        end_time=datetime(2022, 5, 28, 2),
        reference_days=15,
    )

    assert mock_compute.call_args.kwargs["window_steps"] == 3
    assert mock_compute.call_args.kwargs["k"] == 3.0


@patch("src.workflow.spatial_adapter.load_spatial_tec")
def test_reject_incorrect_window_steps(mock_load):
    mock_load.return_value = make_spatial_data(window_steps=2)

    with pytest.raises(ValueError, match="inclusive UTC"):
        run_spatial_verification(
            window=make_window(),
            dataset_dir="dummy/",
        )


@patch("src.workflow.spatial_adapter.load_spatial_tec")
def test_reject_incorrect_total_steps(mock_load):
    data = make_spatial_data()

    mock_load.return_value = SpatialTECData(
        tec=data.tec[:-1],
        timestamps=tuple(),
        samples_per_day=24,
        reference_days=15,
        window_steps=3,
    )

    with pytest.raises(ValueError, match="reference and target"):
        run_spatial_verification(
            window=make_window(),
            dataset_dir="dummy/",
        )


@pytest.mark.parametrize(
    "reference_days,k",
    [
        (0, 3.0),
        (-1, 3.0),
        (15, -1.0),
        (15, float("nan")),
        (15, float("inf")),
    ],
)
def test_reject_invalid_parameters(reference_days, k):
    with pytest.raises(ValueError):
        run_spatial_verification(
            window=make_window(),
            dataset_dir="dummy/",
            reference_days=reference_days,
            k=k,
        )


def test_reject_invalid_window_type():
    with pytest.raises(TypeError, match="TemporalWindow"):
        run_spatial_verification(
            window="invalid",
            dataset_dir="dummy/",
        )


def test_reject_invalid_dataset_dir_type():
    with pytest.raises(TypeError, match="dataset_dir"):
        run_spatial_verification(
            window=make_window(),
            dataset_dir=123,
        )


@patch("src.workflow.spatial_adapter.load_spatial_tec")
def test_reject_incorrect_timestamps(mock_load):
    data = make_spatial_data()

    shifted_timestamps = tuple(
        timestamp + timedelta(hours=1)
        for timestamp in data.timestamps
    )

    mock_load.return_value = SpatialTECData(
        tec=data.tec,
        timestamps=shifted_timestamps,
        samples_per_day=data.samples_per_day,
        reference_days=data.reference_days,
        window_steps=data.window_steps,
    )

    with pytest.raises(ValueError, match="continuous hourly UTC"):
        run_spatial_verification(
            window=make_window(),
            dataset_dir="dummy/",
        )