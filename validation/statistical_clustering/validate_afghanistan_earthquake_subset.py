"""Validate Afghanistan earthquake-subset anomalies against legacy logic."""

from datetime import date

import numpy as np

from src.statistical_clustering.earthquake_samples import (
    select_earthquake_samples,
)
from src.statistical_clustering.earthquake_subset import (
    compute_earthquake_subset_anomalies,
)


# ==========================================================
# Configuration
# ==========================================================

from validation.statistical_clustering.config import (
    AFGHANISTAN_DATA_DIR,
    EQLIST_PATH,
    LEGACY_TEC_PATH,
)

DATA_DIR = AFGHANISTAN_DATA_DIR

ANALYSIS_START = date(1999, 1, 1)
ANALYSIS_END = date(2021, 12, 31)

MINIMUM_MAGNITUDE = 6.0

OBSERVATION_DAYS = 30
REFERENCE_DAYS = 15
THRESHOLD_MULTIPLIER = 3.0

HOURS_PER_DAY = 24


def legacy_process_subset(
    tec: np.ndarray,
    earthquake_dates: np.ndarray,
):
    """Reproduce legacy OneSampleTest.process_subset()."""

    tec = np.asarray(
        tec,
        dtype=np.float64,
    )

    total_days = (
        len(tec) // HOURS_PER_DAY
    )

    tec_arr = tec.reshape(
        total_days,
        HOURS_PER_DAY,
    )

    n_events = len(
        earthquake_dates
    )

    n_relative_days = (
        OBSERVATION_DAYS * 2 + 1
    )

    ref_arr = np.zeros(
        (
            n_relative_days,
            HOURS_PER_DAY,
            REFERENCE_DAYS,
        ),
        dtype=np.float64,
    )

    obs = np.zeros(
        (
            n_relative_days,
            HOURS_PER_DAY,
            n_events,
        ),
        dtype=np.float64,
    )

    q1 = np.zeros_like(obs)
    q2 = np.zeros_like(obs)
    q3 = np.zeros_like(obs)

    for event_index, event_date in enumerate(
        earthquake_dates
    ):

        # Equivalent to legacy ordinal-date indexing.
        event_day_index = (
            event_date - ANALYSIS_START
        ).days

        posi = (
            event_day_index
            - (
                OBSERVATION_DAYS
                + REFERENCE_DAYS
            )
        )

        tec_temp = tec_arr[
            posi:
            posi
            + (
                REFERENCE_DAYS
                + OBSERVATION_DAYS * 2
            )
            + 1
        ]

        for i in range(
            REFERENCE_DAYS
        ):

            ref_arr[
                :,
                :,
                i,
            ] = tec_temp[
                i:
                i
                + tec_temp.shape[0]
                - REFERENCE_DAYS
            ]

        (
            q1_temp,
            q2_temp,
            q3_temp,
        ) = np.percentile(
            ref_arr,
            [25, 50, 75],
            axis=2,
        )

        obs[
            :,
            :,
            event_index,
        ] = tec_temp[
            REFERENCE_DAYS:
        ]

        q1[
            :,
            :,
            event_index,
        ] = q1_temp

        q2[
            :,
            :,
            event_index,
        ] = q2_temp

        q3[
            :,
            :,
            event_index,
        ] = q3_temp

    delta_tec = (
        obs - q2
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

    positive_counts = np.sum(
        (obs - upper_bound) > 0,
        axis=2,
    )

    negative_counts = np.sum(
        (obs - lower_bound) < 0,
        axis=2,
    )

    return (
        positive_counts,
        negative_counts,
        delta_tec,
    )


def main():

    print(
        "========================================"
    )
    print(
        "Afghanistan earthquake subset equivalence"
    )
    print(
        "========================================"
    )

    # ------------------------------------------------------
    # Load historical TEC
    # ------------------------------------------------------

    legacy_tec = np.load(
        LEGACY_TEC_PATH
    ).astype(
        np.float64
    )

    total_days = (
        len(legacy_tec)
        // HOURS_PER_DAY
    )

    daily_tec = legacy_tec.reshape(
        total_days,
        HOURS_PER_DAY,
    )

    print(
        f"\nTEC points       : {len(legacy_tec)}"
    )
    print(
        f"TEC days         : {total_days}"
    )
    print(
        f"Daily TEC shape  : {daily_tec.shape}"
    )

    # ------------------------------------------------------
    # Load earthquake catalogue
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

    print(
        f"Raw earthquakes  : {len(eqlist)}"
    )
    print(
        f"Selected events  : {len(earthquake_dates)}"
    )

    assert len(
        earthquake_dates
    ) == 74

    # ------------------------------------------------------
    # Legacy calculation
    # ------------------------------------------------------

    (
        legacy_positive,
        legacy_negative,
        legacy_delta,
    ) = legacy_process_subset(
        tec=legacy_tec,
        earthquake_dates=earthquake_dates,
    )

    # ------------------------------------------------------
    # New calculation
    # ------------------------------------------------------

    result = compute_earthquake_subset_anomalies(
        tec=daily_tec,
        start_date=ANALYSIS_START,
        earthquake_dates=earthquake_dates,
        observation_days=OBSERVATION_DAYS,
        reference_days=REFERENCE_DAYS,
        threshold_multiplier=THRESHOLD_MULTIPLIER,
    )

    print(
        "\n=== Shapes ==="
    )

    print(
        f"Legacy positive : "
        f"{legacy_positive.shape}"
    )
    print(
        f"New positive    : "
        f"{result.positive_counts.shape}"
    )

    print(
        f"Legacy negative : "
        f"{legacy_negative.shape}"
    )
    print(
        f"New negative    : "
        f"{result.negative_counts.shape}"
    )

    print(
        f"Legacy delta    : "
        f"{legacy_delta.shape}"
    )
    print(
        f"New delta       : "
        f"{result.delta_tec.shape}"
    )

    positive_equal = np.array_equal(
        legacy_positive,
        result.positive_counts,
    )

    negative_equal = np.array_equal(
        legacy_negative,
        result.negative_counts,
    )

    positive_differing_cells = np.count_nonzero(
        legacy_positive
        != result.positive_counts
    )

    negative_differing_cells = np.count_nonzero(
        legacy_negative
        != result.negative_counts
    )

    print(
        "\n=== Count equivalence ==="
    )

    print(
        f"Positive counts equal      : "
        f"{positive_equal}"
    )

    print(
        f"Negative counts equal      : "
        f"{negative_equal}"
    )

    print(
        f"Positive differing cells   : "
        f"{positive_differing_cells}"
    )

    print(
        f"Negative differing cells   : "
        f"{negative_differing_cells}"
    )

    delta_max_diff = np.max(
        np.abs(
            legacy_delta
            - result.delta_tec
        )
    )

    delta_equal = np.array_equal(
        legacy_delta,
        result.delta_tec,
    )

    delta_allclose = np.allclose(
        legacy_delta,
        result.delta_tec,
        atol=1e-12,
        rtol=0.0,
    )

    print(
        "\n=== Delta TEC equivalence ==="
    )

    print(
        f"Exact equal     : "
        f"{delta_equal}"
    )

    print(
        f"Allclose 1e-12  : "
        f"{delta_allclose}"
    )

    print(
        f"Max abs diff    : "
        f"{delta_max_diff:.16g}"
    )

    day_zero_index = np.where(
        result.relative_days == 0
    )[0][0]

    print(
        "\n=== Paper-level diagnostics ==="
    )

    print(
        f"Day 0 index          : "
        f"{day_zero_index}"
    )

    print(
        f"Positive total count : "
        f"{np.sum(result.positive_counts)}"
    )

    print(
        f"Negative total count : "
        f"{np.sum(result.negative_counts)}"
    )

    assert result.positive_counts.shape == (
        61,
        24,
    )

    assert result.negative_counts.shape == (
        61,
        24,
    )

    assert result.delta_tec.shape == (
        61,
        24,
        74,
    )

    assert day_zero_index == 30

    assert positive_equal
    assert negative_equal
    assert delta_allclose

    print(
        "\nPASS: earthquake-subset anomaly "
        "results match the legacy implementation."
    )


if __name__ == "__main__":
    main()