from datetime import datetime, timedelta, timezone

import pytest

from src.workflow.datetime_adapter import (
    to_naive_utc,
    window_to_naive_utc,
)
from src.workflow.temporal_window import TemporalWindow


def test_to_naive_utc():
    value = datetime(2022, 5, 28, 0, tzinfo=timezone.utc)

    result = to_naive_utc(value)

    assert result == datetime(2022, 5, 28, 0)
    assert result.tzinfo is None


def test_reject_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        to_naive_utc(datetime(2022, 5, 28, 0))


def test_reject_non_utc_timezone():
    local_tz = timezone(timedelta(hours=8))

    with pytest.raises(ValueError, match="must use UTC"):
        to_naive_utc(
            datetime(2022, 5, 28, 8, tzinfo=local_tz)
        )


def test_reject_non_datetime():
    with pytest.raises(TypeError, match="datetime"):
        to_naive_utc("2022-05-28")


def test_window_to_naive_utc():
    window = TemporalWindow(
        start_time=datetime(2022, 5, 28, 0, tzinfo=timezone.utc),
        end_time=datetime(2022, 6, 1, 23, tzinfo=timezone.utc),
        selection_mode="explicit",
    )

    start, end = window_to_naive_utc(window)

    assert start == datetime(2022, 5, 28, 0)
    assert end == datetime(2022, 6, 1, 23)
    assert start.tzinfo is None
    assert end.tzinfo is None


def test_reject_invalid_window():
    with pytest.raises(TypeError, match="TemporalWindow"):
        window_to_naive_utc("invalid")