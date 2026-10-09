from datetime import datetime
from pathlib import Path

import numpy as np

from src.spatial_verification.gim_loader import load_spatial_tec
from src.spatial_verification.spatial_anomaly import (
    compute_spatial_anomalies,
)
from src.spatial_verification.spatial_grid import (
    GIM_LATITUDES,
    GIM_LONGITUDES,
    orient_gim_grid,
)


DATASET_DIR = "I:/IRSL/CODEGIM_FIN_py/GIMTEC"

REFERENCE_FILE = (
    Path(__file__).resolve().parent
    / "reference"
    / "afghanistan_spatial_reference.npz"
)


def main():
    # --------------------------------------------------
    # 1. Production GIM loading
    # --------------------------------------------------
    data = load_spatial_tec(
        dataset_dir=DATASET_DIR,
        start_time=datetime(2022, 5, 28, 0),
        end_time=datetime(2022, 6, 1, 23),
        reference_days=15,
    )

    assert data.tec.shape == (480, 5183)
    assert data.window_steps == 120

    print("=== Production Spatial Reproduction ===")
    print("TEC shape       :", data.tec.shape)
    print("Window steps    :", data.window_steps)
    print("Reference days  :", data.reference_days)

    # --------------------------------------------------
    # 2. Production scientific computation
    # --------------------------------------------------
    result = compute_spatial_anomalies(
        tec=data.tec,
        samples_per_day=data.samples_per_day,
        reference_days=data.reference_days,
        window_steps=data.window_steps,
        k=3.0,
        latitudes=GIM_LATITUDES,
        longitudes=GIM_LONGITUDES,
    )

    # --------------------------------------------------
    # 3. Legacy-compatible grid orientation
    # --------------------------------------------------
    matrices = {
        "positive_counts": orient_gim_grid(result.positive_counts),
        "negative_counts": orient_gim_grid(result.negative_counts),
        "positive_ratio": orient_gim_grid(result.positive_ratio),
        "negative_ratio": orient_gim_grid(result.negative_ratio),
    }

    # --------------------------------------------------
    # 4. Frozen reference comparison
    # --------------------------------------------------
    with np.load(REFERENCE_FILE) as reference:
        for name, actual in matrices.items():
            expected = reference[name]

            equal = np.array_equal(
                actual,
                expected,
                equal_nan=True,
            )

            max_diff = np.nanmax(
                np.abs(actual - expected)
            )

            print(
                f"{name:18s} "
                f"equal={equal} "
                f"max_diff={max_diff}"
            )

            np.testing.assert_allclose(
                actual,
                expected,
                rtol=0.0,
                atol=1e-12,
                equal_nan=True,
            )

        np.testing.assert_array_equal(
            result.latitudes,
            reference["latitudes"],
        )

        np.testing.assert_array_equal(
            result.longitudes,
            reference["longitudes"],
        )

        assert (
            result.window_steps
            == int(reference["window_hours"])
        )

    # --------------------------------------------------
    # 5. Afghanistan spatial characteristics
    # --------------------------------------------------
    negative_ratio = matrices["negative_ratio"]
    positive_ratio = matrices["positive_ratio"]

    neg_max = np.nanmax(negative_ratio)
    pos_max = np.nanmax(positive_ratio)

    neg_indices = np.argwhere(
        np.isclose(negative_ratio, neg_max)
    )

    neg_locations = [
        (
            float(GIM_LATITUDES[i]),
            float(GIM_LONGITUDES[j]),
        )
        for i, j in neg_indices
    ]

    print()
    print("Positive maximum :", pos_max, "%")
    print("Negative maximum :", neg_max, "%")
    print("Negative locations:", neg_locations)

    assert np.isclose(pos_max, 10.0)
    assert np.isclose(neg_max, 85.0)
    assert neg_locations == [(30.0, 70.0)]

    print()
    print("Afghanistan production-only spatial reproduction: PASS")


if __name__ == "__main__":
    main()