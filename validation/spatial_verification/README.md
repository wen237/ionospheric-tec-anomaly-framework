# Spatial Anomaly Verification — Validation

This directory contains reproducibility and numerical-equivalence validation scripts for the Spatial Anomaly Verification Framework.

## Scientific Reproduction

The Afghanistan case uses the following configuration:

| Parameter | Value |
| --- | --- |
| Event | 2022 Afghanistan earthquake (M6.0) |
| Epicenter | 33.020°N, 69.464°E |
| Verification window | 2022-05-28 00:00 to 2022-06-01 23:00 UTC |
| Reference period | 15 days |
| Threshold multiplier | 3.0 |
| GIM grid | 71 × 73 (5,183 grid points) |
| Sampling frequency | 24 observations per day |

The verification window is supplied explicitly. Automatic selection of this window from clustering results is not part of the current Spatial Framework.

## Production Workflow

The production-only reproduction uses:

1. `load_spatial_tec()` to load and prepare GIM observations.
2. `compute_spatial_anomalies()` to calculate positive and negative anomaly counts and occurrence ratios.
3. `orient_gim_grid()` to normalize the latitude orientation.
4. A frozen legacy reference to verify numerical equivalence.

The production workflow does not depend on the legacy implementation.

## Validation Commands

Run commands from the repository root.

### Full-window TEC numerical equivalence

```powershell
python -m validation.spatial_verification.validate_gim_window_equivalence
```

### Production-only Afghanistan spatial reproduction

```powershell
python -m validation.spatial_verification.validate_afghanistan_spatial_production
```

### Spatial unit tests

```powershell
python -m pytest tests/spatial_verification -q
```

### Complete regression suite

```powershell
python -m pytest tests -q
```

## Verified Results

The Afghanistan production implementation reproduces the frozen legacy reference with exact agreement for all four spatial matrices:

| Output | Shape | Numerical equivalence |
| --- | --- | --- |
| Positive anomaly counts | 71 × 73 | Exact |
| Negative anomaly counts | 71 × 73 | Exact |
| Positive anomaly ratio | 71 × 73 | Exact |
| Negative anomaly ratio | 71 × 73 | Exact |

The maximum positive anomaly ratio is 10.0%.

The maximum negative anomaly ratio is 85.0%, located at 30.0°N, 70.0°E.

The full-window GIM loading comparison also confirmed exact agreement across 2,487,840 TEC values, including NaN positions and timestamps.

## Data and Reproducibility

Real GIM datasets are not distributed with this repository.

The validation scripts currently use local dataset paths that must be configured for the execution environment. The production loader accepts a dataset directory through its function arguments.

The frozen reference file is located at:

`validation/spatial_verification/reference/afghanistan_spatial_reference.npz`

This reference was generated from the legacy implementation and must not be silently overwritten during routine validation.

## Current Limitations

- The production GIM loader currently supports the 24-observations-per-day format.
- Historical 12-observations-per-day GIM data have not yet been validated with the production loader.
- Spatial verification windows are externally specified rather than automatically inferred from clustering results.
- The three scientific frameworks have not yet been integrated into a single automated end-to-end pipeline.
- Cartographic visualization is separate from the validated numerical reproduction.

These limitations distinguish the completed scientific reproduction from future workflow automation and visualization development.
