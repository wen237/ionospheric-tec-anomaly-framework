import numpy as np

from src.statistical_clustering.clustering import (
    encode_hour_sin_cos,
    prepare_clustering_features,
)


def test_extracts_only_significant_cells():

    mask = np.asarray(
        [
            [0, 1, 0],
            [-1, 0, 1],
        ],
        dtype=np.int8,
    )

    relative_days = np.asarray(
        [-1, 0],
        dtype=int,
    )

    result = prepare_clustering_features(
        mask=mask,
        relative_days=relative_days,
        use_circular_hour=False,
    )

    assert result.raw_features.shape == (
        3,
        3,
    )

    assert np.all(
        result.polarities != 0
    )


def test_positive_cells_precede_negative_cells():

    mask = np.asarray(
        [
            [-1, 0, 1],
            [0, 1, -1],
        ],
        dtype=np.int8,
    )

    relative_days = np.asarray(
        [-1, 0],
        dtype=int,
    )

    result = prepare_clustering_features(
        mask=mask,
        relative_days=relative_days,
        use_circular_hour=False,
    )

    expected = np.asarray(
        [
            [1,  0,  1],
            [2, -1,  1],
            [2,  0, -1],
            [0, -1, -1],
        ],
        dtype=np.float64,
    )

    print("\n=== Test 2 diagnostics ===")

    print("\nActual:")
    print(result.raw_features)

    print("\nExpected:")
    print(expected)

    print("\nActual shape:")
    print(result.raw_features.shape)

    print("\nExpected shape:")
    print(expected.shape)

    print("\nActual days:")
    print(result.relative_days)

    print("\nActual polarities:")
    print(result.polarities)

    print("\nElement-wise equality:")
    print(result.raw_features == expected)

    assert np.array_equal(
        result.raw_features,
        expected,
    )


def test_circular_hour_encoding():

    hours = np.asarray(
        [0, 6, 12, 18],
        dtype=float,
    )

    sin_hour, cos_hour = (
        encode_hour_sin_cos(hours)
    )

    expected_sin = np.asarray(
        [0, 1, 0, -1],
        dtype=float,
    )

    expected_cos = np.asarray(
        [1, 0, -1, 0],
        dtype=float,
    )

    assert np.allclose(
        sin_hour,
        expected_sin,
        atol=1e-12,
    )

    assert np.allclose(
        cos_hour,
        expected_cos,
        atol=1e-12,
    )


def test_circular_features_have_correct_order():

    mask = np.asarray(
        [
            [1, 0],
        ],
        dtype=np.int8,
    )

    relative_days = np.asarray(
        [-5],
        dtype=int,
    )

    result = prepare_clustering_features(
        mask=mask,
        relative_days=relative_days,
        use_circular_hour=True,
    )

    assert result.features.shape == (
        1,
        4,
    )

    assert np.isclose(
        result.features[0, 0],
        0.0,
    )

    assert np.isclose(
        result.features[0, 1],
        1.0,
    )

    assert result.features[0, 2] == -5
    assert result.features[0, 3] == 1

