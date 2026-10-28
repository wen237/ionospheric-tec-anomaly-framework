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

The repository also provides staged research workflow components for
transferring prepared scientific artifacts into spatial anomaly verification.
The Stage 1 Preparation Manifest records references to temporal analysis and
clustering outputs, while Stage 2 accepts a researcher-selected UTC window
and executes spatial anomaly analysis, visualization, and structured summary
export.

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

The standard B+C workflow preserves Framework B's complete Day -30 through
Day +30 statistical and significance results, but selects only Day -30 through
Day 0 (inclusive) before Framework C clustering. With a different
`observation_days`, the selected range is `-observation_days..0`. Day 0 is the
earthquake's UTC calendar date. Clustering summaries report this selected
range and its cell counts separately from the full-window significance counts.

Clustering summaries now use **schema V2** (`schema_version: 2`). This is an
explicit contract change from V1, where `clustering.n_significant_cells`
counted nonzero cells over the entire supplied significance mask. V2 defines
that count over the selected pre-event mask and adds these `clustering` fields:
`window_selection` (`"pre_event"`), inclusive `relative_day_start` /
`relative_day_end`, and selected `positive_mask_count` / `negative_mask_count`.
The `statistical_significance` section retains full-window counts and bounds;
overlap diagnostics and Legacy mask encoding are unchanged.

Consumers that interpret clustering results must check `schema_version` and
handle V1 and V2 scopes explicitly, or reject unsupported versions. Existing V1
files are not migrated; changing their version number alone cannot recover
pre-event counts or anchors. Produce V2 results by rerunning the corrected
workflow with the original inputs. Preparation Manifest and Spatial Summary
remain independently versioned at V1. Stage 2 checks the clustering artifact's
path and existence without interpreting its JSON schema; that check does not
validate either summary format.

The Python `StatisticalClusteringWorkflowResult` retains the original B result
in `significance` and adds required fields `clustering_mask` (a copied
`(observation_days + 1, 24)` mask) and `clustering_relative_days` (its copied
`-observation_days..0` row axis). Its `n_significant_cells` counts nonzero cells
in that selected mask. Code constructing the dataclass directly must provide
both new fields; prefer `run_clustering_workflow()` to obtain a validated result.

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

The historical earthquake catalog has also been checked against the original
Afghanistan catalog: 741 representative event dates and magnitudes match, and
74 events satisfy the M >= 6.0 selection and usable-window criteria. Four
event coordinates differ and remain documented for review. On 2026-10-28,
the original saved 1999–2021 TEC together with the verified filtered USGS
catalog reproduced all five historical B+C references above. Date-aligned
outputs also matched the Legacy catalog and existing Legacy algorithms.
The newly downloaded 23-year Modern GIM archive is **not required**.

#### Reproduce Historical Afghanistan B+C

From the repository root, using an environment with the project dependencies:

```bash
python -m examples.reproduce_afghanistan_historical_bc \
    --tec /path/to/tec33.092_69.514.npy \
    --catalog /path/to/afghanistan_usgs_filtered.csv \
    --legacy-eqlist /path/to/eqlist.npy \
    --output-dir outputs/afghanistan_historical_bc
```

`--legacy-eqlist` is optional. On PowerShell, use backticks for line
continuation, or enter the command on one line. The local project interpreter
can be invoked as `.\.venv\Scripts\python.exe`.

The example calls the five production B+C adapters with the fixed 1999–2021,
M >= 6.0, 30-day observation, 15-day reference, quartile multiplier 3.0,
critical z 1.96, pre-event Day -30..0, and K-means k=2 / random state 42
configuration. It accepts TEC shapes `(201624,)`, `(201624,1)` and `(8401,24)`
in chronological order, rejects missing/non-finite values, and requires zero
adapter interpolation and unchanged TEC values. The UTC hourly timeline is
assigned from the Legacy convention; NPY does not contain timestamps or
historical interpolation provenance.

The output is `afghanistan_historical_bc_summary.json`, with input paths and
SHA-256 hashes, before/after input integrity verification, coverage, dependency
versions and installed K-means defaults (including `n_init`), population and
subset statistics, selected event dates, full-B and pre-event-C significance
and overlap diagnostics, centroids, cluster composition, anchors, silhouette,
and expected-versus-observed reference comparisons. Supplying Legacy data
also runs the same production pipeline for that catalog and compares outputs
after UTC-date alignment.

This standalone report has `summary_type: "afghanistan_historical_bc_reproduction"`
and its own schema version 1. It is not the Preparation workflow's clustering
summary V2 or a Stage 2 manifest; no Framework A placeholder is constructed.
Existing output is rejected (exit 3) unless `--overwrite` explicitly authorizes
replacement. Invalid inputs return exit 2. A completed calculation returns
exit 0 even when references differ: inspect `reference_comparison.all_match`
and, when provided, `legacy_comparison.all_match`. Differences are reported
without fitting parameters to the references. No spatial window or precursor
interpretation is generated.

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

A separate Modern CODE GIM Afghanistan 2022 reproduction has also passed
six reported checks: 120 verification hours on 5,183 grid cells, a
positive maximum of 10.0% at (-22.5°, -155°) and (-22.5°, -150°),
and a negative maximum of 85.0% at (30.0°N, 70.0°E).
The corrected Modern visualization uses ascending physical latitude,
complete grid boundaries, coastlines and national borders, and consistent
maximum-location coordinates in the spatial summary. These reported
checks do not by themselves establish equality of every global grid cell.

The spatial verification window is currently specified explicitly rather
than automatically selected from clustering results. The validated Modern
GIM spatial calculation is available separately; an opt-in Modern input
path for the main Stage 2 CLI is planned, not yet complete.

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

### Modern Afghanistan 2022 Reproduction Examples

