"""Validate multi-day TEC preparation for the Afghanistan case.

This script validates the data-preparation workflow used before temporal
anomaly detection:

processed daily GIM data
    -> TEC grid-point extraction
    -> calendar-day selection
    -> multi-day combination

Each daily dataset contains 25 epochs from 00:00 UT of the target day to
00:00 UT of the following day. Only the 24 epochs belonging to the target
calendar date are retained.
"""

from datetime import timedelta
import numpy as np

from src.temporal_anomaly.tec_timeseries import extract_tec_timeseries
from src.temporal_anomaly.tec_timeseries_collection import (
    combine_tec_timeseries,
    select_calendar_day,
)
from validation.temporal_anomaly.config import (
    END_TIME,
    LATITUDE,
    LONGITUDE,
    PROCESSED_DIR,
    START_TIME,
)


# ==========================================================
# Afghanistan case configuration
# ==========================================================

EXPECTED_DAYS = 46
EXPECTED_RAW_EPOCHS = EXPECTED_DAYS * 25
EXPECTED_SELECTED_EPOCHS = EXPECTED_DAYS * 24

EXPECTED_GRID_LATITUDE = 32.5
EXPECTED_GRID_LONGITUDE = 70.0


def date_range(start_date, end_date):
    """Yield calendar dates inclusively."""

    current = start_date

    while current <= end_date:
        yield current
        current += timedelta(days=1)


def main() -> None:
    """Run the Afghanistan TEC collection validation."""

    daily_series_list = []

    raw_epoch_count = 0
    selected_epoch_count = 0
    selected_grid_points = set()

    print(
        "========================================"
    )
    print(
        "Afghanistan TEC collection validation"
    )
    print(
        "========================================"
    )

    for day in date_range(
        START_TIME.date(),
        END_TIME.date(),
    ):

        path = (
            PROCESSED_DIR
            / f"gim_{day.strftime('%Y%m%d')}.npz"
        )

        data = np.load(path)

        tec = data["tec"]
        epochs = data["epochs"]
        latitudes = data["lat"]
        longitudes = data["lon"]

        series = extract_tec_timeseries(
            tec=tec,
            epochs=epochs,
            latitudes=latitudes,
            longitudes=longitudes,
            latitude=LATITUDE,
            longitude=LONGITUDE,
        )

        raw_epoch_count += len(
            series.epochs
        )

        selected_grid_points.add(
            (
                series.grid_latitude,
                series.grid_longitude,
            )
        )

        daily_series = select_calendar_day(
            series,
            target_date=day,
        )

        selected_epoch_count += len(
            daily_series.epochs
        )

        # Per-day validation
        assert len(series.epochs) == 25, (
            f"{day}: expected 25 raw epochs, "
            f"got {len(series.epochs)}."
        )

        assert len(daily_series.epochs) == 24, (
            f"{day}: expected 24 selected epochs, "
            f"got {len(daily_series.epochs)}."
        )

        assert all(
            epoch.date() == day
            for epoch in daily_series.epochs
        ), (
            f"{day}: selected series contains epochs "
            "outside the target calendar date."
        )

        assert (
            daily_series.epochs[0].hour == 0
        ), (
            f"{day}: first selected epoch is not 00 UT."
        )

        assert (
            daily_series.epochs[-1].hour == 23
        ), (
            f"{day}: last selected epoch is not 23 UT."
        )

        daily_series_list.append(
            daily_series
        )

    # ======================================================
    # Pre-combination validation
    # ======================================================

    print(
        "\n=== Daily preparation summary ==="
    )

    print(
        "Number of daily files :",
        len(daily_series_list),
    )

    print(
        "Raw epoch count       :",
        raw_epoch_count,
    )

    print(
        "Selected epoch count  :",
        selected_epoch_count,
    )

    print(
        "Selected grid points  :",
        selected_grid_points,
    )

    assert (
        len(daily_series_list)
        == EXPECTED_DAYS
    ), (
        f"Expected {EXPECTED_DAYS} daily files."
    )

    assert (
        raw_epoch_count
        == EXPECTED_RAW_EPOCHS
    ), (
        f"Expected {EXPECTED_RAW_EPOCHS} raw epochs."
    )

    assert (
        selected_epoch_count
        == EXPECTED_SELECTED_EPOCHS
    ), (
        f"Expected {EXPECTED_SELECTED_EPOCHS} "
        "selected epochs."
    )

    assert selected_grid_points == {
        (
            EXPECTED_GRID_LATITUDE,
            EXPECTED_GRID_LONGITUDE,
        )
    }, (
        "Unexpected grid-point selection: "
        f"{selected_grid_points}"
    )

    # ======================================================
    # Combine daily series
    # ======================================================

    combined = combine_tec_timeseries(
        daily_series_list
    )

    print(
        "\n=== Combined TEC series ==="
    )

    print(
        "Epoch count :",
        len(combined.epochs),
    )

    print(
        "TEC shape   :",
        combined.tec.shape,
    )

    print(
        "First epoch :",
        combined.epochs[0],
    )

    print(
        "Last epoch  :",
        combined.epochs[-1],
    )

    print(
        "Grid point  :",
        (
            combined.grid_latitude,
            combined.grid_longitude,
        ),
    )

    # ======================================================
    # Final structural validation
    # ======================================================

    assert len(combined.epochs) == (
        EXPECTED_SELECTED_EPOCHS
    )

    assert combined.tec.shape == (
        EXPECTED_SELECTED_EPOCHS,
    )

    assert (
        combined.epochs[0]
        == START_TIME
    ), (
        "Unexpected first combined epoch."
    )

    assert (
        combined.epochs[-1]
        == END_TIME
    ), (
        "Unexpected last combined epoch."
    )

    assert (
        len(set(combined.epochs))
        == len(combined.epochs)
    ), (
        "Combined series contains duplicate timestamps."
    )

    assert all(
        combined.epochs[i]
        < combined.epochs[i + 1]
        for i in range(
            len(combined.epochs) - 1
        )
    ), (
        "Combined epochs are not strictly increasing."
    )

    assert np.isclose(
        combined.grid_latitude,
        EXPECTED_GRID_LATITUDE,
    )

    assert np.isclose(
        combined.grid_longitude,
        EXPECTED_GRID_LONGITUDE,
    )

    print(
        "\nAfghanistan TEC collection "
        "structural validation: PASS"
    )


if __name__ == "__main__":
    main()