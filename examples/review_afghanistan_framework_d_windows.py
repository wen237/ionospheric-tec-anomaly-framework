"""Review Framework A anomaly dates before explicitly selecting Framework D windows.

Run at the ionospheric-tec-anomaly-framework repository root:
    python -m examples.review_afghanistan_framework_d_windows

This diagnostic proposes no causal interpretation or automatic spatial window.
It does not change GIM data, validated algorithms, or Stage 2 outputs.
"""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies
from src.workflow.modern_temporal_input_adapter import (
    load_temporal_tec_from_modern_gim,
)

DATA_DIR = Path(r"C:\Users\Wen\Documents\GitHub\gim-data-tools\processed")
START = datetime(2022, 5, 22, 0)
END = datetime(2022, 6, 21, 23)
REFERENCE_DAYS = 15
K = 3.0
EPICENTER_LATITUDE = 33.02
EPICENTER_LONGITUDE = 69.46


def collect_daily_files(start: datetime, end: datetime) -> list[Path]:
    current = start.date()
    paths: list[Path] = []
    while current <= end.date():
        filename = f"codg{current.timetuple().tm_yday:03d}0.{current.year % 100:02d}i.npz"
        paths.append(DATA_DIR / filename)
        current += timedelta(days=1)
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError("Required GIM files are absent:\n" + "\n".join(map(str, missing)))
    return paths


def main() -> None:
    first_reference = START - timedelta(days=REFERENCE_DAYS)
    paths = collect_daily_files(first_reference, END)
    series = load_temporal_tec_from_modern_gim(
        file_paths=paths,
        start_time=START,
        end_time=END,
        latitude=EPICENTER_LATITUDE,
        longitude=EPICENTER_LONGITUDE,
        reference_days=REFERENCE_DAYS,
    )
    result = detect_temporal_anomalies(
        tec=series.tec,
        epochs=series.epochs,
        reference_days=REFERENCE_DAYS,
        threshold_multiplier=K,
    )
    assert len(result.epochs) == 744, "Unexpected Afghanistan analysis duration"
    counts = Counter(int(v) for v in result.anomaly)
    expected = {-1: 97, 0: 610, 1: 37}
    if any(counts[x] != expected[x] for x in expected):
        raise AssertionError(f"Framework A counts differ from validated case: {dict(counts)}")

    daily = {}
    for epoch, polarity in zip(result.epochs, result.anomaly):
        day = np.datetime64(epoch, "D") if isinstance(epoch, np.datetime64) else epoch.date()
        positive, negative = daily.get(day, (0, 0))
        daily[day] = (positive + (int(polarity) == 1), negative + (int(polarity) == -1))

    print("Framework A daily anomaly evidence (not automated window selection)")
    print("Date UTC     Positive hours   Negative hours")
    for day in sorted(daily):
        pos, neg = daily[day]
        if pos or neg:
            print(f"{str(day):12s} {pos:>8d}         {neg:>8d}")
    print("\nResearcher-confirmed Framework D reference window:")
    print("2022-05-28 00:00 to 2022-06-01 23:00 UTC")
    print("This window is a verified reference, NOT inferred automatically from these counts.")
    print("Next: define a documented candidate-window selection rule before automation.")


if __name__ == "__main__":
    main()
