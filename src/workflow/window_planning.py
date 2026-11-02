"""Pure, review-only retrospective anchor-centered DAILY window proposals.

Scientific rule (anchor_based_daily_expansion_v1): a UTC day has at least
one valid target-polarity anomaly and no opposite-polarity anomalies. Normal
hours are allowed. Validate the anchor day, then expand each direction until
its first nonqualifying day. Anchor.hour never selects an intraday boundary.

Separate V1 quality rule: require all 24 hourly samples to be present and
classifiable. Missing/unclassifiable evidence blocks inclusion; such a stop
is an uncertain boundary, not a confirmed scientific polarity boundary.

Only explicitly selected cluster IDs are evaluated against an explicitly
supplied, traceable event time in retrospective mode. All other anchors are
retained as unselected context; tied dominant polarity abstains. Day 0 means
the event's UTC calendar date, not a strictly pre-earthquake interval. There
is no event-time truncation or prospective interpretation. This module has
no file I/O, detector calls, approval decisions or Framework D integration.
"""

from collections.abc import Sequence
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import math
import re

import numpy as np

from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.temporal_anomaly import TemporalAnomalyResult
from .planning_evidence import (
    HISTORICAL_EVIDENCE_TYPE,
    TEMPORAL_EVIDENCE_TYPE,
    build_historical_bc_evidence,
    build_temporal_evidence,
    evidence_to_json,
)


POLICY_NAME = "anchor_based_daily_expansion_v1"
_VALUES = ("observed", "q1", "median", "q3", "upper_bound", "lower_bound")
_CLASSIFICATIONS = ("positive", "negative", "valid_normal", "unclassifiable", "missing_timestamp")
_DAY = timedelta(days=1)


def _utc(value, *, hourly=False):
    if not isinstance(value, str):
        raise ValueError("UTC times must be explicit ISO 8601 strings.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid UTC timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must specify UTC.")
    if hourly and (parsed.minute or parsed.second or parsed.microsecond):
        raise ValueError("Evidence timestamps must be hourly.")
    return parsed.astimezone(timezone.utc)


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string.")
    return value


def _same_contract(supplied, rebuilt):
    if evidence_to_json(supplied) != evidence_to_json(rebuilt):
        raise ValueError("Evidence is inconsistent with the supported V1 contract.")


def _source_provenance(evidence):
    provenance = evidence["provenance"]
    return {name: provenance[name] for name in ("sources", "processing_history")}


def _temporal(evidence):
    """Validate serialized A via the existing builder, not a second detector.

    Restore V1's explicit nonfinite markers only to revalidate its existing
    result contract. Rebuilding must reproduce every field (including quality
    reasons and missing rows). No quartiles or thresholds are recomputed.
    """
    evidence = json.loads(evidence_to_json(evidence))
    if evidence["evidence_type"] != TEMPORAL_EVIDENCE_TYPE:
        raise ValueError("Expected case temporal anomaly evidence V1.")
    try:
        convention = evidence["input_time_convention"]

        def input_epoch(value):
            value = _utc(value, hourly=True)
            return value.replace(tzinfo=None) if convention == "naive_utc" else value

        epochs, codes = [], []
        values = {name: [] for name in _VALUES}
        for row in evidence["hourly"]:
            if type(row["result_present"]) is not bool:
                raise ValueError("result_present must be boolean.")
            if not row["result_present"]:
                continue
            code = row["anomaly_code"]
            if type(code) is not int or code not in (-1, 0, 1):
                raise ValueError("Anomaly code must be an integer -1, 0 or +1.")
            epochs.append(input_epoch(row["timestamp_utc"]))
            codes.append(code)
            for name in _VALUES:
                value = row[name]
                if value is None:
                    value = {"nan": np.nan, "positive_infinity": np.inf,
                             "negative_infinity": -np.inf}[row["nonfinite_values"][name]]
                elif type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError("Invalid evidence numeric value.")
                values[name].append(value)
        result = TemporalAnomalyResult(
            epochs=np.array(epochs, dtype=object), anomaly=np.array(codes, dtype=np.int8),
            **{name: np.array(items, dtype=float) for name, items in values.items()},
            **evidence["parameters"],
        )
        location = evidence["location"]
        series = None if location is None else TECTimeSeries(
            epochs=result.epochs, tec=result.observed, **location,
        )
        rebuilt = build_temporal_evidence(
            result, case_id=evidence["case_id"],
            expected_start=input_epoch(evidence["analysis"]["start_utc"]),
            expected_end=input_epoch(evidence["analysis"]["end_utc"]),
            input_time_convention=convention, provenance=_source_provenance(evidence), time_series=series,
        )
        _same_contract(evidence, rebuilt)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid temporal evidence V1: {exc}") from exc
    return evidence


