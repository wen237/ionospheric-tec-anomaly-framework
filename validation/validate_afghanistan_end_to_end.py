"""Run end-to-end validation for the Afghanistan temporal-anomaly workflow.

This script validates the complete Module A workflow using processed daily
GIM data:

processed daily GIM data
    -> fixed-point TEC extraction
    -> calendar-day selection
    -> multi-day TEC combination
    -> temporal anomaly detection

The final anomaly counts are compared with the validated Afghanistan case
results.
"""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from tec_timeseries import extract_tec_timeseries
from tec_timeseries_collection import (
    combine_tec_timeseries,
    select_calendar_day,
)
from temporal_anomaly import detect_temporal_anomalies


# ==========================================================
# Afghanistan case configuration
# ==========================================================

LATITUDE = 33.020
LONGITUDE = 69.464

START_TIME = datetime(
    2022,
    5,
    7,
    0,
    0,
)

END_TIME = datetime(
    2022,
    6,
    21,
    23,
    0,
)

REFERENCE_DAYS = 15
THRESHOLD_MULTIPLIER = 3.0

EXPECTED_FILES = 46
EXPECTED_INPUT_POINTS = 1104
EXPECTED_ANALYSIS_POINTS = 744

EXPECTED_GRID_LATITUDE = 32.5
EXPECTED_GRID_LONGITUDE = 70.0

EXPECTED_POSITIVE = 37
EXPECTED_NORMAL = 610
EXPECTED_NEGATIVE = 97

EXPECTED_ANALYSIS_START = datetime(
    2022,
    5,
    22,
    0,
    0,
)

EXPECTED_ANALYSIS_END = datetime(
    2022,
    6,
    21,
    23,
    0,
)

PROCESSED_DIR = Path("processed")


def date_range(start_date, end_date):
    """Yield calendar dates inclusively."""

    current = start_date

    while current <= end_date:
        yield current
        current += timedelta(days=1)


