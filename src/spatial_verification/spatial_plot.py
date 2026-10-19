"""Paper-style spatial TEC anomaly visualization.

Visualization only. No automatic epicentral verification.
"""

from datetime import datetime, timedelta
from pathlib import Path
import math

import matplotlib
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle

from .spatial_anomaly import SpatialAnomalyResult
from .spatial_grid import orient_gim_grid


def _validate_utc_hour(value: datetime, name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be timezone-aware UTC.")

    if value.minute or value.second or value.microsecond:
        raise ValueError(f"{name} must align with an hourly epoch.")


def _legacy_colormap() -> ListedColormap:
    """Reproduce the legacy jet colormap with magenta at its upper end."""
    colors = matplotlib.colormaps["jet"](
        np.linspace(0.0, 1.0, 256)
    )
    colors[-1, :] = [1.0, 0.0, 1.0, 1.0]
    return ListedColormap(colors)


def create_spatial_anomaly_figure(
    result: SpatialAnomalyResult,
    *,
    polarity: str,
    start_time: datetime,
    end_time: datetime,
    epicenter_latitude: float,
    epicenter_longitude: float,
    magnitude: float,
) -> Figure:
    """Create a paper-style spatial anomaly figure.

    The input anomaly arrays use raw GIM ordering.
    Only the plotted arrays are reoriented.

    The preparation-zone circle follows the legacy
    degree approximation, not a geodesic distance.
    """
    if not isinstance(result, SpatialAnomalyResult):
        raise TypeError("result must be a SpatialAnomalyResult.")

    if polarity not in ("positive", "negative"):
        raise ValueError("polarity must be 'positive' or 'negative'.")

    _validate_utc_hour(start_time, "start_time")
    _validate_utc_hour(end_time, "end_time")

    if end_time < start_time:
        raise ValueError("end_time must not precede start_time.")

    expected_steps = (
        int((end_time - start_time).total_seconds() // 3600) + 1
    )
    if result.window_steps != expected_steps:
        raise ValueError("Window duration does not match result.window_steps.")

    for name, value, lower, upper in (
        ("epicenter_latitude", epicenter_latitude, -90.0, 90.0),
        ("epicenter_longitude", epicenter_longitude, -180.0, 180.0),
    ):
        if isinstance(value, bool) or not isinstance(
            value, (int, float)
        ):
            raise TypeError(f"{name} must be numeric.")
        if not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} is outside its valid range.")

    if isinstance(magnitude, bool) or not isinstance(
        magnitude, (int, float)
    ):
        raise TypeError("magnitude must be numeric.")
    if not math.isfinite(magnitude) or magnitude <= 0:
        raise ValueError("magnitude must be finite and positive.")

    latitudes = np.asarray(result.latitudes, dtype=float)
    longitudes = np.asarray(result.longitudes, dtype=float)

    if (
        latitudes.ndim != 1
        or longitudes.ndim != 1
        or latitudes.size < 2
        or longitudes.size < 2
        or not np.all(np.isfinite(latitudes))
        or not np.all(np.isfinite(longitudes))
        or not np.all(np.diff(latitudes) > 0)
        or not np.all(np.diff(longitudes) > 0)
    ):
        raise ValueError("Invalid spatial coordinate arrays.")

    if latitudes.size != 71 or longitudes.size != 73:
        raise ValueError("Expected a 71 x 73 GIM grid.")

    if (
        not np.allclose(latitudes, np.linspace(-87.5, 87.5, 71))
        or not np.allclose(longitudes, np.linspace(-180.0, 180.0, 73))
    ):
        raise ValueError("Unexpected GIM coordinate convention.")

    raw_ratio = (
        result.positive_ratio
        if polarity == "positive"
        else result.negative_ratio
    )

    oriented_ratio = orient_gim_grid(
        np.asarray(raw_ratio, dtype=float)
    )

    if not np.all(np.isfinite(oriented_ratio)):
        raise ValueError("Spatial ratios must be finite.")
    if np.any((oriented_ratio < 0) | (oriented_ratio > 100)):
        raise ValueError("Spatial ratios must be between 0 and 100.")

    maximum = float(np.max(oriented_ratio))
    color_maximum = max(maximum, 1.0)

    fig = Figure(figsize=(14, 7), constrained_layout=True)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)

    # The grid coordinates denote cell centers.
    # The legacy GIM grid spacing is 5 degrees longitude
    # and 2.5 degrees latitude.
    image = ax.imshow(
        oriented_ratio,
        extent=(-182.5, 182.5, -88.75, 88.75),
        origin="lower",
        interpolation="nearest",
        cmap=_legacy_colormap(),
        vmin=0.0,
        vmax=color_maximum,
        aspect="auto",
    )

    ax.set_xlim(-180.0, 180.0)
    ax.set_ylim(-87.5, 87.5)
    ax.set_xticks(np.arange(-180, 181, 30))
    ax.set_yticks(np.arange(-75, 76, 25))
    ax.grid(
        color="black",
        alpha=0.18,
        linestyle=":",
        linewidth=0.6,
    )

    # Epicenter.
    ax.plot(
        epicenter_longitude,
        epicenter_latitude,
        marker="*",
        markersize=16,
        markerfacecolor="yellow",
        markeredgecolor="black",
        markeredgewidth=1.2,
        linestyle="none",
        zorder=5,
    )

    # Legacy earthquake preparation-zone radius.
    radius_km = 10.0 ** (0.43 * magnitude)
    radius_degrees = radius_km / 111.0

    preparation_circle = Circle(
        (epicenter_longitude, epicenter_latitude),
        radius=radius_degrees,
        fill=False,
        edgecolor="blue",
        linewidth=2.0,
        zorder=4,
    )
    ax.add_patch(preparation_circle)

    # Highlight all tied positive maxima.
    # Zero-valued maps must not mark every grid cell.
    if maximum > 0.0:
        peak_rows, peak_cols = np.where(
            np.isclose(oriented_ratio, maximum)
        )

        for row, col in zip(peak_rows, peak_cols):
            rectangle = Rectangle(
                (
                    float(longitudes[col]) - 2.5,
                    float(latitudes[row]) - 1.25,
                ),
                5.0,
                2.5,
                facecolor="none",
                edgecolor="magenta",
                linewidth=1.8,
                zorder=6,
            )
            ax.add_patch(rectangle)

    label = polarity.capitalize()

    ax.set_title(
        f"{label} TEC anomaly occurrence proportion\n"
        f"{start_time:%Y-%m-%d %H:%M} to "
        f"{end_time:%Y-%m-%d %H:%M} UTC",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel("Longitude (degrees)")
    ax.set_ylabel("Latitude (degrees)")

    colorbar = fig.colorbar(
        image,
        ax=ax,
        shrink=0.82,
        pad=0.025,
    )
    colorbar.set_label("TEC anomaly occurrence proportion (%)")

    return fig


def save_spatial_anomaly_plot(
    result: SpatialAnomalyResult,
    *,
    polarity: str,
    output_path: Path,
    start_time: datetime,
    end_time: datetime,
    epicenter_latitude: float,
    epicenter_longitude: float,
    magnitude: float,
) -> Path:
    """Save a paper-style spatial anomaly PNG."""
    if not isinstance(output_path, Path):
        raise TypeError("output_path must be a pathlib.Path.")
    if output_path.suffix.lower() != ".png":
        raise ValueError("output_path must have a .png extension.")

    fig = create_spatial_anomaly_figure(
        result,
        polarity=polarity,
        start_time=start_time,
        end_time=end_time,
        epicenter_latitude=epicenter_latitude,
        epicenter_longitude=epicenter_longitude,
        magnitude=magnitude,
    )

    try:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        fig.savefig(
            output_path,
            dpi=200,
            format="png",
        )
    finally:
        fig.clear()

    return output_path
