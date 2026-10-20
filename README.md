# Ionospheric TEC Anomaly Analysis Framework

This repository provides the scientific implementation of the ionospheric
TEC anomaly analysis framework developed for the associated IEEE JSTARS
study.

The framework is organized into three main components:

1. Temporal Anomaly Detection Framework
2. Statistical–Clustering Hybrid Module
3. Spatial Anomaly Verification Framework

The three scientific frameworks have been implemented and independently
validated for the Afghanistan case.

The repository also provides a staged research workflow for transferring
prepared research artifacts into spatial anomaly verification. Stage 1
produces a Preparation Manifest, while Stage 2 accepts a researcher-selected
UTC window and executes spatial anomaly analysis, visualization, and
structured summary export.

Stage 2 can be executed through either the Python API or a command-line
interface (CLI). Temporal-cluster selection and earthquake-related
interpretation remain researcher-controlled rather than automated.

The repository also includes Modern CODE GIM data adapters and a separate
Legacy–Modern validation suite for checking numerical consistency without
changing the existing scientific algorithms.

## Current Status

### 1. Temporal Anomaly Detection Framework

The Temporal Anomaly Detection Framework has been implemented and validated.

It includes:

- fixed-location TEC time-series extraction
- multi-day TEC time-series preparation
- quartile-based temporal anomaly detection
- temporal anomaly visualization
- synthetic software tests
- legacy numerical-equivalence validation
- Afghanistan case end-to-end validation

The validated Afghanistan case reproduces the expected temporal anomaly
classification:

- Positive: 37
- Normal: 610
- Negative: 97

### 2. Statistical–Clustering Hybrid Module

The Statistical–Clustering Hybrid Module has been implemented and validated.
Its current implementation consists of two stages: statistical analysis and
clustering-based temporal pattern extraction.

The statistical analysis stage includes:

- historical TEC dataset construction
- earthquake sample extraction
- earthquake subset selection
- population and subset anomaly calculation
- one-proportion z-test
- significant temporal–polarity pattern identification

The clustering stage includes:

- clustering feature construction
- circular encoding of hour-of-day
- feature standardization
- K-means clustering
- cluster centroid decoding
- temporal anchor extraction
- paper-style centroid presentation
- integrated clustering pipeline

For the Afghanistan case, the validated 30-day analysis window contains
34 statistically significant cells:

- Positive: 18
- Negative: 16

Using two clusters, the analysis reproduces the paper-style temporal anchors:

- Day -8, positive polarity
- Day -22, negative polarity

The implementation has been verified through synthetic tests, fixed
regression tests, and real-data numerical-equivalence validation against
the legacy implementation used in the associated study.

### 3. Spatial Anomaly Verification Framework

The Spatial Anomaly Verification Framework has been implemented and scientifically validated for the Afghanistan case.

It includes:

- GIM data loading and preprocessing
- spatial quartile-based anomaly detection
- positive and negative anomaly occurrence calculation
- spatial grid orientation normalization
- synthetic software tests
- legacy numerical-equivalence validation
- Afghanistan case production-only reproduction

The validated Afghanistan case reproduces the expected spatial anomaly results:

- Maximum positive anomaly ratio: 10.0%
- Maximum negative anomaly ratio: 85.0%
- Maximum negative anomaly location: 30.0°N, 70.0°E

The production implementation reproduces all four spatial anomaly matrices with exact numerical agreement against the legacy reference.

The spatial verification window is currently specified explicitly rather than automatically selected from clustering results.

### 4. Modern GIM Data Integration and Validation

Modern CODE GIM data interfaces have been added alongside the existing Legacy
loaders. They support daily TEC loading, UTC time-series assembly, and input
adaptation for Framework A, Framework B+C, and Framework D.

The Legacy–Modern validation suite compares the two processing paths using
paired CODE GIM datasets. For the selected January 1–16, 2022 interval, the
validation confirmed identical TEC values, missing-value masks, and hourly
alignment, as well as equivalent selected Framework A, B+C, and D outputs.
The 25th daily map is excluded; only 24 hourly epochs per UTC day are used.

This establishes numerical consistency for the tested configuration, not full
reproduction of the historical earthquake studies. See
[Legacy–Modern GIM Validation](docs/validation/gim_legacy_modern.md).

