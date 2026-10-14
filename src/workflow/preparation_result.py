"""Result contract for Stage 1 workflow preparation."""

from dataclasses import dataclass
from pathlib import Path

from src.temporal_anomaly.temporal_anomaly import (
    TemporalAnomalyResult,
)
from src.statistical_clustering.pipeline import (
    StatisticalClusteringResult,
)

from .workflow_config import WorkflowConfig


@dataclass(frozen=True)
class WorkflowPreparationResult:
    """Hold validated Framework A and B+C results for Stage 1."""

    config: WorkflowConfig
    temporal_result: TemporalAnomalyResult
    clustering_result: StatisticalClusteringResult
    temporal_plot_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.config, WorkflowConfig):
            raise TypeError(
                "config must be a WorkflowConfig."
            )

        if not isinstance(
            self.temporal_result,
            TemporalAnomalyResult,
        ):
            raise TypeError(
                "temporal_result must be a TemporalAnomalyResult."
            )

        if not isinstance(
            self.clustering_result,
            StatisticalClusteringResult,
        ):
            raise TypeError(
                "clustering_result must be a StatisticalClusteringResult."
            )

        if not isinstance(self.temporal_plot_path, Path):
            raise TypeError(
                "temporal_plot_path must be a Path."
            )