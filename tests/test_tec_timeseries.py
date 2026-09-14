from datetime import datetime, timedelta

import numpy as np

from tec_timeseries import extract_tec_timeseries


def main():
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

    print("Requested latitude :", result.requested_latitude)
    print("Requested longitude:", result.requested_longitude)

    print("Grid latitude      :", result.grid_latitude)
    print("Grid longitude     :", result.grid_longitude)

    print("Latitude index     :", result.latitude_index)
    print("Longitude index    :", result.longitude_index)

    print("TEC                :", result.tec)

    print("\n=== Longitude wrap test ===")

    longitudes_wrap = np.array(
        [0.0, 90.0, 180.0, 270.0],
        dtype=float,
    )

    tec_wrap = np.array(
        [
            [
                [10, 20, 30, 40],
            ],
            [
                [11, 21, 31, 41],
            ],
        ],
        dtype=float,
    )

    epochs_wrap = np.array(
        [
            datetime(2022, 1, 1, 0),
            datetime(2022, 1, 1, 1),
        ],
        dtype=object,
    )

    result_wrap = extract_tec_timeseries(
        tec=tec_wrap,
        epochs=epochs_wrap,
        latitudes=np.array([0.0]),
        longitudes=longitudes_wrap,
        latitude=0.0,
        longitude=-90.0,
    )

    print("Grid longitude :", result_wrap.grid_longitude)
    print("TEC            :", result_wrap.tec)


if __name__ == "__main__":
    main()
    