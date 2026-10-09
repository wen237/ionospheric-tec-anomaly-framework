import numpy as np
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

LOCATION = [33.020, 69.464]
MAGNITUDE = 6.0

REFERENCE_DAYS = 15
K = 3.0

EXPECTED_HOURS = 120

EXPECTED_POS_MAX = 10.0
EXPECTED_NEG_MAX = 85.0

EXPECTED_POS_MAX_LOCATIONS = {
    (-22.5, -155.0),
    (-22.5, -150.0),
}

EXPECTED_NEG_MAX_LOCATIONS = {
    (30.0, 70.0),
}


def get_max_locations(ratio, latitudes, longitudes):
    max_value = np.nanmax(ratio)
    indices = np.argwhere(ratio == max_value)

    return {
        (float(latitudes[row]), float(longitudes[col]))
        for row, col in indices
    }


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

    pos_arr, neg_arr, specified_time = spatial.process_Pos_Neg_arr(
        clean_tec,
        clean_time,
        total_days,
    )

    total_hours = sum(
        item.shape[0]
        for item in specified_time[REFERENCE_DAYS:]
    )

    pos_ratio = pos_arr / total_hours * 100
    neg_ratio = neg_arr / total_hours * 100

    latitudes = np.linspace(-87.5, 87.5, 71)
    longitudes = np.linspace(-180.0, 180.0, 73)

    pos_locations = get_max_locations(
        pos_ratio,
        latitudes,
        longitudes,
    )

    neg_locations = get_max_locations(
        neg_ratio,
        latitudes,
        longitudes,
    )

    print("=== Afghanistan Spatial Legacy Reproduction ===")
    print(f"Window hours       : {total_hours}")
    print(f"Matrix shape       : {pos_ratio.shape}")
    print(f"Finite grid points : {np.isfinite(pos_ratio).sum()}")
    print()
    print(f"Positive maximum   : {np.nanmax(pos_ratio)} %")
    print(f"Positive locations : {sorted(pos_locations)}")
    print()
    print(f"Negative maximum   : {np.nanmax(neg_ratio)} %")
    print(f"Negative locations : {sorted(neg_locations)}")

    assert total_hours == EXPECTED_HOURS

    assert pos_ratio.shape == (71, 73)
    assert neg_ratio.shape == (71, 73)

    assert np.isfinite(pos_ratio).sum() == 5183
    assert np.isfinite(neg_ratio).sum() == 5183

    assert np.isclose(
        np.nanmax(pos_ratio),
        EXPECTED_POS_MAX,
    )
    assert np.isclose(
        np.nanmax(neg_ratio),
        EXPECTED_NEG_MAX,
    )

    assert pos_locations == EXPECTED_POS_MAX_LOCATIONS
    assert neg_locations == EXPECTED_NEG_MAX_LOCATIONS

    print()
    print("Afghanistan spatial legacy reproduction: PASS")


    reference_dir = Path(__file__).resolve().parent / "reference"
    reference_dir.mkdir(exist_ok=True)

    reference_file = reference_dir / "afghanistan_spatial_reference.npz"

    # np.savez(
    #     reference_file,
    #     positive_counts=pos_arr,
    #     negative_counts=neg_arr,
    #     positive_ratio=pos_ratio,
    #     negative_ratio=neg_ratio,
    #     latitudes=latitudes,
    #     longitudes=longitudes,
    #     window_hours=np.array(total_hours),
    # )

    # print(f"Reference saved to : {reference_file}")


if __name__ == "__main__":
    main()