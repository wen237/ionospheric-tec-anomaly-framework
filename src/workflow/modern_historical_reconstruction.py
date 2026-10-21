"""Reconstruct case-specific hourly TEC from a shared modern CODE GIM NPZ archive.

Works with different source cadences (e.g., 1999 2-hour and 2022 1-hour).
Never changes the original global GIM archive or any scientific B+C algorithm.

Run from the ionospheric-tec-anomaly-framework repository root:
  python -m src.workflow.modern_historical_reconstruction --help
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class HistoricalReconstructionResult:
    epochs: np.ndarray                   # (n_hours,), datetime64[s]
    tec: np.ndarray                      # (n_hours,), TECU
    observed_mask: np.ndarray            # original finite observations
    interpolated_mask: np.ndarray        # gaps between observations
    boundary_filled_mask: np.ndarray     # filled before first / after last observation
    grid_latitude: float
    grid_longitude: float
    source_file_count: int


def _iter_days(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _day_path(directory: Path, day: date) -> Path:
    doy = day.timetuple().tm_yday
    return directory / f"codg{doy:03d}0.{day.year % 100:02d}i.npz"


def _longitude_distance(grid_lon: np.ndarray, target: float) -> np.ndarray:
    delta = np.abs(((grid_lon - target + 180.0) % 360.0) - 180.0)
    return delta


def reconstruct_historical_tec(
    dataset_dir: str | Path,
    *,
    start_date: date,
    end_date: date,
    latitude: float,
    longitude: float,
) -> HistoricalReconstructionResult:
    """Extract a case grid point daily, then apply pandas time interpolation.

    Select only the source epochs *belonging to each file's UTC calendar day*:
    any 25th, next-day map is discarded, not used as a duplicate.

    Missing source day / wholly invalid source day raises an error instead of
    interpolating silently across that day. Internal missing hours are filled
    with pandas ``method='time'`` and ``limit_direction='both'``; leading and
    trailing hours get the nearest valid TEC value, matching legacy behavior.
    """
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise TypeError("start_date and end_date must be datetime.date objects")
    if start_date > end_date:
        raise ValueError("start_date cannot exceed end_date")
    if not np.isfinite(latitude) or not np.isfinite(longitude):
        raise ValueError("Requested coordinates must be finite")
    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be in [-90, 90]")

    root = Path(dataset_dir).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Modern GIM directory not found: {root}")

    index = pd.date_range(start_date, end_date + timedelta(days=1), freq="h", inclusive="left")
    series = pd.Series(np.nan, index=index, dtype="float64")
    reference_grid = None
    first_grid = None
    file_count = 0

    for day in _iter_days(start_date, end_date):
        path = _day_path(root, day)
        if not path.is_file():
            raise FileNotFoundError(f"Missing daily Modern GIM NPZ: {path}")

        with np.load(path, allow_pickle=False) as data:
            required = {"tec", "epochs", "lat", "lon"}
            if not required.issubset(data.files):
                raise ValueError(f"Missing NPZ fields in {path.name}: {sorted(required - set(data.files))}")
            lat = np.asarray(data["lat"], dtype=np.float64)
            lon = np.asarray(data["lon"], dtype=np.float64)
            epochs = np.asarray(data["epochs"])
            tec = data["tec"]

            if lat.ndim != 1 or lon.ndim != 1 or tec.ndim != 3:
                raise ValueError(f"Invalid GIM dimensions in {path.name}")
            if epochs.ndim != 1 or epochs.dtype.kind != "M":
                raise ValueError(f"Invalid epochs in {path.name}")
            if tec.shape != (len(epochs), len(lat), len(lon)):
                raise ValueError(f"GIM coordinate dimensions differ from TEC in {path.name}")
            if not np.all(np.isfinite(lat)) or not np.all(np.isfinite(lon)):
                raise ValueError(f"Non-finite GIM coordinates in {path.name}")
            if np.isnat(epochs).any():
                raise ValueError(f"NaT epoch in {path.name}")

            if reference_grid is None:
                reference_grid = (lat.copy(), lon.copy())
                lat_idx = int(np.argmin(np.abs(lat - latitude)))
                lon_idx = int(np.argmin(_longitude_distance(lon, longitude)))
                first_grid = (float(lat[lat_idx]), float(lon[lon_idx]))
            else:
                if not (np.array_equal(lat, reference_grid[0]) and np.array_equal(lon, reference_grid[1])):
                    raise ValueError(f"GIM coordinate grids differ in {path.name}")

            # datetime64[s] for unambiguous UTC ownership and indexing.
            epoch_values = epochs.astype("datetime64[s]")
            if np.unique(epoch_values).size != len(epoch_values):
                raise ValueError(f"Duplicate timestamps within {path.name}")
            if not np.all(np.diff(epoch_values) > np.timedelta64(0, "s")):
                raise ValueError(f"Unsorted GIM epochs in {path.name}")
            owner = epoch_values.astype("datetime64[D]") == np.datetime64(day.isoformat())
            if not owner.any():
                raise ValueError(f"No owned UTC observations in {path.name}")

            selected_tec = np.asarray(tec[owner, lat_idx, lon_idx], dtype="float64")
            selected_epochs = pd.to_datetime(epoch_values[owner])
            if not np.all(selected_epochs.isin(index)):
                raise ValueError(f"GIM epochs are outside requested hourly grid in {path.name}")
            if not np.all(selected_epochs.minute == 0) or not np.all(selected_epochs.second == 0):
                raise ValueError(f"Non-hourly source timestamps in {path.name}")
            if not np.isfinite(selected_tec).any():
                raise ValueError(f"All TEC samples missing at selected grid on {day}")
            if np.any(np.isinf(selected_tec)):
                raise ValueError(f"Infinite TEC samples in {path.name}")

            series.loc[selected_epochs] = selected_tec
        file_count += 1

    original = series.notna().to_numpy()
    observed_idx = np.flatnonzero(original)
    if observed_idx.size < 2:
        raise ValueError("At least two valid TEC observations are required")

    reconstructed = series.interpolate(method="time", limit_direction="both")
    if reconstructed.isna().any():
        raise ValueError("Historical TEC still contains NaN after interpolation")

    gap = ~original
    boundary = gap & ((np.arange(len(series)) < observed_idx[0]) | (np.arange(len(series)) > observed_idx[-1]))
    internal = gap & ~boundary

    return HistoricalReconstructionResult(
        epochs=index.to_numpy(dtype="datetime64[s]"),
        tec=reconstructed.to_numpy(dtype="float64"),
        observed_mask=original,
        interpolated_mask=internal,
        boundary_filled_mask=boundary,
        grid_latitude=first_grid[0],
        grid_longitude=first_grid[1],
        source_file_count=file_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct hourly TEC from a shared Modern CODE GIM archive")
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--latitude", type=float, default=33.092)
    parser.add_argument("--longitude", type=float, default=69.514)
    parser.add_argument("--output", type=Path, required=True, help="Case-specific output NPZ (not the source database)")
    args = parser.parse_args()

    result = reconstruct_historical_tec(
        args.dataset_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        latitude=args.latitude,
        longitude=args.longitude,
    )
    target = args.output.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        target,
        tec=result.tec,
        epochs=result.epochs,
        observed_mask=result.observed_mask,
        interpolated_mask=result.interpolated_mask,
        boundary_filled_mask=result.boundary_filled_mask,
        grid_latitude=result.grid_latitude,
        grid_longitude=result.grid_longitude,
        requested_latitude=args.latitude,
        requested_longitude=args.longitude,
        source_file_count=result.source_file_count,
        interpolation_method="time",
        boundary_policy="pandas_limit_direction_both",
    )

    print(f"Source files: {result.source_file_count}")
    print(f"Selected grid: {result.grid_latitude:.2f} N, {result.grid_longitude:.2f} E")
    print(f"Hourly TEC samples: {len(result.tec)}")
    print(f"Original observations: {int(result.observed_mask.sum())}")
    print(f"Internal interpolations: {int(result.interpolated_mask.sum())}")
    print(f"Boundary fills: {int(result.boundary_filled_mask.sum())}")
    print(f"Remaining NaN: {int(np.count_nonzero(~np.isfinite(result.tec)))}")
    print(f"Saved: {target.resolve()}")


if __name__ == "__main__":
    main()
