"""Tests for Stage 2 spatial summary schema and JSON I/O."""

from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import pytest

from src.workflow.spatial_summary import (
    SpatialSummary,
    load_spatial_summary,
    save_spatial_summary,
)


def make_summary(**overrides):
    values = {
        "schema_version": 1,
        "case_id": "synthetic_case",
        "start_time": datetime(
            2022, 5, 28, 6, tzinfo=timezone.utc
        ),
        "end_time": datetime(
            2022, 5, 29, 5, tzinfo=timezone.utc
        ),
        "window_steps": 24,
        "epicenter_latitude": 33.020,
        "epicenter_longitude": 69.464,
        "magnitude": 6.0,
        "reference_days": 3,
        "k": 3.0,
        "spatial_anomalies": {
            "positive": {
                "maximum_ratio_percent": 100.0 / 24.0,
                "maximum_grid_points": [
                    {"latitude": 37.5, "longitude": 70.0}
                ],
            },
            "negative": {
                "maximum_ratio_percent": 100.0 / 24.0,
                "maximum_grid_points": [
                    {"latitude": -12.5, "longitude": -55.0}
                ],
            },
        },
        "preparation_manifest": "preparation_manifest.json",
        "positive_plot": "spatial/positive.png",
        "negative_plot": "spatial/negative.png",
    }

    values.update(overrides)
    return SpatialSummary(**values)


def test_summary_schema_fields():
    summary = make_summary()
    data = summary.to_dict()

    assert data["schema_version"] == 1
    assert data["case_id"] == "synthetic_case"
    assert data["window"]["selection_mode"] == "explicit"
    assert data["window"]["window_steps"] == 24
    assert data["verification"]["automatic_decision"] is None


def test_preparation_radius_is_computed():
    summary = make_summary()

    assert summary.preparation_radius_km == pytest.approx(
        10 ** (0.43 * 6.0)
    )


def test_json_round_trip(tmp_path):
    summary = make_summary()
    path = tmp_path / "spatial" / "summary.json"

    save_spatial_summary(summary, path)
    loaded = load_spatial_summary(path)

    assert loaded == summary
    assert loaded.to_dict() == summary.to_dict()


def test_json_is_strict_and_readable(tmp_path):
    path = tmp_path / "summary.json"
    save_spatial_summary(make_summary(), path)

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["spatial_anomalies"]["positive"][
        "maximum_grid_points"
    ] == [{"latitude": 37.5, "longitude": 70.0}]


def test_zero_anomaly_has_no_peak_points():
    summary = make_summary()
    data = copy.deepcopy(summary.to_dict())

    data["spatial_anomalies"]["positive"] = {
        "maximum_ratio_percent": 0.0,
        "maximum_grid_points": [],
    }

    loaded = SpatialSummary.from_dict(data)

    assert loaded.spatial_anomalies["positive"][
        "maximum_grid_points"
    ] == []


def test_tied_maxima_supported():
    summary = make_summary()
    data = copy.deepcopy(summary.to_dict())

    data["spatial_anomalies"]["positive"][
        "maximum_grid_points"
    ].append({"latitude": 35.0, "longitude": 70.0})

    loaded = SpatialSummary.from_dict(data)

    assert len(
        loaded.spatial_anomalies["positive"][
            "maximum_grid_points"
        ]
    ) == 2


def test_naive_utc_rejected():
    with pytest.raises(ValueError):
        make_summary(
            start_time=datetime(2022, 5, 28, 6)
        )


def test_window_steps_mismatch_rejected():
    with pytest.raises(ValueError):
        make_summary(window_steps=23)


def test_invalid_grid_point_rejected():
    data = copy.deepcopy(make_summary().to_dict())

    data["spatial_anomalies"]["positive"][
        "maximum_grid_points"
    ][0]["latitude"] = 37.0

    with pytest.raises(ValueError, match="GIM grid"):
        SpatialSummary.from_dict(data)


