from datetime import datetime, timedelta, timezone

import pytest

from src.workflow.temporal_window import TemporalWindow


def test_valid_explicit_window():
    window = TemporalWindow(
        start_time=datetime(2022, 5, 28, 0, tzinfo=timezone.utc),
        end_time=datetime(2022, 6, 1, 23, tzinfo=timezone.utc),
        selection_mode="explicit",
    )

    assert window.selection_mode == "explicit"
    assert window.start_time < window.end_time


def test_single_hour_window():
    timestamp = datetime(
        2022, 5, 28, 0, tzinfo=timezone.utc
    )

    window = TemporalWindow(
        start_time=timestamp,
        end_time=timestamp,
        selection_mode="explicit",
    )

    assert window.start_time == window.end_time


def test_reversed_window():
    with pytest.raises(ValueError, match="start_time"):
        TemporalWindow(
            start_time=datetime(2022, 6, 1, tzinfo=timezone.utc),
            end_time=datetime(2022, 5, 28, tzinfo=timezone.utc),
            selection_mode="explicit",
        )


def test_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        TemporalWindow(
            start_time=datetime(2022, 5, 28),
            end_time=datetime(2022, 6, 1, tzinfo=timezone.utc),
            selection_mode="explicit",
        )


def test_non_utc_timezone():
    local_timezone = timezone(timedelta(hours=8))

    with pytest.raises(ValueError, match="must use UTC"):
        TemporalWindow(
            start_time=datetime(
                2022, 5, 28, tzinfo=local_timezone
            ),
            end_time=datetime(
                2022, 6, 1, tzinfo=local_timezone
            ),
            selection_mode="explicit",
        )


def test_non_hourly_timestamp():
    with pytest.raises(ValueError, match="hourly"):
        TemporalWindow(
            start_time=datetime(
                2022, 5, 28, 0, 30, tzinfo=timezone.utc
            ),
            end_time=datetime(
                2022, 6, 1, tzinfo=timezone.utc
            ),
            selection_mode="explicit",
        )


def test_unsupported_mode():
    with pytest.raises(ValueError, match="Unsupported"):
        TemporalWindow(
            start_time=datetime(2022, 5, 28, tzinfo=timezone.utc),
            end_time=datetime(2022, 6, 1, tzinfo=timezone.utc),
            selection_mode="automatic",
        )