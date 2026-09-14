"""Utilities for extracting TEC time series from gridded GIM data.

This module provides a small interface between gridded TEC data produced by
an IONEX/GIM reader and downstream temporal analysis modules.

It performs nearest-grid selection only. Temporal anomaly detection and
visualization are intentionally handled elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class TECTimeSeries:
    """TEC time series extracted from the nearest geographic grid point.

    The object stores the extracted TEC values together with the requested
    location, selected grid coordinates, and corresponding grid indices.
    """

    epochs: np.ndarray
    tec: np.ndarray

    requested_latitude: float
    requested_longitude: float

    grid_latitude: float
    grid_longitude: float

    latitude_index: int
    longitude_index: int


def _validate_inputs(
    tec: np.ndarray,
    epochs: Sequence[datetime],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    latitude: float,
    longitude: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Validate and normalize gridded TEC inputs."""

    tec = np.asarray(tec, dtype=np.float64)
    epochs = np.asarray(epochs, dtype=object)
    latitudes = np.asarray(latitudes, dtype=np.float64)
    longitudes = np.asarray(longitudes, dtype=np.float64)

    if tec.ndim != 3:
        raise ValueError(
            "tec must be a three-dimensional array with shape "
            "(time, latitude, longitude)."
        )

    if epochs.ndim != 1:
        raise ValueError("epochs must be one-dimensional.")

    if latitudes.ndim != 1:
        raise ValueError("latitudes must be one-dimensional.")

    if longitudes.ndim != 1:
        raise ValueError("longitudes must be one-dimensional.")

    expected_shape = (
        len(epochs),
        len(latitudes),
        len(longitudes),
    )

    if tec.shape != expected_shape:
        raise ValueError(
            "TEC shape does not match coordinate dimensions. "
            f"Expected {expected_shape}, got {tec.shape}."
        )

    if len(epochs) == 0:
        raise ValueError("epochs must not be empty.")

    if len(latitudes) == 0:
        raise ValueError("latitudes must not be empty.")

    if len(longitudes) == 0:
        raise ValueError("longitudes must not be empty.")

    if not all(isinstance(epoch, datetime) for epoch in epochs):
        raise TypeError("All epochs must be datetime objects.")

    if len(set(epochs)) != len(epochs):
        raise ValueError("epochs must not contain duplicate timestamps.")

    if any(
        epochs[i] >= epochs[i + 1]
        for i in range(len(epochs) - 1)
    ):
        raise ValueError("epochs must be strictly increasing.")

    if not np.all(np.isfinite(latitudes)):
        raise ValueError("latitudes must contain only finite values.")

    if not np.all(np.isfinite(longitudes)):
        raise ValueError("longitudes must contain only finite values.")

    if not np.isfinite(latitude):
        raise ValueError("latitude must be finite.")

    if not np.isfinite(longitude):
        raise ValueError("longitude must be finite.")

    if not -90.0 <= latitude <= 90.0:
        raise ValueError(
            "latitude must be between -90 and 90 degrees."
        )

    if len(np.unique(latitudes)) != len(latitudes):
        raise ValueError(
            "latitudes must not contain duplicate coordinates."
        )

    _validate_longitude_coordinates(
        longitudes
    )

    return tec, epochs, latitudes, longitudes


def _normalize_longitude_180(longitude: float) -> float:
    """Normalize one longitude to the interval [-180, 180)."""

    return float((longitude + 180.0) % 360.0 - 180.0)


def _normalize_longitudes_180(
    longitudes: np.ndarray,
) -> np.ndarray:
    """Normalize longitude coordinates to [-180, 180)."""

    return (longitudes + 180.0) % 360.0 - 180.0


def _validate_longitude_coordinates(
    longitudes: np.ndarray,
) -> None:
    """Validate geographic uniqueness of longitude coordinates.

    Longitude grids may legitimately include both endpoints of a global
    grid, such as -180 and 180 degrees or 0 and 360 degrees. These pairs
    represent the same geographic meridian and are treated as valid grid
    seams.

    Other duplicate geographic coordinates are rejected.
    """

    normalized = _normalize_longitudes_180(
        longitudes
    )

    for value in np.unique(normalized):
        indices = np.where(
            np.isclose(
                normalized,
                value,
                rtol=0.0,
                atol=1e-10,
            )
        )[0]

        if len(indices) <= 1:
            continue

        original_values = np.sort(
            longitudes[indices]
        )

        differences = np.diff(
            original_values
        )

        if not np.allclose(
            differences,
            360.0,
            rtol=0.0,
            atol=1e-10,
        ):
            raise ValueError(
                "longitudes contain duplicate geographic "
                "coordinates that are not explained by a "
                "360-degree grid seam."
            )


def _longitude_distance(
    grid_longitudes: np.ndarray,
    longitude: float,
) -> np.ndarray:
    """Return minimum angular longitude distance in degrees."""

    normalized_grid = _normalize_longitudes_180(
        grid_longitudes
    )

    normalized_target = _normalize_longitude_180(
        longitude
    )

    difference = np.abs(
        normalized_grid - normalized_target
    )

    return np.minimum(
        difference,
        360.0 - difference,
    )


def extract_tec_timeseries(
    tec: np.ndarray,
    epochs: Sequence[datetime],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    *,
    latitude: float,
    longitude: float,
) -> TECTimeSeries:
    """Extract TEC values from the nearest geographic grid point.

    The nearest latitude is selected using absolute latitude difference.
    Longitude selection uses circular angular distance so that longitude
    conventions such as [-180, 180] and [0, 360] are handled consistently.

    Parameters
    ----------
    tec
        Three-dimensional TEC array with shape
        ``(time, latitude, longitude)``.
    epochs
        UTC datetime associated with the time dimension.
    latitudes
        Latitude coordinates corresponding to the TEC latitude dimension.
    longitudes
        Longitude coordinates corresponding to the TEC longitude dimension.
    latitude
        Requested geographic latitude in degrees.
    longitude
        Requested geographic longitude in degrees. Values outside the
        conventional [-180, 180] interval are accepted and normalized
        geographically.

    Returns
    -------
    TECTimeSeries
        Extracted TEC time series and metadata describing both the requested
        location and the actual grid point used.
    """

    (
        tec,
        epochs,
        latitudes,
        longitudes,
    ) = _validate_inputs(
        tec=tec,
        epochs=epochs,
        latitudes=latitudes,
        longitudes=longitudes,
        latitude=latitude,
        longitude=longitude,
    )

    latitude_index = int(
        np.argmin(
            np.abs(latitudes - latitude)
        )
    )

    longitude_distances = _longitude_distance(
        longitudes,
        longitude,
    )

    longitude_index = int(
        np.argmin(longitude_distances)
    )

    extracted_tec = np.array(
        tec[
            :,
            latitude_index,
            longitude_index,
        ],
        dtype=np.float64,
        copy=True,
    )

    return TECTimeSeries(
        epochs=np.array(
            epochs,
            dtype=object,
            copy=True,
        ),
        tec=extracted_tec,
        requested_latitude=float(latitude),
        requested_longitude=float(longitude),
        grid_latitude=float(
            latitudes[latitude_index]
        ),
        grid_longitude=float(
            longitudes[longitude_index]
        ),
        latitude_index=latitude_index,
        longitude_index=longitude_index,
    )
