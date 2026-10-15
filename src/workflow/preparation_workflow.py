"""Framework A+B+C preparation workflow orchestration."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .workflow_config import WorkflowConfig
from .preparation_result import WorkflowPreparationResult

from .temporal_workflow import (
    TemporalWorkflowResult,
    run_temporal_workflow,
)
from .historical_input_adapter import (
    HistoricalDailyTECResult,
    prepare_historical_daily_tec,
)
from .statistical_analysis_adapter import (
    StatisticalAnalysisResult,
    run_statistical_analysis,
)
from .statistical_significance_adapter import (
    StatisticalSignificanceResult,
    run_statistical_significance,
)
from .clustering_adapter import (
    StatisticalClusteringWorkflowResult,
    run_clustering_workflow,
)


@dataclass(frozen=True)
class PreparationWorkflowRunResult:
    """Complete Framework A+B+C preparation results."""

    preparation: WorkflowPreparationResult
    temporal_workflow: TemporalWorkflowResult
    historical: HistoricalDailyTECResult
    statistical_analysis: StatisticalAnalysisResult
    statistical_significance: StatisticalSignificanceResult
    clustering_workflow: StatisticalClusteringWorkflowResult


def run_preparation_workflow(
    config: WorkflowConfig,
    *,
    temporal_start_time: datetime,
    temporal_end_time: datetime,
    latitude: float,
    longitude: float,
    historical_epochs,
    historical_tec,
    historical_start_date: date,
    historical_end_date: date,
    earthquake_dates,
    earthquake_magnitudes,
    observation_days: int = 30,
    reference_days: int = 15,
    threshold_multiplier: float = 3.0,
    minimum_magnitude: float = 6.0,
    critical_z: float = 1.96,
    n_clusters: int = 2,
    random_state: int = 42,
    allow_historical_interpolation: bool = False,
    min_reference_samples: int | None = None,
) -> PreparationWorkflowRunResult:
    """Execute Framework A and B+C without spatial verification.

    Temporal start/end are inclusive naive UTC hourly timestamps.
    Historical TEC is supplied as hourly timestamps and values.

    Framework D is intentionally excluded.
    """

    if not isinstance(config, WorkflowConfig):
        raise TypeError("config must be a WorkflowConfig.")

    # Validate the historical input first, before generating plots.
    historical = prepare_historical_daily_tec(
        epochs=historical_epochs,
        tec=historical_tec,
        start_date=historical_start_date,
        end_date=historical_end_date,
        allow_interpolation=allow_historical_interpolation,
    )

    # Framework B: historical population and earthquake subset.
    analysis = run_statistical_analysis(
        historical=historical,
        event_dates=earthquake_dates,
        magnitudes=earthquake_magnitudes,
        minimum_magnitude=minimum_magnitude,
        observation_days=observation_days,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
    )

    # Framework B: one-proportion z-test and significance mask.
    significance = run_statistical_significance(
        analysis=analysis,
        critical_z=critical_z,
    )

    # Framework C: validated K-Means and temporal anchors.
    clustering = run_clustering_workflow(
        significance=significance,
        n_clusters=n_clusters,
        random_state=random_state,
    )

    # Framework A: case-specific temporal anomaly analysis.
    # Run after B+C validation to avoid unnecessary plot output
    # when historical statistical preparation fails.
    plot_path = (
        config.output_dir
        / "temporal"
        / f"{config.case_id}_temporal_anomaly.png"
    )

    temporal = run_temporal_workflow(
        dataset_dir=config.temporal_data_dir,
        start_time=temporal_start_time,
        end_time=temporal_end_time,
        latitude=latitude,
        longitude=longitude,
        output_path=plot_path,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
        min_reference_samples=min_reference_samples,
        title=f"{config.case_id} - Temporal TEC Anomalies",
    )

    # Preserve the existing I3-1 public preparation contract.
    preparation = WorkflowPreparationResult(
        config=config,
        temporal_result=temporal.anomaly_result,
        clustering_result=clustering.clustering,
        temporal_plot_path=temporal.plot_path,
    )

    return PreparationWorkflowRunResult(
        preparation=preparation,
        temporal_workflow=temporal,
        historical=historical,
        statistical_analysis=analysis,
        statistical_significance=significance,
        clustering_workflow=clustering,
    )
