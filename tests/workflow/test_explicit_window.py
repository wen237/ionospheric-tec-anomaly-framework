import pytest

from datetime import datetime, timezone

from src.workflow.explicit_window import select_explicit_window


def test_valid_explicit_window():
    window = select_explicit_window(
        "2022-05-28T00:00:00Z",
        "2022-06-01T23:00:00Z",
    )

    assert window.start_time == datetime(
        2022, 5, 28, 0, tzinfo=timezone.utc
    )
    assert window.end_time == datetime(
        2022, 6, 1, 23, tzinfo=timezone.utc
    )
    assert window.selection_mode == "explicit"


def test_valid_utc_offset():
    window = select_explicit_window(
        "2022-05-28T00:00:00+00:00",
        "2022-06-01T23:00:00+00:00",
    )

    assert window.start_time.tzinfo == timezone.utc


def test_reject_naive_datetime_string():
    with pytest.raises(ValueError, match="explicit UTC"):
        select_explicit_window(
            "2022-05-28T00:00:00",
            "2022-06-01T23:00:00Z",
        )


def test_reject_non_utc_timezone():
    with pytest.raises(ValueError, match="must use UTC"):
        select_explicit_window(
            "2022-05-28T08:00:00+08:00",
            "2022-06-01T23:00:00Z",
        )


def test_reject_invalid_format():
    with pytest.raises(ValueError, match="ISO 8601"):
        select_explicit_window(
            "2022/05/28 00:00",
            "2022-06-01T23:00:00Z",
        )


def test_reject_non_hourly_timestamp():
    with pytest.raises(ValueError, match="hourly"):
        select_explicit_window(
            "2022-05-28T00:30:00Z",
            "2022-06-01T23:00:00Z",
        )


def test_reject_reversed_window():
    with pytest.raises(ValueError, match="start_time"):
        select_explicit_window(
            "2022-06-01T23:00:00Z",
            "2022-05-28T00:00:00Z",
        )


def test_reject_non_string_input():
    with pytest.raises(TypeError, match="start_time"):
        select_explicit_window(
            datetime(2022, 5, 28, tzinfo=timezone.utc),
            "2022-06-01T23:00:00Z",
        )