from datetime import datetime, timedelta

import numpy as np

from temporal_anomaly import detect_temporal_anomalies


def main():
    start = datetime(2022, 1, 1, 0, 0)

    # 16 consecutive daily observations at the same UTC time.
    epochs = np.array(
        [start + timedelta(days=i) for i in range(16)],
        dtype=object,
    )

    # First 15 days are used as the reference period.
    # The 16th day is the analysis day.
    reference_tec = np.array(
        [
            10, 11, 12, 13, 14,
            15, 16, 17, 18, 19,
            20, 21, 22, 23, 24,
        ],
        dtype=float,
    )

    print("=== Normal case ===")

    tec_normal = np.append(reference_tec, 17.0)

    result = detect_temporal_anomalies(
        tec_normal,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    print("Observed     :", result.observed)
    print("Q1           :", result.q1)
    print("Median       :", result.median)
    print("Q3           :", result.q3)
    print("Upper bound  :", result.upper_bound)
    print("Lower bound  :", result.lower_bound)
    print("Anomaly      :", result.anomaly)

    print("\n=== Positive anomaly case ===")

    tec_positive = np.append(reference_tec, 40.0)

    result_positive = detect_temporal_anomalies(
        tec_positive,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    print("Observed     :", result_positive.observed)
    print("Upper bound  :", result_positive.upper_bound)
    print("Anomaly      :", result_positive.anomaly)

    print("\n=== Negative anomaly case ===")

    tec_negative = np.append(reference_tec, 0.0)

    result_negative = detect_temporal_anomalies(
        tec_negative,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    print("Observed     :", result_negative.observed)
    print("Lower bound  :", result_negative.lower_bound)
    print("Anomaly      :", result_negative.anomaly)

    print("\n=== Missing reference data case ===")

    reference_tec_nan = np.array(
        [
            10, 11, 12, 13, 14,
            15, 16, np.nan, 18, 19,
            20, 21, 22, 23, 24,
        ],
        dtype=float,
    )

    tec_nan = np.append(reference_tec_nan, 40.0)

    result_strict = detect_temporal_anomalies(
        tec_nan,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    print("Strict mode")
    print("Upper bound :", result_strict.upper_bound)
    print("Lower bound :", result_strict.lower_bound)
    print("Anomaly     :", result_strict.anomaly)

    result_relaxed = detect_temporal_anomalies(
        tec_nan,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
        min_reference_samples=14,
    )

    print("\nRelaxed mode")
    print("Upper bound :", result_relaxed.upper_bound)
    print("Lower bound :", result_relaxed.lower_bound)
    print("Anomaly     :", result_relaxed.anomaly)

    print("\n=== Multiple epochs per day case ===")

    start_multi = datetime(2022, 1, 1)

    epochs_multi = []
    tec_multi = []

    for day in range(16):
        date = start_multi + timedelta(days=day)

        # 00 UT series
        epochs_multi.append(date)
        tec_multi.append(10 + day)

        # 12 UT series
        epochs_multi.append(date + timedelta(hours=12))
        tec_multi.append(100 + day)

    epochs_multi = np.array(epochs_multi, dtype=object)
    tec_multi = np.array(tec_multi, dtype=float)

    # Modify the final analysis day:
    # 00 UT -> positive anomaly
    # 12 UT -> normal
    tec_multi[-2] = 40.0
    tec_multi[-1] = 107.0

    result_multi = detect_temporal_anomalies(
        tec_multi,
        epochs_multi,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    print("Epochs       :", result_multi.epochs)
    print("Observed     :", result_multi.observed)
    print("Median       :", result_multi.median)
    print("Upper bound  :", result_multi.upper_bound)
    print("Lower bound  :", result_multi.lower_bound)
    print("Anomaly      :", result_multi.anomaly)


if __name__ == "__main__":
    main()