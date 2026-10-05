"""Visualization utilities for temporal TEC anomaly results.

This module provides plotting functions for ``TemporalAnomalyResult`` objects.
It does not perform anomaly detection or recalculate anomaly classifications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

from .temporal_anomaly import TemporalAnomalyResult


def plot_temporal_anomaly(
    result: TemporalAnomalyResult,
    *,
    title: str | None = None,
    ylabel: str = "TEC (TECu)",
    xlabel: str = "Time (UT)",
    figsize: tuple[float, float] = (14, 5),
    show_legend: bool = True,
) -> tuple[Figure, Axes]:
    """Plot temporal TEC anomaly detection results.

    Positive and negative anomaly regions are visualized using the
    classifications already stored in ``result.anomaly``. This function
    does not recalculate anomaly classifications.

    Parameters
    ----------
    result
        Output from ``detect_temporal_anomalies``.
    title
        Optional figure title.
    ylabel
        Label of the vertical axis.
    xlabel
        Label of the horizontal axis.
    figsize
        Figure size in inches.
    show_legend
        Whether to display the legend.

    Returns
    -------
    fig, ax
        Matplotlib figure and axes objects.
    """

    _validate_result(result)

    epochs = np.asarray(result.epochs, dtype=object)
    observed = np.asarray(result.observed, dtype=float)
    median = np.asarray(result.median, dtype=float)
    upper = np.asarray(result.upper_bound, dtype=float)
    lower = np.asarray(result.lower_bound, dtype=float)
    anomaly = np.asarray(result.anomaly)

    fig, ax = plt.subplots(figsize=figsize)

    # Reference statistics and observed TEC.
    ax.plot(
        epochs,
        upper,
        color="0.65",
        linewidth=1.5,
        label="Upper bound",
    )

    ax.plot(
        epochs,
        lower,
        color="0.65",
        linewidth=1.5,
        label="Lower bound",
    )

    ax.plot(
        epochs,
        median,
        color="orange",
        linewidth=1.8,
        label="Median",
    )

    ax.plot(
        epochs,
        observed,
        color="black",
        linewidth=1.5,
        label="Observed TEC",
    )

    # Use the anomaly classifications calculated by temporal_anomaly.py.
    positive = (anomaly == 1) & np.isfinite(observed) & np.isfinite(median)
    negative = (anomaly == -1) & np.isfinite(observed) & np.isfinite(median)

    ax.fill_between(
        epochs,
        median,
        observed,
        where=positive,
        interpolate=True,
        color="tomato",
        alpha=0.7,
        label="Positive anomaly",
    )

    ax.fill_between(
        epochs,
        median,
        observed,
        where=negative,
        interpolate=True,
        color=(102 / 255, 102 / 255, 1.0),
        alpha=0.7,
        label="Negative anomaly",
    )

    # Datetime axis formatting.
    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)

    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    if title is not None:
        ax.set_title(title)

    ax.minorticks_on()
    ax.tick_params(
        axis="both",
        which="major",
        direction="in",
        top=True,
        right=True,
    )

    ax.grid(
        visible=True,
        linewidth=0.8,
        alpha=0.4,
        linestyle="--",
    )

    if show_legend:
        ax.legend(frameon=False)

    fig.tight_layout()

    return fig, ax


def _validate_result(result: TemporalAnomalyResult) -> None:
    """Validate fields required for visualization."""

    arrays = {
        "epochs": result.epochs,
        "observed": result.observed,
        "median": result.median,
        "upper_bound": result.upper_bound,
        "lower_bound": result.lower_bound,
        "anomaly": result.anomaly,
    }

    lengths = {
        name: len(values)
        for name, values in arrays.items()
    }

    if len(set(lengths.values())) != 1:
        details = ", ".join(
            f"{name}={length}"
            for name, length in lengths.items()
        )

        raise ValueError(
            "TemporalAnomalyResult fields must have equal lengths: "
            f"{details}"
        )

    if lengths["epochs"] == 0:
        raise ValueError(
            "TemporalAnomalyResult contains no analysis epochs."
        )

    valid_codes = {-1, 0, 1}

    if not set(np.unique(result.anomaly)).issubset(valid_codes):
        raise ValueError(
            "anomaly must contain only -1, 0, and 1."
        )
    