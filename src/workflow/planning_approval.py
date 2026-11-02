"""Immutable review declarations and non-executing, fail-closed validation.

Execution intents and decision records have independent V1 schemas. Their
digests cover compact, sorted-key, strict JSON encoded as UTF-8 with a final
newline, excluding only the record's own digest field. Frozen objects store
only JSON strings and return detached dictionaries; this is content integrity,
not protection against malicious code in the same Python process.

All dataset/manifest hashes and reviewer identities are DECLARATIONS. This
module reads no source files, issues no credentials, and has no trusted-source
or trust=True parameter. Every validation result denies execution eligibility,
including structurally valid, current 'approved' review histories. A record's
trusted_authorization_verification is restricted to 'not_verified'.

Future trusted-authorizer boundary (NOT implemented): an independently
controlled service must attest the authenticated reviewer, exact intent and
proposal digests, decision lineage, expiry/revocation, and completeness of the
authoritative decision history. Its credentials and execution capability must
not be controlled by the proposer. Record omission, source-file authenticity,
reviewer identity and actual data coverage cannot be verified here. Existing
Stage 2 entry points are unchanged and are not intercepted by this module.

History starts at pending_review, then approved/rejected/revision_requested.
Approved can be revoked. Rejected/revision_requested/revoked can restart at
pending_review. Each supersession increments revision by one and binds the
same intent/proposal; a changed intent requires a new review root. Supersession
binds both predecessor ID and digest, never merely a timestamp or filename.

Proposal V1 consistency checks reuse the tested daily planner's pure policy
helpers. They do not rerun Framework A/B/C/D or establish the truth of evidence
content hashes without the original evidence. No scientific cutoffs are added.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
import re

from .planning_evidence import _provenance, _strict_copy
from .window_planning import POLICY_NAME, _assessment, _event, _expand, _iso


_SCIENTIFIC_RULE = "At least one valid target-polarity hour and no opposite-polarity hours per UTC day."
_QUALITY_RULE = "Separately require all 24 hours present and classifiable; otherwise stop with uncertain boundary."
_INTERPRETATION = "Retrospective review only; mapped anchors are neither predictions nor causal findings."
_SCOPE = "Only the bound spatial analysis; no causality or earthquake precursor identification is authorized."
_TRANSITIONS = {
    "pending_review": {"approved", "rejected", "revision_requested"},
    "approved": {"revoked"},
    "rejected": {"pending_review"},
    "revision_requested": {"pending_review"},
    "revoked": {"pending_review"},
}


def _canonical(data):
    return json.dumps(_strict_copy(data), ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")) + "\n"


def _load(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key.")
            result[key] = value
        return result

    def reject(value):
        raise ValueError(f"Invalid JSON constant: {value}.")

    return _strict_copy(json.loads(text, object_pairs_hook=unique, parse_constant=reject))


def _digest(data):
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _seal(data, field):
    data = _strict_copy(data)
    data[field] = _digest(data)
    return data


def _fields(data, fields):
    if type(data) is not dict or set(data) != set(fields):
        raise ValueError("Missing, extra or malformed contract fields.")


def _text(value):
    if type(value) is not str or not value.strip():
        raise ValueError("Identity/reason must be a nonempty string.")


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Digest must be 64 lowercase hexadecimal digits.")


def _integer(value, low=0, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ValueError("Invalid integer contract value.")


def _number(value, low=None, high=None):
    if type(value) not in (int, float) or not math.isfinite(value) or (
        low is not None and value < low
    ) or (high is not None and value > high):
        raise ValueError("Invalid finite numeric contract value.")


def _utc(value):
    if type(value) is not str:
        raise ValueError("Timestamp must be an explicit UTC ISO string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid UTC timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must specify UTC.")
    return parsed.astimezone(timezone.utc)


def _same(left, right):
    if _canonical(left) != _canonical(right):
        raise ValueError("Inconsistent contract content.")


def _check_seal(data, field):
    _hash(data[field])
    if data[field] != _digest({key: value for key, value in data.items() if key != field}):
        raise ValueError("Stale or modified record digest.")


def _window(window, included=None):
    _fields(window, ("start_utc", "end_utc", "inclusive_hours", "bounds"))
    start, end = _utc(window["start_utc"]), _utc(window["end_utc"])
    if (start > end or start.time() != time(0) or end.time() != time(23) or
            window["start_utc"] != _iso(start) or window["end_utc"] != _iso(end) or
            window["bounds"] != "inclusive_hourly_samples"):
        raise ValueError("Expected exact inclusive full-day UTC bounds.")
    _integer(window["inclusive_hours"], 1)
    if window["inclusive_hours"] != int((end - start) / timedelta(hours=1)) + 1:
        raise ValueError("Inclusive-hour count differs from UTC bounds.")
    if included is not None:
        expected = [(start.date() + timedelta(days=i)).isoformat()
                    for i in range((end.date() - start.date()).days + 1)]
        _same(included, expected)
    return start, end


def _references(references):
    _fields(references, ("temporal", "historical"))
    for name, evidence_type in (("temporal", "case_temporal_anomalies"), ("historical", "historical_bc_context")):
        ref = references[name]
        _fields(ref, ("evidence_type", "schema_version", "content_sha256", "provenance", "summary_artifact"))
        if ref["evidence_type"] != evidence_type or type(ref["schema_version"]) is not int or ref["schema_version"] != 1:
            raise ValueError("Unsupported evidence reference schema.")
        _hash(ref["content_sha256"])
        provenance = ref["provenance"]
        _same(provenance, _provenance({key: provenance[key] for key in ("sources", "processing_history")}))
        artifact = ref["summary_artifact"]
        if artifact is not None:
            if name != "historical":
                raise ValueError("Unexpected temporal summary artifact.")
            _fields(artifact, ("identity", "sha256", "size_bytes", "hash_verification"))
            _text(artifact["identity"])
            _hash(artifact["sha256"])
            _integer(artifact["size_bytes"])
            if artifact["hash_verification"] != "computed_from_read_bytes":
                raise ValueError("Unsupported summary artifact claim.")


def _daily(days):
    if type(days) is not list or not days:
        raise ValueError("Missing daily evidence.")
    fields = ("date_utc", "positive", "negative", "valid_normal", "unclassifiable", "missing_hours",
              "explicit_missing_hours", "outside_analysis_hours", "expected_hours", "evidence_hours",
              "quality_complete", "quality_reasons")
    previous = None
    for day in days:
        _fields(day, fields)
        current = date.fromisoformat(day["date_utc"])
        if current.isoformat() != day["date_utc"] or (previous is not None and current - previous != timedelta(days=1)):
            raise ValueError("Daily evidence must be ordered, unique and continuous.")
        previous = current
        for name in fields[1:10]:
            _integer(day[name], 0, 24)
        if (sum(day[name] for name in fields[1:6]) != 24 or day["expected_hours"] != 24 or
                day["explicit_missing_hours"] + day["outside_analysis_hours"] != day["missing_hours"] or
                day["evidence_hours"] + day["outside_analysis_hours"] != 24):
            raise ValueError("Inconsistent daily evidence counts.")
        reasons = (["missing_hours"] if day["missing_hours"] else []) + (
            ["unclassifiable_hours"] if day["unclassifiable"] else [])
        _same(day["quality_reasons"], reasons)
        _same(day["quality_complete"], not reasons)
    return {day["date_utc"]: day for day in days}


def _anchor(anchor):
    _fields(anchor, ("cluster_id", "hour", "centroid_day", "rounded_day", "centroid_polarity",
                     "dominant_polarity", "n_positive", "n_negative", "n_members"))
    _integer(anchor["cluster_id"])
    _integer(anchor["hour"], 0, 23)
    _number(anchor["centroid_day"], high=0)
    if type(anchor["rounded_day"]) is not int or anchor["rounded_day"] > 0:
        raise ValueError("Invalid historical relative-day anchor.")
    _number(anchor["centroid_polarity"], -1, 1)
    for name in ("n_positive", "n_negative"):
        _integer(anchor[name])
    _integer(anchor["n_members"], 1)
    pos, neg = anchor["n_positive"], anchor["n_negative"]
    _same(anchor["dominant_polarity"], 1 if pos > neg else -1 if neg > pos else 0)
    if anchor["n_members"] != pos + neg:
        raise ValueError("Inconsistent anchor composition.")


def _proposal(proposal):
    """Check V1 structure and replay only its existing pure daily policy helpers."""
    proposal = _strict_copy(proposal)
    try:
        _fields(proposal, ("report_type", "schema_version", "policy_name", "mode", "review_only", "case_event",
                           "status", "abstention_reason", "scientific_rule", "data_quality_rule", "evidence_references",
                           "daily_evidence", "anchor_reports", "interpretation", "limitations"))
        if (proposal["report_type"] != "anchor_based_daily_window_proposal" or
                type(proposal["schema_version"]) is not int or proposal["schema_version"] != 1 or
                proposal["policy_name"] != POLICY_NAME or proposal["mode"] != "retrospective" or
                proposal["review_only"] is not True or proposal["scientific_rule"] != _SCIENTIFIC_RULE or
                proposal["data_quality_rule"] != _QUALITY_RULE or proposal["interpretation"] != _INTERPRETATION):
            raise ValueError("Unsupported or inconsistent planning proposal V1.")
        event = proposal["case_event"]
        normalized, event_time = _event(
            {key: event[key] for key in ("case_id", "event_id", "time_utc", "source_reference", "source_sha256")},
            event["case_id"],
        )
        _same(event, normalized)
        _references(proposal["evidence_references"])
        daily = _daily(proposal["daily_evidence"])
        if type(proposal["limitations"]) is not list or not proposal["limitations"]:
            raise ValueError("Missing scientific limitations.")
        for limitation in proposal["limitations"]:
            _text(limitation)
        reports = proposal["anchor_reports"]
        if type(reports) is not list or not reports:
            raise ValueError("Missing anchor reports.")
        ids, pointers = set(), set()
        base = {"anchor", "selected", "anchor_date_utc", "anchor_source_reference", "status", "reason",
                "anchor_day_evidence", "included_days", "candidate_window", "evaluated_days",
                "data_quality_limitations", "backward_stop", "forward_stop", "retrospective_interpretation"}
        for report in reports:
            candidate = report["status"] == "candidate"
            _fields(report, base | ({"contains_day_zero", "contains_post_event_days", "contains_samples_at_or_after_event"}
                                    if candidate else set()))
            anchor = report["anchor"]
            _anchor(anchor)
            if anchor["cluster_id"] in ids or type(report["selected"]) is not bool:
                raise ValueError("Ambiguous anchor identity/selection.")
            ids.add(anchor["cluster_id"])
            source = report["anchor_source_reference"]
            _fields(source, ("content_sha256", "json_pointer"))
            if (source["content_sha256"] != proposal["evidence_references"]["historical"]["content_sha256"] or
                    type(source["json_pointer"]) is not str or not re.fullmatch(
                        r"/historical_summary/clustering/temporal_anchors/(0|[1-9]\d*)", source["json_pointer"]) or
                    source["json_pointer"] in pointers):
                raise ValueError("Invalid or ambiguous anchor source reference.")
            pointers.add(source["json_pointer"])
            if report["retrospective_interpretation"] is not True:
                raise ValueError("Retrospective interpretation required.")
            if not report["selected"]:
                expected = dict(status="no_candidate", reason="not_selected", anchor_date_utc=None,
                                anchor_day_evidence=None, included_days=[], candidate_window=None, evaluated_days=[],
                                data_quality_limitations=[], backward_stop=dict(status="not_attempted", reason="not_selected"),
                                forward_stop=dict(status="not_attempted", reason="not_selected"))
                _same({key: report[key] for key in expected}, expected)
                continue
            day = event_time.date() + timedelta(days=anchor["rounded_day"])
            _same(report["anchor_date_utc"], day.isoformat())
            assessment = _assessment(day, daily, anchor["dominant_polarity"])
            _same(report["anchor_day_evidence"], assessment)
            evaluated = {day.isoformat(): assessment}
            if assessment["qualifies"]:
                backward, stop_b = _expand(day, -1, daily, anchor["dominant_polarity"], evaluated)
                forward, stop_f = _expand(day, 1, daily, anchor["dominant_polarity"], evaluated)
                included = sorted(backward + [day] + forward)
                _same(report["included_days"], [value.isoformat() for value in included])
                if not candidate or report["reason"] != "anchor_and_consecutive_days_qualify":
                    raise ValueError("Inconsistent candidate status.")
                start, end = _window(report["candidate_window"], report["included_days"])
                _same(report["contains_day_zero"], event_time.date() in included)
                _same(report["contains_post_event_days"], included[-1] > event_time.date())
                _same(report["contains_samples_at_or_after_event"], end >= event_time)
            else:
                if candidate or report["status"] != "no_candidate" or report["reason"] != "invalid_anchor:" + assessment["reason"]:
                    raise ValueError("Invalid anchor cannot supply a candidate.")
                _same(report["included_days"], [])
                _same(report["candidate_window"], None)
                stop_b = stop_f = dict(status="not_attempted", reason="anchor_not_qualified")
            _same(report["backward_stop"], stop_b)
            _same(report["forward_stop"], stop_f)
            evaluated = [evaluated[key] for key in sorted(evaluated)]
            _same(report["evaluated_days"], evaluated)
            _same(report["data_quality_limitations"], [
                dict(date_utc=value["date_utc"], reasons=value["quality_reasons"], boundary_uncertain=True)
                for value in evaluated if not value["quality_complete"]])
        if (ids != set(range(len(reports))) or
                {int(pointer.rsplit("/", 1)[1]) for pointer in pointers} != set(range(len(reports)))):
            raise ValueError("Anchor IDs/source pointers do not identify the complete V1 anchor set.")
        any_candidate = any(report["status"] == "candidate" for report in reports)
        _same(proposal["status"], "candidates_proposed" if any_candidate else "abstained")
        _same(proposal["abstention_reason"], None if any_candidate else (
            "no_qualifying_selected_anchors" if any(report["selected"] for report in reports) else "no_anchors_selected"))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid planning proposal V1: {exc}") from exc
    return proposal


def _configuration(config, case_id):
    _fields(config, ("input_mode", "dataset", "reference_days", "k", "epicenter", "case_id", "manifest", "output"))
    if config["input_mode"] not in ("legacy", "modern") or config["case_id"] != case_id:
        raise ValueError("Explicit Legacy/Modern mode and matching case_id required.")
    dataset = config["dataset"]
    _fields(dataset, ("identity", "version", "sha256"))
    _text(dataset["identity"])
    if dataset["version"] is not None:
        _text(dataset["version"])
    if dataset["sha256"] is not None:
        _hash(dataset["sha256"])
    if dataset["version"] is None and dataset["sha256"] is None:
        raise ValueError("Declare a dataset version or hash.")
    _integer(config["reference_days"], 1)
    _number(config["k"], 0)
    epicenter = config["epicenter"]
    _fields(epicenter, ("latitude", "longitude", "magnitude"))
    _number(epicenter["latitude"], -90, 90)
    _number(epicenter["longitude"], -180, 180)
    _number(epicenter["magnitude"])
    if epicenter["magnitude"] <= 0:
        raise ValueError("Magnitude must be positive.")
    manifest = config["manifest"]
    if manifest is None and config["input_mode"] == "legacy":
        raise ValueError("Legacy Stage 2 requires a manifest identity and declared hash.")
    if manifest is not None:
        _fields(manifest, ("identity", "sha256"))
        _text(manifest["identity"])
        _hash(manifest["sha256"])
    _fields(config["output"], ("identity",))
    _text(config["output"]["identity"])


def _intent_shape(data):
    _fields(data, ("intent_type", "schema_version", "proposal_digest", "candidate", "case_event", "policy",
                   "window", "framework_d", "source_hash_verification", "authorization_scope", "execution_intent_digest"))
    if data["intent_type"] != "framework_d_execution_intent" or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported execution-intent schema.")
    _hash(data["proposal_digest"])
    _fields(data["candidate"], ("candidate_id", "cluster_id"))
    _hash(data["candidate"]["candidate_id"])
    _integer(data["candidate"]["cluster_id"])
    _window(data["window"])
    event = data["case_event"]
    normalized, _ = _event({key: event[key] for key in (
        "case_id", "event_id", "time_utc", "source_reference", "source_sha256")}, event["case_id"])
    _same(normalized, event)
    _same(data["policy"], dict(name=POLICY_NAME, mode="retrospective", proposal_schema_version=1,
                               scientific_rule=_SCIENTIFIC_RULE, data_quality_rule=_QUALITY_RULE))
    _configuration(data["framework_d"], event["case_id"])
    if data["source_hash_verification"] != "declared_not_verified" or data["authorization_scope"] != _SCOPE:
        raise ValueError("Source verification or authorization scope cannot be elevated.")
    _check_seal(data, "execution_intent_digest")


def _decision_shape(data):
    _fields(data, ("record_type", "schema_version", "decision_id", "execution_intent_digest", "proposal_digest",
                   "status", "reviewer_identity_declaration", "decision_time_utc", "reason", "expires_at_utc",
                   "supersedes", "revision", "trusted_authorization_verification", "decision_digest"))
    if data["record_type"] != "human_review_decision_declaration" or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported decision-record schema.")
    for name in ("decision_id", "reviewer_identity_declaration", "reason"):
        _text(data[name])
    for name in ("execution_intent_digest", "proposal_digest"):
        _hash(data[name])
    if type(data["status"]) is not str or data["status"] not in _TRANSITIONS:
        raise ValueError("Unsupported review status.")
    stamp = _utc(data["decision_time_utc"])
    if data["expires_at_utc"] is not None and _utc(data["expires_at_utc"]) <= stamp:
        raise ValueError("Expiration must be after the decision timestamp.")
    _integer(data["revision"])
    previous = data["supersedes"]
    if previous is None:
        if data["revision"] != 0:
            raise ValueError("A root decision has revision zero.")
    else:
        _fields(previous, ("decision_id", "decision_digest"))
        _text(previous["decision_id"])
        _hash(previous["decision_digest"])
        if previous["decision_id"] == data["decision_id"] or data["revision"] == 0:
            raise ValueError("Invalid supersession reference/revision.")
    if data["trusted_authorization_verification"] != "not_verified":
        raise ValueError("JSON cannot assert trusted human authorization.")
    _check_seal(data, "decision_digest")


@dataclass(frozen=True)
class ExecutionIntent:
    """Immutable serialized intent; to_dict returns a detached copy."""
    _json: str

    def __post_init__(self):
        try:
            data = _load(self._json)
            _intent_shape(data)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid execution intent: {exc}") from exc
        object.__setattr__(self, "_json", _canonical(data))

    @classmethod
    def from_dict(cls, data):
        return cls(_canonical(data))

    @classmethod
    def from_json(cls, text):
        return cls(text)

    def to_dict(self):
        return json.loads(self._json)

    def to_json(self):
        return self._json

    @property
    def digest(self):
        return self.to_dict()["execution_intent_digest"]


@dataclass(frozen=True)
class DecisionRecord:
    """Immutable UNTRUSTED review declaration, never an approval credential."""
    _json: str

    def __post_init__(self):
        try:
            data = _load(self._json)
            _decision_shape(data)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid decision record: {exc}") from exc
        object.__setattr__(self, "_json", _canonical(data))

    @classmethod
    def from_dict(cls, data):
        return cls(_canonical(data))

    @classmethod
    def from_json(cls, text):
        return cls(text)

    def to_dict(self):
        return json.loads(self._json)

    def to_json(self):
        return self._json

    @property
    def digest(self):
        return self.to_dict()["decision_digest"]


def build_execution_intent(proposal: dict, *, selected_cluster_id: int, framework_d: dict) -> ExecutionIntent:
    """Bind exactly one candidate and complete explicit D configuration.

    Candidate identity hashes case_event, policy name and the full selected
    anchor report. The complete proposal digest also binds all evidence and
    unselected reports. No file hashes, manifest content or coverage are verified.

    framework_d requires input_mode ('legacy'/'modern'), dataset (identity,
    version, sha256; at least version or hash declared), reference_days, k,
    epicenter (latitude, longitude, magnitude), matching case_id, manifest
    (identity/sha256 or null for Modern), and output (identity). Legacy requires
    a manifest declaration. Destinations are bound as declared identities, not
    resolved or checked against the filesystem; future execution must do that.
    """
    proposal = _proposal(proposal)
    _integer(selected_cluster_id)
    matches = [report for report in proposal["anchor_reports"] if report["anchor"]["cluster_id"] == selected_cluster_id]
    if len(matches) != 1 or not matches[0]["selected"] or matches[0]["status"] != "candidate":
        raise ValueError("Select exactly one existing selected candidate.")
    candidate = matches[0]
    framework_d = _strict_copy(framework_d)
    _configuration(framework_d, proposal["case_event"]["case_id"])
    return ExecutionIntent.from_dict(_seal(dict(
        intent_type="framework_d_execution_intent", schema_version=1, proposal_digest=_digest(proposal),
        candidate=dict(cluster_id=selected_cluster_id, candidate_id=_digest(dict(
            case_event=proposal["case_event"], policy_name=proposal["policy_name"], anchor_report=candidate))),
        case_event=proposal["case_event"],
        policy=dict(name=proposal["policy_name"], mode=proposal["mode"], proposal_schema_version=1,
                    scientific_rule=proposal["scientific_rule"], data_quality_rule=proposal["data_quality_rule"]),
        window=candidate["candidate_window"], framework_d=framework_d,
        source_hash_verification="declared_not_verified", authorization_scope=_SCOPE,
    ), "execution_intent_digest"))


def build_decision_record(
    intent: ExecutionIntent, *, decision_id: str, status: str, reviewer_identity_declaration: str,
    decision_time_utc: str, reason: str, expires_at_utc: str | None = None,
    supersedes: DecisionRecord | None = None,
) -> DecisionRecord:
    """Record a review DECLARATION only; this never signs/authenticates approval.

    Structural validation occurs here; lineage and state transitions require
    validate_decisions with the complete history. A changed intent starts a new
    pending_review root, not a supersession of a different revision's intent.
    """
    intent = ExecutionIntent.from_dict(intent.to_dict())
    previous = None if supersedes is None else DecisionRecord.from_dict(supersedes.to_dict()).to_dict()
    if previous is not None and (previous["execution_intent_digest"] != intent.digest or
                                  previous["proposal_digest"] != intent.to_dict()["proposal_digest"]):
        raise ValueError("Changed execution intent requires a new review history.")
    return DecisionRecord.from_dict(_seal(dict(
        record_type="human_review_decision_declaration", schema_version=1, decision_id=decision_id,
        execution_intent_digest=intent.digest, proposal_digest=intent.to_dict()["proposal_digest"],
        status=status, reviewer_identity_declaration=reviewer_identity_declaration,
        decision_time_utc=decision_time_utc, reason=reason, expires_at_utc=expires_at_utc,
        supersedes=None if previous is None else dict(decision_id=previous["decision_id"], decision_digest=previous["decision_digest"]),
        revision=0 if previous is None else previous["revision"] + 1,
        trusted_authorization_verification="not_verified",
    ), "decision_digest"))


def validate_decisions(intent, proposal: dict, records, *, now_utc: str) -> dict:
    """Validate one intent's complete declared history; ALWAYS deny execution.

    Input order is irrelevant. Multiple roots, duplicate IDs, missing parents,
    branches, stale bindings and invalid transitions fail closed. Declared
    timestamps must not be in the future; expiry is exclusive (now >= expiry
    is expired). No filename/mtime is read. Record omission cannot be detected
    without an authoritative ledger. now_utc is explicit for deterministic tests.
    """
    result = dict(intent_valid=False, records_structurally_valid=False, decision_history_valid=False,
                  review_status=None, approved_review_status=False, effective_decision_id=None,
                  trusted_human_authorization=False, authorization_verification_status="not_configured",
                  execution_eligible=False, reasons=["trusted_authorizer_not_configured"])
    try:
        now = _utc(now_utc)
        intent = ExecutionIntent.from_dict(intent.to_dict() if isinstance(intent, ExecutionIntent) else intent)
        data = intent.to_dict()
        current = build_execution_intent(proposal, selected_cluster_id=data["candidate"]["cluster_id"], framework_d=data["framework_d"])
        if current.digest != intent.digest:
            raise ValueError("Proposal or selected candidate changed; new review required.")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {**result, "reasons": result["reasons"] + ["invalid_or_stale_intent"], "detail": str(exc)}
    result["intent_valid"] = True
    if not records:
        return {**result, "reasons": result["reasons"] + ["missing_decision"]}
    try:
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise ValueError("Decision records must be a sequence.")
        decisions = [DecisionRecord.from_dict(record.to_dict() if isinstance(record, DecisionRecord) else record).to_dict()
                     for record in records]
        decisions.sort(key=lambda decision: (decision["decision_id"], decision["decision_digest"]))
    except (KeyError, TypeError, ValueError) as exc:
        return {**result, "reasons": result["reasons"] + ["invalid_decision_record"], "detail": str(exc)}
    result["records_structurally_valid"] = True

    def deny(reason):
        return {**result, "reasons": result["reasons"] + [reason]}

    lookup = {}
    for decision in decisions:
        if decision["decision_id"] in lookup:
            return deny("duplicate_or_conflicting_decision_id")
        lookup[decision["decision_id"]] = decision
        if decision["execution_intent_digest"] != intent.digest or decision["proposal_digest"] != data["proposal_digest"]:
            return deny("mismatched_decision_binding")
        if _utc(decision["decision_time_utc"]) > now:
            return deny("future_decision_timestamp")
    roots = [decision for decision in decisions if decision["supersedes"] is None]
    if len(roots) != 1:
        return deny("missing_or_ambiguous_decision_root")
    if roots[0]["status"] != "pending_review":
        return deny("invalid_initial_state")
    children = {}
    for decision in decisions:
        reference = decision["supersedes"]
        if reference is None:
            continue
        parent = lookup.get(reference["decision_id"])
        if parent is None:
            return deny("missing_superseded_decision")
        if parent["decision_digest"] != reference["decision_digest"]:
            return deny("supersession_digest_mismatch")
        if parent["decision_id"] in children:
            return deny("conflicting_decision_branches")
        if decision["revision"] != parent["revision"] + 1:
            return deny("inconsistent_decision_revision")
        if _utc(decision["decision_time_utc"]) < _utc(parent["decision_time_utc"]):
            return deny("reversed_decision_timestamps")
        if decision["status"] not in _TRANSITIONS[parent["status"]]:
            return deny("invalid_state_transition")
        children[parent["decision_id"]] = decision
    current = roots[0]
    visited = {current["decision_id"]}
    while current["decision_id"] in children:
        current = children[current["decision_id"]]
        if current["decision_id"] in visited:
            return deny("cyclic_decision_history")
        visited.add(current["decision_id"])
    if len(visited) != len(decisions):
        return deny("disconnected_decision_history")
    result.update(decision_history_valid=True, review_status=current["status"],
                  approved_review_status=current["status"] == "approved", effective_decision_id=current["decision_id"])
    if current["status"] != "approved":
        return deny("review_status:" + current["status"])
    if current["expires_at_utc"] is not None and now >= _utc(current["expires_at_utc"]):
        return deny("expired_decision")
    return result
