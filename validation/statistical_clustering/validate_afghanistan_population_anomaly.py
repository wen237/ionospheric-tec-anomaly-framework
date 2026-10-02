"""Validate Afghanistan population anomaly statistics against legacy logic."""

import numpy as np

from src.statistical_clustering.population_anomaly import (
    compute_population_anomaly_probability,
)


# ==========================================================
# Configuration
# ==========================================================

from validation.statistical_clustering.config import LEGACY_TEC_PATH

REFERENCE_DAYS = 15
THRESHOLD_MULTIPLIER = 3.0
HOURS_PER_DAY = 24


def legacy_population_anomaly(
    tec: np.ndarray,
):
    """Reproduce legacy OneSampleTest.process_population()."""

    tec = np.asarray(
        tec,
        dtype=np.float64,
    )

    total_days = (
        len(tec) // HOURS_PER_DAY
    )

    daily_tec = tec.reshape(
        total_days,
        HOURS_PER_DAY,
    )

    # ------------------------------------------------------
    # Legacy reference construction
    # ------------------------------------------------------

    reference = np.asarray(
        [
            daily_tec[
                i:
                i + REFERENCE_DAYS,
                :
            ]
            for i in range(
                total_days
                - REFERENCE_DAYS
            )
        ],
        dtype=np.float64,
    )

    observed = daily_tec[
        REFERENCE_DAYS:,
        :
    ]

    q1 = np.percentile(
        reference,
        25,
        axis=1,
    )

    median = np.percentile(
        reference,
        50,
        axis=1,
    )

    q3 = np.percentile(
        reference,
        75,
        axis=1,
    )

    upper_bound = (
        median
        + THRESHOLD_MULTIPLIER
        * (q3 - median)
    )

    lower_bound = (
        median
        - THRESHOLD_MULTIPLIER
        * (median - q1)
    )

    positive_count = int(
        np.sum(
            observed > upper_bound
        )
    )

    negative_count = int(
        np.sum(
            observed < lower_bound
        )
    )

    valid_sample_count = (
        HOURS_PER_DAY
        * (
            total_days
            - REFERENCE_DAYS
        )
    )

    positive_probability = (
        positive_count
        / valid_sample_count
    )

    negative_probability = (
        negative_count
        / valid_sample_count
    )

    return {
        "positive_count": positive_count,
        "negative_count": negative_count,
        "valid_sample_count": valid_sample_count,
        "positive_probability": positive_probability,
        "negative_probability": negative_probability,
    }


def main():

    print(
        "========================================"
    )
    print(
        "Afghanistan population anomaly equivalence"
    )
    print(
        "========================================"
    )

    # ------------------------------------------------------
    # Load paper historical TEC
    # ------------------------------------------------------

    legacy_tec = np.load(
        LEGACY_TEC_PATH
    ).astype(
        np.float64
    )

    print(
        f"\nTEC points      : {len(legacy_tec)}"
    )

    assert (
        len(legacy_tec)
        % HOURS_PER_DAY
        == 0
    )

    total_days = (
        len(legacy_tec)
        // HOURS_PER_DAY
    )

    print(
        f"Total days      : {total_days}"
    )

    print(
        f"Reference days  : {REFERENCE_DAYS}"
    )

    daily_tec = legacy_tec.reshape(
        total_days,
        HOURS_PER_DAY,
    )

    print(
        f"Daily TEC shape : {daily_tec.shape}"
    )

    # ------------------------------------------------------
    # Legacy calculation
    # ------------------------------------------------------

    legacy = legacy_population_anomaly(
        legacy_tec
    )

    # ------------------------------------------------------
    # New calculation
    # ------------------------------------------------------

    result = compute_population_anomaly_probability(
        tec=daily_tec,
        reference_days=REFERENCE_DAYS,
        threshold_multiplier=THRESHOLD_MULTIPLIER,
    )

    # ------------------------------------------------------
    # Report
    # ------------------------------------------------------

    print(
        "\n=== Legacy ==="
    )

    print(
        f"Positive count       : "
        f"{legacy['positive_count']}"
    )

    print(
        f"Negative count       : "
        f"{legacy['negative_count']}"
    )

    print(
        f"Valid sample count   : "
        f"{legacy['valid_sample_count']}"
    )

    print(
        f"Positive probability : "
        f"{legacy['positive_probability']:.16f}"
    )

    print(
        f"Negative probability : "
        f"{legacy['negative_probability']:.16f}"
    )

    print(
        "\n=== New ==="
    )

    print(
        f"Positive count       : "
        f"{result.positive_count}"
    )

    print(
        f"Negative count       : "
        f"{result.negative_count}"
    )

    print(
        f"Valid sample count   : "
        f"{result.valid_sample_count}"
    )

    print(
        f"Positive probability : "
        f"{result.positive_probability:.16f}"
    )

    print(
        f"Negative probability : "
        f"{result.negative_probability:.16f}"
    )

    # ------------------------------------------------------
    # Equivalence
    # ------------------------------------------------------

    positive_count_equal = (
        result.positive_count
        == legacy["positive_count"]
    )

    negative_count_equal = (
        result.negative_count
        == legacy["negative_count"]
    )

    sample_count_equal = (
        result.valid_sample_count
        == legacy["valid_sample_count"]
    )

    positive_probability_equal = np.isclose(
        result.positive_probability,
        legacy["positive_probability"],
        atol=1e-15,
        rtol=0.0,
    )

    negative_probability_equal = np.isclose(
        result.negative_probability,
        legacy["negative_probability"],
        atol=1e-15,
        rtol=0.0,
    )

    print(
        "\n=== Equivalence ==="
    )

    print(
        f"Positive count equal       : "
        f"{positive_count_equal}"
    )

    print(
        f"Negative count equal       : "
        f"{negative_count_equal}"
    )

    print(
        f"Valid sample count equal   : "
        f"{sample_count_equal}"
    )

    print(
        f"Positive probability equal : "
        f"{positive_probability_equal}"
    )

    print(
        f"Negative probability equal : "
        f"{negative_probability_equal}"
    )

    assert positive_count_equal
    assert negative_count_equal
    assert sample_count_equal
    assert positive_probability_equal
    assert negative_probability_equal

    print(
        "\nPASS: population anomaly statistics "
        "match the legacy implementation."
    )


if __name__ == "__main__":
    main()