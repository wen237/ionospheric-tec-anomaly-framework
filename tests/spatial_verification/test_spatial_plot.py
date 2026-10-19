"""Tests for paper-style spatial anomaly visualization."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from matplotlib.patches import Circle, Rectangle

from src.spatial_verification.spatial_anomaly import (
    SpatialAnomalyResult,
)
from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
)
from src.spatial_verification.spatial_plot import (
    create_spatial_anomaly_figure,
    save_spatial_anomaly_plot,
)


START = datetime(2022, 5, 28, 6, tzinfo=timezone.utc)
END = datetime(2022, 5, 29, 5, tzinfo=timezone.utc)

POSITIVE_INDEX = (20, 50)
NEGATIVE_INDEX = (40, 25)


@pytest.fixture
def spatial_result():
    positive = np.zeros((71, 73), dtype=float)
    negative = np.zeros((71, 73), dtype=float)

    positive[POSITIVE_INDEX] = 1.0
    negative[NEGATIVE_INDEX] = 1.0

    return SpatialAnomalyResult(
        positive_counts=positive.copy(),
        negative_counts=negative.copy(),
        positive_ratio=positive / 24 * 100,
        negative_ratio=negative / 24 * 100,
        latitudes=GIM_LATITUDES.copy(),
        longitudes=GIM_LONGITUDES.copy(),
        window_steps=24,
    )


def make_figure(result, **overrides):
    kwargs = {
        "polarity": "positive",
        "start_time": START,
        "end_time": END,
        "epicenter_latitude": 33.020,
        "epicenter_longitude": 69.464,
        "magnitude": 6.0,
    }
    kwargs.update(overrides)

    return create_spatial_anomaly_figure(
        result,
        **kwargs,
    )


def test_positive_grid_orientation(spatial_result):
    fig = make_figure(spatial_result)

    try:
        displayed = np.asarray(fig.axes[0].images[0].get_array())

        # Raw row 20 becomes oriented row 50.
        assert displayed[50, 50] == pytest.approx(100 / 24)
        assert np.count_nonzero(displayed) == 1

        peak_boxes = [
            patch
            for patch in fig.axes[0].patches
            if isinstance(patch, Rectangle)
        ]

        assert len(peak_boxes) == 1

        # Raw (20, 50) -> 37.5 N, 70 E.
        assert peak_boxes[0].get_xy() == pytest.approx(
            (67.5, 36.25)
        )
    finally:
        fig.clear()


def test_negative_grid_orientation(spatial_result):
    fig = make_figure(
        spatial_result,
        polarity="negative",
    )

    try:
        displayed = np.asarray(fig.axes[0].images[0].get_array())

        # Raw row 40 becomes oriented row 30.
        assert displayed[30, 25] == pytest.approx(100 / 24)
        assert np.count_nonzero(displayed) == 1

        peak_boxes = [
            patch
            for patch in fig.axes[0].patches
            if isinstance(patch, Rectangle)
        ]

        assert len(peak_boxes) == 1

        # Raw (40, 25) -> 12.5 S, 55 W.
        assert peak_boxes[0].get_xy() == pytest.approx(
            (-57.5, -13.75)
        )
    finally:
        fig.clear()


def test_epicenter_and_preparation_circle(spatial_result):
    fig = make_figure(spatial_result)

    try:
        ax = fig.axes[0]

        circles = [
            patch
            for patch in ax.patches
            if isinstance(patch, Circle)
        ]

        assert len(circles) == 1
        assert circles[0].center == pytest.approx(
            (69.464, 33.020)
        )
        assert circles[0].radius == pytest.approx(
            10 ** (0.43 * 6.0) / 111.0
        )

        stars = [
            line
            for line in ax.lines
            if line.get_marker() == "*"
        ]

        assert len(stars) == 1
        np.testing.assert_allclose(
            stars[0].get_xdata(),
            [69.464],
        )
        np.testing.assert_allclose(
            stars[0].get_ydata(),
            [33.020],
        )
    finally:
        fig.clear()


def test_tied_maxima_are_all_marked(spatial_result):
    spatial_result.positive_ratio[10, 10] = 100 / 24

    fig = make_figure(spatial_result)

    try:
        peak_boxes = [
            patch
            for patch in fig.axes[0].patches
            if isinstance(patch, Rectangle)
        ]

        assert len(peak_boxes) == 2
    finally:
        fig.clear()


def test_zero_map_has_no_peak_markers(spatial_result):
    spatial_result.positive_ratio[:] = 0.0

    fig = make_figure(spatial_result)

    try:
        peak_boxes = [
            patch
            for patch in fig.axes[0].patches
            if isinstance(patch, Rectangle)
        ]

        assert len(peak_boxes) == 0
    finally:
        fig.clear()


def test_plot_does_not_modify_scientific_result(spatial_result):
    before = spatial_result.positive_ratio.copy()

    fig = make_figure(spatial_result)

    try:
        np.testing.assert_array_equal(
            spatial_result.positive_ratio,
            before,
        )
    finally:
        fig.clear()


def test_save_png(spatial_result, tmp_path):
    output_path = tmp_path / "spatial" / "positive.png"

    saved_path = save_spatial_anomaly_plot(
        spatial_result,
        polarity="positive",
        output_path=output_path,
        start_time=START,
        end_time=END,
        epicenter_latitude=33.020,
        epicenter_longitude=69.464,
        magnitude=6.0,
    )

    assert saved_path == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0

    # PNG signature.
    assert output_path.read_bytes()[:8] == (
        b"\x89PNG\r\n\x1a\n"
    )


@pytest.mark.parametrize(
    "polarity",
    ["unknown", "", "Positive"],
)
def test_invalid_polarity_rejected(
    spatial_result,
    polarity,
):
    with pytest.raises(ValueError):
        make_figure(
            spatial_result,
            polarity=polarity,
        )


def test_non_utc_time_rejected(spatial_result):
    with pytest.raises(ValueError):
        make_figure(
            spatial_result,
            start_time=datetime(2022, 5, 28, 6),
        )


def test_window_duration_mismatch_rejected(spatial_result):
    with pytest.raises(ValueError):
        make_figure(
            spatial_result,
            end_time=datetime(
                2022, 5, 29, 6,
                tzinfo=timezone.utc,
            ),
        )


def test_invalid_epicenter_rejected(spatial_result):
    with pytest.raises(ValueError):
        make_figure(
            spatial_result,
            epicenter_latitude=95.0,
        )


def test_invalid_magnitude_rejected(spatial_result):
    with pytest.raises(ValueError):
        make_figure(
            spatial_result,
            magnitude=float("nan"),
        )


def test_invalid_output_extension_rejected(
    spatial_result,
    tmp_path,
):
    with pytest.raises(ValueError):
        save_spatial_anomaly_plot(
            spatial_result,
            polarity="positive",
            output_path=tmp_path / "plot.pdf",
            start_time=START,
            end_time=END,
            epicenter_latitude=33.020,
            epicenter_longitude=69.464,
            magnitude=6.0,
        )
