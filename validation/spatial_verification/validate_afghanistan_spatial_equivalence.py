import numpy as np

from src.spatial_verification.spatial_anomaly import (
    compute_spatial_anomalies,
)
from validation.legacy.spatial_verification.old_spatial_verification import (
    SpatialSearch,
)
from src.spatial_verification.spatial_grid import orient_gim_grid


DATASET_PATH = [
    "I:/IRSL/CODEGIM_FIN_py/GIMTEC",
    "D:/matlab/MATLAB",
]

START_TIME = [2022, 5, 28, 0, 0, 0]
END_TIME = [2022, 6, 1, 23, 0, 0]

LOCATION = [33.020, 69.464]
MAGNITUDE = 6.0

REFERENCE_DAYS = 15
K = 3.0

SAMPLES_PER_DAY = 24
WINDOW_STEPS = 120

LATITUDES = np.linspace(-87.5, 87.5, 71)
LONGITUDES = np.linspace(-180.0, 180.0, 73)


def compare(name, current, reference):
    difference = np.abs(current - reference)

    print(
        f"{name:<18} "
        f"equal={np.array_equal(current, reference)}, "
        f"allclose={np.allclose(current, reference, equal_nan=True)}, "
        f"max_abs_diff={np.nanmax(difference)}"
    )

    np.testing.assert_allclose(
        current,
        reference,
        rtol=0.0,
        atol=1e-12,
        equal_nan=True,
    )


def main():
    spatial = SpatialSearch(
        dataset_path=DATASET_PATH,
        start_time=START_TIME,
        end_time=END_TIME,
        location=LOCATION,
        magnitude=MAGNITUDE,
        reference_days=REFERENCE_DAYS,
        k=K,
    )

    tec_arr, time_ls, initial_day, total_days = spatial.load_TEC_info()

    clean_tec, clean_time = spatial.rm_redundant_period(
        tec_arr,
        time_ls,
        initial_day,
        total_days,
    )

    reference_steps = REFERENCE_DAYS * SAMPLES_PER_DAY

    production_tec = clean_tec[
        :reference_steps + WINDOW_STEPS
    ]

    result = compute_spatial_anomalies(
        tec=production_tec,
        samples_per_day=SAMPLES_PER_DAY,
        reference_days=REFERENCE_DAYS,
        window_steps=WINDOW_STEPS,
        k=K,
        latitudes=LATITUDES,
        longitudes=LONGITUDES,
    )

    reference = np.load(
        "validation/spatial_verification/reference/"
        "afghanistan_spatial_reference.npz"
    )

    production_positive_counts = orient_gim_grid(
        result.positive_counts
    )
    production_negative_counts = orient_gim_grid(
        result.negative_counts
    )
    production_positive_ratio = orient_gim_grid(
        result.positive_ratio
    )
    production_negative_ratio = orient_gim_grid(
        result.negative_ratio
    )

    compare(
        "Positive counts",
        production_positive_counts,
        reference["positive_counts"],
    )

    compare(
        "Negative counts",
        production_negative_counts,
        reference["negative_counts"],
    )

    compare(
        "Positive ratio",
        production_positive_ratio,
        reference["positive_ratio"],
    )

    compare(
        "Negative ratio",
        production_negative_ratio,
        reference["negative_ratio"],
    )

    np.testing.assert_array_equal(
        result.latitudes,
        reference["latitudes"],
    )

    np.testing.assert_array_equal(
        result.longitudes,
        reference["longitudes"],
    )

    assert result.window_steps == reference["window_hours"].item()

    print()
    print(
        f"Positive maximum   : "
        f"{np.nanmax(production_positive_ratio)} %"
    )

    print(
        f"Negative maximum   : "
        f"{np.nanmax(production_negative_ratio)} %"
    )

    np.testing.assert_array_equal(
        result.latitudes,
        reference["latitudes"],
    )

    np.testing.assert_array_equal(
        result.longitudes,
        reference["longitudes"],
    )

    assert result.window_steps == reference["window_hours"].item()

    print()
    print("Afghanistan spatial numerical equivalence: PASS")


if __name__ == "__main__":
    main()