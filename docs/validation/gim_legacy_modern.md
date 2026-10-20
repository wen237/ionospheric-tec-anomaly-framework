# Legacy–Modern CODE GIM Validation

## 1. Overview

This document describes the numerical consistency validation between the Legacy CODE GIM processing workflow and the Modern IONEX-based data interface integrated into the Ionospheric TEC Anomaly Framework.

The objective is to verify that modernized data loading and workflow adapters preserve the numerical inputs and selected anomaly analysis results of the existing scientific framework.

The validation does not modify the original scientific algorithms.

## 2. Data and Processing Rules

The validation uses paired Legacy and Modern CODE GIM datasets corresponding to the same UTC dates.

Key processing rules:

- Daily datasets are matched by their internal UTC dates rather than filenames.
- Only the first 24 hourly TEC maps are used for each day.
- The additional 25th map is excluded to avoid duplicate midnight observations.
- Missing TEC values are represented by `NaN`.
- No automatic interpolation or numerical rounding is applied.
- TEC comparisons use the same physical latitude and longitude coordinates.

The Modern IONEX converter preserves float64 TEC values and converts raw missing values, including `0` and `9999`, into `NaN` before scaling.

## 3. Validation Components

| Component | Script | Validation Scope |
| --- | --- | --- |
| Daily comparison | `compare_legacy_modern.py` | Legacy/Modern TEC arrays, UTC epochs, spatial grid and missing-value masks |
| Framework D | `validate_16days.py` | Spatial anomaly counts and ratios |
| Framework A | `validate_temporal.py` | Temporal TEC inputs and selected anomaly results |
| Framework B+C | `validate_historical.py` | Historical daily TEC inputs and hourly metadata |
| Integrated validation | `run_integrated_validation.py` | Sequential execution and reporting of Framework D, A and B+C |

All validation utilities are located under `scripts/validation/gim/`.

## 4. Verified Configuration

The real-data validation was conducted using the following configuration:

| Parameter | Value |
| --- | --- |
| Data source | CODE GIM |
| UTC interval | 2022-01-01 to 2022-01-16 |
| Total days | 16 |
| Total hourly epochs | 384 |
| Physical spatial grid | 71 × 73 |
| Reference days | 15 |
| Observation days | 1 |
| Spatial window steps | 24 |
| Anomaly threshold | k = 3.0 |
| Selected grid point | 30°N, 70°E |

## 5. Running the Validation

Execute commands from the repository root using the project's Python environment.

### 5.1 Automated Tests

```powershell
python -m pytest -q tests/integration/gim
```

### 5.2 Integrated Real-Data Validation

```powershell
python -m scripts.validation.gim.run_integrated_validation `
    --legacy-dir "PATH_TO_LEGACY_YEAR_DIRECTORY" `
    --modern-dir "PATH_TO_MODERN_DIRECTORY" `
    --start 2022-01-01 `
    --days 16 `
    --reference-days 15 `
    --window-steps 24 `
    --latitude 30 `
    --longitude 70 `
    --k 3.0 `
    --report "gim3b6_c_report.json"
```

The Legacy directory should be the year-specific directory, such as `GIMTEC2022`.

The integrated runner executes Framework D, Framework A, and Framework B+C sequentially and writes an audit report containing execution parameters and validation results.

### 5.3 Dry Run

Use `--dry-run` to inspect the generated validation commands without executing the scientific comparisons.

## 6. Validation Results

The selected real-data validation produced the following results:

**Framework D — PASS

- Identical TEC values and missing-value masks across 16 paired UTC days.
- Identical 384 hourly epochs and 71 × 73 physical grids.
- Identical positive and negative spatial anomaly counts and ratios.

**Framework A — PASS

- Identical temporal TEC inputs and missing-value masks.
- Identical selected temporal anomaly results.
- The selected 24-hour observation window contained 12 positive and 0 negative anomalies.

**Framework B+C — PASS

- Identical historical daily TEC inputs.
- Identical hourly metadata.
- No interpolation applied.

**Integrated Validation — PASS

All three validation components completed successfully using the reorganized repository structure.

## 7. Scope and Limitations

These results establish numerical consistency between the Legacy and Modern CODE GIM workflows for the specified data interval and analysis configuration.

They do not constitute full reproduction of the original earthquake-related scientific findings.

In particular, the following remain outside the scope of this validation:

- Full Afghanistan and Japan earthquake-case reproduction.
- Multi-event statistical Z-test equivalence.
- K-means clustering equivalence across historical earthquake samples.
- Generalization to other data intervals or GIM products.
- Predictive model performance.

These tasks will be addressed separately during subsequent scientific validation stages.

## 8. Reproducibility Notes

Validation reports may contain local filesystem paths and should be reviewed before sharing.

Raw datasets, processed GIM files, temporary diagnostics, and generated JSON reports are not required in the Git repository.

The scientific framework and the validation utilities are maintained separately to preserve the original scientific methodology.