## Repository Structure

```text
src/
    data/
        modern_gim_loader.py
        modern_gim_series.py
        modern_gim_bridge.py

    temporal_anomaly/
        __init__.py
        tec_timeseries.py
        tec_timeseries_collection.py
        temporal_anomaly.py
        plotting.py

    statistical_clustering/
        __init__.py
        historical_tec.py
        earthquake_samples.py
        earthquake_subset.py
        population_anomaly.py
        z_test.py
        clustering.py
        feature_scaling.py
        kmeans_clustering.py
        centroid_decoding.py
        temporal_anchors.py
        centroid_presentation.py
        pipeline.py
        reproducibility.py

    spatial_verification/
        __init__.py
        gim_loader.py
        spatial_anomaly.py
        spatial_grid.py

    workflow/
        preparation_manifest.py
        explicit_window.py
        spatial_verification_workflow.py
        spatial_plot_export.py
        spatial_summary.py
        spatial_summary_export.py
        stage2_runner.py
        stage2_cli.py
        modern_temporal_input_adapter.py
        modern_historical_input_adapter.py
        modern_spatial_input_adapter.py

scripts/
    validation/gim/
        Legacy–Modern comparison and integrated real-data validation CLIs.

tests/
    Unit, integration, and regression tests for the scientific frameworks.

    integration/gim/
        Automated tests for the Legacy–Modern validation utilities.

    temporal_anomaly/
        Unit tests for the Temporal Anomaly Detection Framework.

    statistical_clustering/
        Unit and integration tests for the Statistical–Clustering
        Hybrid Module.

    spatial_verification/
        Unit tests for spatial anomaly computation, grid orientation,
        GIM loading, and temporal alignment.

    workflow/
        Unit, integration, regression, and CLI end-to-end tests
        for the staged research workflow.

    regression/
        Fixed Afghanistan regression references and tests.

docs/
    validation/gim_legacy_modern.md
        Modern GIM equivalence validation procedure, results, and limits.

validation/
    Case-specific scientific validation and legacy-equivalence checks.

    temporal_anomaly/
        Afghanistan structural, numerical-equivalence, and
        end-to-end validation for the Temporal Anomaly Detection Framework.

    statistical_clustering/
        Afghanistan real-data validation for the statistical and
        clustering workflows.

    spatial_verification/
        Afghanistan GIM loading equivalence and production-only
        spatial anomaly reproduction.

    legacy/
        Legacy reference implementations retained for numerical-
        equivalence validation.
```

## Dependencies

The current implementation requires:

- Python 3.10+
- NumPy
- Matplotlib
- SciPy
- scikit-learn
- pytest

Install the required packages with:

```bash
python -m pip install -r requirements.txt
```

## Testing

The Statistical–Clustering Hybrid Module can be tested independently with:

```bash
python -m pytest tests/statistical_clustering tests/regression -q
```

These tests include software-level unit tests, integration tests, and a
fixed Afghanistan regression test.

All three scientific frameworks are covered by the repository test suite.

Run the complete software test suite with:

```bash
python -m pytest tests -q
```

### Stage 2 Workflow and CLI Tests

The Stage 2 workflow is covered by unit tests, synthetic integration
tests, failure-injection tests, and command-line integration tests.

Run the CLI unit tests with:

```bash
python -m pytest tests/workflow/test_stage2_cli.py -v
```

Run the CLI end-to-end integration tests with:

```bash
python -m pytest tests/workflow/test_stage2_cli_integration.py -v
```

Run the complete regression suite with:

```bash
python -m pytest tests/ -q
```

The test suite includes the Modern GIM adapters and Legacy–Modern validation
utilities. Run `python -m pytest -q` to obtain the current test count; the
previously documented 412-test baseline predates these additions.

The CLI integration tests use synthetic GIM datasets and verify actual
PNG and JSON generation, explicit UTC window handling, output protection,
Stage 1 artifact preservation, and consistency between CLI and Python API
execution.

### Legacy–Modern GIM Validation Tests

Run the validation utility tests from the repository root:

```bash
python -m pytest -q tests/integration/gim
```