def _historical(evidence):
    evidence = json.loads(evidence_to_json(evidence))
    if evidence["evidence_type"] != HISTORICAL_EVIDENCE_TYPE:
        raise ValueError("Expected historical B+C context evidence V1.")
    try:
        rebuilt = build_historical_bc_evidence(
            evidence["historical_summary"], provenance=_source_provenance(evidence),
        )
        if "summary_artifact" in evidence:
            artifact = evidence["summary_artifact"]
            if (set(artifact) != {"identity", "sha256", "size_bytes", "hash_verification"} or
                    not isinstance(artifact["sha256"], str) or
                    not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]) or
                    type(artifact["size_bytes"]) is not int or artifact["size_bytes"] < 0 or
                    artifact["hash_verification"] != "computed_from_read_bytes"):
                raise ValueError("Invalid summary_artifact metadata.")
            _text(artifact["identity"], "summary artifact identity")
            rebuilt["summary_artifact"] = artifact
        _same_contract(evidence, rebuilt)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid historical evidence V1: {exc}") from exc
    return evidence


def _daily(evidence):
    days = {}
    for row in evidence["hourly"]:
        day = _utc(row["timestamp_utc"], hourly=True).date()
        if day not in days:
            days[day] = {name: 0 for name in _CLASSIFICATIONS}
        days[day][row["classification"]] += 1
    daily = []
    for day, counts in sorted(days.items()):
        evidence_hours = sum(counts.values())
        outside = 24 - evidence_hours
        missing = counts["missing_timestamp"] + outside
        quality_reasons = []
        if missing:
            quality_reasons.append("missing_hours")
        if counts["unclassifiable"]:
            quality_reasons.append("unclassifiable_hours")
        daily.append(dict(
            date_utc=day.isoformat(), positive=counts["positive"], negative=counts["negative"],
            valid_normal=counts["valid_normal"], unclassifiable=counts["unclassifiable"],
            missing_hours=missing, explicit_missing_hours=counts["missing_timestamp"],
            outside_analysis_hours=outside, expected_hours=24, evidence_hours=evidence_hours,
            quality_complete=not quality_reasons, quality_reasons=quality_reasons,
        ))
    return daily


def aggregate_temporal_days(temporal_evidence: dict) -> list[dict]:
    """Return validated UTC daily counts, including partial-day missing hours."""
    return _daily(_temporal(temporal_evidence))


def _assessment(day, daily, polarity):
    date_utc = day.isoformat()
    evidence = daily.get(date_utc)
    if evidence is None:
        evidence = dict(date_utc=date_utc, positive=0, negative=0, valid_normal=0, unclassifiable=0,
                        missing_hours=24, explicit_missing_hours=0, outside_analysis_hours=24,
                        expected_hours=24, evidence_hours=0, quality_complete=False,
                        quality_reasons=["outside_evidence"])
    pos, neg = evidence["positive"], evidence["negative"]
    if polarity == 0:
        polarity_reason = "ambiguous_anchor_polarity"
    elif pos and neg:
        polarity_reason = "mixed_polarity"
    elif not pos and not neg:
        polarity_reason = "no_anomalies"
    elif (polarity == 1 and neg) or (polarity == -1 and pos):
        polarity_reason = "opposite_polarity_only"
    else:
        polarity_reason = "target_polarity_only"
    polarity_qualifies = polarity_reason == "target_polarity_only"
    reason = polarity_reason if evidence["quality_complete"] else (
        "outside_evidence" if not evidence["evidence_hours"] else "incomplete_or_unclassifiable_day"
    )
    return dict(**evidence, polarity_qualifies=polarity_qualifies,
                polarity_reason=polarity_reason, qualifies=polarity_qualifies and evidence["quality_complete"],
                reason=reason, boundary_uncertain=not evidence["quality_complete"],
                polarity_boundary_confirmed=evidence["quality_complete"] and not polarity_qualifies and polarity != 0)


