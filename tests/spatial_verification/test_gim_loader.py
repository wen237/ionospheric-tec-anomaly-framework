from datetime import datetime, timedelta

import numpy as np
import pytest

from src.spatial_verification.gim_loader import (
    load_gim_day,
    load_spatial_tec,
)


def create_synthetic_gim(
    tmp_path,
    day,
    *,
    samples_per_day=24,
):
    """Create a synthetic daily GIM file."""

    year = day.year
    doy = day.timetuple().tm_yday

    directory = tmp_path / f"GIMTEC{year}"
    directory.mkdir(parents=True, exist_ok=True)

    file_path = directory / f"gim{year}{doy:03d}.npz"

    # Include one extra epoch, matching the observed GIM format.
    n_epochs = samples_per_day + 1

    gim = np.full(
        (n_epochs * 71, 73),
        100,
        dtype=np.int32,
    )

    # Different values for the first two epochs.
    gim[:71] = 200
    gim[71:142] = 300

    # Missing-value example.
    gim[0, 0] = 0

    # Extra epoch must be ignored.
    gim[samples_per_day * 71:] = 9990

    gim_time = np.array(
        [
            [
                day.year,
                day.month,
                day.day,
                hour,
                0,
                0,
            ]
            for hour in range(samples_per_day)
        ],
        dtype=np.int32,
    )

    # The final extra timestamp belongs to the next day.
    from datetime import timedelta

    next_day = day + timedelta(days=1)

    gim_time = np.vstack(
        [
            gim_time,
            [
                next_day.year,
                next_day.month,
                next_day.day,
                0,
                0,
                0,
            ],
        ]
    )

    np.savez(
        file_path,
        gim=gim,
        gim_time=gim_time,
        gim_lat=np.linspace(-87.5, 87.5, 71),
        gim_lon=np.linspace(-180, 180, 73),
    )

    return file_path


def test_load_gim_day_shape_and_timestamps(tmp_path):
    day = datetime(2022, 5, 13)

    create_synthetic_gim(tmp_path, day)

    tec, timestamps = load_gim_day(
        dataset_dir=tmp_path / "GIMTEC",
        day=day,
    )

    assert tec.shape == (24, 5183)
    assert len(timestamps) == 24

    assert timestamps[0] == datetime(2022, 5, 13, 0)
    assert timestamps[-1] == datetime(2022, 5, 13, 23)


def test_load_gim_day_scaling_and_missing_values(tmp_path):
    day = datetime(2022, 5, 13)

    create_synthetic_gim(tmp_path, day)

    tec, _ = load_gim_day(
        dataset_dir=tmp_path / "GIMTEC",
        day=day,
    )

    assert np.isnan(tec[0, 0])
    assert tec[0, 1] == 20.0
    assert tec[1, 0] == 30.0
    assert tec[2, 0] == 10.0


def test_load_gim_day_ignores_extra_epoch(tmp_path):
    day = datetime(2022, 5, 13)

    create_synthetic_gim(tmp_path, day)

    tec, timestamps = load_gim_day(
        dataset_dir=tmp_path / "GIMTEC",
        day=day,
    )

    assert tec.shape[0] == 24
    assert len(timestamps) == 24

    # Extra epoch contains 9990 -> 999.0 after scaling.
    # It must not appear in the returned TEC data.
    assert not np.any(tec == 999.0)


def test_load_gim_day_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_gim_day(
            dataset_dir=tmp_path / "GIMTEC",
            day=datetime(2022, 5, 13),
        )


def test_load_gim_day_invalid_shape(tmp_path):
    day = datetime(2022, 5, 13)

    file_path = create_synthetic_gim(tmp_path, day)

    with np.load(file_path) as data:
        gim_time = data["gim_time"]

    np.savez(
        file_path,
        gim=np.zeros((100, 73), dtype=np.int32),
        gim_time=gim_time,
    )

    with pytest.raises(ValueError):
        load_gim_day(
            dataset_dir=tmp_path / "GIMTEC",
            day=day,
        )


def test_load_spatial_tec_midnight_window(tmp_path):
    start = datetime(2022, 5, 28, 0)
    end = datetime(2022, 5, 29, 23)

    for offset in range(17):
        create_synthetic_gim(
            tmp_path,
            datetime(2022, 5, 13) + timedelta(days=offset),
        )

    data = load_spatial_tec(
        dataset_dir=tmp_path / "GIMTEC",
        start_time=start,
        end_time=end,
        reference_days=15,
    )

    assert data.tec.shape == (17 * 24, 5183)
    assert len(data.timestamps) == 17 * 24
    assert data.window_steps == 48

    assert data.timestamps[0] == datetime(2022, 5, 13)
    assert data.timestamps[-1] == end


def test_load_spatial_tec_non_midnight_window(tmp_path):
    start = datetime(2022, 5, 28, 6)
    end = datetime(2022, 5, 29, 5)

    for offset in range(17):
        create_synthetic_gim(
            tmp_path,
            datetime(2022, 5, 13) + timedelta(days=offset),
        )

    data = load_spatial_tec(
        dataset_dir=tmp_path / "GIMTEC",
        start_time=start,
        end_time=end,
        reference_days=15,
    )

    assert data.tec.shape == (16 * 24, 5183)
    assert len(data.timestamps) == 16 * 24
    assert data.window_steps == 24

    assert data.timestamps[0] == datetime(2022, 5, 13, 6)
    assert data.timestamps[-1] == end

    for previous, current in zip(
        data.timestamps[:-1],
        data.timestamps[1:],
    ):
        assert current - previous == timedelta(hours=1)


