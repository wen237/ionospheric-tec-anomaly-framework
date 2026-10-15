"""Tests for Framework B+C clustering summary export."""

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest

from src.workflow.preparation_workflow import (
    PreparationWorkflowRunResult,
)
from src.workflow.clustering_summary import (
    build_clustering_summary,
    save_clustering_summary,
)


def make_result():
    mask = np.array(
        [[1, -1, 0] + [0] * 21],
        dtype=np.int8,
    )

    positive = np.zeros((1, 24), dtype=bool)
    negative = np.zeros((1, 24), dtype=bool)

    positive[0, [0, 2]] = True
    negative[0, [1, 2]] = True

    overlap = positive & negative

    anchors = [
        NS(
            cluster_id=0,
            hour=4,
            centroid_day=-8.2,
            rounded_day=-8,
            centroid_polarity=0.9,
            dominant_polarity=1,
            n_positive=5,
            n_negative=0,
            n_members=5,
        ),
        NS(
            cluster_id=1,
            hour=16,
            centroid_day=-22.1,
            rounded_day=-22,
            centroid_polarity=-0.8,
            dominant_polarity=-1,
            n_positive=0,
            n_negative=4,
            n_members=4,
        ),
    ]

    return PreparationWorkflowRunResult(
        preparation=NS(config=NS(case_id="synthetic_case")),
        temporal_workflow=NS(),
        historical=NS(
            start_date=date(2022, 1, 1),
            end_date=date(2023, 2, 4),
            n_days=400,
        ),
        statistical_analysis=NS(
            n_events=4,
            population=NS(
                positive_probability=0.05,
                negative_probability=0.04,
                valid_sample_count=9240,
                reference_days=15,
                threshold_multiplier=3.0,
            ),
            earthquake_samples=NS(
                selected_dates=[
                    date(2022, 3, 12),
                    date(2022, 6, 10),
                    date(2022, 9, 8),
                    date(2022, 12, 7),
                ],
                minimum_magnitude=6.0,
                observation_days=30,
            ),
            earthquake_subset=NS(
                relative_days=np.array([-8]),
            ),
        ),
        statistical_significance=NS(
            significance_mask=mask,
            positive_significant=positive,
            negative_significant=negative,
            overlap_mask=overlap,
            overlap_count=1,
            critical_z=1.96,
            relative_days=np.array([-8]),
            n_events=4,
        ),
        clustering_workflow=NS(
            clustering=NS(temporal_anchors=anchors),
            n_clusters=2,
            random_state=42,
            n_significant_cells=2,
        ),
    )


def test_summary_structure():
    summary = build_clustering_summary(make_result())

    assert summary["schema_version"] == 1
    assert summary["case_id"] == "synthetic_case"
    assert summary["historical_data"]["n_days"] == 400
    assert summary["earthquake_selection"]["n_selected_events"] == 4

    assert summary["clustering"]["n_clusters"] == 2
    assert summary["clustering"]["n_significant_cells"] == 2
    assert len(summary["clustering"]["temporal_anchors"]) == 2


def test_significance_counts_distinguish_overlap():
    summary = build_clustering_summary(make_result())
    stats = summary["statistical_significance"]

    assert stats["positive_significant_count"] == 2
    assert stats["negative_significant_count"] == 2
    assert stats["overlap_count"] == 1
    assert stats["positive_mask_count"] == 1
    assert stats["negative_mask_count"] == 1


def test_temporal_anchor_fields():
    summary = build_clustering_summary(make_result())
    anchors = summary["clustering"]["temporal_anchors"]

    assert anchors[0]["cluster_id"] == 0
    assert anchors[0]["rounded_day"] == -8
    assert anchors[0]["hour"] == 4
    assert anchors[0]["dominant_polarity"] == 1

    assert anchors[1]["rounded_day"] == -22
    assert anchors[1]["dominant_polarity"] == -1


def test_save_and_reload_json(tmp_path):
    output_path = (
        tmp_path / "clustering" / "summary.json"
    )

    saved = save_clustering_summary(
        make_result(),
        output_path,
    )

    assert saved == output_path
    assert saved.exists()

    with saved.open("r", encoding="utf-8") as file:
        loaded = json.load(file)

    assert loaded == build_clustering_summary(make_result())


def test_json_serializable():
    summary = build_clustering_summary(make_result())

    serialized = json.dumps(
        summary,
        allow_nan=False,
    )

    assert isinstance(serialized, str)


def test_reject_invalid_result():
    with pytest.raises(
        TypeError,
        match="PreparationWorkflowRunResult",
    ):
        build_clustering_summary(None)


def test_reject_invalid_output_path():
    with pytest.raises(TypeError, match="Path"):
        save_clustering_summary(
            make_result(),
            "summary.json",
        )


def test_reject_inconsistent_overlap():
    result = make_result()

    result.statistical_significance.overlap_count = 0

    with pytest.raises(ValueError, match="overlap count"):
        build_clustering_summary(result)


def test_reject_inconsistent_mask():
    result = make_result()

    result.statistical_significance.significance_mask[0, 0] = 0

    with pytest.raises(ValueError, match="encoding"):
        build_clustering_summary(result)


def test_reject_inconsistent_event_count():
    result = make_result()

    result.statistical_significance.n_events = 5

    with pytest.raises(ValueError, match="event counts"):
        build_clustering_summary(result)


def test_reject_nonfinite_anchor():
    result = make_result()

    result.clustering_workflow.clustering.temporal_anchors[
        0
    ].centroid_day = np.nan

    with pytest.raises(ValueError, match="non-finite"):
        build_clustering_summary(result)
