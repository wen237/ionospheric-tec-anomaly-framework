import numpy as np

from src.statistical_clustering.temporal_anchors import (
    extract_temporal_anchors,
)


def test_extracts_cluster_composition():

    decoded_centers = np.asarray(
        [
            [8.0, -7.8, 0.5],
            [6.0, -22.1, -0.5],
        ]
    )

    raw_features = np.asarray(
        [
            [8, -8, 1],
            [9, -7, 1],
            [7, -9, 1],
            [8, -8, -1],
            [6, -22, -1],
            [5, -23, -1],
            [7, -21, -1],
            [6, -22, 1],
        ]
    )

    labels = np.asarray(
        [0, 0, 0, 0, 1, 1, 1, 1]
    )

    anchors = extract_temporal_anchors(
        decoded_centers,
        labels,
        raw_features,
    )

    assert len(anchors) == 2

    assert anchors[0].n_members == 4
    assert anchors[0].n_positive == 3
    assert anchors[0].n_negative == 1
    assert anchors[0].dominant_polarity == 1

    assert anchors[1].n_members == 4
    assert anchors[1].n_positive == 1
    assert anchors[1].n_negative == 3
    assert anchors[1].dominant_polarity == -1


def test_preserves_continuous_centroid_day():

    decoded_centers = np.asarray(
        [
            [8.0, -7.77777778, 0.66666667],
        ]
    )

    raw_features = np.asarray(
        [
            [8, -8, 1],
        ]
    )

    labels = np.asarray([0])

    anchors = extract_temporal_anchors(
        decoded_centers,
        labels,
        raw_features,
    )

    assert anchors[0].centroid_day == -7.77777778
    assert anchors[0].rounded_day == -8
    assert anchors[0].hour == 8


def test_tied_cluster_has_no_dominant_polarity():

    decoded_centers = np.asarray(
        [
            [6.0, -12.0, 0.0],
        ]
    )

    raw_features = np.asarray(
        [
            [6, -12, 1],
            [6, -12, -1],
        ]
    )

    labels = np.asarray([0, 0])

    anchors = extract_temporal_anchors(
        decoded_centers,
        labels,
        raw_features,
    )

    assert anchors[0].dominant_polarity == 0
    assert anchors[0].n_positive == 1
    assert anchors[0].n_negative == 1

