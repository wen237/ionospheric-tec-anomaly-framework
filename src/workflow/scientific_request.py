"""Strict scientific request V1, dispatching ONLY temporal_review.

The request is a JSON-native dict (not JSON text); transport decoding, including
duplicate-key rejection, belongs to the host. All top-level fields in this
example are required; unknown fields at every level are rejected::

    {
      "schema_version": 1,
      "operation": "temporal_review",
      "resources": {"time_series": "tec_case", "historical_summary": "bc_context"},
      "case_id": "case_a",
      "analysis": {"start_utc": "2000-12-20T00:00:00Z",
                   "end_utc": "2000-12-23T23:00:00Z"},
      "input_time_convention": "naive_utc",
      "case_event": {"case_id": "case_a", "event_id": "event_a",
                     "time_utc": "2000-12-29T10:30:00Z",
                     "source_reference": "synthetic:event"},
      "selected_cluster_ids": [0],
      "mode": "retrospective",
      "detector": {"reference_days": 15, "threshold_multiplier": 3.0,
                   "min_reference_samples": null},
      "provenance": null
    }

Analysis bounds are inclusive canonical YYYY-MM-DDTHH:00:00Z strings. They
remain aware UTC for aware_utc; naive_utc explicitly removes only their UTC
tzinfo to match the supplied series. No local time conversion is performed.
Case events and provenance use the existing planner/evidence fields, including
optional event source_sha256 and optional provenance sources/processing_history.
Numbers must be finite native JSON numbers; booleans are not scientific numbers.
Cluster IDs are unique nonnegative native integers; [] requests abstention.
Resource IDs match [A-Za-z][A-Za-z0-9_-]{0,63}, never paths or module names.

The researcher-controlled host separately acquires ONE series and ONE absolute
summary Path, binding them to explicit IDs via keyword arguments. Requests
cannot provide paths, loaders, callbacks, tools or execution options. Metadata
source references are inert declarations and are never opened. This is a data
acquisition boundary, NOT identity authentication, OS isolation or approval.
The host must not populate resource arguments from untrusted request paths and
must control the selected file/ancestors against concurrent replacement. This
module does not verify ACLs, symlinks, file custody or original-source identity.
It does not discover files, load TEC, generate artifacts, recompute B/C or
create authorization records. Existing summary parsing and scientific resource
validation remain in run_temporal_review; errors propagate without retries.

Resource budgets are an unresolved HOST responsibility, not enforced by V1:
hourly ordering/calendar checks do not cap analysis duration. Evidence allocates
every requested hour, including absent hours; A computes on the full supplied
series before clipping, and the full series is copied/hashed. The dispatcher
checks unique nonnegative cluster IDs, but membership in the validated summary
is checked by the planner AFTER A. Accepted selections are bounded by that
summary's anchors; there is no early selection-count or summary-size budget.
The dict interface has no payload-byte, string-length or collection-size cap,
and the summary loader reads the whole explicitly bound file. Fixed-shape
validation rejects malformed deep metadata but is not a resource quota. No
acquisition/transport host implementing quotas is supplied in this checkpoint.
A future host must review/enforce payload limits before decoding, input-series
and summary budgets, analysis/selection budgets and execution resource limits
before dispatch. This library is not a resource-bounded untrusted service;
no new scientific parameter limits or detector behavior are imposed here.
"""

from datetime import timedelta
from pathlib import Path
import re

from src.temporal_anomaly.tec_timeseries import TECTimeSeries

from .planning_evidence import _integer, _number, _provenance, _text
from .temporal_workflow import _REVIEW_INPUT_ID, run_temporal_review
from .window_planning import _event, _utc


def _object(value, required, name, optional=()):
    if (type(value) is not dict or any(type(key) is not str for key in value) or
            not set(required).issubset(value) or set(value) - set(required) - set(optional)):
        raise ValueError(f"Missing or unsupported {name} fields.")
    return value


def _string(value, name):
    if type(value) is not str:
        raise ValueError(f"{name} must be a JSON string.")
    return _text(value, name)


