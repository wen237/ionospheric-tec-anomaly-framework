"""Validated single-file modern GIM NPZ input (GIM-3B.1/3B.2).

The output is in TECU, with ascending physical latitude.  A daily IONEX
file's 25th (next-day 00 UTC) epoch is retained; multi-day de-duplication
belongs to the next integration stage.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ModernGIMData:
    tec: np.ndarray           # (time, latitude, longitude), TECU
    epochs: np.ndarray        # datetime64[s], strictly increasing UTC
    lat: np.ndarray           # ascending -87.5 ... 87.5
    lon: np.ndarray           # ascending -180 ... 180
    source_file: str


def load_modern_gim_day(file_path: str | Path) -> ModernGIMData:
    """Load and validate one CODE-style hourly GIM day from modern NPZ.

    No interpolation, unit rescaling, temporal trimming, or data mutation.
    This V1 contract targets the 71 x 73 global grid and 25 hourly epochs.
    """
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Modern GIM NPZ not found: {path}")

    with np.load(path, allow_pickle=False) as archive:
        required = {"tec", "epochs", "lat", "lon"}
        missing = required.difference(archive.files)
        if missing:
            raise ValueError(f"Missing modern GIM fields: {sorted(missing)}")
        tec = np.array(archive["tec"], dtype=np.float64, copy=True)
        epochs = np.array(archive["epochs"], copy=True)
        lat = np.array(archive["lat"], dtype=np.float64, copy=True)
        lon = np.array(archive["lon"], dtype=np.float64, copy=True)
        source_file = str(archive["source_file"].item()) if "source_file" in archive.files else path.name

    if tec.ndim != 3 or tec.shape != (25, 71, 73):
        raise ValueError(f"Expected TEC shape (25, 71, 73); received {tec.shape}.")
    if epochs.shape != (25,) or epochs.dtype.kind != "M":
        raise ValueError("epochs must be a (25,) datetime64 array.")
    if np.isnat(epochs).any():
        raise ValueError("epochs must not contain NaT.")
    if not np.array_equal(epochs, epochs.astype("datetime64[s]").astype(epochs.dtype)):
        raise ValueError("epochs must align to whole seconds.")
    epochs = epochs.astype("datetime64[s]")
    expected_epochs = epochs[0] + np.arange(25).astype("timedelta64[h]")
    if not np.array_equal(epochs, expected_epochs):
        raise ValueError("epochs must be 25 consecutive hourly UTC instants.")
    # Single daily IONEX products must start at 00:00 UTC.
    if epochs[0].astype("datetime64[D]") != epochs[0]:
        raise ValueError("Daily GIM epochs must begin at 00:00 UTC.")

    expected_lat = np.linspace(-87.5, 87.5, 71)
    expected_lon = np.linspace(-180.0, 180.0, 73)
    if lat.shape != (71,) or not np.all(np.isfinite(lat)):
        raise ValueError("Invalid latitude coordinates.")
    if lon.shape != (73,) or not np.allclose(lon, expected_lon, rtol=0, atol=1e-8):
        raise ValueError("Longitude coordinates do not match the expected global grid.")
    if np.allclose(lat, expected_lat, rtol=0, atol=1e-8):
        pass
    elif np.allclose(lat, expected_lat[::-1], rtol=0, atol=1e-8):
        lat = lat[::-1].copy()
        tec = tec[:, ::-1, :].copy()
    else:
        raise ValueError("Latitude coordinates do not match the expected global grid.")

    # The modern reader must already have masked raw IONEX 0 and 9999.
    if np.any(tec == 0) or np.any(tec == 9999):
        raise ValueError("Invalid TEC sentinel detected; reconvert with the corrected IONEX reader.")
    if np.any(np.isinf(tec)):
        raise ValueError("TEC contains infinite values.")
    if np.any(tec < 0):
        raise ValueError("TEC contains negative values.")

    return ModernGIMData(tec=tec, epochs=epochs, lat=lat, lon=lon, source_file=source_file)
