"""Discover paired Legacy/Modern GIM files by their *internal UTC dates*.

Example (PowerShell, one line):
python validate_16days.py --legacy-dir C:\\data\\legacy --modern-dir C:\\data\\modern --start 2022-01-01 --days 16
"""
import argparse
from datetime import date, timedelta
from pathlib import Path
import numpy as np
from scripts.validation.gim.compare_legacy_modern import compare_pairs


def indexed_files(folder: Path, kind: str):
    if not folder.is_dir():
        raise ValueError(f"{kind} directory does not exist: {folder}")
    index = {}
    for path in sorted(folder.glob('*.npz')):
        with np.load(path, allow_pickle=False) as z:
            required = 'gim_time' if kind == 'Legacy' else 'epochs'
            if required not in z:
                continue  # Ignore unrelated NPZ files.
            if kind == 'Legacy':
                t = np.asarray(z['gim_time'])
                if t.shape != (25, 6):
                    raise ValueError(f"Unexpected Legacy time shape: {path}")
                try:
                    d = date(*map(int, t[0, :3]))
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Invalid Legacy date: {path}") from exc
            else:
                t = np.asarray(z['epochs'])
                if t.shape != (25,) or not np.issubdtype(t.dtype, np.datetime64):
                    raise ValueError(f"Unexpected Modern time format: {path}")
                d = date.fromisoformat(str(t[0].astype('datetime64[D]')))
            if d in index:
                raise ValueError(f"Ambiguous {kind} files for {d}: {index[d]} and {path}")
            index[d] = path
    return index


def select_pairs(legacy_dir, modern_dir, start, days):
    if days < 1:
        raise ValueError('days must be positive')
    old = indexed_files(Path(legacy_dir), 'Legacy')
    new = indexed_files(Path(modern_dir), 'Modern')
    dates = [start + timedelta(days=i) for i in range(days)]
    missing_old = [str(d) for d in dates if d not in old]
    missing_new = [str(d) for d in dates if d not in new]
    if missing_old or missing_new:
        raise ValueError(f"Missing Legacy dates: {missing_old}; missing Modern dates: {missing_new}")
    return [old[d] for d in dates], [new[d] for d in dates]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--legacy-dir', required=True, type=Path)
    p.add_argument('--modern-dir', required=True, type=Path)
    p.add_argument('--start', required=True, type=date.fromisoformat)
    p.add_argument('--days', type=int, default=16)
    p.add_argument('--reference-days', type=int, default=15)
    p.add_argument('--window-steps', type=int, default=24)
    p.add_argument('--k', type=float, default=3.0)
    args = p.parse_args()
    if args.days < args.reference_days + 1:
        p.error('days must include reference-days plus at least one observation day')
    legacy, modern = select_pairs(args.legacy_dir, args.modern_dir, args.start, args.days)
    print(f'Comparing {len(legacy)} paired UTC days: {args.start} to {args.start + timedelta(days=args.days - 1)}')
    compare_pairs(legacy, modern, reference_days=args.reference_days, window_steps=args.window_steps, k=args.k)

if __name__ == '__main__':
    main()
