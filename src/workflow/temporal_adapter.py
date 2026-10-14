"""Adapter for Framework A temporal anomaly results."""

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from src.temporal_anomaly.temporal_anomaly import (
    TemporalAnomalyResult,
)
from src.temporal_anomaly.plotting import (
    plot_temporal_anomaly,
)


def save_temporal_analysis_plot(
    result: TemporalAnomalyResult,
    output_path: Path,
    *,
    title: str | None = None,
) -> Path:
    """Save a validated Framework A temporal anomaly plot."""

    if not isinstance(result, TemporalAnomalyResult):
        raise TypeError(
            "result must be a TemporalAnomalyResult."
        )

    if not isinstance(output_path, Path):
        raise TypeError(
            "output_path must be a Path."
        )

    if output_path.suffix.lower() != ".png":
        raise ValueError(
            "output_path must have a .png extension."
        )

    if title is not None and not isinstance(title, str):
        raise TypeError(
            "title must be a string or None."
        )

    if len(result.epochs) == 0:
        raise ValueError(
            "Temporal anomaly result must not be empty."
        )

    if not (
        len(result.epochs)
        == len(result.observed)
        == len(result.anomaly)
    ):
        raise ValueError(
            "Temporal result arrays must have matching lengths."
        )

    if not np.all(
        np.isin(result.anomaly, [-1, 0, 1])
    ):
        raise ValueError(
            "Temporal anomaly classifications must be -1, 0, or 1."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig, _ = plot_temporal_anomaly(
        result,
        title=title,
    )

    try:
        fig.savefig(
            output_path,
            dpi=150,
            bbox_inches="tight",
        )
    finally:
        plt.close(fig)

    return output_path