def main() -> None:
    """Run the Afghanistan end-to-end validation."""

    daily_series_list = []

    print(
        "========================================"
    )
    print(
        "Afghanistan end-to-end validation"
    )
    print(
        "========================================"
    )

    # ======================================================
    # 1. Build the 46-day TEC input
    # ======================================================

    for day in date_range(
        START_TIME.date(),
        END_TIME.date(),
    ):

        path = (
            PROCESSED_DIR
            / f"gim_{day.strftime('%Y%m%d')}.npz"
        )

        data = np.load(path)

        series = extract_tec_timeseries(
            tec=data["tec"],
            epochs=data["epochs"],
            latitudes=data["lat"],
            longitudes=data["lon"],
            latitude=LATITUDE,
            longitude=LONGITUDE,
        )

        daily_series = select_calendar_day(
            series,
            target_date=day,
        )

        assert len(series.epochs) == 25, (
            f"{day}: expected 25 raw epochs, "
            f"got {len(series.epochs)}."
        )

        assert len(daily_series.epochs) == 24, (
            f"{day}: expected 24 daily epochs, "
            f"got {len(daily_series.epochs)}."
        )

        assert all(
            epoch.date() == day
            for epoch in daily_series.epochs
        ), (
            f"{day}: selected TEC contains epochs "
            "outside the target calendar date."
        )

        daily_series_list.append(
            daily_series
        )

    # ======================================================
    # 2. Combine the daily TEC series
    # ======================================================

    combined = combine_tec_timeseries(
        daily_series_list
    )

    print(
        "\n=== TEC input ==="
    )

    print(
        "Daily files    :",
        len(daily_series_list),
    )

    print(
        "TEC points     :",
        len(combined.tec),
    )

    print(
        "TEC shape      :",
        combined.tec.shape,
    )

    print(
        "First epoch    :",
        combined.epochs[0],
    )

    print(
        "Last epoch     :",
        combined.epochs[-1],
    )

    print(
        "Grid point     :",
        (
            combined.grid_latitude,
            combined.grid_longitude,
        ),
    )

    # ======================================================
    # 3. Validate the TEC input
    # ======================================================

    assert (
        len(daily_series_list)
        == EXPECTED_FILES
    ), (
        f"Expected {EXPECTED_FILES} daily files."
    )

    assert (
        len(combined.tec)
        == EXPECTED_INPUT_POINTS
    ), (
        f"Expected {EXPECTED_INPUT_POINTS} TEC points."
    )

    assert combined.tec.shape == (
        EXPECTED_INPUT_POINTS,
    )

    assert (
        combined.epochs[0]
        == START_TIME
    ), (
        "Unexpected first TEC epoch."
    )

    assert (
        combined.epochs[-1]
        == END_TIME
    ), (
        "Unexpected last TEC epoch."
    )

    assert np.isclose(
        combined.grid_latitude,
        EXPECTED_GRID_LATITUDE,
    )

    assert np.isclose(
        combined.grid_longitude,
        EXPECTED_GRID_LONGITUDE,
    )

    # ======================================================
    # 4. Run temporal anomaly detection
    # ======================================================

    result = detect_temporal_anomalies(
        tec=combined.tec,
        epochs=combined.epochs,
        reference_days=REFERENCE_DAYS,
        threshold_multiplier=THRESHOLD_MULTIPLIER,
    )

    anomaly = np.asarray(
        result.anomaly
    )

    positive_count = int(
        np.count_nonzero(
            anomaly == 1
        )
    )

    normal_count = int(
        np.count_nonzero(
            anomaly == 0
        )
    )

    negative_count = int(
        np.count_nonzero(
            anomaly == -1
        )
    )

    # ======================================================
    # 5. Validate anomaly output structure
    # ======================================================

    print(
        "\n=== Temporal anomaly result ==="
    )

    print(
        "Analysis points:",
        len(result.epochs),
    )

    print(
        "First epoch    :",
        result.epochs[0],
    )

    print(
        "Last epoch     :",
        result.epochs[-1],
    )

    print(
        "Positive       :",
        positive_count,
    )

    print(
        "Normal         :",
        normal_count,
    )

    print(
        "Negative       :",
        negative_count,
    )

    assert (
        len(result.epochs)
        == EXPECTED_ANALYSIS_POINTS
    ), (
        f"Expected {EXPECTED_ANALYSIS_POINTS} "
        "analysis epochs."
    )

    assert (
        result.epochs[0]
        == EXPECTED_ANALYSIS_START
    ), (
        "Unexpected first analysis epoch."
    )

    assert (
        result.epochs[-1]
        == EXPECTED_ANALYSIS_END
    ), (
        "Unexpected last analysis epoch."
    )

    unique_codes = set(
        np.unique(anomaly).tolist()
    )

    assert unique_codes.issubset(
        {-1, 0, 1}
    ), (
        f"Unexpected anomaly codes: {unique_codes}"
    )

    assert (
        positive_count
        + normal_count
        + negative_count
        == EXPECTED_ANALYSIS_POINTS
    ), (
        "Anomaly counts do not sum to "
        "the number of analysis points."
    )

    # ======================================================
    # 6. Validate the Afghanistan scientific result
    # ======================================================

    assert (
        positive_count
        == EXPECTED_POSITIVE
    ), (
        "Unexpected number of positive anomalies: "
        f"{positive_count} "
        f"(expected {EXPECTED_POSITIVE})."
    )

    assert (
        normal_count
        == EXPECTED_NORMAL
    ), (
        "Unexpected number of normal observations: "
        f"{normal_count} "
        f"(expected {EXPECTED_NORMAL})."
    )

    assert (
        negative_count
        == EXPECTED_NEGATIVE
    ), (
        "Unexpected number of negative anomalies: "
        f"{negative_count} "
        f"(expected {EXPECTED_NEGATIVE})."
    )

    print(
        "\nAfghanistan end-to-end validation: PASS"
    )


if __name__ == "__main__":
    main()