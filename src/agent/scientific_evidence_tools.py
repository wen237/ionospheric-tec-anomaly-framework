"""Case-specific evidence views. Paths are host inputs, never model arguments.

Hashes establish snapshot consistency, not origin authentication, raw-source
custody, detector correctness, or human authority. Operational byte/query caps
are not scientific thresholds and do not provide process/OS isolation.
"""

from io import BytesIO
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from zipfile import ZipFile, BadZipFile
import json
import math

import numpy as np

from examples import select_afghanistan_mvp_window as handoff
from examples import compare_afghanistan_mvp_spatial as saved_spatial
from src.workflow.explicit_window import select_explicit_window


MODES = ("pre_spatial", "post_spatial")
PRE_ROOT = "afghanistan_mvp01_review"
POST_ROOT = "afghanistan_mvp02b_comparison"
SELECTION_ROOT = "afghanistan_mvp02b_selections"
EXPERIMENTS = dict(zip(("A", "B"), saved_spatial._EXPERIMENTS))
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_NPZ_BYTES = 8 * 1024 * 1024
MAX_ARGUMENT_BYTES = 2048
MAX_TOOL_BYTES = 24 * 1024
PRE_FILES = ("run_record.json", "scientific_request.json", "temporal_evidence.json",
             "historical_context.json", "window_proposal.json", "review_note.md")


def compact(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True)