def _step(day, direction):
    try:
        return day + direction * _DAY
    except OverflowError:
        return None


def _expand(anchor_day, direction, daily, polarity, evaluated):
    included = []
    current = _step(anchor_day, direction)
    while current is not None:
        assessment = _assessment(current, daily, polarity)
        evaluated[current.isoformat()] = assessment
        if not assessment["qualifies"]:
            return included, dict(status="stopped", date_utc=current.isoformat(),
                                  reason=assessment["reason"], boundary_uncertain=assessment["boundary_uncertain"],
                                  polarity_boundary_confirmed=assessment["polarity_boundary_confirmed"])
        included.append(current)
        current = _step(current, direction)
    return included, dict(status="stopped", date_utc=None, reason="calendar_limit",
                          boundary_uncertain=True, polarity_boundary_confirmed=False)


def _event(case_event, case_id):
    if type(case_event) is not dict or set(case_event) - {
        "case_id", "event_id", "time_utc", "source_reference", "source_sha256"
    }:
        raise ValueError("Invalid case_event fields.")
    try:
        if case_event["case_id"] != case_id:
            raise ValueError("Case event and temporal evidence case_id differ.")
        event_time = _utc(case_event["time_utc"])
        normalized = {name: _text(case_event[name], name)
                      for name in ("case_id", "event_id", "source_reference")}
        digest = case_event.get("source_sha256")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
            raise ValueError("Invalid event source SHA-256.")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid traceable UTC case_event: {exc}") from exc
    return {**normalized, "time_utc": _iso(event_time), "date_utc": event_time.date().isoformat(),
            "source_sha256": digest, "source_verification": "not_performed"}, event_time


def _reference(evidence):
    """Identify contract-validated evidence content, not source authenticity.

    content_sha256 hashes the UTF-8 deterministic evidence_to_json output,
    including its provenance declarations. It is not a raw-source-file hash,
    researcher identity authentication, signature or approval. This planner
    does not open original sources or independently verify declared source
    hashes; existing summary_artifact claims are preserved without rechecking
    that file. Source declarations can remain unchanged as evidence changes.
    """
    return dict(evidence_type=evidence["evidence_type"], schema_version=evidence["schema_version"],
                content_sha256=hashlib.sha256(evidence_to_json(evidence).encode("utf-8")).hexdigest(),
                provenance=evidence["provenance"], summary_artifact=evidence.get("summary_artifact"))


