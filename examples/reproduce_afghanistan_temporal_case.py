"""Reproduce the Framework A TEC panel of Afghanistan Fig. 1(b).

Run from the ionospheric-tec-anomaly-framework repository root:
    python examples/reproduce_afghanistan_temporal_case.py

The script reuses production src modules, and never changes their science.
"""
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.workflow.modern_temporal_input_adapter import load_temporal_tec_from_modern_gim
from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies
from src.temporal_anomaly.plotting import plot_temporal_anomaly


# External data produced by gim-data-tools; never copy GIM data into this repo.
DATA_DIR = Path(r"C:\Users\Wen\Documents\GitHub\gim-data-tools\processed")
OUTPUT_DIR = Path("outputs/afghanistan_2022")

ANALYSIS_START = datetime(2022, 5, 22, 0)
ANALYSIS_END = datetime(2022, 6, 21, 23)  # Inclusive, UTC
REFERENCE_DAYS = 15
THRESHOLD_K = 3.0
EPICENTER_LATITUDE = 33.02
EPICENTER_LONGITUDE = 69.46


def main() -> None:
    reference_start = ANALYSIS_START - timedelta(days=REFERENCE_DAYS)
    end_day = ANALYSIS_END.date()
    day = reference_start.date()
    files: list[Path] = []

    while day <= end_day:
        doy = day.timetuple().tm_yday
        filename = f"codg{doy:03d}0.{day.year % 100:02d}i.npz"
        files.append(DATA_DIR / filename)
        day += timedelta(days=1)

    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required daily NPZ files:\n" + "\n".join(missing))

    print(f"Daily NPZ files: {len(files)}")
    print(f"First: {files[0].name} | Last: {files[-1].name}")

    series = load_temporal_tec_from_modern_gim(
        file_paths=files,
        start_time=ANALYSIS_START,
        end_time=ANALYSIS_END,
        latitude=EPICENTER_LATITUDE,
        longitude=EPICENTER_LONGITUDE,
        reference_days=REFERENCE_DAYS,
    )

    result = detect_temporal_anomalies(
        tec=series.tec,
        epochs=series.epochs,
        reference_days=REFERENCE_DAYS,
        threshold_multiplier=THRESHOLD_K,
    )

    expected_hours = int((ANALYSIS_END - ANALYSIS_START) / timedelta(hours=1)) + 1
    if len(result.epochs) != expected_hours:
        raise AssertionError(f"Expected {expected_hours} hours; got {len(result.epochs)}")
    if result.epochs[0] != ANALYSIS_START or result.epochs[-1] != ANALYSIS_END:
        raise AssertionError("Analysis timestamps do not match intended period")

    counts = {
        "positive": int(np.count_nonzero(result.anomaly == 1)),
        "normal": int(np.count_nonzero(result.anomaly == 0)),
        "negative": int(np.count_nonzero(result.anomaly == -1)),
    }

    print(f"Requested epicenter: {series.requested_latitude:.2f} N, {series.requested_longitude:.2f} E")
    print(f"Selected GIM grid: {series.grid_latitude:.2f} N, {series.grid_longitude:.2f} E")
    print(f"Analysis: {result.epochs[0]} to {result.epochs[-1]} (UTC)")
    print(f"Analyzed hours: {len(result.epochs)}")
    print(f"Anomalies: {counts}")
    print("Legacy Afghanistan reference counts: positive=37, normal=610, negative=97")
    print("Numeric match with legacy counts:", counts == {"positive": 37, "normal": 610, "negative": 97})
    print("Note: matching counts alone does not establish plot-level equivalence.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plot_temporal_anomaly(
        result,
        title="Afghanistan 2022 — Framework A (CODE GIM)",
        ylabel="TEC (TECU)",
        xlabel="2022 (UTC)",
    )
    ax.set_xlim(ANALYSIS_START, ANALYSIS_END)
    destination = OUTPUT_DIR / "afghanistan_2022_fig1b_temporal.png"
    fig.savefig(destination, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {destination.resolve()}")


if __name__ == "__main__":
    main()
