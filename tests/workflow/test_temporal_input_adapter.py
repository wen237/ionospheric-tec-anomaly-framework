"""Unit tests for the GIM-to-Temporal input adapter."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
import pytest

from src.spatial_verification.gim_loader import SpatialTECData
from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)
from src.workflow.temporal_input_adapter import (
    load_temporal_tec_from_gim,
)


START = datetime(2022, 5, 28, 6)
END = datetime(2022, 5, 28, 8)
REFERENCE_DAYS = 1


def make_spatial_data():
    reference_start = START - timedelta(days=REFERENCE_DAYS)
    steps = 24 + 3

    timestamps = tuple(
        reference_start + timedelta(hours=i)
        for i in range(steps)
    )

    tec = np.full(
        (steps, 71 * 73),
        10.0,
        dtype=float,
    )

    return SpatialTECData(
        tec=tec,
        timestamps=timestamps,
        samples_per_day=24,
        reference_days=REFERENCE_DAYS,
        window_steps=3,
    )


def call_adapter(**overrides):
    values = {
        "dataset_dir": "unused_prefix",
        "start_time": START,
        "end_time": END,
        "latitude": 37.5,
        "longitude": 70.0,
        "reference_days": REFERENCE_DAYS,
    }

    values.update(overrides)
    return load_temporal_tec_from_gim(**values)


@patch("src.workflow.temporal_input_adapter.load_spatial_tec")
def test_valid_temporal_series(mock_loader):
    mock_loader.return_value = make_spatial_data()

    result = call_adapter()

    assert len(result.epochs) == 27
    assert len(result.tec) == 27
    assert np.all(result.tec == 10.0)

    assert result.grid_latitude == 37.5
    assert result.grid_longitude == 70.0

    mock_loader.assert_called_once()


@patch("src.workflow.temporal_input_adapter.load_spatial_tec")
def test_latitude_orientation(mock_loader):
    spatial_data = make_spatial_data()

    # Raw row 20 becomes oriented row 50.
    raw_index = 20 * 73 + 50
    spatial_data.tec[:, raw_index] = 42.0

    mock_loader.return_value = spatial_data

    result = call_adapter(
        latitude=float(GIM_LATITUDES[50]),
        longitude=float(GIM_LONGITUDES[50]),
    )

    assert result.latitude_index == 50
    assert result.longitude_index == 50
    assert np.all(result.tec == 42.0)


@patch("src.workflow.temporal_input_adapter.load_spatial_tec")
def test_reject_shifted_timestamps(mock_loader):
    spatial_data = make_spatial_data()

    shifted = list(spatial_data.timestamps)
    shifted[5] += timedelta(hours=1)

    mock_loader.return_value = SpatialTECData(
        tec=spatial_data.tec,
        timestamps=tuple(shifted),
        samples_per_day=24,
        reference_days=REFERENCE_DAYS,
        window_steps=3,
    )

    with pytest.raises(ValueError, match="timestamps"):
        call_adapter()


@patch("src.workflow.temporal_input_adapter.load_spatial_tec")
def test_reject_invalid_grid_shape(mock_loader):
    spatial_data = make_spatial_data()

    mock_loader.return_value = SpatialTECData(
        tec=spatial_data.tec[:, :-1],
        timestamps=spatial_data.timestamps,
        samples_per_day=24,
        reference_days=REFERENCE_DAYS,
        window_steps=3,
    )

    with pytest.raises(ValueError, match="shape"):
        call_adapter()


@pytest.mark.parametrize(
    "field,value,error_type",
    [
        ("start_time", "2022-05-28", TypeError),
        ("end_time", "2022-05-28", TypeError),
        (
            "start_time",
            datetime(2022, 5, 28, 6, tzinfo=timezone.utc),
            ValueError,
        ),
        (
            "end_time",
            datetime(2022, 5, 28, 8, tzinfo=timezone.utc),
            ValueError,
        ),
        (
            "start_time",
            datetime(2022, 5, 28, 6, 30),
            ValueError,
        ),
        (
            "end_time",
            datetime(2022, 5, 28, 8, 30),
            ValueError,
        ),
        ("reference_days", 0, ValueError),
        ("reference_days", 1.5, ValueError),
        ("dataset_dir", 123, TypeError),
    ],
)
def test_reject_invalid_inputs(field, value, error_type):
    with pytest.raises(error_type):
        call_adapter(**{field: value})


def test_reject_reversed_time_window():
    with pytest.raises(ValueError, match="start_time"):
        call_adapter(
            start_time=END,
            end_time=START,
        )
