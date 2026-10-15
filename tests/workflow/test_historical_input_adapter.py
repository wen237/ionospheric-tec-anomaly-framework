"""Tests for the historical TEC input adapter."""

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from src.workflow.historical_input_adapter import (
    prepare_historical_daily_tec,
)


START = datetime(2022, 5, 1)
START_DATE = date(2022, 5, 1)
END_DATE = date(2022, 5, 2)


def make_hourly_data(n_hours=48):
    epochs = np.array(
        [START + timedelta(hours=i) for i in range(n_hours)],
        dtype=object,
    )
    tec = np.arange(n_hours, dtype=float) + 10.0
    return epochs, tec


def prepare(epochs, tec, **kwargs):
    options = {
        "start_date": START_DATE,
        "end_date": END_DATE,
    }
    options.update(kwargs)

    return prepare_historical_daily_tec(
        epochs,
        tec,
        **options,
    )


def test_complete_hourly_data():
    epochs, tec = make_hourly_data()

    result = prepare(epochs, tec)

    assert result.daily_tec.shape == (2, 24)
    assert result.n_days == 2

    np.testing.assert_array_equal(
        result.daily_tec.reshape(-1),
        tec,
    )

    assert np.all(result.hourly_result.observed_mask)
    assert not np.any(result.hourly_result.interpolated_mask)


def test_missing_hour_rejected_by_default():
    epochs, tec = make_hourly_data()

    epochs = np.delete(epochs, 10)
    tec = np.delete(tec, 10)

    with pytest.raises(ValueError, match="interpolation"):
        prepare(epochs, tec)


def test_missing_hour_allowed_explicitly():
    epochs, tec = make_hourly_data()

    epochs = np.delete(epochs, 10)
    tec = np.delete(tec, 10)

    result = prepare(
        epochs,
        tec,
        allow_interpolation=True,
    )

    assert result.daily_tec[0, 10] == 20.0
    assert result.hourly_result.interpolated_mask[10]
    assert not result.hourly_result.observed_mask[10]


def test_internal_nan_requires_interpolation():
    epochs, tec = make_hourly_data()
    tec[12] = np.nan

    with pytest.raises(ValueError, match="interpolation"):
        prepare(epochs, tec)

    result = prepare(
        epochs,
        tec,
        allow_interpolation=True,
    )

    assert result.daily_tec[0, 12] == 22.0
    assert result.hourly_result.interpolated_mask[12]


@pytest.mark.parametrize(
    "index",
    [0, 47],
)
def test_missing_boundary_observation_rejected(index):
    epochs, tec = make_hourly_data()
    tec[index] = np.nan

    with pytest.raises(ValueError, match="missing values"):
        prepare(
            epochs,
            tec,
            allow_interpolation=True,
        )


def test_missing_boundary_epoch_rejected():
    epochs, tec = make_hourly_data()

    with pytest.raises(ValueError, match="missing values"):
        prepare(
            epochs[1:],
            tec[1:],
            allow_interpolation=True,
        )


def test_reject_aware_datetime():
    epochs, tec = make_hourly_data()
    epochs[0] = datetime(
        2022, 5, 1, tzinfo=timezone.utc
    )

    with pytest.raises(ValueError, match="naive UTC"):
        prepare(epochs, tec)


def test_reject_non_hourly_epoch():
    epochs, tec = make_hourly_data()
    epochs[10] += timedelta(minutes=30)

    with pytest.raises(ValueError, match="hourly"):
        prepare(epochs, tec)


def test_reject_duplicate_epoch():
    epochs, tec = make_hourly_data()
    epochs[10] = epochs[9]

    with pytest.raises(ValueError, match="duplicate"):
        prepare(epochs, tec)


def test_reject_out_of_order_epochs():
    epochs, tec = make_hourly_data()
    epochs[10], epochs[11] = epochs[11], epochs[10]

    with pytest.raises(ValueError, match="increasing"):
        prepare(epochs, tec)


def test_reject_outside_requested_interval():
    epochs, tec = make_hourly_data()

    with pytest.raises(ValueError, match="within"):
        prepare(
            epochs,
            tec,
            start_date=date(2022, 5, 2),
        )


def test_reject_invalid_date_range():
    epochs, tec = make_hourly_data()

    with pytest.raises(ValueError, match="start_date"):
        prepare(
            epochs,
            tec,
            start_date=date(2022, 5, 3),
        )


def test_reject_invalid_interpolation_flag():
    epochs, tec = make_hourly_data()

    with pytest.raises(TypeError, match="allow_interpolation"):
        prepare(
            epochs,
            tec,
            allow_interpolation=1,
        )


def test_calendar_day_alignment():
    epochs, tec = make_hourly_data(n_hours=72)

    result = prepare(
        epochs,
        tec,
        end_date=date(2022, 5, 3),
    )

    assert result.daily_tec.shape == (3, 24)
    assert result.daily_tec[0, 0] == 10.0
    assert result.daily_tec[1, 0] == 34.0
    assert result.daily_tec[2, 0] == 58.0
