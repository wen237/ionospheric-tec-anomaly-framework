"""Explicit temporal window selection for workflow integration."""

from datetime import datetime, timezone

from .temporal_window import TemporalWindow


def select_explicit_window(
    start_time: str,
    end_time: str,
) -> TemporalWindow:
    """Create an explicit UTC temporal window from ISO 8601 strings."""

    if not isinstance(start_time, str):
        raise TypeError("start_time must be a string.")

    if not isinstance(end_time, str):
        raise TypeError("end_time must be a string.")

    def parse_utc(value: str, name: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError(
                f"{name} must be a valid ISO 8601 datetime."
            ) from exc

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(
                f"{name} must include an explicit UTC timezone."
            )

        if parsed.utcoffset().total_seconds() != 0:
            raise ValueError(
                f"{name} must use UTC."
            )

        return parsed.astimezone(timezone.utc)

    return TemporalWindow(
        start_time=parse_utc(start_time, "start_time"),
        end_time=parse_utc(end_time, "end_time"),
        selection_mode="explicit",
    )