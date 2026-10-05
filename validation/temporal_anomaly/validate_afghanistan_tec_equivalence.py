"""Validate TEC numerical equivalence for the Afghanistan case.

This script compares the legacy 46-day TEC input used in the Afghanistan
case study with the TEC time series produced by the current data-preparation
workflow.

The validation checks temporal structure, source-precision equivalence,
float32 representation, and machine-level numerical differences.
"""

from datetime import timedelta
import numpy as np

from validation.temporal_anomaly.config import (
    LEGACY_TEC_FILE,
    NEW_TEC_FILE,
    START_TIME,
)


# ==========================================================
# Afghanistan case configuration
# ==========================================================

EXPECTED_LENGTH = 1104
SOURCE_PRECISION_DECIMALS = 1


def main() -> None:
    """Run the Afghanistan TEC numerical-equivalence validation."""

    # ======================================================
    # 1. Load legacy TEC
    # ======================================================

    old_tec_matrix = np.load(
        LEGACY_TEC_FILE
    )["tec"]

    assert old_tec_matrix.shape == (
        24,
        46,
    ), (
        "Legacy TEC matrix must have shape (24, 46)."
    )

    old_tec = old_tec_matrix.reshape(
        -1,
        order="F",
    )

    # ======================================================
    # 2. Load current TEC
    # ======================================================

    new_data = np.load(
        NEW_TEC_FILE
    )

    new_tec = np.asarray(
        new_data["tec"],
        dtype=np.float64,
    )

    new_epochs = np.asarray(
        new_data["epochs"]
    ).astype(
        "datetime64[s]"
    )

    # ======================================================
    # 3. Construct expected epochs
    # ======================================================

    expected_epochs = np.asarray(
        [
            START_TIME
            + timedelta(hours=i)
            for i in range(EXPECTED_LENGTH)
        ],
        dtype="datetime64[s]",
    )

    # ======================================================
    # 4. Structural validation
    # ======================================================

    print(
        "========================================"
    )
    print(
        "Afghanistan TEC numerical equivalence"
    )
    print(
        "========================================"
    )

    print(
        "\n=== Structural comparison ==="
    )

    print(
        "Old TEC shape :",
        old_tec.shape,
    )

    print(
        "New TEC shape :",
        new_tec.shape,
    )

    print(
        "Epoch shape   :",
        new_epochs.shape,
    )

    print(
        "First epoch   :",
        new_epochs[0],
    )

    print(
        "Last epoch    :",
        new_epochs[-1],
    )

    assert old_tec.shape == (
        EXPECTED_LENGTH,
    ), (
        "Legacy TEC series has an unexpected length."
    )

    assert new_tec.shape == (
        EXPECTED_LENGTH,
    ), (
        "Current TEC series has an unexpected length."
    )

    epoch_equal = np.array_equal(
        new_epochs,
        expected_epochs,
    )

    print(
        "Epochs equal  :",
        epoch_equal,
    )

    assert epoch_equal, (
        "Current TEC epochs do not match the expected "
        "hourly Afghanistan time range."
    )

    # ======================================================
    # 5. Numerical comparison
    # ======================================================

    difference = np.abs(
        old_tec - new_tec
    )

    finite_difference = difference[
        np.isfinite(difference)
    ]

    if len(finite_difference) > 0:
        max_abs_diff = float(
            np.max(finite_difference)
        )
    else:
        max_abs_diff = np.nan

    exact_equal = np.array_equal(
        old_tec,
        new_tec,
        equal_nan=True,
    )

    float32_equal = np.array_equal(
        old_tec.astype(np.float32),
        new_tec.astype(np.float32),
        equal_nan=True,
    )

    source_precision_equal = np.array_equal(
        np.round(
            old_tec,
            SOURCE_PRECISION_DECIMALS,
        ),
        np.round(
            new_tec,
            SOURCE_PRECISION_DECIMALS,
        ),
        equal_nan=True,
    )

    different_mask = ~np.isclose(
        old_tec,
        new_tec,
        rtol=0.0,
        atol=0.0,
        equal_nan=True,
    )

    number_different = int(
        np.count_nonzero(
            different_mask
        )
    )

    print(
        "\n=== Numerical comparison ==="
    )

    print(
        "Exact floating-point equal :",
        exact_equal,
    )

    print(
        "Float32 representation equal:",
        float32_equal,
    )

    print(
        "Equal at 0.1 TECU          :",
        source_precision_equal,
    )

    print(
        "Max abs diff               :",
        max_abs_diff,
    )

    print(
        "Different values           :",
        number_different,
    )

    print(
        "Max abs diff / 0.1 TECU    :",
        max_abs_diff / 0.1,
    )

    # ======================================================
    # 6. Diagnostics
    # ======================================================

    if number_different > 0:

        indices = np.where(
            different_mask
        )[0]

        print(
            "\n=== First differences ==="
        )

        for index in indices[:10]:

            print(
                f"index={index}, "
                f"epoch={new_epochs[index]}, "
                f"old={old_tec[index]}, "
                f"new={new_tec[index]}, "
                f"diff={difference[index]}"
            )

    # ======================================================
    # 7. Final validation
    # ======================================================

    assert source_precision_equal, (
        "Legacy and current TEC series differ at "
        "the source TEC precision of 0.1 TECU."
    )

    print(
        "\nAfghanistan TEC numerical equivalence: PASS"
    )


if __name__ == "__main__":
    main()