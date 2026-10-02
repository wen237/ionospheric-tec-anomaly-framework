"""Validate Afghanistan earthquake sample selection against legacy logic."""

from datetime import date, timedelta

import numpy as np

from src.statistical_clustering.earthquake_samples import (
    select_earthquake_samples,
)


# ==========================================================
# Configuration
# ==========================================================

from validation.statistical_clustering.config import EQLIST_PATH

ANALYSIS_START = date(
    1999, 1, 1
)

ANALYSIS_END = date(
    2021, 12, 31
)

MINIMUM_MAGNITUDE = 6.0
OBSERVATION_DAYS = 30
REFERENCE_DAYS = 15


def legacy_filter_eq(
    eqlist: np.ndarray,
):
    """Reproduce the earthquake filtering logic of legacy OneSampleTest."""

    eqlist = np.asarray(
        eqlist
    )

    # Legacy earthquake date representation.
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

    # IMPORTANT:
    # Replace this column only if inspection of the actual eqlist shows
    # that magnitude is stored elsewhere.
    magnitudes = np.asarray(
        eqlist[:, -1],
        dtype=np.float64,
    )

    earliest_date = (
        ANALYSIS_START
        + timedelta(
            days=(
                OBSERVATION_DAYS
                + REFERENCE_DAYS
            )
        )
    )

    latest_date = (
        ANALYSIS_END
        - timedelta(
            days=OBSERVATION_DAYS
        )
    )

    mask = np.asarray(
        [
            (
                magnitude >= MINIMUM_MAGNITUDE
                and event_date >= earliest_date
                and event_date <= latest_date
            )
            for event_date, magnitude
            in zip(
                event_dates,
                magnitudes,
            )
        ],
        dtype=bool,
    )

    return (
        event_dates,
        magnitudes,
        mask,
    )


def main():
    """Run earthquake sample equivalence validation."""

    print(
        "========================================"
    )
    print(
        "Afghanistan earthquake sample equivalence"
    )
    print(
        "========================================"
    )

    eqlist = np.load(
        EQLIST_PATH,
        allow_pickle=True,
    )

    print(
        f"\nRaw eqlist shape : {eqlist.shape}"
    )

    print(
        f"Raw events       : {len(eqlist)}"
    )

    print(
        "\nFirst five rows:"
    )

    for row in eqlist[:5]:
        print(row)

    # ------------------------------------------------------
    # Legacy selection
    # ------------------------------------------------------

    (
        event_dates,
        magnitudes,
        legacy_mask,
    ) = legacy_filter_eq(
        eqlist
    )

    legacy_dates = event_dates[
        legacy_mask
    ]

    legacy_magnitudes = magnitudes[
        legacy_mask
    ]

    # ------------------------------------------------------
    # New selection
    # ------------------------------------------------------

    result = select_earthquake_samples(
        event_dates=event_dates,
        magnitudes=magnitudes,
        analysis_start=ANALYSIS_START,
        analysis_end=ANALYSIS_END,
        minimum_magnitude=MINIMUM_MAGNITUDE,
        observation_days=OBSERVATION_DAYS,
        reference_days=REFERENCE_DAYS,
    )

    # ------------------------------------------------------
    # Comparison
    # ------------------------------------------------------

    print(
        "\n=== Selection summary ==="
    )

    print(
        f"Legacy selected : "
        f"{len(legacy_dates)}"
    )

    print(
        f"New selected    : "
        f"{len(result.selected_dates)}"
    )

    print(
        "\n=== Equivalence ==="
    )

    mask_equal = np.array_equal(
        legacy_mask,
        result.selected_mask,
    )

    dates_equal = np.array_equal(
        legacy_dates,
        result.selected_dates,
    )

    magnitudes_equal = np.array_equal(
        legacy_magnitudes,
        result.selected_magnitudes,
    )

    print(
        f"Selection mask equal : {mask_equal}"
    )

    print(
        f"Selected dates equal : {dates_equal}"
    )

    print(
        f"Magnitudes equal     : {magnitudes_equal}"
    )

    # ------------------------------------------------------
    # Diagnostics if anything differs
    # ------------------------------------------------------

    differing_indices = np.flatnonzero(
        legacy_mask
        != result.selected_mask
    )

    print(
        f"Differing decisions  : "
        f"{len(differing_indices)}"
    )

    if len(differing_indices) > 0:

        print(
            "\n=== Differing events ==="
        )

        for index in differing_indices[:20]:

            print(
                f"index={index} | "
                f"date={event_dates[index]} | "
                f"M={magnitudes[index]} | "
                f"legacy={legacy_mask[index]} | "
                f"new={result.selected_mask[index]}"
            )

    # ------------------------------------------------------
    # Final assertion
    # ------------------------------------------------------

    assert mask_equal
    assert dates_equal
    assert magnitudes_equal

    print(
        "\nPASS: earthquake sample selection "
        "matches the legacy logic."
    )


if __name__ == "__main__":
    main()