"""Validate temporal-anomaly equivalence for the Afghanistan case.

This script compares the current ``detect_temporal_anomalies`` implementation
against the legacy quartile-based temporal anomaly calculation used for the
Afghanistan case study.

Both methods operate on the same 46-day TEC input. The validation compares
observed TEC, quartiles, anomaly bounds, and anomaly classifications.
"""

from datetime import timedelta
import numpy as np

from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies
from validation.temporal_anomaly.config import (
    CASE_END_DATE,
    LATITUDE,
    LEGACY_GIM_DIR,
    LONGITUDE,
    REFERENCE_DAYS,
    THRESHOLD_MULTIPLIER,
)

# ==========================================================
# Afghanistan case configuration
# ==========================================================

DISPLAY_DAYS = 31
TIME_STEPS_PER_DAY = 24
EXPECTED_POSITIVE = 37
EXPECTED_NORMAL = 610
EXPECTED_NEGATIVE = 97


def load_legacy_tec() -> tuple[np.ndarray, np.ndarray]:
    """Load the legacy 46-day TEC matrix and chronological time series."""

    latitude_index = round(
        (87.5 - LATITUDE) / 2.5
    )

    longitude_index = round(
        (LONGITUDE + 180.0) / 5.0
    )

    latitude_indices = (
        np.arange(TIME_STEPS_PER_DAY)
        * 71
        + latitude_index
    )

    number_of_days = (
        DISPLAY_DAYS
        + REFERENCE_DAYS
    )

    tec_matrix = np.zeros(
        (
            TIME_STEPS_PER_DAY,
            number_of_days,
        ),
        dtype=np.float64,
    )

    for i in range(number_of_days):
        current_date = (
            CASE_END_DATE
            - timedelta(days=i)
        )

        year = current_date.year
        doy = current_date.timetuple().tm_yday

        path = (
            LEGACY_GIM_DIR
            / f"GIMTEC{year}"
            / f"gim{year}{doy:03d}.npz"
        )

        gim = np.load(path)

        tec_matrix[:, i] = (
            gim["gim"][
                latitude_indices,
                longitude_index,
            ]
            / 10.0
        )

    tec_matrix = np.fliplr(
        tec_matrix
    )

    tec_series = tec_matrix.reshape(
        -1,
        order="F",
    )

    start_time = (
        CASE_END_DATE
        - timedelta(
            days=number_of_days - 1
        )
    )

    epochs = np.asarray(
        [
            start_time
            + timedelta(hours=i)
            for i in range(len(tec_series))
        ],
        dtype=object,
    )

    return tec_matrix, epochs


def run_legacy_temporal_anomaly(
    tec_matrix: np.ndarray,
) -> dict[str, np.ndarray]:
    """Run the legacy temporal anomaly calculation."""

    pred = np.zeros(
        (
            TIME_STEPS_PER_DAY,
            DISPLAY_DAYS,
            REFERENCE_DAYS,
        ),
        dtype=np.float64,
    )

    for i in range(REFERENCE_DAYS):
        pred[:, :, i] = tec_matrix[
            :,
            i:i + DISPLAY_DAYS,
        ]

    q1, q2, q3 = np.percentile(
        pred,
        [25, 50, 75],
        axis=2,
    )

    observed = tec_matrix.reshape(
        -1,
        order="F",
    )[
        REFERENCE_DAYS
        * TIME_STEPS_PER_DAY:
    ]

    q1 = q1.reshape(
        -1,
        order="F",
    )

    q2 = q2.reshape(
        -1,
        order="F",
    )

    q3 = q3.reshape(
        -1,
        order="F",
    )

    upper_bound = (
        q2
        + THRESHOLD_MULTIPLIER
        * (q3 - q2)
    )

    lower_bound = (
        q2
        - THRESHOLD_MULTIPLIER
        * (q2 - q1)
    )

    anomaly = np.zeros(
        observed.shape,
        dtype=np.int8,
    )

    anomaly[
        observed > upper_bound
    ] = 1

    anomaly[
        observed < lower_bound
    ] = -1

    return {
        "Observed": observed,
        "Q1": q1,
        "Median": q2,
        "Q3": q3,
        "Upper bound": upper_bound,
        "Lower bound": lower_bound,
        "Anomaly": anomaly,
    }


def main() -> None:
    """Run the Afghanistan temporal-anomaly equivalence validation."""

    tec_matrix, epochs = load_legacy_tec()

    tec_series = tec_matrix.reshape(
        -1,
        order="F",
    )

    new_result = detect_temporal_anomalies(
        tec=tec_series,
        epochs=epochs,
        reference_days=REFERENCE_DAYS,
        threshold_multiplier=THRESHOLD_MULTIPLIER,
    )

    legacy = run_legacy_temporal_anomaly(
        tec_matrix
    )

    current = {
        "Observed": new_result.observed,
        "Q1": new_result.q1,
        "Median": new_result.median,
        "Q3": new_result.q3,
        "Upper bound": new_result.upper_bound,
        "Lower bound": new_result.lower_bound,
        "Anomaly": new_result.anomaly,
    }

    print(
        "========================================"
    )
    print(
        "Afghanistan temporal-anomaly equivalence"
    )
    print(
        "========================================"
    )

    for name in (
        "Observed",
        "Q1",
        "Median",
        "Q3",
        "Upper bound",
        "Lower bound",
    ):
        old = legacy[name]
        new = current[name]

        equal = np.allclose(
            old,
            new,
            rtol=1e-12,
            atol=1e-12,
            equal_nan=True,
        )

        max_abs_diff = np.nanmax(
            np.abs(old - new)
        )

        print(
            f"{name:<12} "
            f"equal={equal}, "
            f"max_abs_diff={max_abs_diff:.12g}"
        )

        assert equal, (
            f"{name} does not match "
            "the legacy implementation."
        )

    anomaly_equal = np.array_equal(
        legacy["Anomaly"],
        current["Anomaly"],
    )

    anomaly_difference_count = np.count_nonzero(
        legacy["Anomaly"]
        != current["Anomaly"]
    )

    print(
        f"{'Anomaly':<12} "
        f"equal={anomaly_equal}, "
        f"different={anomaly_difference_count}"
    )

    assert anomaly_equal, (
        "Anomaly classifications do not match "
        "the legacy implementation."
    )

    positive = int(
        np.count_nonzero(
            current["Anomaly"] == 1
        )
    )

    normal = int(
        np.count_nonzero(
            current["Anomaly"] == 0
        )
    )

    negative = int(
        np.count_nonzero(
            current["Anomaly"] == -1
        )
    )

    assert positive == EXPECTED_POSITIVE, (
        "Unexpected number of positive anomalies: "
        f"{positive} (expected {EXPECTED_POSITIVE})."
    )

    assert normal == EXPECTED_NORMAL, (
        "Unexpected number of normal observations: "
        f"{normal} (expected {EXPECTED_NORMAL})."
    )

    assert negative == EXPECTED_NEGATIVE, (
        "Unexpected number of negative anomalies: "
        f"{negative} (expected {EXPECTED_NEGATIVE})."
    )

    print(
        "\nAnomaly counts:"
    )
    print(
        {
            "positive": positive,
            "normal": normal,
            "negative": negative,
        }
    )

    print(
        "\nAfghanistan temporal-anomaly "
        "equivalence: PASS"
    )


if __name__ == "__main__":
    main()