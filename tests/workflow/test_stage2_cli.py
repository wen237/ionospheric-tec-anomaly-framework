"""Unit tests for the Stage 2 command-line interface.

S2-5d-3 verifies the CLI contract without running scientific
calculations or writing research artifacts.
"""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.workflow import stage2_cli


START = "2022-05-28T06:00:00Z"
END = "2022-05-29T05:00:00Z"


def make_args(**overrides):
    """Build a complete valid CLI argument list."""

    values = {
        "manifest": "outputs/preparation_manifest.json",
        "dataset_dir": "data/synthetic_gim",
        "start_time": START,
        "end_time": END,
        "latitude": "33.020",
        "longitude": "69.464",
        "magnitude": "6.0",
    }

    values.update(overrides)

    return [
        "--manifest", values["manifest"],
        "--dataset-dir", values["dataset_dir"],
        "--start-time", values["start_time"],
        "--end-time", values["end_time"],
        "--latitude", values["latitude"],
        "--longitude", values["longitude"],
        "--magnitude", values["magnitude"],
    ]


def make_result():
    """Create a lightweight fake Stage2RunResult."""

    window = SimpleNamespace(
        start_time=datetime(
            2022, 5, 28, 6, tzinfo=timezone.utc
        ),
        end_time=datetime(
            2022, 5, 29, 5, tzinfo=timezone.utc
        ),
    )

    workflow_result = SimpleNamespace(
        window=window,
    )

    plot_result = SimpleNamespace(
        case_id="synthetic_case",
        positive_plot=Path("outputs/spatial/positive.png"),
        negative_plot=Path("outputs/spatial/negative.png"),
    )

    return SimpleNamespace(
        workflow_result=workflow_result,
        plot_result=plot_result,
        summary_path=Path("outputs/spatial/summary.json"),
    )


# ============================================================
# 1. Parser Contract
# ============================================================


def test_parser_accepts_required_arguments():
    parser = stage2_cli.build_parser()

    args = parser.parse_args(make_args())

    assert args.manifest == Path(
        "outputs/preparation_manifest.json"
    )
    assert args.dataset_dir == Path("data/synthetic_gim")
    assert args.start_time == START
    assert args.end_time == END
    assert args.latitude == pytest.approx(33.020)
    assert args.longitude == pytest.approx(69.464)
    assert args.magnitude == pytest.approx(6.0)


def test_parser_uses_default_settings():
    parser = stage2_cli.build_parser()

    args = parser.parse_args(make_args())

    assert args.reference_days == 15
    assert args.k == pytest.approx(3.0)
    assert args.output_dir is None


def test_parser_accepts_optional_settings():
    parser = stage2_cli.build_parser()

    args = parser.parse_args(
        make_args()
        + [
            "--reference-days", "3",
            "--k", "1.5",
            "--output-dir", "outputs/custom_spatial",
        ]
    )

    assert args.reference_days == 3
    assert args.k == pytest.approx(1.5)
    assert args.output_dir == Path("outputs/custom_spatial")


# ============================================================
# 2. Argument Validation
# ============================================================


def test_missing_required_argument_exits_with_code_2():
    parser = stage2_cli.build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args([])

    assert exc.value.code == 2


def test_invalid_numeric_argument_exits_with_code_2():
    parser = stage2_cli.build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(
            make_args(latitude="not-a-number")
        )

    assert exc.value.code == 2


def test_help_exits_with_code_0(capsys):
    parser = stage2_cli.build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])

    assert exc.value.code == 0

    output = capsys.readouterr().out

    assert "--manifest" in output
    assert "--start-time" in output
    assert "--end-time" in output
    assert "--output-dir" in output


# ============================================================
# 3. Orchestrator Delegation
# ============================================================


def test_cli_passes_all_arguments_to_runner(monkeypatch):
    captured = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return make_result()

    monkeypatch.setattr(
        stage2_cli,
        "run_stage2",
        fake_runner,
    )

    code = stage2_cli.main(
        make_args()
        + [
            "--reference-days", "3",
            "--k", "1.5",
            "--output-dir", "outputs/custom_spatial",
        ]
    )

    assert code == 0

    assert captured == {
        "preparation_manifest_path": Path(
            "outputs/preparation_manifest.json"
        ),
        "spatial_dataset_dir": Path("data/synthetic_gim"),
        "start_time": START,
        "end_time": END,
        "epicenter_latitude": 33.020,
        "epicenter_longitude": 69.464,
        "magnitude": 6.0,
        "reference_days": 3,
        "k": 1.5,
        "output_dir": Path("outputs/custom_spatial"),
    }


def test_cli_success_message_contains_artifacts(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        stage2_cli,
        "run_stage2",
        lambda **kwargs: make_result(),
    )

    code = stage2_cli.main(make_args())

    captured = capsys.readouterr()

    assert code == 0
    assert "Stage 2 completed successfully" in captured.out
    assert "synthetic_case" in captured.out
    assert "positive.png" in captured.out
    assert "negative.png" in captured.out
    assert "summary.json" in captured.out
    assert "visual inspection only" in captured.out
    assert captured.err == ""


# ============================================================
# 4. Exit Code Handling
# ============================================================


def test_cli_existing_output_returns_code_3(
    monkeypatch,
    capsys,
):
    def fake_runner(**kwargs):
        raise FileExistsError("Existing spatial output")

    monkeypatch.setattr(
        stage2_cli,
        "run_stage2",
        fake_runner,
    )

    code = stage2_cli.main(make_args())
    captured = capsys.readouterr()

    assert code == 3
    assert "output conflict" in captured.err
    assert "Existing spatial output" in captured.err
    assert "completed successfully" not in captured.out


def test_cli_invalid_input_returns_code_2(
    monkeypatch,
    capsys,
):
    def fake_runner(**kwargs):
        raise ValueError("Invalid UTC window")

    monkeypatch.setattr(
        stage2_cli,
        "run_stage2",
        fake_runner,
    )

    code = stage2_cli.main(make_args())
    captured = capsys.readouterr()

    assert code == 2
    assert "invalid input" in captured.err
    assert "Invalid UTC window" in captured.err


def test_cli_execution_failure_returns_code_1(
    monkeypatch,
    capsys,
):
    def fake_runner(**kwargs):
        raise OSError("Simulated dataset read failure")

    monkeypatch.setattr(
        stage2_cli,
        "run_stage2",
        fake_runner,
    )

    code = stage2_cli.main(make_args())
    captured = capsys.readouterr()

    assert code == 1
    assert "execution failed" in captured.err
    assert "OSError" in captured.err
    assert "Simulated dataset read failure" in captured.err


# ============================================================
# 5. Scientific Boundary
# ============================================================


def test_cli_does_not_select_window_or_make_decision(
    monkeypatch,
    capsys,
):
    """The CLI only delegates the researcher's chosen inputs."""

    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return make_result()

    monkeypatch.setattr(
        stage2_cli,
        "run_stage2",
        fake_runner,
    )

    code = stage2_cli.main(make_args())

    output = capsys.readouterr().out

    assert code == 0
    assert len(calls) == 1

    assert calls[0]["start_time"] == START
    assert calls[0]["end_time"] == END

    assert "visual inspection only" in output
    assert "no automatic decision" in output
