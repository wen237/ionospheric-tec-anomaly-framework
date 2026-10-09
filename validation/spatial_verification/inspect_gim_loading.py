import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from validation.legacy.spatial_verification.old_spatial_verification import (
    SpatialSearch,
)


DATASET_PATH = [
    "I:/IRSL/CODEGIM_FIN_py/GIMTEC",
    "D:/matlab/MATLAB",
]

START_TIME = [2022, 5, 28, 0, 0, 0]
END_TIME = [2022, 6, 1, 23, 0, 0]

REFERENCE_DAYS = 15


def main():
    spatial = SpatialSearch(
        dataset_path=DATASET_PATH,
        start_time=START_TIME,
        end_time=END_TIME,
        location=[33.020, 69.464],
        magnitude=6.0,
        reference_days=REFERENCE_DAYS,
        k=3.0,
    )

    tec_arr, time_ls, initial_day, total_days = spatial.load_TEC_info()

    clean_tec, clean_time = spatial.rm_redundant_period(
        tec_arr,
        time_ls,
        initial_day,
        total_days,
    )

    first_day = datetime(2022, 5, 28) - timedelta(
        days=REFERENCE_DAYS
    )

    file_name = (
        f"gim{first_day.year}"
        f"{first_day.timetuple().tm_yday:03d}.npz"
    )

    file_path = (
        Path(f"{DATASET_PATH[0]}{first_day.year}")
        / file_name
    )

    print("Inspecting GIM file:", file_path)

    if not file_path.is_file():
        raise FileNotFoundError(
            f"GIM file not found: {file_path}"
        )

    with np.load(file_path) as data:
        print("=== Raw GIM File ===")
        print("File:", file_path)
        print("Keys:", data.files)

        for key in data.files:
            arr = data[key]
            print(
                f"{key}: shape={arr.shape}, "
                f"dtype={arr.dtype}"
            )

        gim = data["gim"]
        gim_time = data["gim_time"]

        print("Raw GIM min/max:", np.nanmin(gim), np.nanmax(gim))
        print("First time values:", gim_time[:5])

    print()
    print("=== Legacy Loading ===")
    print("Initial day:", initial_day)
    print("Total days:", total_days)
    print("TEC shape:", tec_arr.shape)
    print("Clean TEC shape:", clean_tec.shape)
    print("Time entries:", len(time_ls))
    print("Clean time entries:", len(clean_time))

    print()
    print("=== TEC Values ===")
    print("TEC min/max:", np.nanmin(clean_tec), np.nanmax(clean_tec))
    print("NaN count:", np.isnan(clean_tec).sum())
    print("Zero count:", np.sum(clean_tec == 0))
    print("999.9 count:", np.sum(clean_tec == 999.9))

    print()
    print("=== Time Samples ===")
    print("First:", clean_time[:3])
    print("Last:", clean_time[-3:])


if __name__ == "__main__":
    main()