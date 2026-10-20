"""GIM-3B.6-A: real paired Legacy/Modern Framework A validation.
Run from project root or this folder; requires installed project src package.
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
# Discover project root from a sibling folder under the repository.
for root in (Path.cwd(), HERE.parent, HERE.parent.parent):
    if (root / 'src' / 'workflow' / 'temporal_input_adapter.py').is_file():
        sys.path.insert(0, str(root))
        break
else:
    raise RuntimeError('Run inside ionospheric-tec-anomaly-framework with src/workflow adapters installed')

from src.workflow.temporal_input_adapter import load_temporal_tec_from_gim
from src.workflow.modern_temporal_input_adapter import load_temporal_tec_from_modern_gim
from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies


def exact_equal(name, a, b):
    a, b = np.asarray(a), np.asarray(b)
    if not np.array_equal(a, b, equal_nan=True if a.dtype.kind in 'fc' and b.dtype.kind in 'fc' else False):
        if a.shape != b.shape:
            raise AssertionError(f'{name}: shape mismatch {a.shape} != {b.shape}')
        if a.dtype.kind in 'fc' and b.dtype.kind in 'fc':
            valid = np.isfinite(a) & np.isfinite(b)
            n = int(np.count_nonzero(a[valid] != b[valid]))
            maxdiff = float(np.max(np.abs(a[valid] - b[valid]))) if np.any(valid) else 0.0
            raise AssertionError(f'{name}: exact mismatch; different finite values={n}, max abs diff={maxdiff}')
        raise AssertionError(f'{name}: exact mismatch')


def verify_series(old, new, expected_steps, reference_days, k):
    for field in ('grid_latitude', 'grid_longitude', 'latitude_index', 'longitude_index'):
        if getattr(old, field) != getattr(new, field):
            raise AssertionError(f'Grid selection mismatch: {field}')
    exact_equal('series epochs', old.epochs, new.epochs)
    exact_equal('series TEC', old.tec, new.tec)
    if len(old.tec) != expected_steps:
        raise AssertionError(f'Expected {expected_steps} hourly epochs, got {len(old.tec)}')
    print(f'PASS: Framework A temporal input; {expected_steps} UTC epochs; grid ({old.grid_latitude}, {old.grid_longitude}); exact TEC and NaN equality')
    a = detect_temporal_anomalies(old.tec, old.epochs, reference_days=reference_days, threshold_multiplier=k)
    b = detect_temporal_anomalies(new.tec, new.epochs, reference_days=reference_days, threshold_multiplier=k)
    for field in ('epochs', 'observed', 'q1', 'median', 'q3', 'upper_bound', 'lower_bound', 'anomaly'):
        exact_equal(f'Framework A {field}', getattr(a, field), getattr(b, field))
    if len(a.epochs) != expected_steps - reference_days * 24:
        raise AssertionError('Unexpected analysis period length')
    positive = int(np.count_nonzero(a.anomaly == 1))
    negative = int(np.count_nonzero(a.anomaly == -1))
    print(f'PASS: Framework A temporal science; {len(a.epochs)} analysis hours; positive={positive}; negative={negative}; all fields exactly equal')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--legacy-dir', required=True, type=Path)
    p.add_argument('--modern-dir', required=True, type=Path)
    p.add_argument('--start', required=True, type=date.fromisoformat, help='First reference UTC date, e.g. 2022-01-01')
    p.add_argument('--days', type=int, default=16)
    p.add_argument('--reference-days', type=int, default=15)
    p.add_argument('--latitude', type=float, default=30.0)
    p.add_argument('--longitude', type=float, default=70.0)
    p.add_argument('--k', type=float, default=3.0)
    args = p.parse_args()
    if args.reference_days < 1 or args.days <= args.reference_days:
        p.error('days must exceed positive reference-days')
    # Reuse the previously validated internal-UTC-date indexing; no filename guessing.
    from scripts.validation.gim.validate_16days import select_pairs
    legacy_year_dir = Path(args.legacy_dir)

    year = str(args.start.year)

    if not legacy_year_dir.name.endswith(year):
        raise ValueError(
            f"Legacy directory must end with {year}: {legacy_year_dir}"
        )

    legacy_base_dir = legacy_year_dir.with_name(
        legacy_year_dir.name[:-len(year)]
    )
    legacy, modern = select_pairs(
        legacy_year_dir,
        args.modern_dir,
        args.start,
        args.days,
    )
    start_time = datetime.combine(args.start + timedelta(days=args.reference_days), datetime.min.time())
    end_time = datetime.combine(args.start + timedelta(days=args.days), datetime.min.time()) - timedelta(hours=1)
    old = load_temporal_tec_from_gim(legacy_base_dir, start_time, end_time, latitude=args.latitude, longitude=args.longitude, reference_days=args.reference_days)
    new = load_temporal_tec_from_modern_gim(modern, start_time, end_time, latitude=args.latitude, longitude=args.longitude, reference_days=args.reference_days)
    verify_series(old, new, args.days * 24, args.reference_days, args.k)
    print('NOTE: Validates specified dates and one grid point, not full historical case reproduction.')

if __name__ == '__main__':
    main()