The `examples/` scripts make the verified Modern case reproducible when
the external 2022 CODE GIM daily NPZ files are available:

- `reproduce_afghanistan_temporal_case.py` — Framework A's 744-hour case:
  37 positive, 610 normal and 97 negative anomaly hours.
- `review_afghanistan_framework_d_windows.py` — a review-only daily
  Framework A anomaly report. The reference May 28–June 1, 2022 interval
  contains 18, 16, 24, 20 and 17 negative hours, respectively (95/120).
  This **does not** automatically select or scientifically confirm a window.
- `reproduce_afghanistan_spatial_visuals.py` — Modern Framework D's
  May 28–June 1 spatial maps and peak summary, using 15 reference days
  and a quartile threshold multiplier of 3.0.

Generated PNG/JSON outputs and research NPZ/NPY data are not committed to
the repository. The `outputs/` directory is ignored by Git.

## Repository Structure

```text
AGENTS.md
    AI-agent instructions and scientific safeguards.

examples/
    reproduce_afghanistan_historical_bc.py
    reproduce_afghanistan_temporal_case.py
    reproduce_afghanistan_spatial_visuals.py
    review_afghanistan_framework_d_windows.py

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
    agent_handoff.md
        Verified results, remaining tasks, and AI-agent acceptance criteria.

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

Modern paper-style spatial maps can optionally overlay coastlines and
national borders using Cartopy. Install it separately when generating those
maps:

```bash
python -m pip install cartopy
```

Cartopy is a visualization dependency, not a requirement for numerical
TEC anomaly calculations. Its Natural Earth geographic layers may require
an initial download.

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

Final verification on 2026-10-28, including the atomic-output follow-up:
28 historical B+C CLI tests passed, and the complete repository suite passed 576 tests
(`python -B -m pytest tests -q -p no:cacheprovider`), with one expected warning
from a simulated Stage 2 cleanup failure. This includes the scientific
frameworks, the historical B+C CLI's 28 integration and failure-injection cases, staged
workflow, Modern CODE GIM adapters, and Legacy–Modern validation utilities.

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

## Research & Publications

The scientific methods implemented in this repository are associated with the
following peer-reviewed publication:

Y.-C. Wen, J.-Y. Liu, C.-Y. Lin, and M.-C. Su,
"A Hybrid Approach Using Statistics and Unsupervised Learning to Investigate
the Impact of Ionospheric Storm Disturbances on Pre-Earthquake Total Electron
Content Anomalies," *IEEE Journal of Selected Topics in Applied Earth
Observations and Remote Sensing*, vol. 19, pp. 23747–23759, 2026.

- [IEEE Xplore paper](https://ieeexplore.ieee.org/document/11595710)
- [DOI: 10.1109/JSTARS.2026.3709918](https://doi.org/10.1109/JSTARS.2026.3709918)
- [Google Scholar profile](https://scholar.google.com/citations?user=8P4lE88AAAAJ&hl=zh-TW)
- [IEEE Xplore author profile](https://ieeexplore.ieee.org/author/152460869663948)

The existing Afghanistan scientific validation results described below are
distinct from full end-to-end reproduction of the published case using the
Modern CODE GIM interface, which has not yet been demonstrated.

## Citation

If you use the scientific methods in academic research, please cite the
associated publication:

```bibtex
@article{Wen2026IonosphericTEC,
  author  = {Wen, Yun-Cheng and Liu, Jann-Yenq and Lin, Chi-Yen and Su, Mu-Chun},
  title   = {A Hybrid Approach Using Statistics and Unsupervised Learning to Investigate the Impact of Ionospheric Storm Disturbances on Pre-Earthquake Total Electron Content Anomalies},
  journal = {IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing},
  volume  = {19},
  pages   = {23747--23759},
  year    = {2026},
  doi     = {10.1109/JSTARS.2026.3709918}
}
```

## Scientific Validation

Real-data validation scripts for the Statistical–Clustering Hybrid Module
are located in:

```text
validation/statistical_clustering/
```

They validate the Afghanistan workflow sequentially through:

1. historical TEC reconstruction (archival equivalence check; not required
   by the saved-TEC reproduction CLI)
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

The three scientific framework implementations are maintained alongside
Legacy references, regression tests, and selected real-data validation.

**Verified work:**

- Framework A: Modern Afghanistan 2022 temporal reproduction
  (37 positive, 610 normal, 97 negative hours).
- Framework B+C: original 1999–2021 TEC plus verified USGS catalog reproduced
  74 selected events, 34 pre-event significant cells (18 positive / 16 negative),
  Day -8 positive and Day -22 negative anchors, and silhouette
  0.31105623341145205. A reproducible example CLI and synthetic integration
  tests cover this path, with optional UTC-date-aligned Legacy comparison.
- Framework D: Modern Afghanistan 2022 spatial calculation and corrected
  geographic visualization (positive maximum 10%, negative maximum 85%).
- Stage 1 Preparation Manifest, legacy-oriented Stage 2 workflow and CLI,
  and selected Legacy–Modern GIM equivalence tests.

**Remaining work:**

- Derive reviewable candidate spatial windows from Framework A evidence and
  B+C statistical/clustering results, while preserving researcher approval.
- Integrate a separately selectable Modern GIM input into the formal Stage 2
  workflow without breaking the existing Legacy path.
- Run and document current full-suite tests after further changes.

The repository is being prepared for AI-agent-assisted development. Coding
agents may handle implementation, testing and integration, while scientific
interpretation and final acceptance stay with the researcher. See
[AGENTS.md](AGENTS.md) and [AI Agent Handoff](docs/agent_handoff.md).

The full autonomous A+B+C-to-D workflow is **not yet implemented**.

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 Yun-Cheng Wen.
