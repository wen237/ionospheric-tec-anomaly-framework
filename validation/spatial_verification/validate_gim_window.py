from datetime import datetime

import numpy as np

from src.spatial_verification.gim_loader import load_spatial_tec


def main():
    data = load_spatial_tec(
        dataset_dir="I:/IRSL/CODEGIM_FIN_py/GIMTEC",
        start_time=datetime(2022, 5, 28, 0),
        end_time=datetime(2022, 6, 1, 23),
        reference_days=15,
    )

    print("=== Production GIM Window Validation ===")
    print("TEC shape       :", data.tec.shape)
    print("Timestamp count :", len(data.timestamps))
    print("Samples/day     :", data.samples_per_day)
    print("Reference days  :", data.reference_days)
    print("Window steps    :", data.window_steps)
    print("First timestamp :", data.timestamps[0])
    print("Last timestamp  :", data.timestamps[-1])
    print("NaN count       :", np.isnan(data.tec).sum())

    assert data.tec.shape == (480, 5183)
    assert len(data.timestamps) == 480
    assert data.samples_per_day == 24
    assert data.reference_days == 15
    assert data.window_steps == 120

    assert data.timestamps[0] == datetime(2022, 5, 13, 0)
    assert data.timestamps[-1] == datetime(2022, 6, 1, 23)

    # Ensure all observations form a continuous hourly sequence.
    from datetime import timedelta

    for previous, current in zip(
        data.timestamps[:-1],
        data.timestamps[1:],
    ):
        assert current - previous == timedelta(hours=1)

    print()
    print("Production GIM window structural validation: PASS")


if __name__ == "__main__":
    main()