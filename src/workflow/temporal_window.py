"""Validated UTC temporal window for workflow integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal


WindowSelectionMode = Literal[
    "explicit",
    "deterministic",
    "exhaustive",
]


@dataclass(frozen=True)
class TemporalWindow:
    """Inclusive UTC window used by downstream scientific frameworks."""

    start_time: datetime
    end_time: datetime
    selection_mode: WindowSelectionMode

    def __post_init__(self) -> None:
        for name, value in (
            ("start_time", self.start_time),
            ("end_time", self.end_time),
        ):
            if not isinstance(value, datetime):
                raise TypeError(
                    f"{name} must be a datetime object."
                )

            offset = value.utcoffset()

            if offset is None:
                raise ValueError(
                    f"{name} must be timezone-aware UTC."
                )

            if offset != timedelta(0):
                raise ValueError(
                    f"{name} must use UTC."
                )

            if (
                value.minute != 0
                or value.second != 0
                or value.microsecond != 0
            ):
                raise ValueError(
                    f"{name} must align with an hourly GIM epoch."
                )

        if self.start_time > self.end_time:
            raise ValueError(
                "start_time must not exceed end_time."
            )

        if self.selection_mode not in (
            "explicit",
            "deterministic",
            "exhaustive",
        ):
            raise ValueError(
                "Unsupported window selection mode."
            )