def test_load_spatial_tec_cross_year(tmp_path):
    start = datetime(2023, 1, 2, 0)
    end = datetime(2023, 1, 2, 23)

    for offset in range(4):
        create_synthetic_gim(
            tmp_path,
            datetime(2022, 12, 30) + timedelta(days=offset),
        )

    data = load_spatial_tec(
        dataset_dir=tmp_path / "GIMTEC",
        start_time=start,
        end_time=end,
        reference_days=3,
    )

    assert data.tec.shape == (4 * 24, 5183)
    assert len(data.timestamps) == 4 * 24
    assert data.window_steps == 24

    assert data.timestamps[0] == datetime(2022, 12, 30)
    assert data.timestamps[-1] == end


def test_load_spatial_tec_missing_day(tmp_path):
    start = datetime(2022, 5, 28)
    end = datetime(2022, 5, 28, 23)

    # Deliberately omit one reference day.
    for offset in range(16):
        if offset == 5:
            continue

        create_synthetic_gim(
            tmp_path,
            datetime(2022, 5, 13) + timedelta(days=offset),
        )

    with pytest.raises(FileNotFoundError):
        load_spatial_tec(
            dataset_dir=tmp_path / "GIMTEC",
            start_time=start,
            end_time=end,
            reference_days=15,
        )


def test_load_spatial_tec_reference_alignment(tmp_path):
    start = datetime(2022, 5, 28, 6)
    end = datetime(2022, 5, 29, 5)
    reference_days = 3

    first_day = datetime(2022, 5, 25)

    # Create five daily files with unique values per epoch.
    for offset in range(5):
        day = first_day + timedelta(days=offset)

        file_path = create_synthetic_gim(tmp_path, day)

        with np.load(file_path) as data:
            gim = data["gim"].copy()
            gim_time = data["gim_time"].copy()
            gim_lat = data["gim_lat"].copy()
            gim_lon = data["gim_lon"].copy()

        # Encode the day and hour into the TEC values.
        for hour in range(24):
            value = (offset * 24 + hour + 1) * 10
            gim[hour * 71:(hour + 1) * 71] = value

        np.savez(
            file_path,
            gim=gim,
            gim_time=gim_time,
            gim_lat=gim_lat,
            gim_lon=gim_lon,
        )

    data = load_spatial_tec(
        dataset_dir=tmp_path / "GIMTEC",
        start_time=start,
        end_time=end,
        reference_days=reference_days,
    )

    assert data.tec.shape == (96, 5183)
    assert data.window_steps == 24

    # Check the reference start and target start.
    assert data.timestamps[0] == datetime(2022, 5, 25, 6)
    assert data.timestamps[72] == start

    # Verify values at one grid point.
    assert data.tec[0, 0] == 7.0
    assert data.tec[24, 0] == 31.0
    assert data.tec[48, 0] == 55.0
    assert data.tec[72, 0] == 79.0

    # Every 24-step shift must represent the same UT hour
    # on the next calendar day.
    for target_step in range(data.window_steps):
        target_index = reference_days * 24 + target_step
        target_timestamp = data.timestamps[target_index]

        for reference_day in range(reference_days):
            reference_index = reference_day * 24 + target_step
            reference_timestamp = data.timestamps[reference_index]

            assert (
                target_timestamp - reference_timestamp
                == timedelta(days=reference_days - reference_day)
            )


@pytest.mark.parametrize(
    "invalid_index, invalid_hour",
    [
        (2, 1),    # Duplicate timestamp: 01:00
        (5, 7),    # Missing expected 05:00
        (23, 22),  # Duplicate final timestamp
    ],
)
def test_load_gim_day_rejects_invalid_hour_sequence(
    tmp_path,
    invalid_index,
    invalid_hour,
):
    day = datetime(2022, 5, 13)

    file_path = create_synthetic_gim(tmp_path, day)

    with np.load(file_path) as data:
        gim = data["gim"].copy()
        gim_time = data["gim_time"].copy()
        gim_lat = data["gim_lat"].copy()
        gim_lon = data["gim_lon"].copy()

    gim_time[invalid_index, 3] = invalid_hour

    np.savez(
        file_path,
        gim=gim,
        gim_time=gim_time,
        gim_lat=gim_lat,
        gim_lon=gim_lon,
    )

    with pytest.raises(
        ValueError,
        match="GIM timestamp",
    ):
        load_gim_day(
            dataset_dir=tmp_path / "GIMTEC",
            day=day,
        )


def test_load_gim_day_rejects_wrong_date(tmp_path):
    day = datetime(2022, 5, 13)

    file_path = create_synthetic_gim(tmp_path, day)

    with np.load(file_path) as data:
        gim = data["gim"].copy()
        gim_time = data["gim_time"].copy()
        gim_lat = data["gim_lat"].copy()
        gim_lon = data["gim_lon"].copy()

    # Change the date of the first observation.
    gim_time[0, 2] = 12

    np.savez(
        file_path,
        gim=gim,
        gim_time=gim_time,
        gim_lat=gim_lat,
        gim_lon=gim_lon,
    )

    with pytest.raises(
        ValueError,
        match="GIM timestamp",
    ):
        load_gim_day(
            dataset_dir=tmp_path / "GIMTEC",
            day=day,
        )


def test_load_gim_day_rejects_invalid_timestamp_shape(tmp_path):
    day = datetime(2022, 5, 13)

    file_path = create_synthetic_gim(tmp_path, day)

    with np.load(file_path) as data:
        gim = data["gim"].copy()

    # Incorrect number of datetime components.
    invalid_time = np.zeros((25, 5), dtype=np.int32)

    np.savez(
        file_path,
        gim=gim,
        gim_time=invalid_time,
    )

    with pytest.raises(
        ValueError,
        match="GIM timestamp",
    ):
        load_gim_day(
            dataset_dir=tmp_path / "GIMTEC",
            day=day,
        )