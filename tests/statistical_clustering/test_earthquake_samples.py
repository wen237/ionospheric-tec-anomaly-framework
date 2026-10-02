from datetime import date

import numpy as np

from src.statistical_clustering.earthquake_samples import (
    select_earthquake_samples,
)


def test_selection_includes_exact_date_boundaries():

    event_dates = np.asarray(
        [
            date(2000, 2, 14),  # one day too early
            date(2000, 2, 15),  # exact lower boundary
            date(2000, 6, 1),   # interior
            date(2000, 12, 1),  # exact upper boundary
            date(2000, 12, 2),  # one day too late
        ],
        dtype=object,
    )

    magnitudes = np.asarray(
        [
            6.0,
            6.0,
            6.5,
            7.0,
            6.0,
        ],
        dtype=np.float64,
    )

    result = select_earthquake_samples(
        event_dates=event_dates,
        magnitudes=magnitudes,
        analysis_start=date(
            2000, 1, 1
        ),
        analysis_end=date(
            2000, 12, 31
        ),
        minimum_magnitude=6.0,
        observation_days=30,
        reference_days=15,
    )

    expected_mask = np.asarray(
        [
            False,
            True,
            True,
            True,
            False,
        ]
    )

    assert np.array_equal(
        result.selected_mask,
        expected_mask,
    )


def test_selection_includes_exact_magnitude_threshold():

    event_dates = np.asarray(
        [
            date(2000, 6, 1),
            date(2000, 6, 2),
            date(2000, 6, 3),
        ],
        dtype=object,
    )

    magnitudes = np.asarray(
        [
            5.9,
            6.0,
            6.1,
        ],
        dtype=np.float64,
    )

    result = select_earthquake_samples(
        event_dates=event_dates,
        magnitudes=magnitudes,
        analysis_start=date(
            2000, 1, 1
        ),
        analysis_end=date(
            2000, 12, 31
        ),
        minimum_magnitude=6.0,
        observation_days=30,
        reference_days=15,
    )

    expected_mask = np.asarray(
        [
            False,
            True,
            True,
        ]
    )

    assert np.array_equal(
        result.selected_mask,
        expected_mask,
    )


def test_datetime_is_selected_by_calendar_date():

    from datetime import datetime

    event_dates = np.asarray(
        [
            datetime(
                2000, 2, 15, 23, 59, 59
            ),
        ],
        dtype=object,
    )

    magnitudes = np.asarray(
        [6.0],
        dtype=np.float64,
    )

    result = select_earthquake_samples(
        event_dates=event_dates,
        magnitudes=magnitudes,
        analysis_start=date(
            2000, 1, 1
        ),
        analysis_end=date(
            2000, 12, 31
        ),
        minimum_magnitude=6.0,
        observation_days=30,
        reference_days=15,
    )

    assert result.selected_mask[0]
    assert result.selected_dates[0] == date(
        2000, 2, 15
    )