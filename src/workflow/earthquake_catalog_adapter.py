"""Load a filtered USGS CSV for the existing Framework B+C selector."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from src.statistical_clustering.earthquake_samples import (
    select_earthquake_samples,
)


@dataclass(frozen=True)
class EarthquakeCatalog:
    event_dates: np.ndarray
    magnitudes: np.ndarray
    event_ids: tuple[str, ...]


def load_usgs_earthquake_csv(path: str | Path) -> EarthquakeCatalog:
    """Preserve each USGS event's UTC date and magnitude without re-filtering."""
    path = Path(path)
    dates, magnitudes, ids = [], [], []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"event_id", "time_utc", "magnitude"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV missing columns: {sorted(required)}")

        for line, row in enumerate(reader, 2):
            try:
                event_id = row["event_id"].strip()
                if not event_id:
                    raise ValueError("empty event_id")
                stamp = row["time_utc"].strip().replace("Z", "+00:00")
                when = datetime.fromisoformat(stamp)
                if when.tzinfo is None:
                    raise ValueError("UTC timestamp lacks timezone")
                mag = float(row["magnitude"])
                if not np.isfinite(mag):
                    raise ValueError("non-finite magnitude")
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid CSV row {line}: {exc}") from exc

            ids.append(event_id)
            dates.append(when.astimezone(timezone.utc).date())
            magnitudes.append(mag)

    if not dates:
        raise ValueError("Earthquake catalog contains no events")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate USGS event IDs")

    return EarthquakeCatalog(
        event_dates=np.asarray(dates, dtype=object),
        magnitudes=np.asarray(magnitudes, dtype=np.float64),
        event_ids=tuple(ids),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Afghanistan USGS catalog for Framework B+C")
    parser.add_argument("--catalog", type=Path, required=True)
    args = parser.parse_args()

    catalog = load_usgs_earthquake_csv(args.catalog)
    selected = select_earthquake_samples(
        event_dates=catalog.event_dates,
        magnitudes=catalog.magnitudes,
        analysis_start=date(1999, 1, 1),
        analysis_end=date(2021, 12, 31),
        minimum_magnitude=6.0,
        observation_days=30,
        reference_days=15,
    )
    print(f"Filtered USGS CSV events : {len(catalog.event_dates)}")
    print(f"Framework B+C M>=6      : {len(selected.selected_dates)}")
    print(f"First selected event     : {min(selected.selected_dates)}")
    print(f"Last selected event      : {max(selected.selected_dates)}")
    if len(catalog.event_dates) != 741 or len(selected.selected_dates) != 74:
        raise SystemExit("FAIL: event counts differ from the Afghanistan baseline")
    print("PASS: Modern USGS catalog is ready for Framework B+C")


if __name__ == "__main__":
    main()
