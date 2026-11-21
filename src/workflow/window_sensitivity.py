"""Reproducible nested-window diagnostics from actual hourly detector evidence.

No Stage 2 entry point or authorization is called. Saved aggregate differences
are cross-checks only: they cannot identify individual anomalous UTC hours.
"""

from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile

import numpy as np

from src.workflow.explicit_window import select_explicit_window


PARAMETERS = dict(reference_days=15, k=3.0, samples_per_day=24, grid_orientation="canonical")
LIMITATIONS = [
    "Grid-hour occurrences are spatially correlated, not unique anomalous UTC hours or independent observations.",
    "Ratios retain all target UTC hours, including missing or unevaluated observations.",
    "Non-NaN detector decisions and finite target/threshold decisions are reported separately; neither proves scientific reliability.",
    "Partial rolling references use the existing nanpercentile convention; no new minimum reference count is imposed.",
    "Original interpolation history and physical observation quality are not established by finite inputs.",
    "Window sensitivity is descriptive; it does not select a window or establish earthquake causality or predictive skill.",
]
SNAPSHOT_FIELDS = {"positive", "negative", "target_finite", "reference_finite_counts",
                   "positive_finite", "negative_finite", "epochs", "latitudes", "longitudes"}


def bounds(value):
    """Validate explicit, inclusive, hour-aligned UTC bounds."""
    if not isinstance(value, dict) or not {"start_utc", "end_utc"} <= set(value):
        raise ValueError("Explicit UTC bounds are required")
    w = select_explicit_window(value["start_utc"], value["end_utc"])
    if any((t.minute, t.second, t.microsecond) != (0, 0, 0) for t in (w.start_time, w.end_time)):
        raise ValueError("Windows must be hour-aligned")
    hours = int((w.end_time - w.start_time).total_seconds() / 3600) + 1
    if not 1 <= hours <= 744:
        raise ValueError("Diagnostic windows support at most 744 hours")
    result = dict(start_utc=w.start_time.strftime("%Y-%m-%dT%H:00:00Z"),
                  end_utc=w.end_time.strftime("%Y-%m-%dT%H:00:00Z"), inclusive_hours=hours)
    if "inclusive_hours" in value and (type(value["inclusive_hours"]) is not int or value["inclusive_hours"] != hours):
        raise ValueError("Inconsistent inclusive duration")
    return result


