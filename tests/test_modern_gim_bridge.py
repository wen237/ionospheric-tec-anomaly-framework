from datetime import datetime
import numpy as np
import pytest
from src.data.modern_gim_bridge import load_modern_gim_window


def make_day(tmp_path, day, val, last_val):
    path = tmp_path / f'{day}.npz'
    start = np.datetime64(day, 's')
    tec = np.full((25, 71, 73), float(val))
    tec[24] = last_val
    np.savez_compressed(path, tec=tec,
        epochs=start + np.arange(25).astype('timedelta64[h]'),
        lat=np.linspace(87.5, -87.5, 71), lon=np.linspace(-180, 180, 73))
    return path


def test_window_midnight_owned_by_next_day(tmp_path):
    d1 = make_day(tmp_path, '2022-01-01', 11, 999)
    d2 = make_day(tmp_path, '2022-01-02', 22, 888)
    result = load_modern_gim_window([d2, d1], datetime(2022, 1, 2, 0),
                                    datetime(2022, 1, 2, 2), reference_days=1)
    assert result.tec.shape == (27, 71, 73)
    assert np.all(result.tec[:24] == 11)
    assert np.all(result.tec[24:] == 22)
    assert result.timestamps[24] == datetime(2022, 1, 2)
    assert result.window_steps == 3
    assert result.lat[0] == -87.5


def test_partial_window_and_nan_preserved(tmp_path):
    d1 = make_day(tmp_path, '2022-01-01', 11, 999)
    d2 = make_day(tmp_path, '2022-01-02', 22, 888)
    with np.load(d2) as z:
        data = {k:z[k].copy() for k in z.files}
    data['tec'][0, 0, 0] = np.nan
    np.savez_compressed(d2, **data)
    result = load_modern_gim_window([d1,d2], datetime(2022,1,2,1),
                                    datetime(2022,1,2,2), reference_days=1)
    assert np.isnan(result.tec[23, -1, 0])
    assert result.tec.shape[0] == 26


def test_incomplete_requested_range_rejected(tmp_path):
    d1 = make_day(tmp_path, '2022-01-01', 11, 999)
    with pytest.raises(ValueError, match='complete requested'):
        load_modern_gim_window([d1], datetime(2022,1,2),
                               datetime(2022,1,2,1), reference_days=1)


@pytest.mark.parametrize('start,end,reference_days', [
    (datetime(2022,1,2,0,30), datetime(2022,1,2,1), 1),
    (datetime(2022,1,2), datetime(2022,1,1), 1),
    (datetime(2022,1,2), datetime(2022,1,2), 0),
])
def test_invalid_time_request_rejected(tmp_path, start, end, reference_days):
    d1 = make_day(tmp_path, '2022-01-01', 11, 999)
    with pytest.raises(ValueError):
        load_modern_gim_window([d1], start, end, reference_days=reference_days)
