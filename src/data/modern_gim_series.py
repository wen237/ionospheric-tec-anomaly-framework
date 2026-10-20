"""Merge consecutive modern CODE GIM daily NPZ files (GIM-3B.3).

Daily files contain 25 hourly epochs. Only indexes 0..23 belong to that
day; index 24 is always discarded. The next day 00 UTC comes exclusively
from the next daily file. No interpolation or rescaling is performed.
"""
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

import numpy as np

from .modern_gim_loader import load_modern_gim_day


@dataclass(frozen=True)
class ModernGIMSeries:
    tec: np.ndarray       # (N, 71, 73), TECU, latitude ascending
    epochs: np.ndarray    # (N,), datetime64[s], hourly and unique
    lat: np.ndarray
    lon: np.ndarray
    source_files: tuple[str, ...]  # one source per daily input, in UTC order


def load_modern_gim_series(file_paths: Sequence[str | Path]) -> ModernGIMSeries:
    """Concatenate only hours 00..23 of each consecutive UTC daily file.

    Input order is irrelevant; files are sorted by their first UTC epoch.
    Adjacent files must cover consecutive days with identical coordinates.
    Index 24 is never included or compared against the next day's index 0.
    """
    if isinstance(file_paths, (str, bytes, Path)):
        raise TypeError("file_paths must be a sequence of file paths, not one path.")
    paths = list(file_paths)
    if not paths:
        raise ValueError("At least one daily GIM file is required.")
    if any(not isinstance(p, (str, Path)) for p in paths):
        raise TypeError("Every file path must be a string or Path.")
    days = [load_modern_gim_day(p) for p in paths]
    days.sort(key=lambda day: day.epochs[0])

    for previous, current in zip(days, days[1:]):
        if not np.array_equal(previous.lat, current.lat) or not np.array_equal(previous.lon, current.lon):
            raise ValueError("GIM grids differ between daily files.")
        if current.epochs[0] != previous.epochs[0] + np.timedelta64(1, "D"):
            raise ValueError("Daily GIM files must cover consecutive, unique UTC days.")
    # Strict ownership: each day's index 0..23 comes from its own file.
    tec = np.concatenate([day.tec[:24] for day in days], axis=0)
    epochs = np.concatenate([day.epochs[:24] for day in days])
    expected = epochs[0] + np.arange(len(epochs)).astype("timedelta64[h]")
    if not np.array_equal(epochs, expected):
        raise ValueError("Merged GIM epochs are not continuous hourly UTC.")
    return ModernGIMSeries(
        tec=tec,
        epochs=epochs,
        lat=days[0].lat.copy(),
        lon=days[0].lon.copy(),
        source_files=tuple(day.source_file for day in days),
    )
