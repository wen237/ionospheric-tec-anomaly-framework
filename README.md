# Ionospheric TEC Anomaly Analysis Framework

This repository provides the scientific implementation of the ionospheric
TEC anomaly analysis framework developed for the associated IEEE JSTARS
study.

The framework is organized into three main components:

1. Temporal Anomaly Detection Framework
2. Statistical–Clustering Hybrid Module
3. Spatial Anomaly Verification Framework

The repository is currently being organized and validated module by module.

## Current Status

### Temporal Anomaly Detection Framework

The temporal anomaly detection module has been implemented and validated.

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

## Repository Structure

```text
src/
    temporal_anomaly.py
    tec_timeseries.py
    tec_timeseries_collection.py
    plot_temporal_anomaly.py

tests/
    Software-level and synthetic tests.

validation/
    Case-specific scientific validation and legacy-equivalence checks.

See validation/README.md for details about the Afghanistan validation
workflow and required local data.

Dependencies

The current implementation requires:

Python 3.10+
NumPy
Matplotlib
Development Status

The repository is under active development.

Current progress:

 Temporal Anomaly Detection Framework
 One-Proportion z-Test
 K-Means Clustering
 Statistical–Clustering Hybrid Module
 Spatial Anomaly Verification Framework
Data

Research data and local validation artifacts are not distributed directly
with this repository.

GIM/IONEX data acquisition and parsing are handled separately from the
scientific analysis framework.

License

License information will be provided with the finalized repository.
