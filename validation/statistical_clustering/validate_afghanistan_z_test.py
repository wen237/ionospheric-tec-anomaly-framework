"""Validate Afghanistan one-proportion z-test against legacy logic."""

from datetime import date

import numpy as np

from src.statistical_clustering.earthquake_samples import (
    select_earthquake_samples,
)
from src.statistical_clustering.population_anomaly import (
    compute_population_anomaly_probability,
)
from src.statistical_clustering.earthquake_subset import (
    compute_earthquake_subset_anomalies,
)
from src.statistical_clustering.z_test import (
    one_proportion_z_test,
    generate_significance_mask,
)


# ==========================================================
# Configuration
# ==========================================================

from validation.statistical_clustering.config import (
    AFGHANISTAN_DATA_DIR,
    EQLIST_PATH,
)

DATA_DIR = AFGHANISTAN_DATA_DIR
TEC_PATH = DATA_DIR / "tec33.092_69.514.npy"

ANALYSIS_START = date(1999, 1, 1)
ANALYSIS_END = date(2021, 12, 31)

MINIMUM_MAGNITUDE = 6.0
OBSERVATION_DAYS = 30
REFERENCE_DAYS = 15
THRESHOLD_MULTIPLIER = 3.0

CRITICAL_Z = 1.96
HOURS_PER_DAY = 24


def legacy_z_test(
    positive_counts,
    negative_counts,
    positive_population_count,
    negative_population_count,
    total_days,
    n_events,
):
    """Reproduce legacy process_Z_score()."""

    p_positive = (
        positive_counts
        / n_events
    )

    p0_positive = (
        positive_population_count
        / HOURS_PER_DAY
        / (total_days - REFERENCE_DAYS)
    )

    z_positive = (
        p_positive - p0_positive
    ) / np.sqrt(
        p0_positive
        * (1.0 - p0_positive)
        / n_events
    )

    p_negative = (
        negative_counts
        / n_events
    )

    p0_negative = (
        negative_population_count
        / HOURS_PER_DAY
        / (total_days - REFERENCE_DAYS)
    )

    z_negative = (
        p_negative - p0_negative
    ) / np.sqrt(
        p0_negative
        * (1.0 - p0_negative)
        / n_events
    )

    return (
        z_positive,
        z_negative,
        p0_positive,
        p0_negative,
    )


def legacy_generate_mask(
    positive_z,
    negative_z,
):
    """Reproduce legacy generate_mask()."""

    positive_mask = np.where(
        positive_z > CRITICAL_Z,
        1,
        0,
    )

    negative_mask = np.where(
        negative_z > CRITICAL_Z,
        -1,
        0,
    )

    return (
        positive_mask
        + negative_mask
    )


