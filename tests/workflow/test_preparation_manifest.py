"""Tests for the Stage 1 preparation manifest contract."""

from datetime import datetime, timezone
import json

import pytest

from src.workflow.preparation_manifest import (
    PreparationManifest,
    load_preparation_manifest,
    save_preparation_manifest,
)


def make_manifest(**overrides):
    values = {
        "schema_version": 1,
        "case_id": "afghanistan_2022",
        "created_at": datetime(
            2026, 10, 14, 7, 0, tzinfo=timezone.utc
        ),
        "temporal_plot": "temporal_anomaly.png",
        "clustering_summary": "clustering_summary.json",
        "analysis_parameters": {
            "temporal": {
                "reference_days": 15,
                "threshold_multiplier": 3.0,
            },
            "clustering": {
                "n_clusters": 2,
                "random_state": 42,
            },
        },
        "data_sources": {
            "temporal": "GIM/CODE",
            "statistical": "historical TEC",
        },
    }

    values.update(overrides)
    return PreparationManifest(**values)


def test_valid_manifest():
    manifest = make_manifest()

    assert manifest.schema_version == 1
    assert manifest.case_id == "afghanistan_2022"


def test_json_round_trip(tmp_path):
    path = tmp_path / "preparation.json"

    original = make_manifest()

    save_preparation_manifest(original, path)
    restored = load_preparation_manifest(path)

    assert restored == original


def test_reject_unsupported_schema():
    with pytest.raises(ValueError, match="schema version"):
        make_manifest(schema_version=2)


def test_reject_naive_created_at():
    with pytest.raises(ValueError, match="UTC"):
        make_manifest(
            created_at=datetime(2026, 10, 14, 7, 0)
        )


def test_reject_invalid_case_id():
    with pytest.raises(ValueError, match="case_id"):
        make_manifest(case_id="../afghanistan")


def test_reject_absolute_artifact_path():
    with pytest.raises(ValueError, match="relative path"):
        make_manifest(
            temporal_plot="C:/private/temporal_anomaly.png"
        )


def test_reject_parent_directory_traversal():
    with pytest.raises(ValueError, match="relative path"):
        make_manifest(
            clustering_summary="../clustering_summary.json"
        )


def test_reject_numpy_array():
    import numpy as np

    with pytest.raises(TypeError, match="Unsupported JSON"):
        make_manifest(
            analysis_parameters={"array": np.array([1, 2, 3])}
        )


def test_reject_nonfinite_json_value():
    with pytest.raises(ValueError, match="finite"):
        make_manifest(
            analysis_parameters={"value": float("nan")}
        )


def test_reject_missing_fields():
    data = make_manifest().to_dict()
    del data["clustering_summary"]

    with pytest.raises(ValueError, match="fields"):
        PreparationManifest.from_dict(data)


def test_reject_invalid_json_constant(tmp_path):
    path = tmp_path / "preparation.json"

    data = make_manifest().to_dict()
    data["analysis_parameters"] = {"value": float("nan")}

    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid JSON constant"):
        load_preparation_manifest(path)