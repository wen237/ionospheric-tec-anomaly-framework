from datetime import datetime, timedelta

import numpy as np

from src.temporal_anomaly.tec_timeseries import extract_tec_timeseries


def test_extract_tec_timeseries_nearest_grid_point():
    epochs = np.array(
        [
            datetime(2022, 1, 1) + timedelta(hours=i)
            for i in range(3)
        ],
        dtype=object,
    )

    latitudes = np.array(
        [10.0, 7.5, 5.0],
        dtype=float,
    )

    longitudes = np.array(
        [0.0, 5.0, 10.0],
        dtype=float,
    )

    tec = np.array(
        [
            [
                [1, 2, 3],
                [4, 5, 6],
                [7, 8, 9],
            ],
            [
                [11, 12, 13],
                [14, 15, 16],
                [17, 18, 19],
            ],
            [
                [21, 22, 23],
                [24, 25, 26],
                [27, 28, 29],
            ],
        ],
        dtype=float,
    )

    result = extract_tec_timeseries(
        tec=tec,
        epochs=epochs,
        latitudes=latitudes,
        longitudes=longitudes,
        latitude=7.4,
        longitude=5.2,
    )

    assert result.requested_latitude == 7.4
    assert result.requested_longitude == 5.2
    assert result.grid_latitude == 7.5
    assert result.grid_longitude == 5.0
    assert result.latitude_index == 1
    assert result.longitude_index == 1

    np.testing.assert_array_equal(
        result.tec,
        np.array([5.0, 15.0, 25.0]),
    )


def test_extract_tec_timeseries_wraps_negative_longitude():
    longitudes = np.array(
        [0.0, 90.0, 180.0, 270.0],
        dtype=float,
    )

    tec = np.array(
        [
            [[10, 20, 30, 40]],
            [[11, 21, 31, 41]],
        ],
        dtype=float,
    )

    epochs = np.array(
        [
            datetime(2022, 1, 1, 0),
            datetime(2022, 1, 1, 1),
        ],
        dtype=object,
    )

    result = extract_tec_timeseries(
        tec=tec,
        epochs=epochs,
        latitudes=np.array([0.0]),
        longitudes=longitudes,
        latitude=0.0,
        longitude=-90.0,
    )

    assert result.grid_longitude == 270.0

    np.testing.assert_array_equal(
        result.tec,
        np.array([40.0, 41.0]),
    )