def test_duplicate_grid_point_rejected():
    data = copy.deepcopy(make_summary().to_dict())

    point = data["spatial_anomalies"]["positive"][
        "maximum_grid_points"
    ][0]

    data["spatial_anomalies"]["positive"][
        "maximum_grid_points"
    ].append(point.copy())

    with pytest.raises(ValueError, match="Duplicate"):
        SpatialSummary.from_dict(data)


def test_unsafe_artifact_path_rejected():
    with pytest.raises(ValueError):
        make_summary(
            positive_plot="../outside.png"
        )


def test_automatic_decision_rejected():
    data = copy.deepcopy(make_summary().to_dict())
    data["verification"]["automatic_decision"] = True

    with pytest.raises(ValueError, match="Automatic verification"):
        SpatialSummary.from_dict(data)


def test_inconsistent_radius_rejected():
    data = copy.deepcopy(make_summary().to_dict())
    data["earthquake"]["preparation_radius_km"] = 999.0

    with pytest.raises(ValueError, match="Preparation radius"):
        SpatialSummary.from_dict(data)


def test_invalid_json_constant_rejected(tmp_path):
    path = tmp_path / "invalid_summary.json"
    path.write_text(
        '{"maximum": NaN}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid JSON constant"):
        load_spatial_summary(path)


def test_unknown_schema_field_rejected():
    data = copy.deepcopy(make_summary().to_dict())
    data["unexpected_field"] = "not_allowed"

    with pytest.raises(ValueError, match="fields"):
        SpatialSummary.from_dict(data)


# ============================================================
# S2-5c-3a: Atomic JSON Write Tests
# ============================================================

def test_atomic_save_creates_valid_json(tmp_path):
    """A successful save publishes a complete JSON document."""

    summary = make_summary()
    path = tmp_path / "spatial" / "summary.json"

    save_spatial_summary(summary, path)

    assert path.is_file()
    assert load_spatial_summary(path) == summary

    assert list(path.parent.glob("*.tmp")) == []


def test_atomic_save_rejects_existing_destination(tmp_path):
    """An existing JSON must never be overwritten."""

    path = tmp_path / "summary.json"
    original = b"existing-scientific-result"
    path.write_bytes(original)

    with pytest.raises(FileExistsError):
        save_spatial_summary(make_summary(), path)

    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_save_rejects_invalid_mutated_summary(tmp_path):
    """Validation failure must not create an output file."""

    summary = make_summary()

    summary.spatial_anomalies["positive"][
        "maximum_ratio_percent"
    ] = float("nan")

    path = tmp_path / "summary.json"

    with pytest.raises(ValueError):
        save_spatial_summary(summary, path)

    assert not path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_save_link_failure_cleans_temp(
    tmp_path,
    monkeypatch,
):
    """A failed publish must not leave partial JSON or temp files."""

    import src.workflow.spatial_summary as summary_module

    path = tmp_path / "summary.json"

    def failing_link(source, destination):
        raise OSError("Simulated hard-link failure")

    monkeypatch.setattr(
        summary_module.os,
        "link",
        failing_link,
    )

    with pytest.raises(OSError, match="hard-link failure"):
        save_spatial_summary(make_summary(), path)

    assert not path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_save_race_preserves_existing_file(
    tmp_path,
    monkeypatch,
):
    """A destination appearing during publication is preserved."""

    import src.workflow.spatial_summary as summary_module

    path = tmp_path / "summary.json"
    original_link = summary_module.os.link

    def competing_link(source, destination):
        # Simulate another writer creating the final path
        # after the initial existence check.
        Path(destination).write_bytes(b"another-writer-result")

        # The real link operation must refuse to overwrite it.
        return original_link(source, destination)

    monkeypatch.setattr(
        summary_module.os,
        "link",
        competing_link,
    )

    with pytest.raises(FileExistsError):
        save_spatial_summary(make_summary(), path)

    assert path.read_bytes() == b"another-writer-result"
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_save_leaves_no_temporary_file(
    tmp_path,
):
    """Successful publication must remove its temporary name."""

    path = tmp_path / "spatial" / "summary.json"

    save_spatial_summary(make_summary(), path)

    assert path.is_file()

    temporary_files = list(
        path.parent.glob(f".{path.stem}_*.tmp")
    )

    assert temporary_files == []
