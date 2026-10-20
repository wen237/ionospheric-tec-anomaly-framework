"""Integration tests: real Framework A extraction, synthetic daily NPZ inputs."""
from datetime import datetime, timedelta

import numpy as np
import pytest

from src.workflow.modern_temporal_input_adapter import load_temporal_tec_from_modern_gim


def make_day(path, day, *, boundary=8888.0, zero=False):
    epochs = np.array([np.datetime64(day + timedelta(hours=h), 's') for h in range(25)])
    lat = np.linspace(-87.5, 87.5, 71)
    lon = np.linspace(-180, 180, 73)
    tec = np.full((25, 71, 73), 5.0, dtype=float)
    tec[:24, 35, 36] = np.arange(24) + (day.day * 100)
    if zero:
        tec[1, 35, 36] = np.nan
    tec[24] = boundary  # poison the forbidden 25th map
    np.savez_compressed(path, tec=tec, epochs=epochs, lat=lat, lon=lon,
                        height=np.full((25, 71), 450.0), exponent=-1,
                        source_file=path.name)
    return path


def test_uses_next_days_own_midnight(tmp_path):
    d1 = make_day(tmp_path/'day1.npz', datetime(2022, 1, 1))
    d2 = make_day(tmp_path/'day2.npz', datetime(2022, 1, 2))
    result = load_temporal_tec_from_modern_gim(
        [d2, d1], datetime(2022, 1, 2), datetime(2022, 1, 2, 2),
        latitude=0, longitude=0, reference_days=1)
    assert result.tec.shape == (27,)
    assert result.tec[23] == 123
    assert result.tec[24] == 200  # not Day 1's poison boundary map
    assert result.tec[25] == 201
    assert result.epochs[24] == datetime(2022, 1, 2)
    assert result.grid_latitude == 0 and result.grid_longitude == 0


def test_nan_preserved(tmp_path):
    d1 = make_day(tmp_path/'day1.npz', datetime(2022, 1, 1), zero=True)
    d2 = make_day(tmp_path/'day2.npz', datetime(2022, 1, 2))
    result = load_temporal_tec_from_modern_gim(
        [d1, d2], datetime(2022, 1, 2), datetime(2022, 1, 2),
        latitude=0, longitude=0, reference_days=1)
    assert np.isnan(result.tec[1])


def test_missing_day_rejected(tmp_path):
    d1 = make_day(tmp_path/'day1.npz', datetime(2022, 1, 1))
    d3 = make_day(tmp_path/'day3.npz', datetime(2022, 1, 3))
    with pytest.raises(ValueError):
        load_temporal_tec_from_modern_gim(
            [d1, d3], datetime(2022, 1, 3), datetime(2022, 1, 3),
            latitude=0, longitude=0, reference_days=1)


def test_nearest_grid_and_no_rescaling(tmp_path):
    d1 = make_day(tmp_path/'day1.npz', datetime(2022, 1, 1))
    d2 = make_day(tmp_path/'day2.npz', datetime(2022, 1, 2))
    result = load_temporal_tec_from_modern_gim(
        [d1, d2], datetime(2022, 1, 2), datetime(2022, 1, 2),
        latitude=0.4, longitude=0.4, reference_days=1)
    assert result.tec[0] == 100
    assert result.tec[24] == 200
    assert result.latitude_index == 35 and result.longitude_index == 36