The real-data integration runner is available as:

```bash
python -m scripts.validation.gim.run_integrated_validation --help
```

Real-data comparisons require separately supplied Legacy and Modern CODE GIM
files. See [validation instructions](docs/validation/gim_legacy_modern.md)
for configuration, tested results, and limitations.

## Stage 2 Research Workflow

The Stage 2 workflow provides a reproducible execution interface for
spatial ionospheric TEC anomaly verification.

It consumes an existing Stage 1 Preparation Manifest and a researcher-
selected UTC verification window. It then performs spatial anomaly
analysis and exports visual and structured research artifacts.

### Workflow Overview

The execution sequence is:

1. Load the Stage 1 Preparation Manifest.
2. Validate the explicitly selected UTC verification window.
3. Load and process the required GIM data.
4. Compute positive and negative spatial anomaly occurrence ratios.
5. Generate positive and negative spatial anomaly maps.
6. Export a structured Spatial Summary JSON.

The CLI delegates scientific computations to the existing Stage 2
orchestrator. It does not implement separate anomaly calculations.

### Command-Line Interface

Display the available CLI arguments:

```bash
python -m src.workflow.stage2_cli --help
```

Example execution:

```bash
python -m src.workflow.stage2_cli \
    --manifest /path/to/case/preparation_manifest.json \
    --dataset-dir /path/to/gim_dataset_prefix \
    --start-time 2022-05-28T06:00:00Z \
    --end-time 2022-05-29T05:00:00Z \
    --latitude 33.020 \
    --longitude 69.464 \
    --magnitude 6.0 \
    --reference-days 3 \
    --k 3.0
```

