"""S2-5d-4: Real CLI integration tests with synthetic GIM.

Execution:
    CLI -> Stage 2 Runner -> Framework D -> PNG + JSON

No scientific functions are mocked.
All artifacts are isolated in pytest temporary directories.
"""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

import matplotlib.image as mpimg
import pytest

from src.workflow.preparation_manifest import (
    PreparationManifest,
    save_preparation_manifest,
)
from src.workflow.spatial_summary import load_spatial_summary
from src.workflow.stage2_runner import run_stage2


PROJECT_ROOT = Path(__file__).resolve().parents[2]

START = "2022-05-28T06:00:00Z"
END = "2022-05-29T05:00:00Z"

CASE_ID = "synthetic_case"
LATITUDE = 33.020
LONGITUDE = 69.464
MAGNITUDE = 6.0
REFERENCE_DAYS = 3
K = 3.0


def load_synthetic_gim_helper():
    """Reuse the existing Stage 2 synthetic GIM generator."""

    helper_path = (
        Path(__file__).parent
        / "test_spatial_plot_export_integration.py"
    )

    spec = importlib.util.spec_from_file_location(
        "_stage2_cli_gim_helper",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load synthetic GIM helper.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.create_gim_dataset


CREATE_GIM_DATASET = load_synthetic_gim_helper()


def file_hash(path: Path) -> str:
    """Return a SHA-256 hash for artifact immutability checks."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_case(root: Path) -> dict:
    """Create an independent Stage 1 + synthetic GIM case."""

    output_root = root / "outputs"
    dataset_prefix = root / "gim"

    CREATE_GIM_DATASET(dataset_prefix)

    temporal_path = (
        output_root / "temporal" / "synthetic_temporal.png"
    )
    clustering_path = (
        output_root / "clustering" / "synthetic_summary.json"
    )

    temporal_path.parent.mkdir(parents=True, exist_ok=True)
    clustering_path.parent.mkdir(parents=True, exist_ok=True)

    temporal_path.write_bytes(
        b"synthetic-stage-one-temporal-artifact"
    )
    clustering_path.write_text(
        '{"case_id": "synthetic_case"}',
        encoding="utf-8",
    )

    manifest = PreparationManifest(
        schema_version=1,
        case_id=CASE_ID,
        created_at=datetime(
            2022, 6, 1, tzinfo=timezone.utc
        ),
        temporal_plot="temporal/synthetic_temporal.png",
        clustering_summary="clustering/synthetic_summary.json",
        analysis_parameters={
            "reference_days": REFERENCE_DAYS,
            "threshold_multiplier": K,
        },
        data_sources={
            "temporal": "synthetic_gim",
            "historical": "synthetic_tec",
        },
    )

    manifest_path = output_root / "preparation_manifest.json"
    save_preparation_manifest(manifest, manifest_path)

    stage_one_paths = (
        manifest_path,
        temporal_path,
        clustering_path,
    )

    return {
        "root": root,
        "manifest": manifest_path,
        "dataset_prefix": dataset_prefix,
        "output_root": output_root,
        "stage_one_paths": stage_one_paths,
        "stage_one_hashes": {
            str(path): file_hash(path)
            for path in stage_one_paths
        },
    }


def cli_arguments(case: dict) -> list[str]:
    """Build CLI arguments for a valid synthetic research case."""

    return [
        "--manifest", str(case["manifest"]),
        "--dataset-dir", str(case["dataset_prefix"]),
        "--start-time", START,
        "--end-time", END,
        "--latitude", str(LATITUDE),
        "--longitude", str(LONGITUDE),
        "--magnitude", str(MAGNITUDE),
        "--reference-days", str(REFERENCE_DAYS),
        "--k", str(K),
    ]


def run_cli(arguments: list[str]) -> subprocess.CompletedProcess:
    """Run the real CLI using the active virtual environment."""

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src.workflow.stage2_cli",
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


def expected_paths(case: dict) -> tuple[Path, Path, Path]:
    """Return the expected filenames for the explicit UTC window."""

    prefix = (
        f"{CASE_ID}_"
        "20220528T0600_20220529T0500"
    )

    output_dir = case["output_root"] / "spatial"

    return (
        output_dir / f"{prefix}_positive_spatial.png",
        output_dir / f"{prefix}_negative_spatial.png",
        output_dir / f"{prefix}_spatial_summary.json",
    )


@pytest.fixture(scope="module")
def cli_e2e(tmp_path_factory):
    """Execute one complete CLI research case."""

    root = tmp_path_factory.mktemp("stage2_cli_e2e")
    case = create_case(root)

    process = run_cli(cli_arguments(case))

    positive, negative, summary_path = expected_paths(case)

    return {
        "case": case,
        "process": process,
        "positive": positive,
        "negative": negative,
        "summary_path": summary_path,
    }


# ============================================================
# 1. Real CLI execution
# ============================================================


def test_cli_e2e_creates_all_artifacts(cli_e2e):
    process = cli_e2e["process"]

    assert process.returncode == 0, process.stderr

    positive = cli_e2e["positive"]
    negative = cli_e2e["negative"]
    summary_path = cli_e2e["summary_path"]

    assert positive.is_file()
    assert negative.is_file()
    assert summary_path.is_file()

    for path in (positive, negative):
        assert path.read_bytes().startswith(
            b"\x89PNG\r\n\x1a\n"
        )

        image = mpimg.imread(path)
        assert image.size > 0

    assert "Stage 2 completed successfully" in process.stdout
    assert "visual inspection only" in process.stdout


# ============================================================
# 2. Scientific result verification
# ============================================================


def test_cli_e2e_scientific_results(cli_e2e):
    summary = load_spatial_summary(cli_e2e["summary_path"])
    anomalies = summary.spatial_anomalies

    assert anomalies["positive"][
        "maximum_ratio_percent"
    ] == pytest.approx(100.0 / 24.0)

    assert anomalies["negative"][
        "maximum_ratio_percent"
    ] == pytest.approx(100.0 / 24.0)

    assert anomalies["positive"][
        "maximum_grid_points"
    ] == [
        {"latitude": 37.5, "longitude": 70.0}
    ]

    assert anomalies["negative"][
        "maximum_grid_points"
    ] == [
        {"latitude": -12.5, "longitude": -55.0}
    ]


# ============================================================
# 3. JSON research contract
# ============================================================


def test_cli_e2e_summary_contract(cli_e2e):
    summary_path = cli_e2e["summary_path"]

    data = json.loads(
        summary_path.read_text(encoding="utf-8")
    )

    assert data["schema_version"] == 1
    assert data["case_id"] == CASE_ID

    assert data["window"]["selection_mode"] == "explicit"
    assert data["window"]["window_steps"] == 24

    assert data["window"]["start_time"] == (
        "2022-05-28T06:00:00+00:00"
    )
    assert data["window"]["end_time"] == (
        "2022-05-29T05:00:00+00:00"
    )

    assert data["verification"] == {
        "method": "visual_inspection",
        "automatic_decision": None,
    }


# ============================================================
# 4. No-overwrite protection
# ============================================================


def test_cli_e2e_repeated_execution_is_rejected(cli_e2e):
    case = cli_e2e["case"]

    paths = expected_paths(case)

    before = {
        str(path): file_hash(path)
        for path in paths
    }

    process = run_cli(cli_arguments(case))

    assert process.returncode == 3
    assert "output conflict" in process.stderr

    for path in paths:
        assert file_hash(path) == before[str(path)]


# ============================================================
# 5. Invalid UTC window
# ============================================================


def test_cli_e2e_invalid_window_rejected(tmp_path):
    case = create_case(tmp_path / "invalid_window")

    args = cli_arguments(case)

    index = args.index("--start-time") + 1
    args[index] = "2022-05-28T06:30:00Z"

    process = run_cli(args)

    assert process.returncode == 2
    assert "invalid input" in process.stderr

    assert not any(
        path.exists()
        for path in expected_paths(case)
    )


# ============================================================
# 6. Missing required arguments
# ============================================================


def test_cli_e2e_missing_arguments_rejected():
    process = run_cli([])

    assert process.returncode == 2
    assert "required" in process.stderr.lower()


# ============================================================
# 7. Stage 1 artifact immutability
# ============================================================


def test_cli_e2e_preserves_stage_one(cli_e2e):
    case = cli_e2e["case"]

    for path in case["stage_one_paths"]:
        assert file_hash(path) == (
            case["stage_one_hashes"][str(path)]
        )


# ============================================================
# 8. CLI vs Python API reproducibility
# ============================================================


def test_cli_e2e_matches_python_api(cli_e2e, tmp_path):
    cli_summary = load_spatial_summary(
        cli_e2e["summary_path"]
    )

    api_case = create_case(tmp_path / "api_case")

    api_result = run_stage2(
        preparation_manifest_path=api_case["manifest"],
        spatial_dataset_dir=api_case["dataset_prefix"],
        start_time=START,
        end_time=END,
        epicenter_latitude=LATITUDE,
        epicenter_longitude=LONGITUDE,
        magnitude=MAGNITUDE,
        reference_days=REFERENCE_DAYS,
        k=K,
    )

    api_summary = load_spatial_summary(
        api_result.summary_path
    )

    assert cli_summary.to_dict() == api_summary.to_dict()

    assert api_result.plot_result.positive_plot.is_file()
    assert api_result.plot_result.negative_plot.is_file()

    assert api_result.summary_path.is_file()