def strict_json(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return handoff._decode(raw)


def object_schema(properties):
    return dict(type="object", properties=properties, required=list(properties), additionalProperties=False)


def _tool(name, description, properties=None):
    return dict(type="function", name=name, description=description, strict=True,
                parameters=object_schema(properties or {}))


def definitions(mode):
    if mode not in MODES:
        raise ValueError("Unknown mode")
    result = [
        _tool("get_evidence_inventory", "Availability and integrity status; no external space-weather data."),
        _tool("get_temporal_summary", "Validated temporal counts, UTC coverage, detector parameters and grid location."),
        _tool("inspect_anomaly_interval", "Inspect saved hourly classifications within coverage; at most 168 hours per query.",
              dict(start_utc=dict(type="string"), end_utc=dict(type="string"))),
        _tool("get_historical_context", "Historical period, population, significant cells, silhouette and mixed-polarity anchors; not a prediction."),
        _tool("list_candidate_windows", "Saved daily-policy candidates and separate published reference; no execution selections."),
    ]
    if mode == "post_spatial":
        result += [
            _tool("get_spatial_experiment_summary", "Recorded researcher selection, window, denominator and global peaks from validated saved arrays.",
                  dict(experiment=dict(type="string", enum=["A", "B"]))),
            _tool("compare_spatial_experiments", "Whole-grid saved B-minus-A count, ratio and availability differences; ratio changes use percentage points."),
            _tool("inspect_spatial_grid_cell", "Both saved experiments and differences at nearest actual grid cell; never interpolates. Longitude distance is circular.",
                  dict(latitude=dict(type="number", minimum=-90, maximum=90),
                       longitude=dict(type="number", minimum=-180, maximum=180))),
        ]
    return result


class EvidenceError(ValueError):
    pass


class EvidenceTools:
    """Validated in-memory snapshots; tool dispatch never accepts file identities.

    Pre mode never reads or tests existence of spatial or selection paths.
    Missing/corrupt bundles remain unavailable; they are not synthesized.
    """

    def __init__(self, evidence_root, mode):
        if mode not in MODES:
            raise ValueError("Unknown mode")
        self.root = Path(evidence_root).resolve(strict=True)
        self.mode = mode
        self.sources, self.raw, self.arrays = {}, {}, {}
        self.status = dict(temporal_historical="unavailable_or_invalid")
        self.bundle = None
        try:
            for name in PRE_FILES:
                self._read(PRE_ROOT + "/" + name)
            self.bundle = handoff.validate_bundle(self.root / PRE_ROOT)
            # Legacy validator rereads its fixed files. Ensure both snapshots agree.
            for name in PRE_FILES:
                self._unchanged(PRE_ROOT + "/" + name)
            self.temporal = strict_json(self.raw[PRE_ROOT + "/temporal_evidence.json"])
            self.historical = strict_json(self.raw[PRE_ROOT + "/historical_context.json"])["historical_summary"]
            self.proposal = self.bundle["proposal"]
            self.status["temporal_historical"] = "validated_snapshot"
        except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError):
            self.bundle = None
        if mode == "post_spatial":
            self.status["spatial"] = "unavailable_or_invalid"
            if self.bundle is not None:
                try:
                    self._load_spatial()
                    self.status["spatial"] = "validated_snapshot"
                except (OSError, ValueError, KeyError, TypeError, OverflowError, EOFError, BadZipFile, StopIteration, RecursionError):
                    self.arrays.clear()

    def _path(self, identity):
        # Only internal constants reach this method. Refuse redirected components.
        path = self.root
        for part in identity.split("/"):
            if part in ("", ".", ".."):
                raise EvidenceError("invalid_identity")
            path = path / part
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise EvidenceError("redirected_evidence")
        if not path.resolve(strict=True).is_relative_to(self.root):
            raise EvidenceError("redirected_evidence")
        return path

    def _bytes(self, identity):
        path = self._path(identity)
        if not path.is_file():
            raise EvidenceError("not_regular_file")
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise EvidenceError("artifact_size_limit")
        return raw

    def _read(self, identity, pin=None):
        raw = self._bytes(identity)
        meta = handoff._metadata(raw)
        if pin is not None:
            if "path" in pin and pin["path"] != identity.split("/")[-1]:
                raise EvidenceError("unexpected_artifact_path")
            handoff._same(meta, {k: pin[k] for k in ("sha256", "size_bytes")}, "artifact hash")
        self.sources[identity] = meta
        self.raw[identity] = raw
        return raw

    def _unchanged(self, identity):
        handoff._same(handoff._metadata(self._bytes(identity)), self.sources[identity], "evidence changed")

    def recheck(self):
        for identity in self.sources:
            self._unchanged(identity)

    def _json(self, identity, pin=None):
        return strict_json(self._read(identity, pin))

    def _npz(self, raw):
        with ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if (len(entries) > 12 or len({e.filename for e in entries}) != len(entries)
                    or sum(e.file_size for e in entries) > MAX_NPZ_BYTES):
                raise EvidenceError("npz_expansion_limit")
            # Inspect NPY headers before NumPy can allocate their declared shape.
            for entry in entries:
                if not entry.filename.endswith(".npy") or "/" in entry.filename or "\\" in entry.filename:
                    raise EvidenceError("unexpected_npz_member")
                with archive.open(entry) as stream:
                    fmt = np.lib.format.read_magic(stream)
                    if fmt == (1, 0):
                        shape, _, dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=4096)
                    elif fmt == (2, 0):
                        shape, _, dtype = np.lib.format.read_array_header_2_0(stream, max_header_size=4096)
                    else:
                        raise EvidenceError("unsupported_npy_version")
                    if (shape not in ((), (71,), (73,), (71, 73)) or dtype.kind not in "iuf" or dtype.itemsize > 8
                            or stream.tell() + math.prod(shape) * dtype.itemsize != entry.file_size):
                        raise EvidenceError("invalid_npy_shape_or_dtype")
        with np.load(BytesIO(raw), allow_pickle=False) as values:
            arrays = {key: values[key] for key in values.files}
        if any(a.dtype.kind not in "iuf" for a in arrays.values()):
            raise EvidenceError("unsupported_array_dtype")
        return arrays

    @staticmethod
    def _peaks(a):
        peaks = {}
        for polarity in ("positive", "negative"):
            ratio = a[polarity + "_ratio"]
            maximum = float(ratio.max())
            points = [dict(latitude=float(a["latitudes"][i]), longitude=float(a["longitudes"][j]))
                      for i, j in np.argwhere(ratio == maximum)]
            peaks[polarity] = dict(maximum_ratio_percent=maximum, maximum_grid_points=points)
        return peaks

    def _load_spatial(self):
        prefix = POST_ROOT + "/"
        c = self._json(prefix + "comparison_summary.json")
        handoff._same([c["record_type"], c["schema_version"], c["framework_d_execution"]],
                     ["afghanistan_mvp_dual_window_comparison", 1, "executed"], "comparison type/status")
        expected = {"cellwise_differences.npz", "comparison_report.md"} | {
            name + "/experiment_summary.json" for name in EXPERIMENTS.values()}
        if set(c["artifacts"]) != expected or set(c["experiments"]) != set(EXPERIMENTS.values()):
            raise EvidenceError("incomplete_comparison")
        for name in expected:
            self._read(prefix + name, c["artifacts"][name])
        self.summaries, self.selections = {}, {}
        for label, name in EXPERIMENTS.items():
            base = prefix + name + "/"
            s = strict_json(self.raw[base + "experiment_summary.json"])
            handoff._same(s, c["experiments"][name], "embedded experiment")
            handoff._same([s["record_type"], s["schema_version"], s["experiment"], s["framework_d_execution"]],
                         ["afghanistan_mvp_spatial_experiment", 1, name, "executed"], "experiment type/status")
            handoff._same(s["event"], self.bundle["record"]["confirmed_event"], "event")
            handoff._same(s["parameters"], dict(reference_days=15, k=3.0, grid_orientation="canonical", show_boundaries=False), "parameters")
            handoff._same(s["parent_review_bundle"], self.bundle["binding"], "parent bundle")
            for key in ("execution_eligible", "windows_local_isolation", "trusted_human_authorization"):
                expected_state = False if key == "execution_eligible" else "NOT VERIFIED"
                handoff._same(s[key], expected_state, "security state")
                handoff._same(c[key], expected_state, "comparison security state")
            files = {"selection_record.json", "execution_status.json", "spatial_arrays.npz", "positive.png", "negative.png"}
            if set(s["artifacts"]) != files:
                raise EvidenceError("incomplete_experiment")
            for filename in files:
                self._read(base + filename, s["artifacts"][filename])
            status = strict_json(self.raw[base + "execution_status.json"])
            handoff._same(status, saved_spatial._state("executed"), "execution status")
            selection_id = SELECTION_ROOT + "/" + name + "/selection_record.json"
            raw_selection = self._read(selection_id)
            if raw_selection != self.raw[base + "selection_record.json"]:
                raise EvidenceError("selection_copy_mismatch")
            handoff._same(handoff._metadata(raw_selection), {k: s["selection"][k] for k in ("sha256", "size_bytes")}, "selection pin")
            selection = strict_json(raw_selection)
            if set(selection) != saved_spatial._SELECTION_FIELDS:
                raise EvidenceError("incomplete_selection")
            for key, expected_value in dict(record_type="afghanistan_mvp_window_selection", schema_version=1,
                case_id=self.bundle["record"]["case_id"], review_only=True, **saved_spatial._state("not_performed")).items():
                handoff._same(selection[key], expected_value, "selection metadata")
            handoff._same(selection["parent_review_bundle"], self.bundle["binding"], "selection parent")
            handoff._same(selection["event"], s["event"], "selection event")
            handoff._same(selection["window"], s["window"], "selection window")
            handoff._same(s["input_files"], selection["modern_gim_inputs"]["required_daily_files"], "recorded source files")
            originals = {}
            for source in self.bundle["record"]["inputs"]["modern_daily_files"]:
                originals.setdefault(PureWindowsPath(source["path"]).name.casefold(), []).append(source)
            for source in s["input_files"]:
                matches = originals.get(source["filename"].casefold(), [])
                if len(matches) != 1:
                    raise EvidenceError("ambiguous_or_missing_original_identity")
                handoff._same(source["original_source"], matches[0], "recorded original source")
                handoff._same({k: source[k] for k in ("sha256", "size_bytes")},
                             {k: matches[0][k] for k in ("sha256", "size_bytes")}, "recorded source consistency")
                handoff._same(source["source_consistency"], "matched", "recorded source status")
            if label == "A":
                handoff._same([selection["selection_mode"], selection["cluster_id"], selection["selected_candidate"]],
                             ["independent", None, None], "reference selection")
                handoff._same(selection["window"], self.bundle["record"]["historical_research_reference"]["window"], "reference window")
            else:
                candidate = next(r for r in self.proposal["anchor_reports"] if r["anchor"]["cluster_id"] == selection["cluster_id"])
                handoff._same(selection["selection_mode"], "candidate", "candidate selection")
                handoff._same(selection["selected_candidate"], candidate, "saved candidate")
                handoff._same(s["window"], {k: candidate["candidate_window"][k] for k in s["window"]}, "candidate window")
            window = handoff._window(s["window"]["start_utc"], s["window"]["end_utc"])
            handoff._same(handoff._bounds(window), s["window"], "window duration")
            a = self._npz(self.raw[base + "spatial_arrays.npz"])
            required = {"positive_counts", "negative_counts", "positive_ratio", "negative_ratio", "latitudes", "longitudes",
                        "window_steps", "ratio_denominator", "target_input_finite_counts", "initial_reference_input_finite_counts"}
            if set(a) != required or a["window_steps"].shape != () or a["ratio_denominator"].shape != ():
                raise EvidenceError("unexpected_array_fields")
            checked = saved_spatial._arrays(SimpleNamespace(**(a | dict(window_steps=int(a["window_steps"])))), window,
                {k: a[k] for k in ("target_input_finite_counts", "initial_reference_input_finite_counts")})
            for key in a:
                if not np.array_equal(a[key], checked[key]):
                    raise EvidenceError("inconsistent_arrays")
            handoff._same(s["ratio_denominator"], int(a["ratio_denominator"]), "denominator")
            handoff._same(s["spatial_anomalies"], self._peaks(a), "peak summaries")
            if label == "A":
                handoff._same(s["historical_reference_checks"], saved_spatial._reference_checks(a, self._peaks(a)), "reference checks")
            self.arrays[label], self.summaries[label], self.selections[label] = a, s, selection
        diff = self._npz(self.raw[prefix + "cellwise_differences.npz"])
        derived = saved_spatial._differences(self.arrays["A"], self.arrays["B"])
        if set(diff) != set(derived) or any(not np.array_equal(diff[k], derived[k]) for k in derived):
            raise EvidenceError("inconsistent_difference_arrays")
        stats = {key: dict(minimum=float(v.min()), maximum=float(v.max()), mean=float(v.mean()),
                           changed_cells=int(np.count_nonzero(v))) for key, v in diff.items()
                 if key.endswith("_b_minus_a") and v.ndim == 2}
        handoff._same(c["cellwise_statistics"], stats, "difference statistics")
        handoff._same(c["ratio_denominator_change"], int(diff["ratio_denominator_b_minus_a"]), "denominator change")
        self.statistics, self.differences = stats, diff
        self.recheck()

    def _refs(self, *identities):
        return [dict(artifact=identity, **self.sources[identity]) for identity in identities]

    def call(self, name, arguments):
        """No exceptions or source-recorded strings escape as tool errors."""
        allowed = {t["name"]: t for t in definitions(self.mode)}
        if name not in allowed:
            return dict(ok=False, error="tool_not_allowed")
        try:
            if type(arguments) is not str or len(arguments.encode("utf-8")) > MAX_ARGUMENT_BYTES:
                raise ValueError()
            args = strict_json(arguments)
            schema = allowed[name]["parameters"]["properties"]
            if type(args) is not dict or set(args) != set(schema):
                raise ValueError()
            for key, rule in schema.items():
                v = args[key]
                if rule["type"] == "string" and (type(v) is not str or len(v) > 80):
                    raise ValueError()
                if rule["type"] == "number" and (type(v) not in (int, float) or not math.isfinite(v) or not rule["minimum"] <= v <= rule["maximum"]):
                    raise ValueError()
                if "enum" in rule and v not in rule["enum"]:
                    raise ValueError()
            if name == "inspect_anomaly_interval":
                w = select_explicit_window(args["start_utc"], args["end_utc"])
                bounds = handoff._bounds(w)
                if bounds["inclusive_hours"] > 168:
                    raise ValueError()
        except (ValueError, TypeError, OverflowError, RecursionError):
            return dict(ok=False, error="invalid_arguments")
        if name != "get_evidence_inventory" and (self.bundle is None or
                (name in {"get_spatial_experiment_summary", "compare_spatial_experiments", "inspect_spatial_grid_cell"}
                 and self.status.get("spatial") != "validated_snapshot")):
            return dict(ok=False, error="evidence_unavailable")
        try:
            self.recheck()
        except (ValueError, OSError):
            return dict(ok=False, error="evidence_changed")
        try:
            data, refs = self._dispatch(name, args)
            result = dict(ok=True, data=data, sources=refs)
            if len(compact(result).encode("utf-8")) > MAX_TOOL_BYTES:
                return dict(ok=False, error="tool_output_limit")
            return result
        except (ValueError, KeyError, TypeError, OverflowError):
            return dict(ok=False, error="invalid_arguments")

    def _dispatch(self, name, args):
        pre = PRE_ROOT + "/"
        if name == "get_evidence_inventory":
            return dict(mode=self.mode, availability=self.status, external_indices=dict(Kp="unavailable", Dst="unavailable", F10_7="unavailable"),
                        verification="snapshot consistency only; origin and raw-source custody not authenticated"), []
        if name == "get_temporal_summary":
            data = {k: self.temporal[k] for k in ("analysis", "counts", "parameters", "location", "input_time_convention")}
            data["confirmed_event"] = self.bundle["record"]["confirmed_event"]
            data["scientific_input_coordinates"] = self.bundle["record"]["scientific_input_coordinates"]
            return data, self._refs(pre + "temporal_evidence.json", pre + "run_record.json")
        if name == "inspect_anomaly_interval":
            bounds = handoff._bounds(select_explicit_window(args["start_utc"], args["end_utc"]))
            coverage = self.bundle["analysis_coverage"]
            if bounds["start_utc"] < coverage["start_utc"] or bounds["end_utc"] > coverage["end_utc"]:
                raise ValueError()
            hourly = [{k: h[k] for k in ("timestamp_utc", "classification", "anomaly_code")}
                      for h in self.temporal["hourly"] if bounds["start_utc"] <= h["timestamp_utc"] <= bounds["end_utc"]]
            return dict(window=bounds, hourly=hourly), self._refs(pre + "temporal_evidence.json")
        if name == "get_historical_context":
            h = self.historical
            return dict(configuration=h["configuration"], n_selected_events=h["earthquake_selection"]["n_selected_events"],
                        n_catalog_events=h["earthquake_selection"]["n_catalog_events"],
                        silhouette=h["clustering"]["silhouette"], significant_cells=h["clustering"]["n_significant_cells"],
                        anchors=h["clustering"]["temporal_anchors"], population_baseline=h["population_baseline"],
                        original_observation_quality="unknown", original_interpolation_history="unknown"), self._refs(pre + "historical_context.json")
        if name == "list_candidate_windows":
            fields = ("anchor", "anchor_date_utc", "status", "reason", "candidate_window", "backward_stop", "forward_stop")
            return dict(policy_name=self.proposal["policy_name"], scientific_rule=self.proposal["scientific_rule"],
                        data_quality_rule=self.proposal["data_quality_rule"],
                        candidates=[{k: r[k] for k in fields} for r in self.proposal["anchor_reports"]],
                        historical_reference=self.bundle["record"]["historical_research_reference"],
                        authority="Candidates are proposals only; anchors do not establish complete windows or execution approval."), self._refs(pre + "window_proposal.json", pre + "run_record.json")
        refs = self._refs(POST_ROOT + "/comparison_summary.json", POST_ROOT + "/cellwise_differences.npz",
                          *(POST_ROOT + "/" + n + "/spatial_arrays.npz" for n in EXPERIMENTS.values()))
        if name == "get_spatial_experiment_summary":
            label = args["experiment"]
            s, selected, a = self.summaries[label], self.selections[label], self.arrays[label]
            return dict(experiment=label, selection_origin="saved researcher record; not an Agent decision or authenticated approval",
                        selection_mode=selected["selection_mode"], cluster_id=selected["cluster_id"], window=s["window"],
                        parameters=s["parameters"], peaks=self._peaks(a), ratio_denominator=int(a["ratio_denominator"]),
                        historical_reference_checks=s["historical_reference_checks"], effective_detector_valid_counts=None,
                        availability_scope="Finite input counts are diagnostics only, not detector-valid counts or ratio denominators."), refs + self._refs(
                            POST_ROOT + "/" + EXPERIMENTS[label] + "/experiment_summary.json",
                            SELECTION_ROOT + "/" + EXPERIMENTS[label] + "/selection_record.json")
        if name == "compare_spatial_experiments":
            return dict(direction="B minus A", ratio_difference_unit="percentage_points", statistics=self.statistics,
                        denominators={k: int(a["ratio_denominator"]) for k, a in self.arrays.items()},
                        stable_peak_coordinates={p: self._peaks(self.arrays["A"])[p]["maximum_grid_points"] ==
                                                 self._peaks(self.arrays["B"])[p]["maximum_grid_points"] for p in ("positive", "negative")},
                        missing_physical_evidence=["Kp", "Dst", "F10.7"], effective_detector_valid_counts=None,
                        scope="Global grid statistics are not an epicentral distribution or causal evidence."), refs
        a = self.arrays["A"]
        i = int(np.argmin(np.abs(a["latitudes"] - args["latitude"])))
        j = int(np.argmin(np.abs((a["longitudes"] - args["longitude"] + 180) % 360 - 180)))
        fields = ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio", "target_input_finite_counts", "initial_reference_input_finite_counts")
        return dict(requested_coordinates=args, actual_grid=dict(latitude=float(a["latitudes"][i]), longitude=float(a["longitudes"][j])),
                    nearest_rule="absolute latitude and circular longitude; first index wins ties", ratio_unit="percent",
                    experiments={k: {**{f: v[f][i, j].item() for f in fields}, "ratio_denominator": int(v["ratio_denominator"])} for k, v in self.arrays.items()},
                    differences_b_minus_a={f: self.differences[f + "_b_minus_a"][i, j].item() for f in fields},
                    effective_detector_valid_counts=None), refs