def utc_epoch(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def utc_string(epoch):
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")


def make_hourly_snapshot(hourly, timestamps, latitudes, longitudes):
    """Freeze the shared detector's observations; no inference from count maps."""
    result = {key: np.asarray(getattr(hourly, key)).astype(np.uint8) for key in
              ("target_finite", "reference_finite_counts", "positive_finite", "negative_finite")}
    for p in ("positive", "negative"):
        a = np.asarray(getattr(hourly, p))
        result[p] = np.where(np.isnan(a), -1, a).astype(np.int8)
    result.update(epochs=np.array([int(t.replace(tzinfo=timezone.utc).timestamp()) if t.tzinfo is None
                                  else int(t.timestamp()) for t in timestamps], dtype=np.int64),
                  latitudes=np.asarray(latitudes, dtype=float), longitudes=np.asarray(longitudes, dtype=float))
    validate_snapshot(result)
    return result


def validate_snapshot(a):
    if set(a) != SNAPSHOT_FIELDS:
        raise ValueError("Unsupported hourly snapshot fields")
    lat, lon, epochs = (a[k] for k in ("latitudes", "longitudes", "epochs"))
    if (lat.ndim != 1 or lon.ndim != 1 or not 1 <= len(lat) <= 71 or not 1 <= len(lon) <= 73
            or not np.isfinite(lat).all() or not np.isfinite(lon).all()
            or not np.all(np.diff(lat) > 0) or not np.all(np.diff(lon) > 0)
            or np.any(abs(lat) > 90) or np.any(abs(lon) > 180)):
        raise ValueError("Canonical ascending physical coordinates are required")
    if (epochs.ndim != 1 or epochs.dtype.kind not in "iu" or not 1 <= len(epochs) <= 744
            or np.any(epochs % 3600) or not np.all(np.diff(epochs) == 3600)):
        raise ValueError("Continuous UTC hours are required")
    shape = (len(epochs), len(lat) * len(lon))
    for key in SNAPSHOT_FIELDS - {"epochs", "latitudes", "longitudes"}:
        x = a[key]
        if x.shape != shape or x.dtype.kind not in "biu":
            raise ValueError("Invalid hourly evidence shape or dtype")
        low, high = (-1, 1) if key in ("positive", "negative") else (0, 15 if key == "reference_finite_counts" else 1)
        if np.any(x < low) or np.any(x > high):
            raise ValueError("Invalid hourly evidence value")
    if np.any((a["positive"] == 1) & (a["negative"] == 1)):
        raise ValueError("Contradictory polarities")
    for p in ("positive", "negative"):
        if np.any(a[p + "_finite"].astype(bool) & ((a[p] < 0) | ~a["target_finite"].astype(bool))):
            raise ValueError("Inconsistent finite detector validity")


def load_hourly_snapshot(raw):
    """Bounded numeric NPZ reader for a host-pinned saved snapshot."""
    with ZipFile(BytesIO(raw)) as z:
        entries = z.infolist()
        if ({e.filename for e in entries} != {k + ".npy" for k in SNAPSHOT_FIELDS}
                or len(entries) != len(SNAPSHOT_FIELDS) or sum(e.file_size for e in entries) > 64 * 1024 * 1024):
            raise ValueError("Unsupported hourly archive")
        for e in entries:
            with z.open(e) as stream:
                fmt = np.lib.format.read_magic(stream)
                reader = {(1, 0): np.lib.format.read_array_header_1_0,
                          (2, 0): np.lib.format.read_array_header_2_0}.get(fmt)
                if reader is None:
                    raise ValueError("Unsupported NPY version")
                shape, _, dtype = reader(stream, max_header_size=4096)
                if (len(shape) not in (1, 2) or any(n < 1 for n in shape) or dtype.kind not in "biuf"
                        or dtype.itemsize > 8 or np.prod(shape, dtype=object) > 744 * 5183
                        or stream.tell() + int(np.prod(shape, dtype=object)) * dtype.itemsize != e.file_size):
                    raise ValueError("Invalid hourly array header")
    with np.load(BytesIO(raw), allow_pickle=False) as z:
        result = {key: z[key] for key in z.files}
    validate_snapshot(result)
    return result


def masks(a, baseline, extended):
    base, ext = bounds(baseline), bounds(extended)
    if not (ext["start_utc"] <= base["start_utc"] <= base["end_utc"] <= ext["end_utc"]):
        raise ValueError("Windows must be nested")
    if base == ext:
        raise ValueError("The extended window must add hours")
    if [int(a["epochs"][0]), int(a["epochs"][-1])] != [utc_epoch(ext["start_utc"]), utc_epoch(ext["end_utc"])]:
        raise ValueError("Hourly evidence must cover exactly the extended window")
    b = (a["epochs"] >= utc_epoch(base["start_utc"])) & (a["epochs"] <= utc_epoch(base["end_utc"]))
    return {"baseline": b, "extended": np.ones(len(b), dtype=bool), "additional": ~b}


def nearest_cell(a, latitude, longitude):
    if (type(latitude) not in (int, float) or type(longitude) not in (int, float)
            or not np.isfinite([latitude, longitude]).all() or abs(latitude) > 90 or abs(longitude) > 180):
        raise ValueError("Invalid coordinates")
    i = int(np.argmin(abs(a["latitudes"] - latitude)))
    j = int(np.argmin(abs((a["longitudes"] - longitude + 180) % 360 - 180)))
    return i, j, i * len(a["longitudes"]) + j


def segment_summary(a, mask, index=None):
    hours = int(mask.sum())
    select = slice(None) if index is None else slice(index, index + 1)
    data = {key: x[mask, select] for key, x in a.items() if x.ndim == 2}
    grids = data["positive"].shape[1]
    summary = dict(ratio_denominator_hours=hours, grid_count=grids, grid_hours=hours * grids,
                   target_finite_grid_hours=int(data["target_finite"].sum()),
                   incomplete_reference_grid_hours=int((data["reference_finite_counts"] < 15).sum()),
                   empty_reference_grid_hours=int((data["reference_finite_counts"] == 0).sum()))
    for p in ("positive", "negative"):
        counts = (data[p] == 1).sum(axis=0)
        summary[p] = dict(anomaly_grid_hours=int(counts.sum()), unique_anomalous_utc_hours=int(np.any(data[p] == 1, axis=1).sum()),
                          evaluated_grid_hours=int((data[p] >= 0).sum()), finite_detector_grid_hours=int(data[p + "_finite"].sum()),
                          mean_occurrence_ratio_percent=float(np.mean(counts / hours * 100.0)))
    return summary


def cell_summary(a, window_masks, latitude, longitude):
    i, j, index = nearest_cell(a, latitude, longitude)
    return dict(requested_coordinates=dict(latitude=latitude, longitude=longitude),
                actual_grid=dict(row_index=i, column_index=j, latitude=float(a["latitudes"][i]), longitude=float(a["longitudes"][j])),
                segments={key: segment_summary(a, m, index) for key, m in window_masks.items()})


def hourly_rows(a, baseline, extended, start_utc, end_utc, latitude=None, longitude=None):
    window_masks = masks(a, baseline, extended)
    interval = bounds(dict(start_utc=start_utc, end_utc=end_utc))
    if interval["inclusive_hours"] > 24:
        raise ValueError("Inspect at most 24 UTC hours per call")
    wanted = (a["epochs"] >= utc_epoch(interval["start_utc"])) & (a["epochs"] <= utc_epoch(interval["end_utc"]))
    if int(wanted.sum()) != interval["inclusive_hours"] or np.any(wanted & ~window_masks["additional"]):
        raise ValueError("Inspect only additional UTC hours")
    index = None if latitude is None else nearest_cell(a, latitude, longitude)[2]
    rows = []
    for h in np.flatnonzero(wanted):
        mask = np.arange(len(wanted)) == h
        row = dict(timestamp_utc=utc_string(a["epochs"][h]), global_grid=segment_summary(a, mask))
        if index is not None:
            row["cell"] = {p: int(a[p][h, index]) for p in ("positive", "negative")}
            row["cell"].update(target_finite=bool(a["target_finite"][h, index]),
                               reference_finite_count=int(a["reference_finite_counts"][h, index]),
                               positive_finite=bool(a["positive_finite"][h, index]), negative_finite=bool(a["negative_finite"][h, index]))
        rows.append(row)
    return rows


def build_window_diagnostic(a, baseline, extended, *, case_id, selected_cells=()):
    validate_snapshot(a)
    base, ext = bounds(baseline), bounds(extended)
    window_masks = masks(a, base, ext)
    segments = {key: segment_summary(a, m) for key, m in window_masks.items()}
    additional = [utc_string(e) for e in a["epochs"][window_masks["additional"]]]
    spatial, auto_cells = {}, list(selected_cells)
    for p in ("positive", "negative"):
        counts = {key: (a[p][m] == 1).sum(axis=0) for key, m in window_masks.items()}
        delta = counts["extended"] / ext["inclusive_hours"] * 100.0 - counts["baseline"] / base["inclusive_hours"] * 100.0
        peaks = {}
        for key in ("baseline", "extended", "additional"):
            points = np.flatnonzero(counts[key] == counts[key].max())
            coords = [dict(latitude=float(a["latitudes"][i // len(a["longitudes"])]),
                           longitude=float(a["longitudes"][i % len(a["longitudes"])])) for i in points[:8]]
            peaks[key] = dict(maximum_count=int(counts[key].max()), maximum_ratio_percent=float(counts[key].max() / int(window_masks[key].sum()) * 100.0),
                              tied_peak_cells=len(points), first_peak_coordinates=coords)
            if key != "additional" and counts[key].max() > 0:
                auto_cells.extend(coords[:2])
        spatial[p] = dict(changed_count_cells=int(np.count_nonzero(counts["additional"])),
                          ratio_difference_unit="percentage_points", minimum_ratio_change=float(delta.min()),
                          maximum_ratio_change=float(delta.max()), peaks=peaks)
    cells, seen = [], set()
    for point in auto_cells:
        i, j, index = nearest_cell(a, point["latitude"], point["longitude"])
        if index not in seen and len(cells) < 12:
            cells.append(cell_summary(a, window_masks, point["latitude"], point["longitude"]))
            seen.add(index)
    added_share = len(additional) / ext["inclusive_hours"]
    contribution = dict(additional_hour_share_of_extended=added_share)
    for p in ("positive", "negative"):
        b, e, x = (segments[key][p]["anomaly_grid_hours"] for key in ("baseline", "extended", "additional"))
        rate_b = b / segments["baseline"]["grid_hours"]
        rate_x = x / segments["additional"]["grid_hours"]
        contribution[p] = dict(additional_anomaly_share_of_extended=None if e == 0 else x / e,
                               baseline_anomaly_rate_per_grid_hour=rate_b, additional_anomaly_rate_per_grid_hour=rate_x,
                               lower_additional_anomaly_rate_than_baseline=rate_x < rate_b)
    hourly = []
    for h in np.flatnonzero(window_masks["additional"]):
        m = np.arange(len(a["epochs"])) == h
        hourly.append(dict(timestamp_utc=utc_string(a["epochs"][h]), **segment_summary(a, m)))
    return dict(record_type="window_sensitivity_diagnostic", schema_version=1, case_id=case_id,
                parameters=dict(PARAMETERS), baseline=base, extended=ext, additional_utc_hours=additional,
                grid=dict(latitude_order="ascending", longitude_order="ascending", shape=[len(a["latitudes"]), len(a["longitudes"])],
                          count_unit="grid-hour occurrences", ratio_unit="percent of full target hours"),
                segments=segments, contribution=contribution, spatial_distribution=spatial, relevant_cells=cells,
                additional_hourly=hourly, selected_cells=list(selected_cells), limitations=list(LIMITATIONS),
                framework_d_execution="not_performed", diagnostic_computation="shared detector hourly diagnostics only",
                human_approval_required=True, execution_eligible=False)


def compare_saved_counts(a, baseline, extended, saved_arrays):
    """Verify all grid counts and ratios against accepted saved experiments."""
    window_masks = masks(a, baseline, extended)
    checks = {}
    for key in ("baseline", "extended"):
        s, m = saved_arrays[key], window_masks[key]
        matched = np.array_equal(a["latitudes"], s["latitudes"]) and np.array_equal(a["longitudes"], s["longitudes"])
        matched = matched and int(s["ratio_denominator"]) == int(m.sum())
        for p in ("positive", "negative"):
            counts = (a[p][m] == 1).sum(axis=0).reshape(len(a["latitudes"]), len(a["longitudes"]))
            matched = matched and np.array_equal(counts, s[p + "_counts"]) and np.array_equal(counts / int(m.sum()) * 100.0, s[p + "_ratio"])
        checks[key] = bool(matched)
    return checks
