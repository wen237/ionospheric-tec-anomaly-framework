"""End-to-end Framework A workflow integration."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.temporal_anomaly import (
    TemporalAnomalyResult,
    detect_temporal_anomalies,
)

from .temporal_input_adapter import load_temporal_tec_from_gim
from .temporal_adapter import save_temporal_analysis_plot


@dataclass(frozen=True)
class TemporalWorkflowResult:
    """Framework A result and its supporting workflow outputs."""

    time_series: TECTimeSeries
    anomaly_result: TemporalAnomalyResult
    plot_path: Path


def run_temporal_workflow(
    dataset_dir: str | Path,
    start_time: datetime,
    end_time: datetime,
    *,
    latitude: float,
    longitude: float,
    output_path: Path,
    reference_days: int = 15,
    threshold_multiplier: float = 3.0,
    min_reference_samples: int | None = None,
    title: str | None = None,
) -> TemporalWorkflowResult:
    """Run Framework A from GIM files through temporal plot output.

    start_time and end_time are inclusive, naive UTC hourly epochs.
    """

    # 1. Load reference + observation TEC at selected location.
    series = load_temporal_tec_from_gim(
        dataset_dir=dataset_dir,
        start_time=start_time,
        end_time=end_time,
        latitude=latitude,
        longitude=longitude,
        reference_days=reference_days,
    )

    # 2. Run the validated Framework A detector.
    anomaly_result = detect_temporal_anomalies(
        tec=series.tec,
        epochs=series.epochs,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
        min_reference_samples=min_reference_samples,
    )

    # 3. Save the validated Framework A visualization.
    saved_path = save_temporal_analysis_plot(
        result=anomaly_result,
        output_path=output_path,
        title=title,
    )

    return TemporalWorkflowResult(
        time_series=series,
        anomaly_result=anomaly_result,
        plot_path=saved_path,
    )
