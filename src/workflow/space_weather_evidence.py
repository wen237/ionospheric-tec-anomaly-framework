"""Offline adapter to space-weather-data-tools, without retrieval or reprocessing.

The host supplies the toolkit module and either its exported CSV or a saved
OMNI response. Raw response conversion/fill handling delegates to that toolkit.
CSV numbers are already processed and must obey its export contract.
"""

import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
from io import StringIO
import math
from pathlib import Path
import sys

from src.workflow.window_sensitivity import bounds, utc_epoch, utc_string


INDICES = ("kp", "dst", "f107")
RESOLUTION = {
    "kp": dict(unit="dimensionless", native_resolution_hours=3, exported_resolution_hours=1),
    "dst": dict(unit="nT", native_resolution_hours=1, exported_resolution_hours=1),
    "f107": dict(unit="sfu", native_resolution_hours=24, exported_resolution_hours=1),
}
LIMITATIONS = [
    "Hourly OMNI rows do not make Kp or F10.7 independent hourly measurements; native cadences may repeat.",
    "Absent UTC rows and missing index values remain null; no interpolation or forward fill is performed.",
    "Index extrema and temporal coincidence alone do not establish a storm explanation, earthquake causality or predictive skill.",
    "Source hashes establish snapshot consistency, not authenticated origin or original-provider data quality.",
]


def metadata(raw):
    return dict(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))


def load_toolkit(module_path):
    """Load only a researcher-specified local module; never call retrieve()."""
    path = Path(module_path).resolve(strict=True)
    raw = path.read_bytes()
    name = "_tec_omni_" + hashlib.sha256(raw).hexdigest()[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # dataclasses resolves the defining module here.
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    module = sys.modules[name]
    if not all(hasattr(module, k) for k in ("OMNIWebDownloader", "OMNIRecord", "VARIABLES", "save_csv", "OMNI_URL")):
        raise ValueError("Unsupported space-weather-data-tools interface")
    return module, dict(identity=path.name, **metadata(raw))


def _timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)  # toolkit documents naive UTC.
    value = value.astimezone(timezone.utc)
    if (value.minute, value.second, value.microsecond) != (0, 0, 0):
        raise ValueError("Space-weather timestamps must be hour-aligned")
    return value


def read_exported_csv(raw, toolkit):
    """Consume save_csv output; do not repeat the toolkit's Kp/fill conversion."""
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    required = {"datetime_utc", "year", "doy", "hour", "kp", "kp_x10", "dst", "f107"}
    if (reader.fieldnames is None or not required <= set(reader.fieldnames)
            or len(set(reader.fieldnames)) != len(reader.fieldnames)):
        raise ValueError("Expected toolkit CSV exporting kp, dst and f107")
    records = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Incomplete CSV row")
        stamp = _timestamp(row["datetime_utc"])
        if [int(row[k]) for k in ("year", "doy", "hour")] != [stamp.year, stamp.timetuple().tm_yday, stamp.hour]:
            raise ValueError("CSV UTC and calendar fields disagree")
        values = {}
        for key in (*INDICES, "kp_x10"):
            text = row[key].strip()
            value = None if text == "" else float(text)
            if value is not None and not math.isfinite(value):
                raise ValueError("Nonfinite CSV observations must be exported as empty values")
            # Exported fills must already be empty. The authoritative sentinel
            # definitions come from the original toolkit, not another table.
            source_key = "kp" if key == "kp_x10" else key
            if key != "kp" and value is not None and value in {float(x) for x in toolkit.VARIABLES[source_key]["fill_values"]}:
                raise ValueError("Raw OMNI fills require the original toolkit parser")
            values[key] = value
        if (values["kp"] is None) != (values["kp_x10"] is None):
            raise ValueError("Kp and original Kp-times-ten availability disagree")
        if values["kp"] is not None and values["kp"] != values["kp_x10"] / 10.0:
            raise ValueError("Kp differs from the toolkit conversion")
        records.append(toolkit.OMNIRecord(stamp, stamp.year, stamp.timetuple().tm_yday, stamp.hour, values))
    return records


