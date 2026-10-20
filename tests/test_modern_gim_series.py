"""Synthetic-only tests for GIM-3B.3 cross-day joining."""
import numpy as np
import pytest

from src.data.modern_gim_series import load_modern_gim_series


def day_file(tmp_path, date, *, values=None, source=None):
    day = np.datetime64(date, 's')
    path = tmp_path / f'{date}.npz'
    tec = np.full((25, 71, 73), 10.0) if values is None else values.copy()
    np.savez_compressed(
        path, tec=tec,
        epochs=day + np.arange(25).astype('timedelta64[h]'),
        lat=np.linspace(87.5, -87.5, 71),
        lon=np.linspace(-180, 180, 73),
        source_file=np.array(source or f'{date}.ionex'),
    )
    return path


def test_one_day_keeps_only_24_epochs(tmp_path):
    a = day_file(tmp_path, '2022-01-01')
    result = load_modern_gim_series([a])
    assert result.tec.shape == (24, 71, 73)
    assert result.epochs[-1] == np.datetime64('2022-01-01T23:00:00')


def test_two_days_uses_each_days_own_midnight_and_sorts(tmp_path):
    a = day_file(tmp_path, '2022-01-01')
    b = day_file(tmp_path, '2022-01-02')
    result = load_modern_gim_series([b, a])
    assert result.tec.shape == (48, 71, 73)
    assert len(np.unique(result.epochs)) == 48
    assert result.source_files == ('2022-01-01.ionex', '2022-01-02.ionex')
    assert result.lat[0] == -87.5
    assert result.tec[0, 0, 0] == 10.0


def test_three_days_have_72_hours(tmp_path):
    paths = [day_file(tmp_path, f'2022-01-0{d}') for d in (1, 2, 3)]
    result = load_modern_gim_series(paths)
    assert result.tec.shape[0] == 72
    assert result.epochs[-1] == np.datetime64('2022-01-03T23:00:00')


def test_boundary_values_may_differ_and_next_day_owns_midnight(tmp_path):
    x = np.full((25, 71, 73), 10.0)
    y = np.full((25, 71, 73), 20.0)
    x[24, 2, 3] = np.nan  # Must not propagate into next day.
    y[0, 2, 3] = 22.0
    a = day_file(tmp_path, '2022-01-01', values=x)
    b = day_file(tmp_path, '2022-01-02', values=y)
    result = load_modern_gim_series([a, b])
    assert result.tec.shape[0] == 48
    assert result.tec[23, -3, 3] == 10.0
    assert result.tec[24, -3, 3] == 22.0
    assert result.epochs[24] == np.datetime64('2022-01-02T00:00:00')


def test_discarded_25th_map_is_not_used_even_for_single_day(tmp_path):
    x = np.full((25, 71, 73), 10.0)
    x[24, :, :] = 99.0
    a = day_file(tmp_path, '2022-01-01', values=x)
    result = load_modern_gim_series([a])
    assert result.tec.shape[0] == 24
    assert np.all(result.tec == 10.0)


def test_next_day_midnight_nan_is_preserved(tmp_path):
    x = np.full((25, 71, 73), 10.0)
    y = np.full((25, 71, 73), 20.0)
    x[24, 0, 0] = 15.0
    y[0, 0, 0] = np.nan
    a = day_file(tmp_path, '2022-01-01', values=x)
    b = day_file(tmp_path, '2022-01-02', values=y)
    result = load_modern_gim_series([a, b])
    assert np.isnan(result.tec[24, -1, 0])


def test_gap_rejected(tmp_path):
    a = day_file(tmp_path, '2022-01-01')
    b = day_file(tmp_path, '2022-01-03')
    with pytest.raises(ValueError, match='consecutive'):
        load_modern_gim_series([a, b])


def test_duplicate_day_rejected(tmp_path):
    a = day_file(tmp_path, '2022-01-01')
    with pytest.raises(ValueError, match='unique UTC days'):
        load_modern_gim_series([a, a])


def test_empty_and_single_path_rejected(tmp_path):
    with pytest.raises(ValueError, match='At least one'):
        load_modern_gim_series([])
    with pytest.raises(TypeError, match='sequence'):
        load_modern_gim_series(str(tmp_path / 'x.npz'))


def test_invalid_day_delegates_to_single_day_validation(tmp_path):
    x = np.full((25, 71, 73), 10.0)
    x[0, 0, 0] = 0.0
    a = day_file(tmp_path, '2022-01-01', values=x)
    with pytest.raises(ValueError, match='Invalid TEC sentinel'):
        load_modern_gim_series([a])
