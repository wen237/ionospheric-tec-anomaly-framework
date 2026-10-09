from datetime import datetime

import numpy as np

from src.spatial_verification.gim_loader import load_gim_day


def main():
    tec, timestamps = load_gim_day(
        dataset_dir="I:/IRSL/CODEGIM_FIN_py/GIMTEC",
        day=datetime(2022, 5, 13),
        samples_per_day=24,
    )

    print("=== Production GIM Day Validation ===")
    print("TEC shape      :", tec.shape)
    print("Timestamp count:", len(timestamps))
    print("First timestamp:", timestamps[0])
    print("Last timestamp :", timestamps[-1])
    print("TEC min/max   :", np.nanmin(tec), np.nanmax(tec))
    print("NaN count     :", np.isnan(tec).sum())

    assert tec.shape == (24, 5183)
    assert len(timestamps) == 24

    assert timestamps[0] == datetime(2022, 5, 13, 0)
    assert timestamps[-1] == datetime(2022, 5, 13, 23)

    print()
    print("Production GIM day structural validation: PASS")


if __name__ == "__main__":
    main()