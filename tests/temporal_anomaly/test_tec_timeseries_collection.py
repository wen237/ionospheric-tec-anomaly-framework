from datetime import datetime, timedelta

import numpy as np
import pytest

from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.tec_timeseries_collection import combine_tec_timeseries


def make_series(
    epochs,
    tec,
) -> TECTimeSeries:
    return TECTimeSeries(
        epochs=np.asarray(
            epochs,
            dtype=object,
        ),
        tec=np.asarray(
            tec,
            dtype=float,
        ),
        requested_latitude=33.020,
        requested_longitude=69.464,
        grid_latitude=32.5,
        grid_longitude=70.0,
        latitude_index=22,
        longitude_index=50,
    )


def test_combine_tec_timeseries_combines_non_overlapping_segments():
    start = datetime(2022, 1, 1)

    series_a = make_series(
        epochs=[
            start,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
        ],
        tec=[10.0, 11.0, 12.0],
    )

    series_b = make_series(
        epochs=[
            start + timedelta(hours=3),
            start + timedelta(hours=4),
        ],
        tec=[13.0, 14.0],
    )

    combined = combine_tec_timeseries(
        [series_a, series_b]
    )

    expected_epochs = np.array(
        [
            start + timedelta(hours=i)
            for i in range(5)
        ],
        dtype=object,
    )

    np.testing.assert_array_equal(
        combined.epochs,
        expected_epochs,
    )

    np.testing.assert_array_equal(
        combined.tec,
        np.array(
            [10.0, 11.0, 12.0, 13.0, 14.0],
        ),
    )


def test_combine_tec_timeseries_is_independent_of_input_order():
    start = datetime(2022, 1, 1)

    series_a = make_series(
        epochs=[
            start,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
        ],
        tec=[10.0, 11.0, 12.0],
    )

    series_b = make_series(
        epochs=[
            start + timedelta(hours=3),
            start + timedelta(hours=4),
        ],
        tec=[13.0, 14.0],
    )

    combined = combine_tec_timeseries(
        [series_a, series_b]
    )

    combined_reverse = combine_tec_timeseries(
        [series_b, series_a]
    )

    np.testing.assert_array_equal(
        combined.epochs,
        combined_reverse.epochs,
    )

    np.testing.assert_array_equal(
        combined.tec,
        combined_reverse.tec,
    )


def test_combine_tec_timeseries_rejects_duplicate_timestamp():
    start = datetime(2022, 1, 1)

    series_a = make_series(
        epochs=[
            start,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
        ],
        tec=[10.0, 11.0, 12.0],
    )

    series_duplicate = make_series(
        epochs=[
            start + timedelta(hours=2),
            start + timedelta(hours=3),
        ],
        tec=[12.0, 13.0],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate timestamps",
    ):
        combine_tec_timeseries(
            [series_a, series_duplicate]
        )


def test_combine_tec_timeseries_rejects_inconsistent_duplicate():
    start = datetime(2022, 1, 1)

    series_a = make_series(
        epochs=[
            start,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
        ],
        tec=[10.0, 11.0, 12.0],
    )

    series_conflict = make_series(
        epochs=[
            start + timedelta(hours=2),
            start + timedelta(hours=3),
        ],
        tec=[99.0, 13.0],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate timestamps",
    ):
        combine_tec_timeseries(
            [series_a, series_conflict]
        )