from datetime import datetime, timedelta

import numpy as np

from tec_timeseries import TECTimeSeries
from tec_timeseries_collection import combine_tec_timeseries


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


def main():
    start = datetime(2022, 1, 1)

    series_a = make_series(
        epochs=[
            start,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
        ],
        tec=[
            10.0,
            11.0,
            12.0,
        ],
    )

    series_b = make_series(
        epochs=[
            start + timedelta(hours=2),
            start + timedelta(hours=3),
            start + timedelta(hours=4),
        ],
        tec=[
            12.0,
            13.0,
            14.0,
        ],
    )

    print("=== Normal combination ===")

    combined = combine_tec_timeseries(
        [
            series_a,
            series_b,
        ]
    )

    print("Epoch count:", len(combined.epochs))
    print("TEC        :", combined.tec)
    print("First epoch:", combined.epochs[0])
    print("Last epoch :", combined.epochs[-1])

    assert len(combined.epochs) == 5

    assert np.array_equal(
        combined.tec,
        np.array(
            [10, 11, 12, 13, 14],
            dtype=float,
        ),
    )

    print("Normal combination: PASS")

    print("\n=== Reverse input order ===")

    combined_reverse = combine_tec_timeseries(
        [
            series_b,
            series_a,
        ]
    )

    assert np.array_equal(
        combined.epochs,
        combined_reverse.epochs,
    )

    assert np.array_equal(
        combined.tec,
        combined_reverse.tec,
    )

    print("Reverse input order: PASS")

    print("\n=== Duplicate NaN case ===")

    series_nan_a = make_series(
        epochs=[
            start,
            start + timedelta(hours=1),
        ],
        tec=[
            10.0,
            np.nan,
        ],
    )

    series_nan_b = make_series(
        epochs=[
            start + timedelta(hours=1),
            start + timedelta(hours=2),
        ],
        tec=[
            np.nan,
            12.0,
        ],
    )

    combined_nan = combine_tec_timeseries(
        [
            series_nan_a,
            series_nan_b,
        ]
    )

    assert len(combined_nan.epochs) == 3
    assert np.isnan(combined_nan.tec[1])

    print("Duplicate NaN: PASS")

    print("\n=== Inconsistent duplicate case ===")

    series_conflict = make_series(
        epochs=[
            start + timedelta(hours=2),
            start + timedelta(hours=3),
        ],
        tec=[
            99.0,
            13.0,
        ],
    )

    try:
        combine_tec_timeseries(
            [
                series_a,
                series_conflict,
            ]
        )

    except ValueError as exc:
        print("Expected error:")
        print(exc)
        print("Inconsistent duplicate: PASS")

    else:
        raise AssertionError(
            "Expected inconsistent duplicate TEC values "
            "to raise ValueError."
        )


if __name__ == "__main__":
    main()
    