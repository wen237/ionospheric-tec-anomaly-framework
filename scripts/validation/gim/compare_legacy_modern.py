"""GIM-3B.5: compare paired Legacy/Modern daily NPZs at physical coordinates.

Usage: python compare_legacy_modern.py --legacy gim2022001.npz --modern codg0010.22i.npz
For full spatial science validation supply 16+ consecutive paired days and --reference-days 15.
Modern inputs MUST already have invalid raw 0 and 9999 converted to NaN.
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

LAT = np.linspace(-87.5, 87.5, 71)
LON = np.linspace(-180, 180, 73)


def read_legacy(path):
    with np.load(path, allow_pickle=False) as z:
        raw = np.asarray(z['gim'])
        times = np.asarray(z['gim_time'])
        lat = np.asarray(z['gim_lat'], dtype=float)
        lon = np.asarray(z['gim_lon'], dtype=float)
    if raw.shape != (25*71,73) or times.shape != (25,6):
        raise ValueError(f'Unexpected legacy shape: {path}')
    tec = raw[:24*71].reshape(24,71,73).astype(float)/10
    tec[(tec == 0) | (tec == 999.9)] = np.nan
    if not np.array_equal(lat, LAT[::-1]) or not np.array_equal(lon,LON):
        raise ValueError('Legacy grid coordinates differ from expected')
    epochs = np.array([np.datetime64(datetime(*map(int,t)), 's') for t in times[:24]])
    return epochs, tec[:,::-1,:].copy()


def read_modern(path):
    with np.load(path, allow_pickle=False) as z:
        tec = np.asarray(z['tec'],dtype=float)
        epochs = np.asarray(z['epochs'])
        lat = np.asarray(z['lat'],dtype=float)
        lon = np.asarray(z['lon'],dtype=float)
    if tec.shape != (25,71,73) or epochs.shape != (25,):
        raise ValueError(f'Unexpected modern shape: {path}')
    if not np.array_equal(lon,LON):
        raise ValueError('Modern longitude mismatch')
    if np.array_equal(lat,LAT[::-1]):
        tec = tec[:,::-1,:]
    elif not np.array_equal(lat,LAT):
        raise ValueError('Modern latitude mismatch')
    if np.any(tec == 0) or np.any(tec == 9999):
        raise ValueError(f'Modern NPZ contains invalid 0/9999: reconvert first: {path}')
    return epochs[:24].astype('datetime64[s]'), tec[:24]


def compare_pairs(legacy_paths, modern_paths, reference_days=15, window_steps=24, k=3.0):
    if len(legacy_paths) != len(modern_paths) or not legacy_paths:
        raise ValueError('Provide the same nonzero number of paired daily files')
    pairs = []
    for lp, mp in zip(legacy_paths, modern_paths):
        le, lt = read_legacy(lp)
        me, mt = read_modern(mp)
        if not np.array_equal(le,me):
            raise AssertionError(f'UTC epoch mismatch: {lp} vs {mp}')
        if not np.array_equal(np.isnan(lt), np.isnan(mt)):
            raise AssertionError(f'NaN mask mismatch: {lp} vs {mp}')
        if not np.array_equal(lt, mt, equal_nan=True):
            valid = np.isfinite(lt) & np.isfinite(mt)
            differences = int(np.count_nonzero(lt[valid] != mt[valid]))
            max_diff = (float(np.max(np.abs(lt[valid] - mt[valid])))
                        if np.any(valid) else float('nan'))
            raise AssertionError(
                f'Exact TEC mismatch: {lp} vs {mp}\n'
                f'Different finite values: {differences}\n'
                f'Maximum absolute difference: {max_diff}'
            )
        pairs.append((le[0],lt,mt))
    pairs.sort(key=lambda p:p[0])
    for i,(epoch,_,_) in enumerate(pairs):
        if i and epoch != pairs[i-1][0] + np.timedelta64(1,'D'):
            raise AssertionError('Daily files are not consecutive')
    print(f'PASS: {len(pairs)} daily pairs; {24*len(pairs)} hourly epochs; physical grid 71x73; NaN masks and TEC identical')
    if len(pairs) < reference_days+1:
        print(f'SCIENCE NOT RUN: need >= {reference_days+1} consecutive paired days for {reference_days}-day reference + observation')
        return
    if not (1 <= window_steps <= 24):
        raise ValueError('window_steps must be 1..24 in this initial daily science check')
    from scripts.validation.gim.spatial_anomaly import compute_spatial_anomalies
    # Compare same original science function on independently loaded and normalized data.
    old = np.concatenate([p[1] for p in pairs[:reference_days]] + [pairs[reference_days][1][:window_steps]])
    new = np.concatenate([p[2] for p in pairs[:reference_days]] + [pairs[reference_days][2][:window_steps]])
    kwargs = dict(samples_per_day=24, reference_days=reference_days,window_steps=window_steps,k=k,latitudes=LAT,longitudes=LON)
    a = compute_spatial_anomalies(old.reshape(-1,5183),**kwargs)
    b = compute_spatial_anomalies(new.reshape(-1,5183),**kwargs)
    for field in ('positive_counts','negative_counts','positive_ratio','negative_ratio'):
        if not np.allclose(getattr(a,field),getattr(b,field),rtol=0,atol=1e-10,equal_nan=True):
            raise AssertionError(f'Spatial science mismatch: {field}')
    print(f'PASS: Framework D spatial anomaly counts and ratios identical (reference_days={reference_days}, window_steps={window_steps}, k={k})')
    print('NOTE: This validates one specified science window; full historical reproduction is a separate test.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy',nargs='+',required=True,type=Path)
    parser.add_argument('--modern',nargs='+',required=True,type=Path)
    parser.add_argument('--reference-days',type=int,default=15)
    parser.add_argument('--window-steps',type=int,default=24)
    parser.add_argument('--k',type=float,default=3.0)
    args=parser.parse_args()
    compare_pairs(args.legacy,args.modern,args.reference_days,args.window_steps,args.k)

if __name__=='__main__':
    main()
