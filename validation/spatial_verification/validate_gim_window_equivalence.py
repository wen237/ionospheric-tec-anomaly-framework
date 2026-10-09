from datetime import datetime

import numpy as np

from src.spatial_verification.gim_loader import load_spatial_tec

from validation.legacy.spatial_verification.old_spatial_verification import (
    SpatialSearch,
)


DATASET_PATH = [
    "I:/IRSL/CODEGIM_FIN_py/GIMTEC",
    "D:/matlab/MATLAB",
]


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
        reference_days=15,
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

    # --------------------------------------------------
    # 2. Production loading
    # --------------------------------------------------
    production = load_spatial_tec(
        dataset_dir=DATASET_PATH[0],
        start_time=datetime(2022, 5, 28, 0),
        end_time=datetime(2022, 6, 1, 23),
        reference_days=15,
    )

    # --------------------------------------------------
    # 3. Full-matrix numerical equivalence
    # --------------------------------------------------
    assert production.tec.shape == legacy_tec.shape

    equal = np.array_equal(
        production.tec,
        legacy_tec,
        equal_nan=True,
    )

    difference = np.abs(production.tec - legacy_tec)

    print("=== Afghanistan Full-Window TEC Equivalence ===")
    print("Legacy shape        :", legacy_tec.shape)
    print("Production shape    :", production.tec.shape)
    print("Total TEC values    :", production.tec.size)
    print("Legacy NaN count    :", np.isnan(legacy_tec).sum())
    print("Production NaN count:", np.isnan(production.tec).sum())
    print("Equal (NaN-aware)   :", equal)
    print("Max absolute diff   :", np.nanmax(difference))

    np.testing.assert_allclose(
        production.tec,
        legacy_tec,
        rtol=0.0,
        atol=0.0,
        equal_nan=True,
    )

    # --------------------------------------------------
    # 4. Timestamp equivalence
    # --------------------------------------------------
    legacy_timestamps = tuple(
        datetime(*map(int, row))
        for day_times in legacy_time
        for row in day_times
    )

    assert len(production.timestamps) == len(legacy_timestamps)
    assert production.timestamps == legacy_timestamps

    print("Timestamp equivalence: PASS")
    print("Afghanistan full-window TEC equivalence: PASS")


if __name__ == "__main__":
    main()