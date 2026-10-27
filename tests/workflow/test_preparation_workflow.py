"""Tests for Framework A+B+C preparation orchestration."""

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.workflow.preparation_workflow as module

from src.workflow.workflow_config import WorkflowConfig


def make_config(tmp_path):
    return WorkflowConfig(
        case_id="synthetic_case",
        output_dir=tmp_path / "outputs",
        temporal_data_dir=tmp_path / "temporal_data",
        statistical_data_dir=tmp_path / "statistical_data",
        spatial_dataset_dir=tmp_path / "spatial_data",
    )


def make_kwargs():
    return {
        "temporal_start_time": datetime(2022, 2, 1),
        "temporal_end_time": datetime(2022, 2, 28, 23),
        "latitude": 35.0,
        "longitude": 70.0,
        "historical_epochs": ["synthetic_epochs"],
        "historical_tec": ["synthetic_tec"],
        "historical_start_date": date(2021, 1, 1),
        "historical_end_date": date(2022, 12, 31),
        "earthquake_dates": ["synthetic_events"],
        "earthquake_magnitudes": ["synthetic_magnitudes"],
    }


def install_stubs(monkeypatch, tmp_path):
    """Replace expensive scientific stages with controlled results."""

    calls = []

    historical = SimpleNamespace(name="historical")
    analysis = SimpleNamespace(name="analysis")
    significance = SimpleNamespace(name="significance")
    clustering_core = SimpleNamespace(name="clustering_core")
    clustering = SimpleNamespace(
        name="clustering",
        clustering=clustering_core,
    )
    temporal_anomaly = SimpleNamespace(name="temporal_anomaly")
    temporal = SimpleNamespace(
        name="temporal",
        anomaly_result=temporal_anomaly,
        plot_path=tmp_path / "saved_plot.png",
    )

    def historical_stub(**kwargs):
        calls.append(("historical", kwargs))
        return historical

    def analysis_stub(**kwargs):
        calls.append(("analysis", kwargs))
        return analysis

    def significance_stub(**kwargs):
        calls.append(("significance", kwargs))
        return significance

    def clustering_stub(**kwargs):
        calls.append(("clustering", kwargs))
        return clustering

    def temporal_stub(**kwargs):
        calls.append(("temporal", kwargs))
        return temporal

    monkeypatch.setattr(
        module, "prepare_historical_daily_tec", historical_stub
    )
    monkeypatch.setattr(
        module, "run_statistical_analysis", analysis_stub
    )
    monkeypatch.setattr(
        module, "run_statistical_significance", significance_stub
    )
    monkeypatch.setattr(
        module, "run_clustering_workflow", clustering_stub
    )
    monkeypatch.setattr(
        module, "run_temporal_workflow", temporal_stub
    )

    # Only the result constructor is replaced, because its
    # strict type checks belong to the existing I3-1 tests.
    def preparation_stub(**kwargs):
        calls.append(("preparation", kwargs))
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(
        module, "WorkflowPreparationResult", preparation_stub
    )

    return calls


def test_stage_execution_order(monkeypatch, tmp_path):
    calls = install_stubs(monkeypatch, tmp_path)

    module.run_preparation_workflow(
        make_config(tmp_path),
        **make_kwargs(),
    )

    assert [name for name, _ in calls] == [
        "historical",
        "analysis",
        "significance",
        "clustering",
        "temporal",
        "preparation",
    ]