def plan_anchor_based_daily_windows(
    temporal_evidence: dict,
    historical_evidence: dict,
    *,
    case_event: dict,
    selected_cluster_ids: Sequence[int],
    mode: str,
) -> dict:
    """Produce a deterministic review-only proposal for explicitly selected anchors.

    mode must be 'retrospective'. case_event requires case_id, event_id,
    time_utc (explicit UTC ISO string, actual event time), source_reference;
    source_sha256 is optional. Selected IDs use the historical dominant
    polarity and rounded_day. Empty selection abstains; invalid IDs reject.
    Every anchor is reported, but unselected anchors are never expanded.
    """
    if mode != "retrospective":
        raise ValueError("This policy supports explicit retrospective analysis only.")
    temporal = _temporal(temporal_evidence)
    historical = _historical(historical_evidence)
    event, event_time = _event(case_event, temporal["case_id"])
    anchors = historical["historical_summary"]["clustering"]["temporal_anchors"]
    if (not isinstance(selected_cluster_ids, Sequence) or isinstance(selected_cluster_ids, (str, bytes)) or
            any(type(item) is not int for item in selected_cluster_ids) or
            len(set(selected_cluster_ids)) != len(selected_cluster_ids) or
            set(selected_cluster_ids) - {anchor["cluster_id"] for anchor in anchors}):
        raise ValueError("Select unique, existing integer cluster IDs explicitly.")
    selected = set(selected_cluster_ids)
    daily_evidence = _daily(temporal)
    daily = {day["date_utc"]: day for day in daily_evidence}
    references = {"temporal": _reference(temporal), "historical": _reference(historical)}
    reports = []
    for index, anchor in sorted(enumerate(anchors), key=lambda pair: pair[1]["cluster_id"]):
        report = dict(
            anchor=anchor, selected=anchor["cluster_id"] in selected, anchor_date_utc=None,
            anchor_source_reference=dict(
                content_sha256=references["historical"]["content_sha256"],
                json_pointer=f"/historical_summary/clustering/temporal_anchors/{index}",
            ),
            status="no_candidate", reason="not_selected", anchor_day_evidence=None,
            included_days=[], candidate_window=None, evaluated_days=[], data_quality_limitations=[],
            backward_stop=dict(status="not_attempted", reason="not_selected"),
            forward_stop=dict(status="not_attempted", reason="not_selected"),
            retrospective_interpretation=True,
        )
        reports.append(report)
        if not report["selected"]:
            continue
        try:
            anchor_day = event_time.date() + timedelta(days=anchor["rounded_day"])
        except OverflowError as exc:
            raise ValueError("Anchor mapping exceeds the supported UTC calendar.") from exc
        report["anchor_date_utc"] = anchor_day.isoformat()
        assessment = _assessment(anchor_day, daily, anchor["dominant_polarity"])
        evaluated = {anchor_day.isoformat(): assessment}
        report["anchor_day_evidence"] = assessment
        report["reason"] = "invalid_anchor:" + assessment["reason"]
        report["backward_stop"] = dict(status="not_attempted", reason="anchor_not_qualified")
        report["forward_stop"] = dict(status="not_attempted", reason="anchor_not_qualified")
        if assessment["qualifies"]:
            backward, report["backward_stop"] = _expand(anchor_day, -1, daily, anchor["dominant_polarity"], evaluated)
            forward, report["forward_stop"] = _expand(anchor_day, 1, daily, anchor["dominant_polarity"], evaluated)
            included = sorted(backward + [anchor_day] + forward)
            start = datetime.combine(included[0], time(0), tzinfo=timezone.utc)
            end = datetime.combine(included[-1], time(23), tzinfo=timezone.utc)
            report.update(
                status="candidate", reason="anchor_and_consecutive_days_qualify",
                included_days=[day.isoformat() for day in included],
                candidate_window=dict(start_utc=_iso(start), end_utc=_iso(end),
                                      inclusive_hours=len(included) * 24, bounds="inclusive_hourly_samples"),
                contains_day_zero=event_time.date() in included,
                contains_post_event_days=included[-1] > event_time.date(),
                contains_samples_at_or_after_event=end >= event_time,
            )
        report["evaluated_days"] = [evaluated[day] for day in sorted(evaluated)]
        report["data_quality_limitations"] = [
            dict(date_utc=day["date_utc"], reasons=day["quality_reasons"], boundary_uncertain=True)
            for day in report["evaluated_days"] if not day["quality_complete"]
        ]
    any_candidate = any(report["status"] == "candidate" for report in reports)
    return dict(
        report_type="anchor_based_daily_window_proposal", schema_version=1,
        policy_name=POLICY_NAME, mode=mode, review_only=True, case_event=event,
        status="candidates_proposed" if any_candidate else "abstained",
        abstention_reason=None if any_candidate else (
            "no_anchors_selected" if not selected else "no_qualifying_selected_anchors"
        ),
        scientific_rule="At least one valid target-polarity hour and no opposite-polarity hours per UTC day.",
        data_quality_rule="Separately require all 24 hours present and classifiable; otherwise stop with uncertain boundary.",
        evidence_references=references, daily_evidence=daily_evidence, anchor_reports=reports,
        interpretation="Retrospective review only; mapped anchors are neither predictions nor causal findings.",
        limitations=["Day 0 is a UTC calendar date and is not necessarily entirely pre-earthquake.",
                     "Upstream observation quality is not established by classifications or source hashes.",
                     "Framework D target/reference data coverage has not been checked."],
    )
