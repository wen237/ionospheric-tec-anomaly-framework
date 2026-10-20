"""Synthetic regression tests for GIM-3B.1/3B.2 (no research data)."""
import numpy as np
import pytest

from src.data.modern_gim_loader import load_modern_gim_day


def make_npz(tmp_path, **overrides):
    path = tmp_path / "synthetic_day.npz"
    payload = dict(
        tec=np.full((25, 71, 73), 12.5),
        epochs=np.datetime64("2022-01-01T00:00:00") + np.arange(25).astype("timedelta64[h]"),
        lat=np.linspace(87.5, -87.5, 71),
        lon=np.linspace(-180, 180, 73),
        source_file=np.array("synthetic.22i.Z"),
    )
    payload.update(overrides)
    np.savez_compressed(path, **payload)
    return path


def test_load_and_orient(tmp_path):
    tec = np.full((25, 71, 73), 12.5)
    tec[:, 0, 0] = 42.0  # northernmost raw row
    tec[:, -1, 0] = np.nan  # southernmost raw row
    result = load_modern_gim_day(make_npz(tmp_path, tec=tec))
    assert result.tec.shape == (25, 71, 73)
    assert result.lat[0] == -87.5 and result.lat[-1] == 87.5
    assert np.isnan(result.tec[0, 0, 0])
    assert result.tec[0, -1, 0] == 42.0
    assert result.tec[0, 1, 1] == 12.5  # no scaling
    assert result.epochs[-1] == np.datetime64("2022-01-02T00:00:00")
    assert result.source_file == "synthetic.22i.Z"


def test_ascending_latitude_not_flipped(tmp_path):
    tec = np.full((25, 71, 73), 9.0)
    tec[:, 0, 0] = 23.0
    result = load_modern_gim_day(make_npz(tmp_path, tec=tec, lat=np.linspace(-87.5, 87.5, 71)))
    assert result.tec[0, 0, 0] == 23.0


@pytest.mark.parametrize("bad", [0.0, 9999.0, np.inf, -2.0])
def test_invalid_tec_rejected(tmp_path, bad):
    tec = np.full((25, 71, 73), 12.5)
    tec[0, 0, 0] = bad
    with pytest.raises(ValueError):
        load_modern_gim_day(make_npz(tmp_path, tec=tec))


def test_missing_required_key(tmp_path):
    path = tmp_path / "missing.npz"
    np.savez(path, tec=np.ones((25, 71, 73)))
    with pytest.raises(ValueError, match="Missing modern GIM fields"):
        load_modern_gim_day(path)


def test_bad_shape(tmp_path):
    with pytest.raises(ValueError, match="TEC shape"):
        load_modern_gim_day(make_npz(tmp_path, tec=np.ones((24, 71, 73))))


def test_duplicate_epoch(tmp_path):
    epochs = np.datetime64("2022-01-01") + np.arange(25).astype("timedelta64[h]")
    epochs[5] = epochs[4]
    with pytest.raises(ValueError, match="consecutive hourly"):
        load_modern_gim_day(make_npz(tmp_path, epochs=epochs))


def test_bad_latitude(tmp_path):
    with pytest.raises(ValueError, match="Latitude"):
        load_modern_gim_day(make_npz(tmp_path, lat=np.linspace(-90, 90, 71)))


def test_bad_longitude(tmp_path):
    with pytest.raises(ValueError, match="Longitude"):
        load_modern_gim_day(make_npz(tmp_path, lon=np.linspace(0, 360, 73)))


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_modern_gim_day(tmp_path / "absent.npz")
