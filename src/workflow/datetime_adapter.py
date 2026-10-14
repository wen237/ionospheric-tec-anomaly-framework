"""Datetime adapters between workflow and validated scientific cores."""

from datetime import datetime, timezone

from .temporal_window import TemporalWindow


def to_naive_utc(value: datetime) -> datetime:
    """Convert an aware UTC datetime to naive UTC."""

    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime object.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("value must be timezone-aware.")

    if value.utcoffset().total_seconds() != 0:
        raise ValueError("value must use UTC.")

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def window_to_naive_utc(
    window: TemporalWindow,
) -> tuple[datetime, datetime]:
    """Return naive UTC start/end times for scientific core APIs."""

    if not isinstance(window, TemporalWindow):
        raise TypeError("window must be a TemporalWindow.")

    return (
        to_naive_utc(window.start_time),
        to_naive_utc(window.end_time),
    )