def test_shared_parameters_forwarded(monkeypatch, tmp_path):
    calls = install_stubs(monkeypatch, tmp_path)

    module.run_preparation_workflow(
        make_config(tmp_path),
        **make_kwargs(),
        observation_days=20,
        reference_days=12,
        threshold_multiplier=1.5,
        minimum_magnitude=6.5,
        critical_z=2.5,
        n_clusters=3,
        random_state=7,
        allow_historical_interpolation=True,
        min_reference_samples=8,
    )

    arguments = dict(calls)

    assert arguments["historical"]["allow_interpolation"] is True

    assert arguments["analysis"]["observation_days"] == 20
    assert arguments["analysis"]["reference_days"] == 12
    assert arguments["analysis"]["threshold_multiplier"] == 1.5
    assert arguments["analysis"]["minimum_magnitude"] == 6.5

    assert arguments["significance"]["critical_z"] == 2.5

    assert arguments["clustering"]["n_clusters"] == 3
    assert arguments["clustering"]["random_state"] == 7
    assert arguments["clustering"]["observation_days"] == 20

    assert arguments["temporal"]["reference_days"] == 12
    assert arguments["temporal"]["threshold_multiplier"] == 1.5
    assert arguments["temporal"]["min_reference_samples"] == 8


def test_result_identity_preserved(monkeypatch, tmp_path):
    calls = install_stubs(monkeypatch, tmp_path)

    result = module.run_preparation_workflow(
        make_config(tmp_path),
        **make_kwargs(),
    )

    arguments = dict(calls)

    assert (
        result.historical
        is arguments["analysis"]["historical"]
    )
    assert (
        result.statistical_analysis
        is arguments["significance"]["analysis"]
    )
    assert (
        result.statistical_significance
        is arguments["clustering"]["significance"]
    )
    assert (
        result.clustering_workflow.clustering
        is result.preparation.clustering_result
    )
    assert (
        result.temporal_workflow.anomaly_result
        is result.preparation.temporal_result
    )
    assert (
        result.temporal_workflow.plot_path
        is result.preparation.temporal_plot_path
    )


def test_temporal_paths_and_coordinates(monkeypatch, tmp_path):
    calls = install_stubs(monkeypatch, tmp_path)

    config = make_config(tmp_path)
    module.run_preparation_workflow(
        config,
        **make_kwargs(),
    )

    arguments = dict(calls)
    temporal_args = arguments["temporal"]

    assert temporal_args["dataset_dir"] == config.temporal_data_dir
    assert temporal_args["latitude"] == 35.0
    assert temporal_args["longitude"] == 70.0
    assert temporal_args["output_path"] == (
        config.output_dir
        / "temporal"
        / "synthetic_case_temporal_anomaly.png"
    )


def test_historical_input_forwarded(monkeypatch, tmp_path):
    calls = install_stubs(monkeypatch, tmp_path)

    kwargs = make_kwargs()
    module.run_preparation_workflow(
        make_config(tmp_path),
        **kwargs,
    )

    historical_args = dict(calls)["historical"]
    analysis_args = dict(calls)["analysis"]

    assert historical_args["epochs"] is kwargs["historical_epochs"]
    assert historical_args["tec"] is kwargs["historical_tec"]
    assert (
        historical_args["start_date"]
        == kwargs["historical_start_date"]
    )
    assert (
        historical_args["end_date"]
        == kwargs["historical_end_date"]
    )
    assert analysis_args["event_dates"] is kwargs["earthquake_dates"]
    assert (
        analysis_args["magnitudes"]
        is kwargs["earthquake_magnitudes"]
    )


@pytest.mark.parametrize(
    "stage",
    [
        "prepare_historical_daily_tec",
        "run_statistical_analysis",
        "run_statistical_significance",
        "run_clustering_workflow",
        "run_temporal_workflow",
    ],
)
def test_failure_propagation(monkeypatch, tmp_path, stage):
    calls = install_stubs(monkeypatch, tmp_path)

    def failing_stage(**kwargs):
        raise RuntimeError("Synthetic stage failure")

    monkeypatch.setattr(module, stage, failing_stage)

    with pytest.raises(
        RuntimeError, match="Synthetic stage failure"
    ):
        module.run_preparation_workflow(
            make_config(tmp_path),
            **make_kwargs(),
        )

    assert not any(
        name == "preparation" for name, _ in calls
    )


def test_invalid_config_rejected(tmp_path):
    with pytest.raises(TypeError, match="WorkflowConfig"):
        module.run_preparation_workflow(
            None,
            **make_kwargs(),
        )
