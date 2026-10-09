# Ionospheric TEC Anomaly Analysis Framework

This repository provides the scientific implementation of the ionospheric
TEC anomaly analysis framework developed for the associated IEEE JSTARS
study.

The framework is organized into three main components:

1. Temporal Anomaly Detection Framework
2. Statistical–Clustering Hybrid Module
3. Spatial Anomaly Verification Framework

The repository is being organized and validated module by module.
All three scientific frameworks have been implemented and independently
validated for the Afghanistan case. Their integration into a fully
automated end-to-end workflow remains future work.

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

## Repository Structure

```text
src/
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

tests/
    Unit, integration, and regression tests for the scientific frameworks.

    temporal_anomaly/
        Unit tests for the Temporal Anomaly Detection Framework.

    statistical_clustering/
        Unit and integration tests for the Statistical–Clustering
        Hybrid Module.

    spatial_verification/
        Unit tests for spatial anomaly computation, grid orientation,
        GIM loading, and temporal alignment.

    regression/
        Fixed Afghanistan regression references and tests.

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

## Development Status

The repository is under active development.

Current progress:

- Temporal Anomaly Detection Framework — implemented, structurally organized, and scientifically validated
- Statistical–Clustering Hybrid Module — implemented and scientifically validated
- Spatial Anomaly Verification Framework — implemented and scientifically validated for the Afghanistan case

The three scientific frameworks have been independently implemented and validated. However, the repository does not yet provide a fully coupled end-to-end pipeline across all three frameworks.

## License

License information will be provided with the finalized repository.
