from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np


@dataclass(frozen=True)
class SpatialTECData:
    """Prepared GIM TEC observations for spatial anomaly calculation.

    TEC values retain the legacy flattened GIM grid ordering.
    Latitude orientation normalization is performed separately.
    """

    tec: np.ndarray
    timestamps: tuple[datetime, ...]
    samples_per_day: int
    reference_days: int
    window_steps: int


def load_spatial_tec(
    dataset_dir: str,
    start_time: datetime,
    end_time: datetime,
    reference_days: int,
) -> SpatialTECData:
    """Load GIM TEC observations for a spatial verification window.

    The returned matrix includes the preceding reference period and
    preserves the legacy flattened GIM ordering.

    Currently supports the 24-samples-per-day GIM format.
    """

    if reference_days <= 0:
        raise ValueError("reference_days must be positive.")

    if start_time > end_time:
        raise ValueError("start_time must not exceed end_time.")

    samples_per_day = 24

    # This implementation currently supports hourly GIM observations.
    if (
        start_time.minute != 0
        or start_time.second != 0
        or start_time.microsecond != 0
        or end_time.minute != 0
        or end_time.second != 0
        or end_time.microsecond != 0
    ):
        raise ValueError(
            "Start and end times must align with hourly GIM epochs."
        )

    reference_start = start_time - timedelta(days=reference_days)

    first_day = reference_start.date()
    last_day = end_time.date()

    tec_parts = []
    timestamp_parts = []

    current_day = first_day

    while current_day <= last_day:
        day_tec, day_timestamps = load_gim_day(
            dataset_dir=dataset_dir,
            day=datetime.combine(current_day, datetime.min.time()),
            samples_per_day=samples_per_day,
        )

        tec_parts.append(day_tec)
        timestamp_parts.extend(day_timestamps)

        current_day += timedelta(days=1)

    all_tec = np.concatenate(tec_parts, axis=0)
    all_timestamps = tuple(timestamp_parts)

    # Select exactly the reference period and target window.
    selected_indices = [
        index
        for index, timestamp in enumerate(all_timestamps)
        if reference_start <= timestamp <= end_time
    ]

    if not selected_indices:
        raise ValueError("No GIM observations found in the requested period.")

    selected_tec = all_tec[selected_indices]
    selected_timestamps = tuple(
        all_timestamps[index] for index in selected_indices
    )

    window_steps = sum(
        start_time <= timestamp <= end_time
        for timestamp in selected_timestamps
    )

    return SpatialTECData(
        tec=selected_tec,
        timestamps=selected_timestamps,
        samples_per_day=samples_per_day,
        reference_days=reference_days,
        window_steps=window_steps,
    )


def load_gim_day(
    dataset_dir: str | Path,
    day: datetime,
    samples_per_day: int = 24,
) -> tuple[np.ndarray, tuple[datetime, ...]]:
    """Load one daily GIM file using legacy spatial TEC conventions."""

    dataset_dir = Path(dataset_dir)

    year = day.year
    doy = day.timetuple().tm_yday

    file_path = (
        Path(f"{dataset_dir}{year}")
        / f"gim{year}{doy:03d}.npz"
    )

    if not file_path.is_file():
        raise FileNotFoundError(
            f"GIM file not found: {file_path}"
        )

    with np.load(file_path) as data:
        gim = data["gim"]
        gim_time = data["gim_time"]

    expected_rows = samples_per_day * 71

    if gim.shape[0] < expected_rows or gim.shape[1] != 73:
        raise ValueError(
            f"Unexpected GIM shape: {gim.shape}"
        )

    if (
        gim_time.ndim != 2
        or gim_time.shape[1] != 6
        or gim_time.shape[0] < samples_per_day
    ):
        raise ValueError(
            f"Invalid GIM timestamp shape: {gim_time.shape}"
        )

    tec = (
        gim[:expected_rows]
        .reshape(samples_per_day, 71 * 73)
        .astype(float)
        / 10.0
    )

    # Preserve the legacy missing-value convention.
    tec[(tec == 0) | (tec == 999.9)] = np.nan

    try:
        timestamps = tuple(
            datetime(*map(int, row))
            for row in gim_time[:samples_per_day]
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid GIM timestamp values in {file_path}"
        ) from exc

    expected_start = datetime(
        day.year,
        day.month,
        day.day,
    )

    expected_timestamps = tuple(
        expected_start + timedelta(hours=hour)
        for hour in range(samples_per_day)
    )

    if timestamps != expected_timestamps:
        raise ValueError(
            f"GIM timestamp sequence mismatch in {file_path}"
        )

    return tec, timestamps