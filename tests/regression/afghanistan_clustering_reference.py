"""Validated Afghanistan clustering regression reference."""

import numpy as np


EXPECTED_SIGNIFICANT_POINTS = 34

EXPECTED_POSITIVE_POINTS = 18

EXPECTED_NEGATIVE_POINTS = 16

EXPECTED_CLUSTER_SIZES = np.asarray(
    [18, 16],
    dtype=np.int64,
)

EXPECTED_SILHOUETTE = 0.31105623341145205

EXPECTED_CONTINUOUS_CENTROIDS = np.asarray(
    [
        [8.0, -7.777777777777778, 0.6666666666666666],
        [6.0, -22.0625, -0.625],
    ],
    dtype=np.float64,
)

EXPECTED_ROUNDED_CENTROIDS = np.asarray(
    [
        [8.0, -8.0, 1.0],
        [6.0, -22.0, -1.0],
    ],
    dtype=np.float64,
)

EXPECTED_CLUSTER_COMPOSITION = (
    {
        "cluster_id": 0,
        "positive": 15,
        "negative": 3,
        "total": 18,
    },
    {
        "cluster_id": 1,
        "positive": 3,
        "negative": 13,
        "total": 16,
    },
)