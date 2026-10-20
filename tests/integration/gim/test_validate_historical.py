from datetime import date
from types import SimpleNamespace
import numpy as np
import pytest
from scripts.validation.gim.validate_historical import compare_results, exact_equal


def result(values, *, interpolated=False):
    v = np.asarray(values, dtype=float).reshape(2, 24)
    return SimpleNamespace(start_date=date(2022, 1, 1), end_date=date(2022, 1, 2), n_days=2,
        daily_tec=v, hourly_result=SimpleNamespace(epochs=np.arange(48), tec=v.ravel(),
        observed_mask=np.ones(48, dtype=bool), interpolated_mask=np.full(48, interpolated, dtype=bool)))


def test_identical_daily_and_hourly():
    a = result(np.arange(48))
    compare_results(a, result(np.arange(48)), 2)


def test_tiny_difference_rejected():
    a = result(np.arange(48))
    b = result(np.arange(48))
    b.daily_tec[0, 1] = np.nextafter(b.daily_tec[0, 1], np.inf)
    with pytest.raises(AssertionError, match='daily_tec'):
        compare_results(a, b, 2)


def test_interpolation_rejected():
    with pytest.raises(AssertionError, match='Interpolation'):
        compare_results(result(np.arange(48), interpolated=True), result(np.arange(48), interpolated=True), 2)


def test_nan_masks_equal_but_values_different():
    exact_equal('tec', np.array([np.nan, 2.]), np.array([np.nan, 2.]))
    with pytest.raises(AssertionError):
        exact_equal('tec', np.array([np.nan, 2.]), np.array([np.nan, 3.]))


def test_wrong_number_of_days():
    with pytest.raises(AssertionError, match='dimensions'):
        compare_results(result(np.arange(48)), result(np.arange(48)), 3)
