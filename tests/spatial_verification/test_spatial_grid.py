import numpy as np
import pytest

from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
    orient_gim_grid,
)


def test_gim_coordinate_definition():
    assert GIM_LATITUDES.shape == (71,)
    assert GIM_LONGITUDES.shape == (73,)

    assert GIM_LATITUDES[0] == -87.5
    assert GIM_LATITUDES[-1] == 87.5

    assert GIM_LONGITUDES[0] == -180.0
    assert GIM_LONGITUDES[-1] == 180.0


def test_orient_gim_grid_reverses_latitude_axis():
    matrix = np.arange(71 * 73).reshape(71, 73)

    oriented = orient_gim_grid(matrix)

    np.testing.assert_array_equal(
        oriented[0],
        matrix[-1],
    )

    np.testing.assert_array_equal(
        oriented[-1],
        matrix[0],
    )