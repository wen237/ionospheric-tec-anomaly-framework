"""Read-only data bridge from validated modern GIM daily series to workflows.

No analysis, interpolation, time substitution, or unit conversion occurs here.
The source series owns each day's 00..23 UTC maps; index 24 is discarded.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import Sequence

import numpy as np

from .modern_gim_series import load_modern_gim_series


@dataclass(frozen=True)
class ModernGIMWindow:
    tec: np.ndarray                 # (hours, 71, 73), TECU, latitude ascending
    timestamps: tuple[datetime, ...]  # naive UTC, inclusive
    lat: np.ndarray
    lon: np.ndarray
    reference_days: int
    window_steps: int
    source_files: tuple[str, ...]


def load_modern_gim_window(
    file_paths: Sequence[str | Path],
    start_time: datetime,
    end_time: datetime,
    *,
    reference_days: int = 15,
) -> ModernGIMWindow:
    """Select exact reference + analysis hours from daily modern NPZ inputs.

    File paths are explicitly supplied; no provider or missing day is guessed.
    """
    for name, value in (("start_time", start_time), ("end_time", end_time)):
        if not isinstance(value, datetime):
            raise TypeError(f"{name} must be a datetime.")
        if value.tzinfo is not None or (value.minute, value.second, value.microsecond) != (0, 0, 0):
            raise ValueError(f"{name} must be naive UTC and hour-aligned.")
    if start_time > end_time:
        raise ValueError("start_time must not exceed end_time.")
    if type(reference_days) is not int or reference_days <= 0:
        raise ValueError("reference_days must be a positive integer.")

    series = load_modern_gim_series(file_paths)
    ref_start = start_time - timedelta(days=reference_days)
    wanted = np.arange(
        np.datetime64(ref_start, 's'),
        np.datetime64(end_time + timedelta(hours=1), 's'),
        np.timedelta64(1, 'h'),
    )
    if wanted.size == 0:
        raise ValueError("Requested window has no hourly samples.")
    first = np.searchsorted(series.epochs, wanted[0])
    last = first + wanted.size
    if last > len(series.epochs) or not np.array_equal(series.epochs[first:last], wanted):
        raise ValueError("Daily GIM inputs do not cover the complete requested UTC window.")
    timestamps = tuple(ref_start + timedelta(hours=i) for i in range(wanted.size))
    return ModernGIMWindow(
        tec=series.tec[first:last].copy(),
        timestamps=timestamps,
        lat=series.lat.copy(), lon=series.lon.copy(),
        reference_days=reference_days,
        window_steps=int((end_time-start_time)/timedelta(hours=1)) + 1,
        source_files=series.source_files,
    )