def build_space_weather_report(records, window, *, case_id, provenance):
    window = bounds(window)
    by_time = {}
    for record in records:
        stamp = _timestamp(record.timestamp)
        epoch = int(stamp.timestamp())
        if epoch in by_time:
            raise ValueError("Duplicate UTC space-weather observations")
        if [record.year, record.doy, record.hour] != [stamp.year, stamp.timetuple().tm_yday, stamp.hour]:
            raise ValueError("Invalid OMNI calendar fields")
        values = {key: record.values.get(key) for key in (*INDICES, "kp_x10")}
        for value in values.values():
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError("Invalid space-weather observation")
        if (values["kp"] is not None and (values["kp_x10"] is None or values["kp"] != values["kp_x10"] / 10.0)
                or values["kp"] is None and values["kp_x10"] is not None):
            raise ValueError("Inconsistent original Kp representation")
        by_time[epoch] = values
    rows = []
    for epoch in range(utc_epoch(window["start_utc"]), utc_epoch(window["end_utc"]) + 1, 3600):
        present = epoch in by_time
        rows.append(dict(timestamp_utc=utc_string(epoch), source_row_present=present,
                         values=by_time.get(epoch, {key: None for key in (*INDICES, "kp_x10")})))
    summary = {}
    for key in INDICES:
        available = [r for r in rows if r["values"][key] is not None]
        values = [r["values"][key] for r in available]
        summary[key] = dict(**RESOLUTION[key], available_hourly_rows=len(values), missing_hourly_rows=len(rows) - len(values),
                            minimum=None if not values else min(values), maximum=None if not values else max(values),
                            maximum_utc_hours=[r["timestamp_utc"] for r in available if r["values"][key] == max(values)][:24],
                            extrema_timestamp_limit=24, independent_sample_count="not inferred from repeated hourly rows")
    return dict(record_type="space_weather_evidence", schema_version=1, case_id=case_id, window=window,
                provenance=provenance, resolution=RESOLUTION, rows=rows, summary=summary,
                absent_utc_rows=sum(not r["source_row_present"] for r in rows),
                limitations=list(LIMITATIONS), execution_eligible=False, human_approval_required=True)


def prepare_space_weather_report(source_path, module_path, window, *, case_id, source_format="csv"):
    toolkit, code_pin = load_toolkit(module_path)
    path = Path(source_path)
    raw = path.read_bytes()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Space-weather source exceeds offline byte limit")
    if source_format == "csv":
        records = read_exported_csv(raw, toolkit)
        interface = "save_csv exported CSV; already processed values"
    elif source_format == "omni_response":
        # This is the existing implementation's offline parsing interface.
        records = toolkit.OMNIWebDownloader._parse_response(raw.decode("utf-8"), list(INDICES))
        interface = "OMNIWebDownloader._parse_response; no downloader instance or retrieval"
    else:
        raise ValueError("Use csv or omni_response")
    return build_space_weather_report(records, window, case_id=case_id, provenance=dict(
        provider="NASA OMNIWeb", product="OMNI2 hourly", service_url=toolkit.OMNI_URL,
        input=dict(identity=path.name, format=source_format, **metadata(raw)), toolkit=code_pin,
        integration_interface=interface, retrieval_performed=False,
        record_time_convention="Toolkit naive timestamps mean UTC; aware timestamps are normalized to UTC"))


def validate_space_weather_report(report):
    """Recompute only saved-evidence alignment and summaries, never processing."""
    from types import SimpleNamespace
    records = []
    for row in report["rows"]:
        if type(row["source_row_present"]) is not bool:
            raise ValueError("Invalid row presence marker")
        if set(row["values"]) != {*INDICES, "kp_x10"}:
            raise ValueError("Unsupported index fields")
        stamp = _timestamp(row["timestamp_utc"])
        if row["source_row_present"]:
            records.append(SimpleNamespace(timestamp=stamp, year=stamp.year, doy=stamp.timetuple().tm_yday,
                                           hour=stamp.hour, values=row["values"]))
        elif any(v is not None for v in row["values"].values()):
            raise ValueError("Absent observations cannot carry values")
    return build_space_weather_report(records, report["window"], case_id=report["case_id"], provenance=report["provenance"])
