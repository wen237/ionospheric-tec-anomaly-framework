"""GIM-3B.6-B: paired Legacy/Modern Framework B+C historical-input validation."""
import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
for root in (Path.cwd(), HERE.parent, HERE.parent.parent):
    if (root / 'src' / 'workflow' / 'historical_input_adapter.py').is_file():
        sys.path.insert(0, str(root))
        break
else:
    raise RuntimeError('Run inside ionospheric-tec-anomaly-framework with src/workflow adapters installed')

from src.workflow.historical_input_adapter import prepare_historical_daily_tec
from src.workflow.modern_historical_input_adapter import load_historical_daily_tec_from_modern_gim
from scripts.validation.gim.compare_legacy_modern import read_legacy, LAT, LON
from scripts.validation.gim.validate_16days import select_pairs


def exact_equal(name, old, new):
    old, new = np.asarray(old), np.asarray(new)
    if old.shape != new.shape:
        raise AssertionError(f'{name}: shapes differ {old.shape} vs {new.shape}')
    equal_nan = old.dtype.kind in 'fc' and new.dtype.kind in 'fc'
    if not np.array_equal(old, new, equal_nan=equal_nan):
        if equal_nan:
            valid = np.isfinite(old) & np.isfinite(new)
            count = int(np.count_nonzero(old[valid] != new[valid]))
            maximum = float(np.max(np.abs(old[valid] - new[valid]))) if np.any(valid) else 0.0
            raise AssertionError(f'{name}: exact mismatch; finite differences={count}; max absolute difference={maximum}')
        raise AssertionError(f'{name}: exact mismatch')


def prepare_legacy(paths, start_date, end_date, latitude, longitude):
    li = int(np.argmin(np.abs(LAT - latitude)))
    lj = int(np.argmin(np.abs(LON - longitude)))
    epochs, values = [], []
    for path in paths:
        day_epochs, day_tec = read_legacy(path)
        epochs.extend(datetime.fromtimestamp(int(e.astype('datetime64[s]').astype('int64')), tz=timezone.utc).replace(tzinfo=None) for e in day_epochs)
        values.extend(day_tec[:, li, lj].tolist())
    # Reject NaNs explicitly; B+C preparation does not permit silent interpolation.
    if not np.all(np.isfinite(values)):
        raise ValueError(f'Selected Legacy historical TEC contains NaN at grid ({LAT[li]}, {LON[lj]}); choose another location or interval, no interpolation permitted.')
    return prepare_historical_daily_tec(
        epochs=epochs, tec=values, start_date=start_date, end_date=end_date,
        allow_interpolation=False,
    ), (float(LAT[li]), float(LON[lj]))


def compare_results(old, new, expected_days):
    if old.start_date != new.start_date or old.end_date != new.end_date or old.n_days != new.n_days:
        raise AssertionError('Historical date range / number of days mismatch')
    if old.n_days != expected_days or old.daily_tec.shape != (expected_days, 24):
        raise AssertionError('Historical daily TEC dimensions are not days x 24')
    exact_equal('daily_tec', old.daily_tec, new.daily_tec)
    for field in ('epochs', 'tec', 'observed_mask', 'interpolated_mask'):
        exact_equal('hourly_result.' + field, getattr(old.hourly_result, field), getattr(new.hourly_result, field))
    if np.any(old.hourly_result.interpolated_mask) or np.any(new.hourly_result.interpolated_mask):
        raise AssertionError('Interpolation is forbidden for this validation')
    print(f'PASS: Framework B+C historical input; {expected_days} UTC days; {expected_days * 24} hours; exact daily TEC and hourly metadata equality; no interpolation')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--legacy-dir', required=True, type=Path, help='Actual directory containing Legacy NPZ, including year')
    p.add_argument('--modern-dir', required=True, type=Path)
    p.add_argument('--start', required=True, type=date.fromisoformat)
    p.add_argument('--days', type=int, default=16)
    p.add_argument('--latitude', type=float, default=30)
    p.add_argument('--longitude', type=float, default=70)
    args = p.parse_args()
    if args.days < 1:
        p.error('--days must be positive')
    legacy, modern = select_pairs(args.legacy_dir, args.modern_dir, args.start, args.days)
    end_date = args.start + timedelta(days=args.days - 1)
    old, grid = prepare_legacy(legacy, args.start, end_date, args.latitude, args.longitude)
    new = load_historical_daily_tec_from_modern_gim(
        modern, start_date=args.start, end_date=end_date,
        latitude=args.latitude, longitude=args.longitude,
    )
    compare_results(old, new, args.days)
    print(f'Grid: {grid}; UTC interval: {args.start} through {end_date}')
    print('NOTE: Validates historical TEC preparation only, not multi-event Z-test or K-means science.')

if __name__ == '__main__':
    main()