For Windows PowerShell, use a backtick (`` ` ``) instead of a
backslash (`\`) for command continuation, or enter the command
on a single line.

The paths above are placeholders and must be replaced with paths
matching the local research environment and GIM loader configuration.

The start and end times must be explicitly supplied by the researcher.
The workflow does not automatically select a verification window from
temporal clustering results.

### CLI Arguments

| Argument | Required | Description |
| --- | --- | --- |
| `--manifest` | Yes | Stage 1 Preparation Manifest JSON path |
| `--dataset-dir` | Yes | GIM dataset directory or prefix expected by the loader |
| `--start-time` | Yes | Explicit UTC verification start time |
| `--end-time` | Yes | Explicit UTC verification end time |
| `--latitude` | Yes | Earthquake epicenter latitude |
| `--longitude` | Yes | Earthquake epicenter longitude |
| `--magnitude` | Yes | Earthquake magnitude |
| `--reference-days` | No | Reference days; default: 15 |
| `--k` | No | Quartile threshold multiplier; default: 3.0 |
| `--output-dir` | No | Output directory; default: `spatial/` under the manifest directory |

### Output Artifacts

A successful Stage 2 execution produces three artifacts:

- Positive spatial anomaly map (PNG).
- Negative spatial anomaly map (PNG).
- Spatial Summary (JSON).

The filenames contain the case identifier and the selected UTC
verification window.

The Spatial Summary records the analysis configuration, spatial anomaly
results, artifact references, and verification metadata.

The verification method is recorded as `visual_inspection`, with
`automatic_decision` set to `null`.

Spatial anomaly occurrence ratios are quantitative analysis results.
They must not be interpreted as automatic confirmation of an
earthquake-related ionospheric precursor.

### CLI Exit Codes

| Exit code | Meaning |
| --- | --- |
| `0` | Successful execution |
| `1` | Scientific workflow or filesystem execution failure |
| `2` | Invalid command-line arguments or research inputs |
| `3` | Existing output artifact conflict |

### Research Integrity and Execution Limitations

The Stage 2 V1 workflow follows these principles:

- The UTC verification window must be explicitly selected by the researcher.
- Temporal clustering results are not automatically converted into spatial verification windows.
- Existing output artifacts are not overwritten.
- Stage 1 artifacts are preserved during Stage 2 execution.
- Spatial verification outputs are intended for researcher inspection.
- No automatic earthquake precursor decision is produced.
- Execution assumes a single writer for each research case and output window.

Artifact export includes filesystem failure handling and cleanup
mechanisms. However, the current implementation does not guarantee
a fully atomic transaction across all PNG and JSON outputs, and it
does not provide multi-process concurrency protection.

### Synthetic Testing and Research Data

Automated CLI integration tests use synthetic GIM data to verify
software behavior and numerical reproducibility.

These tests are distinct from the Afghanistan real-data scientific
validation described elsewhere in this README.

Real GIM datasets and local research artifacts are not included
in the repository.

## Scientific Validation

Real-data validation scripts for the Statistical–Clustering Hybrid Module
are located in:

```text
validation/statistical_clustering/
```

They validate the Afghanistan workflow sequentially through:

1. historical TEC reconstruction
2. earthquake sample extraction
3. earthquake subset selection
4. population anomaly calculation
5. one-proportion z-test
6. clustering and temporal-anchor extraction

The legacy implementations used for numerical-equivalence comparisons are
retained separately under:

```text
validation/legacy/statistical_clustering/
```

These legacy scripts are reference implementations for scientific
validation and are not the production interface of the framework.

### Legacy–Modern CODE GIM Equivalence

An additional validation suite is maintained in `scripts/validation/gim/`.
It verifies selected Legacy/Modern CODE GIM inputs and Framework A, B+C,
and D outputs, independently of the existing Afghanistan reproduction checks.
The documented January 1–16, 2022 integration run passed after the repository
reorganization. This does not establish multi-event statistical or clustering
equivalence, or full earthquake-case reproduction.

Detailed methods and commands are documented in
[Legacy–Modern GIM Validation](docs/validation/gim_legacy_modern.md).

## External Validation Data

Research data and local validation artifacts are not distributed directly
with this repository.

The Statistical–Clustering validation workflow uses two external data
locations:

- CODE GIM data
- Afghanistan historical TEC and earthquake data

Default local paths and environment-variable overrides are defined in:

```text
validation/statistical_clustering/config.py
```

The data locations can be overridden with the following environment
variables:

```text
IONO_CODE_GIM_DIR
IONO_GIMTEC_DATASET_DIR
```

This allows the validation workflow to be reproduced on another system
without modifying the validation scripts themselves.

GIM/IONEX data acquisition and parsing are handled separately from the
scientific analysis framework.

## Reproducibility

The Statistical–Clustering Hybrid Module includes utilities for recording
the software environment and effective K-means configuration, including
Python, NumPy, SciPy, and scikit-learn versions and the clustering
parameters used at runtime.

The reproducibility utilities are provided in:

```text
src/statistical_clustering/reproducibility.py
```

### Stage 2 Reproducibility

Stage 2 reproducibility is supported through explicit UTC window
selection, validated analysis parameters, structured spatial summaries,
and deterministic output naming.

The workflow maintains a separation between numerical anomaly
analysis and researcher interpretation.

Synthetic end-to-end integration tests verify that CLI execution and
direct Python API execution produce equivalent Spatial Summary results
when supplied with the same input data and analysis parameters.

These software reproducibility tests complement, rather than replace,
the real-data scientific validation of the Afghanistan case.

## Development Status

The repository is under active development.

Current progress:

- Temporal Anomaly Detection Framework — implemented and scientifically validated.
- Statistical–Clustering Hybrid Module — implemented and scientifically validated.
- Spatial Anomaly Verification Framework — implemented and scientifically validated for the Afghanistan case.
- Stage 1 Preparation Manifest — implemented and tested.
- Stage 2 Spatial Verification Workflow — implemented and tested.
- Stage 2 CLI — implemented and validated through synthetic end-to-end integration tests.
- Modern CODE GIM adapters — implemented and tested for Framework A, B+C, and D inputs.
- Legacy–Modern CODE GIM validation suite — selected 16-day real-data integration validation passed.

The full test count should be refreshed from the latest `python -m pytest -q` run before release.

The staged workflow supports reproducible spatial verification using
researcher-selected UTC windows and structured research artifacts.

A fully automated pipeline coupling temporal anomaly detection,
statistical clustering, verification-window selection, and scientific
interpretation is not yet provided.

Future development will focus on extending workflow integration while
preserving scientific reproducibility and researcher control.

## License

License information will be provided with the finalized repository.
