"""Versioned Stage 2 spatial summary contract and JSON I/O."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import json
import math
import re


SPATIAL_SUMMARY_SCHEMA_VERSION = 1


def _require_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    return float(value)


def _require_keys(
    value: Any,
    expected: set[str],
    name: str,
) -> None:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dictionary.")
    if set(value) != expected:
        raise ValueError(f"Invalid {name} fields.")


def _require_utc_hour(value: datetime, name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime.")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be timezone-aware UTC.")
    if value.minute or value.second or value.microsecond:
        raise ValueError(f"{name} must align with an hourly epoch.")


def _require_relative_path(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or re.match(r"^[A-Za-z]:", value)
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError(f"{name} must be a safe POSIX relative path.")


def _validate_anomaly(data: Any, name: str) -> None:
    _require_keys(
        data,
        {"maximum_ratio_percent", "maximum_grid_points"},
        name,
    )

    maximum = _require_number(
        data["maximum_ratio_percent"],
        f"{name}.maximum_ratio_percent",
    )
    if not 0.0 <= maximum <= 100.0:
        raise ValueError("Maximum ratio must be between 0 and 100.")

    points = data["maximum_grid_points"]
    if not isinstance(points, list):
        raise TypeError("maximum_grid_points must be a list.")

    if maximum == 0.0 and points:
        raise ValueError("Zero-anomaly maps cannot have peak points.")
    if maximum > 0.0 and not points:
        raise ValueError("Positive maxima require peak points.")

    seen = set()

    for point in points:
        _require_keys(point, {"latitude", "longitude"}, "grid point")

        latitude = _require_number(point["latitude"], "latitude")
        longitude = _require_number(point["longitude"], "longitude")

        if not -87.5 <= latitude <= 87.5:
            raise ValueError("Grid latitude is outside GIM bounds.")
        if not -180.0 <= longitude <= 180.0:
            raise ValueError("Grid longitude is outside GIM bounds.")

        # GIM grid spacing: 2.5 degrees latitude, 5 longitude.
        lat_index = (latitude + 87.5) / 2.5
        lon_index = (longitude + 180.0) / 5.0

        if not (
            math.isclose(lat_index, round(lat_index), abs_tol=1e-8)
            and math.isclose(lon_index, round(lon_index), abs_tol=1e-8)
        ):
            raise ValueError("Peak point is not on the GIM grid.")

        key = (round(lat_index), round(lon_index))
        if key in seen:
            raise ValueError("Duplicate maximum grid point.")
        seen.add(key)


@dataclass(frozen=True)
class SpatialSummary:
    """Serializable scientific metadata for one explicit UTC window."""

    schema_version: int
    case_id: str
    start_time: datetime
    end_time: datetime
    window_steps: int
    epicenter_latitude: float
    epicenter_longitude: float
    magnitude: float
    reference_days: int
    k: float
    spatial_anomalies: dict[str, Any]
    preparation_manifest: str
    positive_plot: str
    negative_plot: str

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != SPATIAL_SUMMARY_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported spatial summary schema version.")

        if (
            not isinstance(self.case_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", self.case_id)
        ):
            raise ValueError("Invalid case_id.")

        _require_utc_hour(self.start_time, "start_time")
        _require_utc_hour(self.end_time, "end_time")

        if self.end_time < self.start_time:
            raise ValueError("End time precedes start time.")

        expected_steps = (
            int((self.end_time - self.start_time).total_seconds() // 3600)
            + 1
        )

        if (
            type(self.window_steps) is not int
            or self.window_steps != expected_steps
        ):
            raise ValueError("window_steps does not match UTC window.")

        latitude = _require_number(
            self.epicenter_latitude, "epicenter_latitude"
        )
        longitude = _require_number(
            self.epicenter_longitude, "epicenter_longitude"
        )
        magnitude = _require_number(self.magnitude, "magnitude")

        if not -90 <= latitude <= 90:
            raise ValueError("Invalid epicenter latitude.")
        if not -180 <= longitude <= 180:
            raise ValueError("Invalid epicenter longitude.")
        if magnitude <= 0:
            raise ValueError("Magnitude must be positive.")

        if type(self.reference_days) is not int or self.reference_days <= 0:
            raise ValueError("reference_days must be a positive integer.")

        if _require_number(self.k, "k") < 0:
            raise ValueError("k must be non-negative.")

        _require_keys(
            self.spatial_anomalies,
            {"positive", "negative"},
            "spatial_anomalies",
        )

        _validate_anomaly(
            self.spatial_anomalies["positive"], "positive"
        )
        _validate_anomaly(
            self.spatial_anomalies["negative"], "negative"
        )

        for name in (
            "preparation_manifest",
            "positive_plot",
            "negative_plot",
        ):
            _require_relative_path(getattr(self, name), name)

        if self.positive_plot == self.negative_plot:
            raise ValueError("Positive and negative plot paths must differ.")

    @property
    def preparation_radius_km(self) -> float:
        """Legacy earthquake preparation radius, in kilometers."""
        return 10.0 ** (0.43 * self.magnitude)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "window": {
                "selection_mode": "explicit",
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "window_steps": self.window_steps,
            },
            "earthquake": {
                "epicenter_latitude": self.epicenter_latitude,
                "epicenter_longitude": self.epicenter_longitude,
                "magnitude": self.magnitude,
                "preparation_radius_km": self.preparation_radius_km,
            },
            "analysis_parameters": {
                "reference_days": self.reference_days,
                "k": self.k,
            },
            "spatial_anomalies": self.spatial_anomalies,
            "artifacts": {
                "preparation_manifest": self.preparation_manifest,
                "positive_plot": self.positive_plot,
                "negative_plot": self.negative_plot,
            },
            "verification": {
                "method": "visual_inspection",
                "automatic_decision": None,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpatialSummary":
        _require_keys(
            data,
            {
                "schema_version", "case_id", "window", "earthquake",
                "analysis_parameters", "spatial_anomalies",
                "artifacts", "verification",
            },
            "spatial summary",
        )

        window = data["window"]
        earthquake = data["earthquake"]
        parameters = data["analysis_parameters"]
        artifacts = data["artifacts"]
        verification = data["verification"]

        _require_keys(
            window,
            {"selection_mode", "start_time", "end_time", "window_steps"},
            "window",
        )
        _require_keys(
            earthquake,
            {
                "epicenter_latitude", "epicenter_longitude",
                "magnitude", "preparation_radius_km",
            },
            "earthquake",
        )
        _require_keys(
            parameters, {"reference_days", "k"}, "analysis_parameters"
        )
        _require_keys(
            artifacts,
            {"preparation_manifest", "positive_plot", "negative_plot"},
            "artifacts",
        )
        _require_keys(
            verification,
            {"method", "automatic_decision"},
            "verification",
        )

        if window["selection_mode"] != "explicit":
            raise ValueError("Only explicit UTC windows are supported.")

        if verification != {
            "method": "visual_inspection",
            "automatic_decision": None,
        }:
            raise ValueError("Automatic verification is not supported in V1.")

        for name in ("start_time", "end_time"):
            if not isinstance(window[name], str):
                raise TypeError(f"{name} must be an ISO 8601 string.")

        try:
            start = datetime.fromisoformat(
                window["start_time"].replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                window["end_time"].replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError("Invalid UTC datetime format.") from exc

        summary = cls(
            schema_version=data["schema_version"],
            case_id=data["case_id"],
            start_time=start,
            end_time=end,
            window_steps=window["window_steps"],
            epicenter_latitude=earthquake["epicenter_latitude"],
            epicenter_longitude=earthquake["epicenter_longitude"],
            magnitude=earthquake["magnitude"],
            reference_days=parameters["reference_days"],
            k=parameters["k"],
            spatial_anomalies=data["spatial_anomalies"],
            preparation_manifest=artifacts["preparation_manifest"],
            positive_plot=artifacts["positive_plot"],
            negative_plot=artifacts["negative_plot"],
        )

        radius = _require_number(
            earthquake["preparation_radius_km"],
            "preparation_radius_km",
        )
        if not math.isclose(
            radius, summary.preparation_radius_km, rel_tol=1e-10
        ):
            raise ValueError("Preparation radius does not match magnitude.")

        return summary


def save_spatial_summary(summary: SpatialSummary, path: Path) -> None:
    if not isinstance(summary, SpatialSummary):
        raise TypeError("summary must be a SpatialSummary.")
    if not isinstance(path, Path):
        raise TypeError("path must be a Path.")

    # Revalidate in case mutable nested dictionaries were modified.
    summary = SpatialSummary.from_dict(summary.to_dict())

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(
            summary.to_dict(),
            file,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )


def load_spatial_summary(path: Path) -> SpatialSummary:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path.")

    def reject_constant(value: str):
        raise ValueError(f"Invalid JSON constant: {value}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file, parse_constant=reject_constant)

    return SpatialSummary.from_dict(data)
