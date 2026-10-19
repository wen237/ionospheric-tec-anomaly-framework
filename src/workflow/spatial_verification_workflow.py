"""Stage 2 workflow for researcher-selected spatial verification."""

from dataclasses import dataclass
from pathlib import Path
import math

from src.spatial_verification.spatial_anomaly import (
    SpatialAnomalyResult,
)

from .explicit_window import select_explicit_window
from .preparation_manifest import (
    PreparationManifest,
    load_preparation_manifest,
)
from .spatial_adapter import run_spatial_verification
from .temporal_window import TemporalWindow


@dataclass(frozen=True)
class SpatialVerificationWorkflowResult:
    """Result of one explicitly selected spatial analysis."""

    preparation_manifest_path: Path
    preparation_manifest: PreparationManifest
    window: TemporalWindow
    spatial_result: SpatialAnomalyResult
    spatial_dataset_dir: Path
    reference_days: int
    k: float


def _validate_preparation_artifact(
    output_root: Path,
    relative_path: str,
) -> Path:
    """Validate a Stage 1 artifact without leaving its output root."""

    root = output_root.resolve()
    artifact = (root / relative_path).resolve()

    try:
        artifact.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Preparation artifact must remain inside "
            "the preparation output directory."
        ) from exc

    if not artifact.is_file():
        raise FileNotFoundError(
            f"Preparation artifact does not exist: {artifact}"
        )

    return artifact


def run_spatial_verification_workflow(
    preparation_manifest_path: Path,
    *,
    start_time: str,
    end_time: str,
    spatial_dataset_dir: Path,
    reference_days: int = 15,
    k: float = 3.0,
) -> SpatialVerificationWorkflowResult:
    """Run Framework D using a researcher-selected UTC window.

    The function does not infer a window from temporal anchors,
    modify Stage 1 outputs, or perform epicentral verification.
    """

    # --------------------------------------------------------
    # 1. Validate workflow inputs.
    # --------------------------------------------------------

    if not isinstance(preparation_manifest_path, Path):
        raise TypeError(
            "preparation_manifest_path must be a Path."
        )

    if not isinstance(spatial_dataset_dir, Path):
        raise TypeError(
            "spatial_dataset_dir must be a Path."
        )

    if type(reference_days) is not int or reference_days <= 0:
        raise ValueError(
            "reference_days must be a positive integer."
        )

    if isinstance(k, bool) or not isinstance(k, (int, float)):
        raise TypeError("k must be a real number.")

    if not math.isfinite(k) or k < 0:
        raise ValueError(
            "k must be finite and non-negative."
        )

    # --------------------------------------------------------
    # 2. Load and validate the Stage 1 manifest.
    # --------------------------------------------------------

    manifest = load_preparation_manifest(
        preparation_manifest_path
    )

    # The Stage 1 exporter places the manifest directly
    # inside config.output_dir.
    output_root = preparation_manifest_path.resolve().parent

    _validate_preparation_artifact(
        output_root,
        manifest.temporal_plot,
    )

    _validate_preparation_artifact(
        output_root,
        manifest.clustering_summary,
    )

    # --------------------------------------------------------
    # 3. Parse the explicitly selected UTC window.
    # --------------------------------------------------------

    window = select_explicit_window(
        start_time=start_time,
        end_time=end_time,
    )

    if window.selection_mode != "explicit":
        raise ValueError(
            "Stage 2 requires an explicitly selected UTC window."
        )

    # --------------------------------------------------------
    # 4. Execute the existing Framework D adapter.
    # --------------------------------------------------------

    spatial_result = run_spatial_verification(
        window=window,
        dataset_dir=spatial_dataset_dir,
        reference_days=reference_days,
        k=float(k),
    )

    # --------------------------------------------------------
    # 5. Package the result without changing Stage 1.
    # --------------------------------------------------------

    return SpatialVerificationWorkflowResult(
        preparation_manifest_path=(
            preparation_manifest_path.resolve()
        ),
        preparation_manifest=manifest,
        window=window,
        spatial_result=spatial_result,
        spatial_dataset_dir=spatial_dataset_dir,
        reference_days=reference_days,
        k=float(k),
    )
