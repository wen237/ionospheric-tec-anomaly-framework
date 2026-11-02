"""Framework A workflows: existing plot output and review-only composition."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np

from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.temporal_anomaly import (
    TemporalAnomalyResult,
    detect_temporal_anomalies,
)

from .temporal_input_adapter import load_temporal_tec_from_gim
from .planning_evidence import (
    _epochs, _integer, _location, _number, _provenance, _text, _utc_hour, _vector,
    build_temporal_evidence, load_historical_bc_evidence,
)
from .window_planning import plan_anchor_based_daily_windows


_REVIEW_INPUT_ID = "computed:temporal-review-input-series-v1"


@dataclass(frozen=True)
class TemporalWorkflowResult:
    """Framework A result and its supporting workflow outputs."""

    time_series: TECTimeSeries
    anomaly_result: TemporalAnomalyResult
    plot_path: Path


def run_temporal_review(
    time_series: TECTimeSeries,
    *,
    case_id: str,
    analysis_start: datetime,
    analysis_end: datetime,
    input_time_convention: str,
    historical_summary_path: str | Path,
    case_event: dict,
    selected_cluster_ids: Sequence[int],
    mode: str,
    reference_days: int = 15,
    threshold_multiplier: float = 3.0,
    min_reference_samples: int | None = None,
    provenance: dict | None = None,
) -> tuple[dict, dict, dict]:
    """Compute A once and return (temporal evidence, historical context, proposal).

    All artifacts retain their existing V1 schemas. Mode must explicitly be
    ``retrospective``. Bounds are inclusive hourly samples under the declared
    ``naive_utc`` or ``aware_utc`` convention; local time is never inferred.
    The full supplied series must be ordered, unique UTC hours and start at
    least reference_days before analysis_start (the detector's calendar startup
    requirement). Gaps/nonfinite TEC remain missing or unclassifiable. Missing
    calendar history raises ValueError; no parameters are relaxed or retried.
    Detector rows outside the requested bounds are omitted without changing
    their statistics/codes. Empty/missing analysis coverage uses V1 abstention.

    The summary is validated/read/hashed before A; B/C are NOT recomputed or
    relabeled as newly reproduced. Other inputs are validated by the existing
    evidence/planner contracts. Validation and I/O exceptions propagate; no
    fallback, file output, plotting, review records or protected execution occurs.

    Caller provenance is preserved; duplicate source identities and the reserved
    computed source identity are rejected as ambiguous. An additional source
    ``computed:temporal-review-input-series-v1`` binds the FULL input series,
    including reference/unused rows. Its SHA-256 covers domain prefix
    b'ionospheric-tec/temporal-review-input/v1\\0', then sorted compact UTF-8 JSON
    plus LF (convention, UTC epochs, validated location, little-endian TEC dtype),
    then C-order little-endian TEC bytes. It is not a raw-file hash or proof of
    original-source/observation quality; declared source hashes are not verified.
    Caller arrays/metadata are not modified. Concurrent caller mutation is not
    an authenticated acquisition protocol.

    Example (series contains the preceding reference period):
        temporal, historical, proposal = run_temporal_review(
            series, case_id='case_a', analysis_start=start, analysis_end=end,
            input_time_convention='naive_utc', historical_summary_path=summary,
            case_event=event, selected_cluster_ids=[0], mode='retrospective',
        )
    """
    if mode != "retrospective":
        raise ValueError("This review workflow requires explicit retrospective mode.")
    if not isinstance(time_series, TECTimeSeries):
        raise TypeError("time_series must be a TECTimeSeries.")
    _text(case_id, "case_id")
    if input_time_convention not in ("naive_utc", "aware_utc"):
        raise ValueError("Declare input_time_convention as naive_utc or aware_utc.")
    start = _utc_hour(analysis_start, input_time_convention)
    end = _utc_hour(analysis_end, input_time_convention)
    if start > end:
        raise ValueError("analysis_start must not exceed analysis_end.")
    # Use the evidence contract for ALL timestamps, including reference rows.
    snapshot = replace(time_series, epochs=np.array(time_series.epochs, dtype=object, copy=True),
                       tec=np.array(time_series.tec, copy=True))
    times = _epochs(snapshot.epochs, input_time_convention)
    values = _vector(snapshot.tec, len(times), "time_series.tec")
    if not times:
        raise ValueError("time_series must not be empty.")
    location = _location(snapshot, times, values, input_time_convention)
    reference_days = _integer(reference_days, "reference_days", 1)
    threshold_multiplier = _number(threshold_multiplier, "threshold_multiplier", 0)
    if min_reference_samples is not None:
        min_reference_samples = _integer(min_reference_samples, "min_reference_samples", 1, reference_days)
    try:
        reference_start = start - timedelta(days=reference_days)
    except OverflowError as exc:
        raise ValueError("Reference period exceeds the supported UTC calendar.") from exc
    if times[0] > reference_start:
        raise ValueError("Input lacks the detector's full calendar reference period before analysis_start.")
    declared = _provenance(provenance)
    sources = declared["sources"] or []
    identities = [source["identity"] for source in sources]
    if len(set(identities)) != len(identities) or _REVIEW_INPUT_ID in identities:
        raise ValueError("Ambiguous or reserved provenance source identity.")
    canonical_values = values.astype(values.dtype.newbyteorder("<"), copy=False)
    header = dict(input_time_convention=input_time_convention,
                  epochs_utc=[epoch.isoformat().replace("+00:00", "Z") for epoch in times],
                  location=location, tec_dtype=canonical_values.dtype.str)
    digest = hashlib.sha256(b"ionospheric-tec/temporal-review-input/v1\x00")
    digest.update((json.dumps(header, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8"))
    digest.update(canonical_values.tobytes(order="C"))
    bound_provenance = dict(sources=sources + [dict(identity=_REVIEW_INPUT_ID, sha256=digest.hexdigest())],
                            processing_history=declared["processing_history"])
    historical = load_historical_bc_evidence(historical_summary_path)
    detected = detect_temporal_anomalies(snapshot.tec, snapshot.epochs, reference_days=reference_days,
        threshold_multiplier=threshold_multiplier, min_reference_samples=min_reference_samples)
    selected = np.array([start <= _utc_hour(epoch, input_time_convention) <= end for epoch in detected.epochs], dtype=bool)
    detected = replace(detected, **{name: getattr(detected, name)[selected].copy() for name in (
        "epochs", "observed", "q1", "median", "q3", "upper_bound", "lower_bound", "anomaly")})
    temporal = build_temporal_evidence(detected, case_id=case_id, expected_start=analysis_start,
        expected_end=analysis_end, input_time_convention=input_time_convention,
        provenance=bound_provenance, time_series=snapshot)
    proposal = plan_anchor_based_daily_windows(temporal, historical, case_event=case_event,
        selected_cluster_ids=selected_cluster_ids, mode=mode)
    return temporal, historical, proposal


def save_temporal_analysis_plot(
    result: TemporalAnomalyResult,
    output_path: Path,
    *,
    title: str | None = None,
) -> Path:
    """Load plotting only on use, retaining the workflow's patchable target."""
    from .temporal_adapter import save_temporal_analysis_plot as save_plot

    return save_plot(result, output_path, title=title)


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
