"""Synthetic integration tests for Framework A and Workflow Adapter."""

from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from src.temporal_anomaly.temporal_anomaly import (
    detect_temporal_anomalies,
)
from src.workflow.temporal_adapter import (
    save_temporal_analysis_plot,
)


def make_synthetic_temporal_data():
    """Create 3 reference days and 1 observation day."""

    start_time = datetime(2022, 5, 25)

    epochs = np.array(
        [
            start_time + timedelta(hours=i)
            for i in range(96)
        ],
        dtype=object,
    )

    tec = np.full(96, 10.0, dtype=float)

    # Observation day begins at index 72.
    # Inject one positive and one negative anomaly.
    tec[72 + 6] = 30.0
    tec[72 + 18] = 2.0

    return epochs, tec


def test_synthetic_temporal_detection_and_plot(tmp_path):
    epochs, tec = make_synthetic_temporal_data()

    # Step 1: Real Framework A detection.
    result = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=3,
        threshold_multiplier=3.0,
        min_reference_samples=3,
    )

    # Step 2: Validate the scientific result.
    assert len(result.epochs) == 24
    assert len(result.observed) == 24
    assert len(result.anomaly) == 24

    expected_anomaly = np.zeros(24, dtype=int)
    expected_anomaly[6] = 1
    expected_anomaly[18] = -1

    np.testing.assert_array_equal(
        result.anomaly,
        expected_anomaly,
    )

    np.testing.assert_allclose(
        result.median,
        np.full(24, 10.0),
    )

    np.testing.assert_allclose(
        result.upper_bound,
        np.full(24, 10.0),
    )

    np.testing.assert_allclose(
        result.lower_bound,
        np.full(24, 10.0),
    )

    assert result.epochs[0] == datetime(2022, 5, 28, 0)
    assert result.epochs[-1] == datetime(2022, 5, 28, 23)

    # Step 3: Real Workflow Adapter + real plotter.
    output_path = tmp_path / "temporal_anomaly.png"

    saved_path = save_temporal_analysis_plot(
        result,
        output_path,
        title="Synthetic Temporal Anomaly Integration",
    )

    # Step 4: Validate the generated artifact.
    assert saved_path == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0

    # PNG file signature.
    assert output_path.read_bytes()[:8] == (
        b"\x89PNG\r\n\x1a\n"
    )

    # The adapter should close the created figure.
    assert plt.get_fignums() == []