def _resource_id(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
        raise ValueError("Invalid resource ID; paths and module names are not supported.")
    return value


def _int(value, name, minimum, maximum=None):
    if type(value) is not int:
        raise ValueError(f"{name} must be a native JSON integer.")
    return _integer(value, name, minimum, maximum)


def _request_provenance(value):
    # Check the shallow fixed shape before the existing recursive strict copy.
    # Deep/cyclic malformed metadata must never reach that recursive validator.
    if value is not None:
        _object(value, (), "provenance", ("sources", "processing_history"))
        if value.get("processing_history") is not None:
            _string(value["processing_history"], "processing_history")
        sources = value.get("sources")
        if sources is not None:
            if type(sources) is not list:
                raise ValueError("sources must be a JSON list or null.")
            for source in sources:
                _object(source, ("identity", "sha256"), "source")
                _string(source["identity"], "source identity")
                if source["sha256"] is not None:
                    _string(source["sha256"], "source SHA-256")
    checked = _provenance(value)
    identities = [source["identity"] for source in checked["sources"] or []]
    if len(set(identities)) != len(identities) or _REVIEW_INPUT_ID in identities:
        raise ValueError("Ambiguous or reserved provenance source identity.")
    return None if value is None else {key: checked[key] for key in ("sources", "processing_history")}


def dispatch_scientific_request(
    request: dict,
    *,
    time_series_id: str,
    time_series: TECTimeSeries,
    historical_summary_id: str,
    historical_summary_path: Path,
) -> tuple[dict, dict, dict]:
    """Validate V1 metadata, then call run_temporal_review exactly once.

    Resource keyword arguments belong to the researcher-controlled acquisition
    host, separately from the request. No resource registry or caller-supplied
    execution callback is accepted. Invalid requests raise ValueError before
    dispatch or file I/O. Valid ones return the existing temporal evidence,
    historical context evidence and review-only proposal tuple unchanged.
    Scientific data/context/I/O failures propagate from the existing workflow;
    valid syntax/IDs do not prove resource quality or human authorization.
    """
    _object(request, ("schema_version", "operation", "resources", "case_id", "analysis",
                     "input_time_convention", "case_event", "selected_cluster_ids",
                     "mode", "detector", "provenance"), "request")
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise ValueError("Unsupported scientific request schema_version.")
    if type(request["operation"]) is not str or request["operation"] != "temporal_review":
        raise ValueError("Only operation temporal_review is supported.")
    if type(request["mode"]) is not str or request["mode"] != "retrospective":
        raise ValueError("Only explicit retrospective mode is supported.")
    convention = request["input_time_convention"]
    if type(convention) is not str or convention not in ("naive_utc", "aware_utc"):
        raise ValueError("Declare naive_utc or aware_utc explicitly.")
    case_id = _string(request["case_id"], "case_id")
    analysis = _object(request["analysis"], ("start_utc", "end_utc"), "analysis")
    bounds = []
    for name in ("start_utc", "end_utc"):
        value = analysis[name]
        if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:00:00Z", value):
            raise ValueError("Analysis bounds require canonical UTC hourly strings.")
        parsed = _utc(value, hourly=True)
        bounds.append(parsed.replace(tzinfo=None) if convention == "naive_utc" else parsed)
    if bounds[0] > bounds[1]:
        raise ValueError("Analysis start must not exceed end.")
    event = _object(request["case_event"], ("case_id", "event_id", "time_utc", "source_reference"),
                    "case_event", ("source_sha256",))
    for key, value in event.items():
        if key != "source_sha256" or value is not None:
            _string(value, key)
    _event(event, case_id)
    selected = request["selected_cluster_ids"]
    if type(selected) is not list:
        raise ValueError("selected_cluster_ids must be an explicit JSON list.")
    for value in selected:
        _int(value, "cluster_id", 0)
    if len(set(selected)) != len(selected):
        raise ValueError("Cluster IDs must be unique.")
    detector = _object(request["detector"], ("reference_days", "threshold_multiplier", "min_reference_samples"), "detector")
    days = _int(detector["reference_days"], "reference_days", 1)
    try:
        bounds[0] - timedelta(days=days)
    except OverflowError as exc:
        raise ValueError("Reference period exceeds the supported UTC calendar.") from exc
    multiplier = detector["threshold_multiplier"]
    if type(multiplier) not in (int, float):
        raise ValueError("threshold_multiplier must be a native JSON number.")
    try:
        _number(multiplier, "threshold_multiplier", 0)
    except OverflowError as exc:
        raise ValueError("threshold_multiplier exceeds the supported numeric range.") from exc
    minimum = detector["min_reference_samples"]
    if minimum is not None:
        _int(minimum, "min_reference_samples", 1, days)
    provenance = _request_provenance(request["provenance"])
    resources = _object(request["resources"], ("time_series", "historical_summary"), "resources")
    if (_resource_id(resources["time_series"]) != _resource_id(time_series_id) or
            _resource_id(resources["historical_summary"]) != _resource_id(historical_summary_id)):
        raise ValueError("Request references an unbound scientific resource.")
    if not isinstance(time_series, TECTimeSeries):
        raise ValueError("Bound time_series must be a TECTimeSeries.")
    if not isinstance(historical_summary_path, Path) or not historical_summary_path.is_absolute():
        raise ValueError("Bound historical summary must be an explicit absolute Path.")
    return run_temporal_review(
        time_series, case_id=case_id, analysis_start=bounds[0], analysis_end=bounds[1],
        input_time_convention=convention, historical_summary_path=historical_summary_path,
        case_event=dict(event), selected_cluster_ids=list(selected), mode=request["mode"],
        reference_days=days, threshold_multiplier=multiplier,
        min_reference_samples=minimum, provenance=provenance,
    )
