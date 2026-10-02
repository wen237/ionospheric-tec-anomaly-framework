from datetime import datetime, timedelta

import numpy as np

from src.statistical_clustering.historical_tec import (
    interpolate_hourly_tec,
)


def test_two_hour_to_one_hour_interpolation():

    start = datetime(
        2020,
        1,
        1,
        0,
    )

    epochs = np.asarray(
        [
            start,
            start + timedelta(hours=2),
            start + timedelta(hours=4),
        ],
        dtype=object,
    )

    tec = np.asarray(
        [
            10.0,
            14.0,
            18.0,
        ],
        dtype=np.float64,
    )

    result = interpolate_hourly_tec(
        epochs=epochs,
        tec=tec,
    )

    expected = np.asarray(
        [
            10.0,
            12.0,
            14.0,
            16.0,
            18.0,
        ],
        dtype=np.float64,
    )

    np.testing.assert_allclose(
        result.tec,
        expected,
    )

    assert np.array_equal(
        result.observed_mask,
        [
            True,
            False,
            True,
            False,
            True,
        ],
    )

    assert np.array_equal(
        result.interpolated_mask,
        [
            False,
            True,
            False,
            True,
            False,
        ],
    )


def test_existing_hourly_data_are_preserved():

    start = datetime(
        2020,
        1,
        1,
        0,
    )

    epochs = np.asarray(
        [
            start + timedelta(hours=i)
            for i in range(4)
        ],
        dtype=object,
    )

    tec = np.asarray(
        [
            10.0,
            11.0,
            12.0,
            13.0,
        ],
        dtype=np.float64,
    )

    result = interpolate_hourly_tec(
        epochs=epochs,
        tec=tec,
    )

    np.testing.assert_array_equal(
        result.tec,
        tec,
    )

    assert np.all(
        result.observed_mask
    )

    assert not np.any(
        result.interpolated_mask
    )


def test_two_hour_cadence_starting_at_01_ut_across_days():

    start = datetime(
        2020,
        1,
        1,
        1,
    )

    epochs = np.asarray(
        [
            start + timedelta(hours=2 * i)
            for i in range(14)
        ],
        dtype=object,
    )

    tec = np.asarray(
        [
            10.0 + 2.0 * i
            for i in range(14)
        ],
        dtype=np.float64,
    )

    result = interpolate_hourly_tec(
        epochs=epochs,
        tec=tec,
    )

    # 01 UT on Jan 1 through 03 UT on Jan 2
    assert result.epochs[0] == datetime(
        2020, 1, 1, 1
    )

    assert result.epochs[-1] == datetime(
        2020, 1, 2, 3
    )

    assert len(result.epochs) == 27

    expected = np.arange(
        10.0,
        37.0,
        1.0,
        dtype=np.float64,
    )

    np.testing.assert_allclose(
        result.tec,
        expected,
    )

    # Original observations occur every two hours.
    assert np.all(
        result.observed_mask[::2]
    )

    assert not np.any(
        result.observed_mask[1::2]
    )

    # Missing internal hours are interpolated.
    assert not np.any(
        result.interpolated_mask[::2]
    )

    assert np.all(
        result.interpolated_mask[1::2]
    )


def test_transition_from_two_hour_to_hourly_cadence():

    epochs = np.asarray(
        [
            datetime(2020, 1, 1, 19),
            datetime(2020, 1, 1, 21),
            datetime(2020, 1, 1, 23),

            datetime(2020, 1, 2, 0),
            datetime(2020, 1, 2, 1),
            datetime(2020, 1, 2, 2),
            datetime(2020, 1, 2, 3),
        ],
        dtype=object,
    )

    tec = np.asarray(
        [
            10.0,
            12.0,
            14.0,
            15.0,
            16.0,
            17.0,
            18.0,
        ],
        dtype=np.float64,
    )

    result = interpolate_hourly_tec(
        epochs=epochs,
        tec=tec,
    )

    expected_epochs = np.asarray(
        [
            datetime(2020, 1, 1, 19),
            datetime(2020, 1, 1, 20),
            datetime(2020, 1, 1, 21),
            datetime(2020, 1, 1, 22),
            datetime(2020, 1, 1, 23),
            datetime(2020, 1, 2, 0),
            datetime(2020, 1, 2, 1),
            datetime(2020, 1, 2, 2),
            datetime(2020, 1, 2, 3),
        ],
        dtype=object,
    )

    expected_tec = np.asarray(
        [
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
            16.0,
            17.0,
            18.0,
        ],
        dtype=np.float64,
    )

    assert np.array_equal(
        result.epochs,
        expected_epochs,
    )

    np.testing.assert_allclose(
        result.tec,
        expected_tec,
    )

    expected_observed = np.asarray(
        [
            True,
            False,
            True,
            False,
            True,
            True,
            True,
            True,
            True,
        ]
    )

    assert np.array_equal(
        result.observed_mask,
        expected_observed,
    )

    assert np.array_equal(
        result.interpolated_mask,
        ~expected_observed,
    )


def test_requested_range_preserves_boundary_as_nan():

    epochs = np.asarray(
        [
            datetime(1999, 1, 1, 1),
            datetime(1999, 1, 1, 3),
            datetime(1999, 1, 1, 5),
        ],
        dtype=object,
    )

    tec = np.asarray(
        [
            10.0,
            14.0,
            18.0,
        ],
        dtype=np.float64,
    )

    result = interpolate_hourly_tec(
        epochs=epochs,
        tec=tec,
        start_time=datetime(
            1999, 1, 1, 0
        ),
        end_time=datetime(
            1999, 1, 1, 5
        ),
    )

    expected = np.asarray(
        [
            np.nan,
            10.0,
            12.0,
            14.0,
            16.0,
            18.0,
        ],
        dtype=np.float64,
    )

    np.testing.assert_allclose(
        result.tec,
        expected,
        equal_nan=True,
    )

    assert not result.observed_mask[0]
    assert not result.interpolated_mask[0]

    assert result.observed_mask[1]
    assert result.interpolated_mask[2]