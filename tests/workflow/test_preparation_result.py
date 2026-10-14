from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.temporal_anomaly.temporal_anomaly import (
    TemporalAnomalyResult,
)
from src.statistical_clustering.pipeline import (
    StatisticalClusteringResult,
)
from src.workflow.preparation_result import (
    WorkflowPreparationResult,
)
from src.workflow.workflow_config import WorkflowConfig


def make_config():
    return WorkflowConfig(
        case_id="afghanistan_2022",
        output_dir=Path("outputs"),
        temporal_data_dir=Path("data/temporal"),
        statistical_data_dir=Path("data/statistical"),
        spatial_dataset_dir=Path("data/gim"),
    )


def make_preparation_result(**overrides):
    values = {
        "config": make_config(),
        "temporal_result": object.__new__(
            TemporalAnomalyResult
        ),
        "clustering_result": object.__new__(
            StatisticalClusteringResult
        ),
        "temporal_plot_path": Path(
            "outputs/afghanistan_2022/temporal_anomaly.png"
        ),
    }

    values.update(overrides)

    return WorkflowPreparationResult(**values)


def test_valid_preparation_result():
    result = make_preparation_result()

    assert result.config.case_id == "afghanistan_2022"
    assert isinstance(
        result.temporal_result,
        TemporalAnomalyResult,
    )
    assert isinstance(
        result.clustering_result,
        StatisticalClusteringResult,
    )


def test_reject_invalid_config():
    with pytest.raises(TypeError, match="WorkflowConfig"):
        make_preparation_result(config="invalid")


def test_reject_invalid_temporal_result():
    with pytest.raises(TypeError, match="TemporalAnomalyResult"):
        make_preparation_result(temporal_result="invalid")


def test_reject_invalid_clustering_result():
    with pytest.raises(
        TypeError,
        match="StatisticalClusteringResult",
    ):
        make_preparation_result(clustering_result="invalid")


def test_reject_invalid_plot_path():
    with pytest.raises(TypeError, match="Path"):
        make_preparation_result(
            temporal_plot_path="temporal_anomaly.png"
        )


def test_preparation_result_is_immutable():
    result = make_preparation_result()

    with pytest.raises(FrozenInstanceError):
        result.temporal_plot_path = Path("another.png")