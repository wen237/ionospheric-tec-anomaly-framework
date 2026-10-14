"""Tests for Framework A workflow adapter."""

from datetime import datetime, timedelta
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from src.temporal_anomaly.temporal_anomaly import (
    TemporalAnomalyResult,
)
from src.workflow.temporal_adapter import (
    save_temporal_analysis_plot,
)


def make_temporal_result():
    epochs = tuple(
        datetime(2022, 5, 28) + timedelta(hours=i)
        for i in range(3)
    )

    observed = np.array([10.0, 20.0, 10.0])
    q1 = np.array([10.0, 10.0, 10.0])
    median = np.array([10.0, 10.0, 10.0])
    q3 = np.array([10.0, 10.0, 10.0])

    return TemporalAnomalyResult(
        epochs=epochs,
        observed=observed,
        q1=q1,
        median=median,
        q3=q3,
        upper_bound=np.array([10.0, 10.0, 10.0]),
        lower_bound=np.array([10.0, 10.0, 10.0]),
        anomaly=np.array([0, 1, 0]),
        reference_days=3,
        threshold_multiplier=3.0,
        min_reference_samples=3,
    )


@patch("src.workflow.temporal_adapter.plot_temporal_anomaly")
def test_save_plot_calls_validated_plotter(mock_plot, tmp_path):
    fig, ax = plt.subplots()
    mock_plot.return_value = (fig, ax)

    output_path = tmp_path / "temporal_anomaly.png"

    result = save_temporal_analysis_plot(
        make_temporal_result(),
        output_path,
        title="Afghanistan 2022",
    )

    assert result == output_path
    assert output_path.is_file()

    mock_plot.assert_called_once()
    assert mock_plot.call_args.kwargs["title"] == "Afghanistan 2022"

    assert not plt.fignum_exists(fig.number)


def test_reject_invalid_result(tmp_path):
    with pytest.raises(TypeError, match="TemporalAnomalyResult"):
        save_temporal_analysis_plot(
            "invalid",
            tmp_path / "plot.png",
        )


def test_reject_invalid_output_path():
    with pytest.raises(TypeError, match="Path"):
        save_temporal_analysis_plot(
            make_temporal_result(),
            "plot.png",
        )


def test_reject_non_png_output(tmp_path):
    with pytest.raises(ValueError, match=".png"):
        save_temporal_analysis_plot(
            make_temporal_result(),
            tmp_path / "plot.pdf",
        )


def test_reject_invalid_title(tmp_path):
    with pytest.raises(TypeError, match="title"):
        save_temporal_analysis_plot(
            make_temporal_result(),
            tmp_path / "plot.png",
            title=123,
        )


def test_reject_empty_temporal_result(tmp_path):
    result = make_temporal_result()

    object.__setattr__(result, "epochs", tuple())

    with pytest.raises(ValueError, match="must not be empty"):
        save_temporal_analysis_plot(
            result,
            tmp_path / "plot.png",
        )


def test_reject_mismatched_lengths(tmp_path):
    result = make_temporal_result()

    object.__setattr__(
        result,
        "anomaly",
        np.array([0, 1]),
    )

    with pytest.raises(ValueError, match="matching lengths"):
        save_temporal_analysis_plot(
            result,
            tmp_path / "plot.png",
        )


def test_reject_invalid_anomaly_classification(tmp_path):
    result = make_temporal_result()

    object.__setattr__(
        result,
        "anomaly",
        np.array([0, 2, 0]),
    )

    with pytest.raises(ValueError, match="classifications"):
        save_temporal_analysis_plot(
            result,
            tmp_path / "plot.png",
        )