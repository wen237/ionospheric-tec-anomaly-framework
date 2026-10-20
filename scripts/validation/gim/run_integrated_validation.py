"""GIM-3B.6-C: run already validated A, B+C, D checks and save audit report."""
import argparse
from datetime import date, timedelta, datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


def legacy_base(year_dir: Path, start: date, days: int) -> Path:
    last = start + timedelta(days=days - 1)
    if last.year != start.year:
        raise ValueError('Cross-year intervals are not supported by this integration runner')
    year = str(start.year)
    if not year_dir.name.endswith(year):
        raise ValueError(f'Legacy folder must end in {year}: {year_dir}')
    stem = year_dir.name[:-4]
    if not stem:
        raise ValueError('Legacy folder prefix must not be empty')
    return year_dir.with_name(stem)


def commands(args, here: Path):
    base = legacy_base(args.legacy_dir, args.start, args.days)

    common = [
        '--modern-dir', str(args.modern_dir),
        '--start', args.start.isoformat(),
        '--days', str(args.days)
    ]

    py = sys.executable

    return [
        (
            'D',
            [py, '-m', 'scripts.validation.gim.validate_16days',
             '--legacy-dir', str(args.legacy_dir), *common,
             '--reference-days', str(args.reference_days),
             '--window-steps', str(args.window_steps),
             '--k', str(args.k)]
        ),
        (
            'A',
            [py, '-m', 'scripts.validation.gim.validate_temporal',
             '--legacy-dir', str(args.legacy_dir), *common,
             '--reference-days', str(args.reference_days),
             '--latitude', str(args.latitude),
             '--longitude', str(args.longitude),
             '--k', str(args.k)]
        ),
        (
            'B+C',
            [py, '-m', 'scripts.validation.gim.validate_historical',
             '--legacy-dir', str(args.legacy_dir), *common,
             '--latitude', str(args.latitude),
             '--longitude', str(args.longitude)]
        ),
    ]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--legacy-dir', type=Path, required=True)
    p.add_argument('--modern-dir', type=Path, required=True)
    p.add_argument('--start', type=date.fromisoformat, required=True)
    p.add_argument('--days', type=int, default=16)
    p.add_argument('--reference-days', type=int, default=15)
    p.add_argument('--window-steps', type=int, default=24)
    p.add_argument('--latitude', type=float, default=30.0)
    p.add_argument('--longitude', type=float, default=70.0)
    p.add_argument('--k', type=float, default=3.0)
    p.add_argument('--report', type=Path, default=Path('gim3b6_c_report.json'))
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    if args.reference_days < 1 or args.days != args.reference_days + 1:
        p.error('This runner requires exactly reference-days + 1 days (one observation day)')
    if not 1 <= args.window_steps <= 24:
        p.error('window-steps must be 1..24')
    here = Path(__file__).resolve().parent
    repo_root = here.parents[2]

    jobs = commands(args, here)

    for module in (
        "validate_16days.py",
        "validate_temporal.py",
        "validate_historical.py",
    ):
        if not (here / module).is_file():
            p.error(f"Missing validation script: {here / module}")
    if args.dry_run:
        for label, cmd in jobs:
            print(f'{label}: {subprocess.list2cmdline(cmd)}')
        return
    if not args.legacy_dir.is_dir() or not args.modern_dir.is_dir():
        p.error('Legacy and Modern directories must both exist')
    report = {
        'stage': 'GIM-3B.6-C', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'parameters': {'legacy_dir': str(args.legacy_dir), 'modern_dir': str(args.modern_dir),
                       'start': args.start.isoformat(), 'days': args.days, 'reference_days': args.reference_days,
                       'window_steps': args.window_steps, 'latitude': args.latitude, 'longitude': args.longitude, 'k': args.k},
        'results': [], 'overall': 'FAIL',
        'scope': 'One selected 16-day window, one grid point for A and B+C; not historical paper reproduction'
    }
    for label, cmd in jobs:
        print(f'\n=== Framework {label} ===', flush=True)
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False
        )
        if result.stdout:
            print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, file=sys.stderr, end='')
        report['results'].append({'framework': label, 'status': 'PASS' if result.returncode == 0 else 'FAIL',
                                  'returncode': result.returncode, 'command': cmd,
                                  'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode != 0:
            break
    if len(report['results']) == len(jobs) and all(x['status'] == 'PASS' for x in report['results']):
        report['overall'] = 'PASS'
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nGIM-3B.6-C {report["overall"]}; report: {args.report}')
    if report['overall'] != 'PASS':
        sys.exit(1)

if __name__ == '__main__':
    main()