def main():

    print(
        "========================================"
    )
    print(
        "Afghanistan one-proportion z-test equivalence"
    )
    print(
        "========================================"
    )

    # ------------------------------------------------------
    # Historical TEC
    # ------------------------------------------------------

    tec = np.load(
        TEC_PATH
    ).astype(
        np.float64
    )

    total_days = (
        len(tec)
        // HOURS_PER_DAY
    )

    daily_tec = tec.reshape(
        total_days,
        HOURS_PER_DAY,
    )

    # ------------------------------------------------------
    # Earthquake catalogue
    # ------------------------------------------------------

    eqlist = np.load(
        EQLIST_PATH,
        allow_pickle=True,
    )

    event_dates = np.asarray(
        [
            date(
                int(row[0]),
                int(row[1]),
                int(row[2]),
            )
            for row in eqlist
        ],
        dtype=object,
    )

    magnitudes = np.asarray(
        eqlist[:, -1],
        dtype=np.float64,
    )

    selection = select_earthquake_samples(
        event_dates=event_dates,
        magnitudes=magnitudes,
        analysis_start=ANALYSIS_START,
        analysis_end=ANALYSIS_END,
        minimum_magnitude=MINIMUM_MAGNITUDE,
        observation_days=OBSERVATION_DAYS,
        reference_days=REFERENCE_DAYS,
    )

    earthquake_dates = (
        selection.selected_dates
    )

    n_events = len(
        earthquake_dates
    )

    print(
        f"\nHistorical days : {total_days}"
    )

    print(
        f"Selected events : {n_events}"
    )

    assert total_days == 8401
    assert n_events == 74

    population = (
        compute_population_anomaly_probability(
            tec=daily_tec,
            reference_days=REFERENCE_DAYS,
            threshold_multiplier=THRESHOLD_MULTIPLIER,
        )
    )

    subset = (
        compute_earthquake_subset_anomalies(
            tec=daily_tec,
            start_date=ANALYSIS_START,
            earthquake_dates=earthquake_dates,
            observation_days=OBSERVATION_DAYS,
            reference_days=REFERENCE_DAYS,
            threshold_multiplier=THRESHOLD_MULTIPLIER,
        )
    )

    print(
        "\n=== Inputs ==="
    )

    print(
        f"Population positive count : "
        f"{population.positive_count}"
    )

    print(
        f"Population negative count : "
        f"{population.negative_count}"
    )

    print(
        f"p0 positive               : "
        f"{population.positive_probability:.16f}"
    )

    print(
        f"p0 negative               : "
        f"{population.negative_probability:.16f}"
    )

    (
        legacy_positive_z,
        legacy_negative_z,
        legacy_p0_positive,
        legacy_p0_negative,
    ) = legacy_z_test(
        positive_counts=subset.positive_counts,
        negative_counts=subset.negative_counts,
        positive_population_count=population.positive_count,
        negative_population_count=population.negative_count,
        total_days=total_days,
        n_events=n_events,
    )

    result = one_proportion_z_test(
        positive_counts=subset.positive_counts,
        negative_counts=subset.negative_counts,
        n_events=n_events,
        positive_null_proportion=(
            population.positive_probability
        ),
        negative_null_proportion=(
            population.negative_probability
        ),
    )

    positive_z_equal = np.array_equal(
        legacy_positive_z,
        result.positive_z,
    )

    negative_z_equal = np.array_equal(
        legacy_negative_z,
        result.negative_z,
    )

    positive_z_max_diff = np.max(
        np.abs(
            legacy_positive_z
            - result.positive_z
        )
    )

    negative_z_max_diff = np.max(
        np.abs(
            legacy_negative_z
            - result.negative_z
        )
    )

    print(
        "\n=== Z-score equivalence ==="
    )

    print(
        f"Positive exact equal : "
        f"{positive_z_equal}"
    )

    print(
        f"Negative exact equal : "
        f"{negative_z_equal}"
    )

    print(
        f"Positive max diff    : "
        f"{positive_z_max_diff:.16g}"
    )

    print(
        f"Negative max diff    : "
        f"{negative_z_max_diff:.16g}"
    )

    legacy_mask = legacy_generate_mask(
        positive_z=legacy_positive_z,
        negative_z=legacy_negative_z,
    )

    new_mask = generate_significance_mask(
        positive_z=result.positive_z,
        negative_z=result.negative_z,
        critical_z=CRITICAL_Z,
    )

    mask_equal = np.array_equal(
        legacy_mask,
        new_mask,
    )

    differing_mask_cells = np.count_nonzero(
        legacy_mask != new_mask
    )

    print(
        "\n=== Mask equivalence ==="
    )

    print(
        f"Mask exact equal       : "
        f"{mask_equal}"
    )

    print(
        f"Differing mask cells   : "
        f"{differing_mask_cells}"
    )

    positive_significant = (
        result.positive_z
        > CRITICAL_Z
    )

    negative_significant = (
        result.negative_z
        > CRITICAL_Z
    )

    overlap = (
        positive_significant
        & negative_significant
    )

    relative_days = np.arange(
        -OBSERVATION_DAYS,
        OBSERVATION_DAYS + 1,
        dtype=int,
    )

    positive_significant = (
        result.positive_z > CRITICAL_Z
    )

    negative_significant = (
        result.negative_z > CRITICAL_Z
    )

    overlap = (
        positive_significant
        & negative_significant
    )

    overlap_indices = np.argwhere(
        overlap
    )

    print(
        "\n=== Overlapping significant cells ==="
    )

    print(
        f"Overlap count : "
        f"{len(overlap_indices)}"
    )

    for row, hour in overlap_indices:

        relative_day = int(
            relative_days[row]
        )

        positive_count = int(
            subset.positive_counts[
                row,
                hour,
            ]
        )

        negative_count = int(
            subset.negative_counts[
                row,
                hour,
            ]
        )

        print(
            f"Day {relative_day:+3d}, "
            f"Hour {hour:02d} UT"
        )

        print(
            f"  Positive count : "
            f"{positive_count}/{n_events}"
        )

        print(
            f"  Negative count : "
            f"{negative_count}/{n_events}"
        )

        print(
            f"  z+             : "
            f"{result.positive_z[row, hour]:.6f}"
        )

        print(
            f"  z-             : "
            f"{result.negative_z[row, hour]:.6f}"
        )

        print(
            f"  Legacy mask    : "
            f"{legacy_mask[row, hour]}"
        )

    paper_window = (
        relative_days <= 0
    )

    paper_overlap = overlap[
        paper_window,
        :
    ]

    paper_overlap_count = np.count_nonzero(
        paper_overlap
    )

    print(
        "\n=== Paper-window overlap ==="
    )

    print(
        f"Day range              : "
        f"{relative_days[paper_window][0]} "
        f"through "
        f"{relative_days[paper_window][-1]}"
    )

    print(
        f"Overlapping cells      : "
        f"{paper_overlap_count}"
    )

    overlap_count = np.count_nonzero(
        overlap
    )

    print(
        "\n=== Significance overlap ==="
    )

    print(
        f"Positive significant cells : "
        f"{np.count_nonzero(positive_significant)}"
    )

    print(
        f"Negative significant cells : "
        f"{np.count_nonzero(negative_significant)}"
    )

    print(
        f"Overlapping cells           : "
        f"{overlap_count}"
    )

    pre_event_mask = new_mask[
        :OBSERVATION_DAYS + 1,
        :
    ]

    positive_pre_event = np.count_nonzero(
        pre_event_mask == 1
    )

    negative_pre_event = np.count_nonzero(
        pre_event_mask == -1
    )

    significant_pre_event = (
        positive_pre_event
        + negative_pre_event
    )

    print(
        "\n=== Paper analysis window ==="
    )

    print(
        "Relative days              : "
        "-30 through 0"
    )

    print(
        f"Mask shape                 : "
        f"{pre_event_mask.shape}"
    )

    print(
        f"Positive significant cells : "
        f"{positive_pre_event}"
    )

    print(
        f"Negative significant cells : "
        f"{negative_pre_event}"
    )

    print(
        f"Total significant cells    : "
        f"{significant_pre_event}"
    )

    significant_positions = np.argwhere(
        pre_event_mask != 0
    )

    print(
        "\n=== Significant cells ==="
    )

    for row, hour in significant_positions:

        relative_day = (
            row - OBSERVATION_DAYS
        )

        polarity = int(
            pre_event_mask[
                row,
                hour,
            ]
        )

        print(
            f"Day {relative_day:+3d}, "
            f"Hour {hour:02d} UT, "
            f"Polarity {polarity:+d}"
        )

    count_sum = (
        subset.positive_counts
        + subset.negative_counts
    )

    print(
        "\n=== Positive/negative count sanity check ==="
    )

    print(
        f"Maximum positive + negative count : "
        f"{np.max(count_sum)}"
    )

    print(
        f"Number of events                  : "
        f"{n_events}"
    )

    assert np.all(
        count_sum <= n_events
    )

    assert np.isclose(
        legacy_p0_positive,
        population.positive_probability,
    )

    assert np.isclose(
        legacy_p0_negative,
        population.negative_probability,
    )

    assert np.allclose(
        legacy_positive_z,
        result.positive_z,
        atol=1e-15,
        rtol=0.0,
    )

    assert np.allclose(
        legacy_negative_z,
        result.negative_z,
        atol=1e-15,
        rtol=0.0,
    )

    assert mask_equal

    assert pre_event_mask.shape == (
        31,
        24,
    )

    # Paper-level regression check
    assert significant_pre_event == 34

    print(
        "\nPASS: one-proportion z-test and "
        "paper significant-cell results match."
    )


if __name__ == "__main__":
    main()