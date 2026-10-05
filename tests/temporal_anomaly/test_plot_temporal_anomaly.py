from datetime import datetime, timedelta

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import numpy as np

from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies
from src.temporal_anomaly.plotting import plot_temporal_anomaly


def test_plot_temporal_anomaly_returns_figure_and_axes():
    start = datetime(2022, 1, 1)

    epochs = np.array(
        [
            start + timedelta(days=day, hours=hour)
            for day in range(20)
            for hour in range(24)
        ],
        dtype=object,
    )

    tec = np.array(
        [
            20.0
            + 5.0 * np.sin(
                2.0 * np.pi * epoch.hour / 24.0
            )
            for epoch in epochs
        ],
        dtype=float,
    )

    positive_epoch = datetime(2022, 1, 18, 12)
    negative_epoch = datetime(2022, 1, 19, 12)

    positive_index = np.where(
        epochs == positive_epoch
    )[0][0]

    negative_index = np.where(
        epochs == negative_epoch
    )[0][0]

    tec[positive_index] += 15.0
    tec[negative_index] -= 15.0

    result = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    assert np.count_nonzero(result.anomaly == 1) >= 1
    assert np.count_nonzero(result.anomaly == -1) >= 1

    fig, ax = plot_temporal_anomaly(
        result,
        title="Synthetic Temporal TEC Anomaly Test",
    )

    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)

    assert ax.get_title() == (
        "Synthetic Temporal TEC Anomaly Test"
    )

    assert len(ax.lines) > 0

    plt.close(fig)