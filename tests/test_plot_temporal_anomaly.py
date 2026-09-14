from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np

from temporal_anomaly import detect_temporal_anomalies
from plot_temporal_anomaly import plot_temporal_anomaly


def main():
    start = datetime(2022, 1, 1)

    epochs = np.array(
        [
            start + timedelta(days=day, hours=hour)
            for day in range(20)
            for hour in range(24)
        ],
        dtype=object,
    )

    # A simple repeating diurnal TEC pattern.
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

    # Add artificial anomalies during the analysis period.
    positive_epoch = datetime(2022, 1, 18, 12)
    negative_epoch = datetime(2022, 1, 19, 12)

    tec[np.where(epochs == positive_epoch)[0][0]] += 15.0
    tec[np.where(epochs == negative_epoch)[0][0]] -= 15.0

    result = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    print(
        "Positive anomalies:",
        np.count_nonzero(result.anomaly == 1),
    )

    print(
        "Negative anomalies:",
        np.count_nonzero(result.anomaly == -1),
    )

    fig, ax = plot_temporal_anomaly(
        result,
        title="Synthetic Temporal TEC Anomaly Test",
    )

    plt.show()


if __name__ == "__main__":
    main()
    