from datetime import datetime

import numpy as np

from src.spatial_verification.gim_loader import load_gim_day

from validation.legacy.spatial_verification.old_spatial_verification import (
    SpatialSearch,
)


DATASET_PATH = [
    "I:/IRSL/CODEGIM_FIN_py/GIMTEC",
    "D:/matlab/MATLAB",
]

REFERENCE_DAYS = 15


def main():
    # --------------------------------------------------
    # 1. Legacy loading
    # --------------------------------------------------
    spatial = SpatialSearch(
        dataset_path=DATASET_PATH,
        start_time=[2022, 5, 28, 0, 0, 0],
        end_time=[2022, 6, 1, 23, 0, 0],
        location=[33.020, 69.464],
        magnitude=6.0,
        reference_days=REFERENCE_DAYS,
        k=3.0,
    )

    tec_arr, time_ls, initial_day, total_days = (
        spatial.load_TEC_info()
    )

    legacy_tec, legacy_time = spatial.rm_redundant_period(
        tec_arr,
        time_ls,
        initial_day,
        total_days,
    )

    # The first 24 observations correspond to 2022-05-13.
    legacy_day = legacy_tec[:24]

    # --------------------------------------------------
    # 2. Production loading
    # --------------------------------------------------
    production_day, timestamps = load_gim_day(
        dataset_dir=DATASET_PATH[0],
        day=datetime(2022, 5, 13),
        samples_per_day=24,
    )

    # --------------------------------------------------
    # 3. Structural checks
    # --------------------------------------------------
    assert legacy_day.shape == (24, 5183)
    assert production_day.shape == (24, 5183)
    assert len(timestamps) == 24

    # --------------------------------------------------
    # 4. Numerical equivalence
    # --------------------------------------------------
    equal = np.array_equal(
        production_day,
        legacy_day,
        equal_nan=True,
    )

    difference = np.abs(production_day - legacy_day)

    print("=== Single-Day GIM Numerical Equivalence ===")
    print("Legacy shape       :", legacy_day.shape)
    print("Production shape   :", production_day.shape)
    print("Legacy NaN count   :", np.isnan(legacy_day).sum())
    print("Production NaN count:", np.isnan(production_day).sum())
    print("Equal (NaN-aware)  :", equal)
    print("Max absolute diff  :", np.nanmax(difference))

    np.testing.assert_allclose(
        production_day,
        legacy_day,
        rtol=0.0,
        atol=0.0,
        equal_nan=True,
    )

    # --------------------------------------------------
    # 5. Timestamp equivalence
    # --------------------------------------------------
    legacy_day_time = legacy_time[0]

    expected_timestamps = tuple(
        datetime(*map(int, row))
        for row in legacy_day_time
    )

    assert timestamps == expected_timestamps

    print("Timestamp equivalence: PASS")
    print("Single-day GIM numerical equivalence: PASS")


if __name__ == "__main__":
    main()