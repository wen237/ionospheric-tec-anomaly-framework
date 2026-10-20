from datetime import date, datetime, timedelta

import numpy as np
import pytest

from src.workflow.modern_historical_input_adapter import load_historical_daily_tec_from_modern_gim


def day_file(path, day, *, descending=False, nan_hour=None):
    epochs = np.array([np.datetime64(day + timedelta(hours=h), 's') for h in range(25)])
    lat = np.linspace(-87.5, 87.5, 71)
    lon = np.linspace(-180, 180, 73)
    tec = np.full((25, 71, 73), 4.0)
    tec[:24, 35, 36] = day.day * 100 + np.arange(24)
    tec[24] = 7777.0  # forbidden boundary map
    if nan_hour is not None:
        tec[nan_hour, 35, 36] = np.nan
    if descending:
        lat = lat[::-1]
        tec = tec[:, ::-1, :]
    np.savez_compressed(path, tec=tec, epochs=epochs, lat=lat, lon=lon, source_file=path.name)
    return path


def load(paths, start, end):
    return load_historical_daily_tec_from_modern_gim(
        paths, start_date=start, end_date=end, latitude=0.2, longitude=0.2)


def test_two_days_own_midnight_and_no_25th(tmp_path):
    a = day_file(tmp_path/'a.npz', datetime(2022, 1, 1))
    b = day_file(tmp_path/'b.npz', datetime(2022, 1, 2))
    r = load([b, a], date(2022, 1, 1), date(2022, 1, 2))
    assert r.daily_tec.shape == (2, 24)
    assert r.daily_tec[0, -1] == 123
    assert r.daily_tec[1, 0] == 200
    assert r.daily_tec[1, -1] == 223
    assert not np.any(r.daily_tec == 7777)
    assert r.n_days == 2
    assert not r.hourly_result.interpolated_mask.any()


def test_subrange_and_latitude_orientation(tmp_path):
    a = day_file(tmp_path/'a.npz', datetime(2022, 1, 1))
    b = day_file(tmp_path/'b.npz', datetime(2022, 1, 2), descending=True)
    c = day_file(tmp_path/'c.npz', datetime(2022, 1, 3))
    r = load([c, a, b], date(2022, 1, 2), date(2022, 1, 2))
    assert r.daily_tec.shape == (1, 24)
    np.testing.assert_array_equal(r.daily_tec[0], 200 + np.arange(24))


def test_nan_rejected_without_interpolation(tmp_path):
    a = day_file(tmp_path/'a.npz', datetime(2022, 1, 1), nan_hour=5)
    with pytest.raises(ValueError, match='NaN'):
        load([a], date(2022, 1, 1), date(2022, 1, 1))


def test_missing_requested_day_rejected(tmp_path):
    a = day_file(tmp_path/'a.npz', datetime(2022, 1, 1))
    with pytest.raises(ValueError, match='cover'):
        load([a], date(2022, 1, 1), date(2022, 1, 2))


def test_invalid_date_range_rejected(tmp_path):
    with pytest.raises(ValueError, match='start_date'):
        load([], date(2022, 1, 2), date(2022, 1, 1))


def test_datetime_not_accepted_as_calendar_date(tmp_path):
    with pytest.raises(TypeError, match='start_date'):
        load([], datetime(2022, 1, 1), date(2022, 1, 2))
