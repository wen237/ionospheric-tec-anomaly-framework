"""Validate historical hourly TEC against the legacy Afghanistan dataset.

This script reproduces the fixed-point TEC input used by the historical
statistical analysis and compares the new hourly interpolation workflow
against the legacy interpolated TEC dataset.

The legacy grid-point extraction is intentionally preserved so that this
validation isolates temporal interpolation behavior.
"""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.statistical_clustering.historical_tec import (
    interpolate_hourly_tec,
)


# ==========================================================
# Configuration
# ==========================================================

from validation.statistical_clustering.config import (
    CODE_GIM_DIR,
    LEGACY_TEC_PATH,
)

GIM_DIR = CODE_GIM_DIR

START_TIME = datetime(
    1999, 1, 1, 0
)

END_TIME = datetime(
    2021, 12, 31, 23
)

LATITUDE = 33.092
LONGITUDE = 69.514


# ==========================================================
# Legacy grid definition
# ==========================================================

LATITUDE_INDEX = round(
    (87.5 - LATITUDE) / 2.5
)

LONGITUDE_INDEX = round(
    (LONGITUDE + 180.0) / 5.0
)


def iter_dates(
    start_time: datetime,
    end_time: datetime,
):
    """Yield calendar dates inclusively."""

    current = start_time.date()
    end_date = end_time.date()

    while current <= end_date:

        yield current

        current += timedelta(
            days=1
        )


def get_gim_path(day) -> Path:
    """Return the legacy processed GIM path."""

    year = day.year
    doy = day.timetuple().tm_yday

    return (
        GIM_DIR
        / f"GIMTEC{year}"
        / f"gim{year}{doy:03d}.npz"
    )


def load_historical_fixed_point_tec():
    """Load actual historical GIM epochs and fixed-point TEC."""

    epochs = []
    tec = []

    for day in iter_dates(
        START_TIME,
        END_TIME,
    ):

        path = get_gim_path(day)

        if not path.exists():
            raise FileNotFoundError(
                f"Missing GIM file: {path}"
            )

        with np.load(path) as data:

            gim_tec = data["gim"]
            gim_time = data["gim_time"]

            for z, time_row in enumerate(
                gim_time
            ):

                epoch = datetime(
                    int(time_row[0]),
                    int(time_row[1]),
                    int(time_row[2]),
                    int(time_row[3]),
                )

                value = (
                    gim_tec[
                        LATITUDE_INDEX
                        + z * 71,
                        LONGITUDE_INDEX,
                    ]
                    / 10.0
                )

                epochs.append(
                    epoch
                )

                tec.append(
                    value
                )

    return (
        np.asarray(
            epochs,
            dtype=object,
        ),
        np.asarray(
            tec,
            dtype=np.float64,
        ),
    )


def resolve_duplicate_epochs_last(
    epochs: np.ndarray,
    tec: np.ndarray,
):
    """Resolve duplicate timestamps by retaining the last occurrence.

    Historical daily GIM files may share an endpoint timestamp with the
    following day's file. Retaining the last occurrence reproduces the
    overwrite behavior of the legacy historical TEC assembly workflow.
    """

    if epochs.ndim != 1 or tec.ndim != 1:
        raise ValueError(
            "epochs and tec must be one-dimensional."
        )

    if len(epochs) != len(tec):
        raise ValueError(
            "epochs and tec must have the same length."
        )

    value_by_epoch = {}

    for epoch, value in zip(
        epochs,
        tec,
    ):
        value_by_epoch[epoch] = value

    sorted_epochs = sorted(
        value_by_epoch
    )

    resolved_epochs = np.asarray(
        sorted_epochs,
        dtype=object,
    )

    resolved_tec = np.asarray(
        [
            value_by_epoch[epoch]
            for epoch in sorted_epochs
        ],
        dtype=np.float64,
    )

    return (
        resolved_epochs,
        resolved_tec,
    )


def restrict_to_analysis_interval(
    epochs: np.ndarray,
    tec: np.ndarray,
    start_time: datetime,
    end_time: datetime,
):
    """Restrict observations to the requested analysis interval."""

    mask = np.asarray(
        [
            start_time <= epoch <= end_time
            for epoch in epochs
        ],
        dtype=bool,
    )

    return (
        epochs[mask],
        tec[mask],
    )


def inspect_duplicate_epoch(
    epochs: np.ndarray,
    tec: np.ndarray,
    target_epoch: datetime,
):
    """Print all raw TEC values associated with one timestamp."""

    indices = np.asarray(
        [
            i
            for i, epoch in enumerate(epochs)
            if epoch == target_epoch
        ],
        dtype=int,
    )

    values = tec[indices]

    print(
        f"{target_epoch} | "
        f"count={len(values)} | "
        f"values={values}"
    )


