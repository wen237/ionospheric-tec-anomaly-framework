# src/spatial_verification/spatial_grid.py

import numpy as np


GIM_LATITUDES = np.linspace(-87.5, 87.5, 71)
GIM_LONGITUDES = np.linspace(-180.0, 180.0, 73)


def orient_gim_grid(matrix: np.ndarray) -> np.ndarray:
    """Orient a reshaped GIM grid to ascending physical latitude.

    Raw GIM data used by the legacy implementation are ordered opposite
    to the canonical latitude coordinates. The first axis is therefore
    reversed so that matrix[row, col] corresponds directly to
    GIM_LATITUDES[row] and GIM_LONGITUDES[col].
    """
    matrix = np.asarray(matrix)

    expected_shape = (
        GIM_LATITUDES.size,
        GIM_LONGITUDES.size,
    )

    if matrix.shape != expected_shape:
        raise ValueError(
            f"Expected GIM grid shape {expected_shape}, "
            f"but received {matrix.shape}."
        )

    return np.flipud(matrix)