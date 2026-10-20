from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SpatialAnomalyResult:
    positive_counts: np.ndarray
    negative_counts: np.ndarray
    positive_ratio: np.ndarray
    negative_ratio: np.ndarray
    latitudes: np.ndarray
    longitudes: np.ndarray
    window_steps: int


def compute_spatial_anomalies(
    tec: np.ndarray,
    samples_per_day: int,
    reference_days: int,
    window_steps: int,
    k: float,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> SpatialAnomalyResult:
    """Compute spatial TEC anomaly counts and occurrence proportions.

    The reference distribution for each target observation is constructed
    from the same time-of-day samples over the preceding reference days.
    """
    tec = np.asarray(tec, dtype=float)
    latitudes = np.asarray(latitudes, dtype=float)
    longitudes = np.asarray(longitudes, dtype=float)

    if tec.ndim != 2:
        raise ValueError("tec must be a 2-D array.")

    if samples_per_day <= 0:
        raise ValueError("samples_per_day must be positive.")

    if reference_days <= 0:
        raise ValueError("reference_days must be positive.")

    if window_steps <= 0:
        raise ValueError("window_steps must be positive.")

    if k < 0:
        raise ValueError("k must be non-negative.")

    n_grid_points = latitudes.size * longitudes.size

    if tec.shape[1] != n_grid_points:
        raise ValueError(
            "TEC grid size does not match latitude/longitude coordinates."
        )

    reference_steps = reference_days * samples_per_day
    expected_steps = reference_steps + window_steps

    if tec.shape[0] != expected_steps:
        raise ValueError(
            f"Expected {expected_steps} temporal samples, "
            f"but received {tec.shape[0]}."
        )

    reference = np.empty(
        (window_steps, n_grid_points, reference_days),
        dtype=float,
    )

    for day in range(reference_days):
        start = day * samples_per_day
        stop = start + window_steps

        reference[:, :, day] = tec[start:stop]

    observed = tec[reference_steps:]

    q1, q2, q3 = np.nanpercentile(
        reference,
        [25, 50, 75],
        axis=2,
    )

    upper_bound = q2 + k * (q3 - q2)
    lower_bound = q2 - k * (q2 - q1)

    positive = np.where(
        np.isnan(observed) | np.isnan(upper_bound),
        np.nan,
        (observed > upper_bound).astype(float),
    )

    negative = np.where(
        np.isnan(observed) | np.isnan(lower_bound),
        np.nan,
        (observed < lower_bound).astype(float),
    )

    positive_counts = np.nansum(
        positive,
        axis=0,
    ).reshape(latitudes.size, longitudes.size)

    negative_counts = np.nansum(
        negative,
        axis=0,
    ).reshape(latitudes.size, longitudes.size)

    positive_ratio = positive_counts / window_steps * 100.0
    negative_ratio = negative_counts / window_steps * 100.0

    return SpatialAnomalyResult(
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        positive_ratio=positive_ratio,
        negative_ratio=negative_ratio,
        latitudes=latitudes.copy(),
        longitudes=longitudes.copy(),
        window_steps=window_steps,
    )