def main():
    """Run historical TEC equivalence validation."""

    print(
        "========================================"
    )
    print(
        "Afghanistan historical TEC equivalence"
    )
    print(
        "========================================"
    )

    # ------------------------------------------------------
    # Load legacy reference
    # ------------------------------------------------------

    legacy_tec = np.load(
        LEGACY_TEC_PATH
    )

    legacy_tec = np.asarray(
        legacy_tec,
        dtype=np.float64,
    ).reshape(-1)

    print(
        f"\nLegacy TEC points : "
        f"{legacy_tec.size}"
    )

    # ------------------------------------------------------
    # Reconstruct historical input
    # ------------------------------------------------------

    raw_epochs, raw_tec = (
        load_historical_fixed_point_tec()
    )

    print(
        f"Raw GIM epochs    : "
        f"{len(raw_epochs)}"
    )

    print(
        "\n=== Duplicate endpoint diagnostic ==="
    )

    targets = [
        datetime(2014, 9, 9, 0),
        datetime(2014, 9, 12, 0),
        datetime(2014, 10, 19, 0),
        datetime(2004, 1, 1, 0),
        datetime(2010, 10, 3, 0),
    ]

    for target in targets:
        inspect_duplicate_epoch(
            epochs=raw_epochs,
            tec=raw_tec,
            target_epoch=target,
        )

    epochs, tec = resolve_duplicate_epochs_last(
        raw_epochs,
        raw_tec,
    )

    print(
        f"Unique GIM epochs : "
        f"{len(epochs)}"
    )

    epochs, tec = (
        restrict_to_analysis_interval(
            epochs=epochs,
            tec=tec,
            start_time=START_TIME,
            end_time=END_TIME,
        )
    )

    print(
        f"Analysis epochs   : "
        f"{len(epochs)}"
    )

    print(
        f"First observation : "
        f"{epochs[0]}"
    )

    print(
        f"Last observation  : "
        f"{epochs[-1]}"
    )

    # ------------------------------------------------------
    # New hourly interpolation
    # ------------------------------------------------------

    result = interpolate_hourly_tec(
        epochs=epochs,
        tec=tec,
        start_time=START_TIME,
        end_time=END_TIME,
    )

    new_tec = result.tec
    new_tec_nan = result.tec.copy()

    new_tec_legacy_boundary = result.tec.copy()
    new_tec_legacy_boundary[0] = legacy_tec[0]

    print(
        f"New hourly points : "
        f"{new_tec.size}"
    )

    print(
        f"Observed points   : "
        f"{np.sum(result.observed_mask)}"
    )

    print(
        f"Interpolated      : "
        f"{np.sum(result.interpolated_mask)}"
    )

    print(
        f"Remaining NaN     : "
        f"{np.sum(~np.isfinite(new_tec))}"
    )

    # ------------------------------------------------------
    # Structural equivalence
    # ------------------------------------------------------

    expected_hours = int(
        (
            END_TIME - START_TIME
        ).total_seconds()
        / 3600
    ) + 1

    if new_tec.size != expected_hours:
        raise AssertionError(
            "Unexpected new hourly TEC length."
        )

    if legacy_tec.size != expected_hours:
        raise AssertionError(
            "Unexpected legacy TEC length."
        )

    # ------------------------------------------------------
    # Numerical comparison
    # ------------------------------------------------------
    comparison_start = 1

    equivalent_after_boundary = np.allclose(
        new_tec[comparison_start:],
        legacy_tec[comparison_start:],
        atol=1e-12,
        rtol=0.0,
        equal_nan=True,
    )

    print(
        f"Equivalent after first boundary: "
        f"{equivalent_after_boundary}"
    )

    difference_after_boundary = np.abs(
        new_tec[1:]
        - legacy_tec[1:]
    )

    print(
        f"Max abs diff after boundary: "
        f"{np.nanmax(difference_after_boundary):.16g}"
    )

    finite = (
        np.isfinite(legacy_tec)
        & np.isfinite(new_tec)
    )

    difference = (
        new_tec[finite]
        - legacy_tec[finite]
    )

    abs_difference = np.abs(
        difference
    )

    print(
        "\n=== Numerical comparison ==="
    )

    print(
        f"Finite comparison : "
        f"{np.sum(finite)}"
    )

    print(
        f"Max abs difference: "
        f"{np.max(abs_difference):.16g}"
    )

    print(
        f"Mean abs diff     : "
        f"{np.mean(abs_difference):.16g}"
    )

    print(
        f"Exact equal       : "
        f"{np.array_equal(new_tec, legacy_tec)}"
    )

    print(
        f"Allclose 1e-12    : "
        f"{np.allclose(new_tec, legacy_tec, atol=1e-12, rtol=0, equal_nan=True)}"
    )

    print(
        f"Equal at 0.1 TECU : "
        f"{np.array_equal(np.round(new_tec, 1), np.round(legacy_tec, 1))}"
    )

    # ------------------------------------------------------
    # Largest differences
    # ------------------------------------------------------

    if len(abs_difference) > 0:

        order = np.argsort(
            abs_difference
        )[::-1]

        print(
            "\n=== Largest differences ==="
        )

        for index in order[:10]:

            original_index = np.flatnonzero(
                finite
            )[index]

            epoch = (
                START_TIME
                + timedelta(
                    hours=int(
                        original_index
                    )
                )
            )

            print(
                f"{epoch} | "
                f"legacy={legacy_tec[original_index]:.12f} | "
                f"new={new_tec[original_index]:.12f} | "
                f"diff={new_tec[original_index] - legacy_tec[original_index]:.12g}"
            )

    # ------------------------------------------------------
    # Boundary diagnostic
    # ------------------------------------------------------

    print(
        "\n=== Boundary diagnostic ==="
    )

    for index in range(6):

        epoch = (
            START_TIME
            + timedelta(
                hours=index
            )
        )

        print(
            f"{epoch} | "
            f"legacy={legacy_tec[index]} | "
            f"new={new_tec[index]}"
        )

    print(
        "\nValidation completed."
    )


if __name__ == "__main__":
    main()