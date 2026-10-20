from datetime import datetime, timezone

import numpy as np
import pytest

from src.workflow.modern_spatial_input_adapter import (
    load_spatial_tec_from_modern_gim,
    run_spatial_verification_from_modern_gim,
)
from src.workflow.temporal_window import TemporalWindow
from src.spatial_verification.spatial_anomaly import compute_spatial_anomalies
from src.spatial_verification.spatial_grid import GIM_LATITUDES, GIM_LONGITUDES


def make_day(path, day, value, *, descending=True, last_value=777.0, nan=False):
    lat = GIM_LATITUDES[::-1].copy() if descending else GIM_LATITUDES.copy()
    tec = np.full((25, 71, 73), float(value))
    # Vary by physical latitude to detect accidental reversed rows.
    tec[:, :, :] += lat[None, :, None] / 100.0
    if nan:
        tec[0, 0, 0] = np.nan
    tec[24] = last_value
    epochs = np.datetime64(day, 's') + np.arange(25).astype('timedelta64[h]')
    np.savez_compressed(path, tec=tec, epochs=epochs, lat=lat,
                        lon=GIM_LONGITUDES, source_file=np.array(path.name))
    return path


@pytest.fixture
def files(tmp_path):
    a = make_day(tmp_path / 'first.npz', '2022-01-01', 10, last_value=777)
    b = make_day(tmp_path / 'second.npz', '2022-01-02', 20, last_value=888, nan=True)
    return [a, b]


def test_uses_next_days_own_zero_hour_and_never_day25(files):
    out = load_spatial_tec_from_modern_gim(files, datetime(2022, 1, 2),
                                           datetime(2022, 1, 2, 2), reference_days=1)
    assert out.tec.shape == (27, 5183)
    assert out.timestamps[24] == datetime(2022, 1, 2)
    assert np.isclose(out.tec[23, 0], 10 - .875)
    assert np.isnan(out.tec[24, -73])  # nan at source descending row 0 -> ascending row 70
    assert np.isclose(out.tec[24, 0], 20 - .875)
    assert not np.any(out.tec == 777)
    assert not np.any(out.tec == 888)
    assert out.window_steps == 3


def test_grid_is_ascending_physical_latitude(files):
    out = load_spatial_tec_from_modern_gim(files, datetime(2022, 1, 2),
                                           datetime(2022, 1, 2), reference_days=1)
    assert np.isclose(out.tec[0, 0], 10 - .875)
    assert np.isclose(out.tec[0, -1], 10 + .875)


def test_input_order_does_not_change_result(files):
    kwargs = dict(start_time=datetime(2022, 1, 2), end_time=datetime(2022, 1, 2), reference_days=1)
    a = load_spatial_tec_from_modern_gim(files, **kwargs)
    b = load_spatial_tec_from_modern_gim(files[::-1], **kwargs)
    np.testing.assert_array_equal(a.tec, b.tec)
    assert a.timestamps == b.timestamps


def test_nan_is_not_interpolated(files):
    out = load_spatial_tec_from_modern_gim(files, datetime(2022, 1, 2),
                                           datetime(2022, 1, 2), reference_days=1)
    assert np.isnan(out.tec[24, -73])


def test_missing_day_is_rejected(files):
    with pytest.raises(ValueError, match='cover|complete|consecutive'):
        load_spatial_tec_from_modern_gim(files[:1], datetime(2022, 1, 2),
                                         datetime(2022, 1, 2), reference_days=1)


def test_modern_spatial_runner_uses_original_scientific_core(files):
    window = TemporalWindow(datetime(2022, 1, 2, tzinfo=timezone.utc),
                            datetime(2022, 1, 2, 2, tzinfo=timezone.utc), 'explicit')
    actual = run_spatial_verification_from_modern_gim(window, files, reference_days=1, k=1.5)
    inp = load_spatial_tec_from_modern_gim(files, datetime(2022, 1, 2),
                                           datetime(2022, 1, 2, 2), reference_days=1)
    expected = compute_spatial_anomalies(inp.tec, 24, 1, 3, 1.5,
                                         GIM_LATITUDES, GIM_LONGITUDES)
    np.testing.assert_array_equal(actual.positive_ratio, expected.positive_ratio)
    np.testing.assert_array_equal(actual.negative_ratio, expected.negative_ratio)
    assert actual.window_steps == 3


def test_invalid_k_is_rejected(files):
    window = TemporalWindow(datetime(2022, 1, 2, tzinfo=timezone.utc),
                            datetime(2022, 1, 2, tzinfo=timezone.utc), 'explicit')
    for bad in [float('nan'), float('inf'), -1, True]:
        with pytest.raises(ValueError):
            run_spatial_verification_from_modern_gim(window, files, reference_days=1, k=bad)
