"""Run validated Framework D on Modern CODE GIM and export corrected PNGs + peak JSON.

Place in examples/ and run:
  python -m examples.reproduce_afghanistan_spatial_visuals

Cartopy is required for coastlines and political borders; Natural Earth 110m
geometry may be downloaded on first use.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import numpy as np

from src.workflow.temporal_window import TemporalWindow
from src.workflow.modern_spatial_input_adapter import run_spatial_verification_from_modern_gim
from src.spatial_verification.spatial_plot import save_spatial_anomaly_plot
from src.workflow.spatial_summary_export import _maximum_anomaly

DATA_DIR = Path(r"C:\Users\Wen\Documents\GitHub\gim-data-tools\processed")
OUT_DIR = Path("outputs/afghanistan_2022/spatial_corrected")
START = datetime(2022, 5, 28, tzinfo=timezone.utc)
END = datetime(2022, 6, 1, 23, tzinfo=timezone.utc)
LAT, LON, MAG = 33.020, 69.464, 6.0
REFERENCE_DAYS, K = 15, 3.0


def main():
    files = []
    current = (START - timedelta(days=REFERENCE_DAYS)).date()
    while current <= END.date():
        name = f"codg{current.timetuple().tm_yday:03d}0.{current.year % 100:02d}i.npz"
        path = DATA_DIR / name
        if not path.is_file():
            raise FileNotFoundError(path)
        files.append(path)
        current += timedelta(days=1)

    window = TemporalWindow(START, END, "explicit")
    result = run_spatial_verification_from_modern_gim(
        window, files, reference_days=REFERENCE_DAYS, k=K
    )
    assert result.window_steps == 120
    assert result.positive_ratio.shape == (71, 73)
    assert result.negative_ratio.shape == (71, 73)
    assert np.isclose(result.positive_ratio.max(), 10.0)
    assert np.isclose(result.negative_ratio.max(), 85.0)

    summary = {
        "case": "afghanistan_2022",
        "source": "Modern CODE GIM (daily NPZ)",
        "window_utc": [START.isoformat(), END.isoformat()],
        "reference_days": REFERENCE_DAYS,
        "threshold_multiplier": K,
        "grid_orientation": "canonical",
        "earthquake": {"latitude": LAT, "longitude": LON, "magnitude": MAG},
        "spatial_anomalies": {
            "positive": _maximum_anomaly(result.positive_ratio, result.latitudes, result.longitudes, grid_orientation="canonical"),
            "negative": _maximum_anomaly(result.negative_ratio, result.latitudes, result.longitudes, grid_orientation="canonical"),
        },
    }
    neg = summary["spatial_anomalies"]["negative"]
    assert np.isclose(neg["maximum_ratio_percent"], 85.0)
    assert neg["maximum_grid_points"] == [{"latitude": 30.0, "longitude": 70.0}]

    paths = [OUT_DIR / f"afghanistan_2022_{kind}_spatial.png" for kind in ("positive", "negative")]
    summary_path = OUT_DIR / "afghanistan_2022_spatial_peak_summary.json"
    if any(p.exists() for p in [*paths, summary_path]):
        raise FileExistsError("Corrected spatial outputs already exist; remove or archive them first.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for kind, path in zip(("positive", "negative"), paths):
        save_spatial_anomaly_plot(
            result, polarity=kind, output_path=path,
            start_time=START, end_time=END,
            epicenter_latitude=LAT, epicenter_longitude=LON, magnitude=MAG,
            grid_orientation="canonical", show_boundaries=True,
        )
        print("Saved", path.resolve())
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Saved", summary_path.resolve())
    print("PASS: Modern spatial peaks use the correct geographic coordinates")


if __name__ == "__main__":
    main()
