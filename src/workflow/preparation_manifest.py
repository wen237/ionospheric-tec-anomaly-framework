"""Versioned preparation manifest for two-stage workflows."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import json
import math
import re


SCHEMA_VERSION = 1


def _validate_json_value(value: Any) -> None:
    """Reject values that cannot be represented as strict JSON."""

    if value is None or isinstance(value, (str, bool, int)):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON values must be finite.")
        return

    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return

    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings.")

        for item in value.values():
            _validate_json_value(item)
        return

    raise TypeError(
        f"Unsupported JSON value type: {type(value).__name__}"
    )


def _validate_relative_path(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    if not value or "\\" in value:
        raise ValueError(
            f"{name} must be a non-empty POSIX relative path."
        )

    path = Path(value)

    if (
        path.is_absolute()
        or re.match(r"^[A-Za-z]:", value)
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError(
            f"{name} must be a safe relative path."
        )


@dataclass(frozen=True)
class PreparationManifest:
    """Serializable Stage 1 metadata for later spatial verification."""

    schema_version: int
    case_id: str
    created_at: datetime
    temporal_plot: str
    clustering_summary: str
    analysis_parameters: dict[str, Any]
    data_sources: dict[str, Any]

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != SCHEMA_VERSION
        ):
            raise ValueError("Unsupported manifest schema version.")

        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or not re.fullmatch(r"[A-Za-z0-9_-]+", self.case_id)
        ):
            raise ValueError("Invalid manifest case_id.")

        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime.")

        offset = self.created_at.utcoffset()

        if offset is None or offset != timedelta(0):
            raise ValueError("created_at must be timezone-aware UTC.")

        _validate_relative_path(
            self.temporal_plot, "temporal_plot"
        )
        _validate_relative_path(
            self.clustering_summary, "clustering_summary"
        )

        for name, value in (
            ("analysis_parameters", self.analysis_parameters),
            ("data_sources", self.data_sources),
        ):
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be a dictionary.")

            _validate_json_value(value)

    def to_dict(self) -> dict[str, Any]:
        """Convert the manifest to a JSON-compatible dictionary."""

        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "created_at": self.created_at.isoformat(),
            "temporal_plot": self.temporal_plot,
            "clustering_summary": self.clustering_summary,
            "analysis_parameters": self.analysis_parameters,
            "data_sources": self.data_sources,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "PreparationManifest":
        """Reconstruct and validate a manifest dictionary."""

        if not isinstance(data, dict):
            raise TypeError("Manifest data must be a dictionary.")

        expected_keys = {
            "schema_version",
            "case_id",
            "created_at",
            "temporal_plot",
            "clustering_summary",
            "analysis_parameters",
            "data_sources",
        }

        if set(data) != expected_keys:
            raise ValueError("Invalid manifest fields.")

        if not isinstance(data["created_at"], str):
            raise TypeError("created_at must be an ISO 8601 string.")

        try:
            created_at = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError("Invalid created_at format.") from exc

        return cls(
            schema_version=data["schema_version"],
            case_id=data["case_id"],
            created_at=created_at,
            temporal_plot=data["temporal_plot"],
            clustering_summary=data["clustering_summary"],
            analysis_parameters=data["analysis_parameters"],
            data_sources=data["data_sources"],
        )


def save_preparation_manifest(
    manifest: PreparationManifest,
    path: Path,
) -> None:
    """Save a validated manifest as UTF-8 JSON."""

    if not isinstance(manifest, PreparationManifest):
        raise TypeError("manifest must be a PreparationManifest.")

    if not isinstance(path, Path):
        raise TypeError("path must be a Path.")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            manifest.to_dict(),
            file,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )


def load_preparation_manifest(path: Path) -> PreparationManifest:
    """Load and validate a preparation manifest from JSON."""

    if not isinstance(path, Path):
        raise TypeError("path must be a Path.")

    def reject_constant(value: str):
        raise ValueError(f"Invalid JSON constant: {value}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(
            file,
            parse_constant=reject_constant,
        )

    return PreparationManifest.from_dict(data)