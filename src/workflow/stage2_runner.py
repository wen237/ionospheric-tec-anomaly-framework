"""Unified Stage 2 execution entry point.

The researcher explicitly selects the UTC window. This module
coordinates existing scientific and export components without
changing their calculations or making earthquake decisions.
"""

from dataclasses import dataclass
from pathlib import Path
import math
import warnings

from .explicit_window import select_explicit_window
from .preparation_manifest import load_preparation_manifest
from .spatial_plot_export import (
    SpatialPlotExportResult,
    export_spatial_plots,
)
from .spatial_summary_export import export_spatial_summary
from .spatial_verification_workflow import (
    SpatialVerificationWorkflowResult,
    run_spatial_verification_workflow,
)


@dataclass(frozen=True)
class Stage2RunResult:
    """Outputs produced by one complete Stage 2 execution."""

    workflow_result: SpatialVerificationWorkflowResult
    plot_result: SpatialPlotExportResult
    summary_path: Path


def _validate_earthquake(
    latitude: float,
    longitude: float,
    magnitude: float,
) -> None:
    for name, value, minimum, maximum in (
        ("epicenter_latitude", latitude, -90.0, 90.0),
        ("epicenter_longitude", longitude, -180.0, 180.0),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric.")
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"Invalid {name}.")

    if isinstance(magnitude, bool) or not isinstance(
        magnitude, (int, float)
    ):
        raise TypeError("magnitude must be numeric.")

    if not math.isfinite(magnitude) or magnitude <= 0:
        raise ValueError("magnitude must be finite and positive.")


def _validate_parameters(reference_days: int, k: float) -> None:
    if type(reference_days) is not int or reference_days <= 0:
        raise ValueError("reference_days must be a positive integer.")

    if isinstance(k, bool) or not isinstance(k, (int, float)):
        raise TypeError("k must be numeric.")

    if not math.isfinite(k) or k < 0:
        raise ValueError("k must be finite and non-negative.")


def _planned_paths(
    output_dir: Path,
    case_id: str,
    start_time,
    end_time,
) -> tuple[Path, Path, Path]:
    """Use the filename convention of the existing exporters."""

    window_id = (
        f"{start_time:%Y%m%dT%H%M}_"
        f"{end_time:%Y%m%dT%H%M}"
    )
    prefix = f"{case_id}_{window_id}"

    return (
        output_dir / f"{prefix}_positive_spatial.png",
        output_dir / f"{prefix}_negative_spatial.png",
        output_dir / f"{prefix}_spatial_summary.json",
    )


def _remove_created_files(paths: tuple[Path, ...]) -> None:
    """Best-effort cleanup of planned Stage 2 outputs.

    A cleanup failure must not prevent attempts to remove
    the remaining files.

    This function does not establish file ownership and is
    intended for the V1 single-writer execution model.
    """

    for path in paths:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
        except OSError as exc:
            warnings.warn(
                f"Could not clean up Stage 2 artifact {path}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )


def _validate_plot_result_paths(
    plot_result: SpatialPlotExportResult,
    *,
    expected_positive: Path,
    expected_negative: Path,
    expected_directory: Path,
    expected_case_id: str,
) -> None:
    """Validate paths returned by the PNG exporter."""

    if not isinstance(plot_result, SpatialPlotExportResult):
        raise TypeError("Invalid SpatialPlotExportResult.")

    if plot_result.case_id != expected_case_id:
        raise ValueError("Plot exporter returned an unexpected case_id.")

    if plot_result.output_dir.resolve() != expected_directory:
        raise ValueError("Plot exporter returned an unexpected directory.")

    if plot_result.positive_plot.resolve() != expected_positive:
        raise ValueError("Plot exporter returned an unexpected positive path.")

    if plot_result.negative_plot.resolve() != expected_negative:
        raise ValueError("Plot exporter returned an unexpected negative path.")

    if not expected_positive.is_file():
        raise FileNotFoundError(expected_positive)

    if not expected_negative.is_file():
        raise FileNotFoundError(expected_negative)


def run_stage2(
    preparation_manifest_path: Path,
    *,
    spatial_dataset_dir: Path,
    start_time: str,
    end_time: str,
    epicenter_latitude: float,
    epicenter_longitude: float,
    magnitude: float,
    reference_days: int = 15,
    k: float = 3.0,
    output_dir: Path | None = None,
) -> Stage2RunResult:
    """Run Framework D, export PNG maps, and export summary JSON.

    The UTC window must be selected by the researcher.

    Existing output files are never intentionally overwritten.
    If a downstream export fails, files created during this run
    are cleaned up on a best-effort basis.

    This V1 entry point is intended for single-process execution;
    it does not provide concurrent-writer locking.
    """

    # 1. Validate input types and values.
    if not isinstance(preparation_manifest_path, Path):
        raise TypeError("preparation_manifest_path must be a Path.")

    if not isinstance(spatial_dataset_dir, Path):
        raise TypeError("spatial_dataset_dir must be a Path.")

    if output_dir is not None and not isinstance(output_dir, Path):
        raise TypeError("output_dir must be a Path or None.")

    _validate_earthquake(
        epicenter_latitude,
        epicenter_longitude,
        magnitude,
    )
    _validate_parameters(reference_days, k)

    window = select_explicit_window(
        start_time=start_time,
        end_time=end_time,
    )

    # 2. Determine the output root and intended filenames.
    manifest_path = preparation_manifest_path.resolve()
    manifest = load_preparation_manifest(manifest_path)

    root = manifest_path.parent

    if output_dir is None:
        destination = root / "spatial"
    else:
        destination = output_dir.resolve()

    destination = destination.resolve()

    # Stage 2 outputs must stay inside the case output root.
    try:
        relative_dir = destination.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Stage 2 output_dir must be inside the "
            "Preparation Manifest output root."
        ) from exc

    if not relative_dir.parts:
        raise ValueError(
            "Stage 2 output_dir must be a subdirectory "
            "of the Preparation Manifest output root."
        )

    if destination.exists() and not destination.is_dir():
        raise ValueError("output_dir must be a directory.")

    positive_path, negative_path, summary_path = _planned_paths(
        destination,
        manifest.case_id,
        window.start_time,
        window.end_time,
    )

    planned = (
        positive_path,
        negative_path,
        summary_path,
    )

    # Reject incomplete or existing exports before scientific work.
    if any(path.exists() or path.is_symlink() for path in planned):
        raise FileExistsError(
            "Stage 2 output already exists for this case "
            "and explicit UTC window."
        )

    # 3. Run the existing Framework D workflow.
    workflow_result = run_spatial_verification_workflow(
        preparation_manifest_path=manifest_path,
        start_time=start_time,
        end_time=end_time,
        spatial_dataset_dir=spatial_dataset_dir,
        reference_days=reference_days,
        k=k,
    )

    # 4. Export both PNGs using the existing exporter.
    # The exporter handles its own partial PNG failures.
    plot_result = export_spatial_plots(
        workflow_result,
        output_dir=destination,
        epicenter_latitude=epicenter_latitude,
        epicenter_longitude=epicenter_longitude,
        magnitude=magnitude,
    )

    try:
        # 5. Confirm that the PNG exporter followed
        # the paths planned by the orchestrator.
        _validate_plot_result_paths(
            plot_result,
            expected_positive=positive_path,
            expected_negative=negative_path,
            expected_directory=destination,
            expected_case_id=manifest.case_id,
        )

        # 6. Export the JSON summary.
        exported_summary_path = export_spatial_summary(
            workflow_result,
            plot_result,
            epicenter_latitude=epicenter_latitude,
            epicenter_longitude=epicenter_longitude,
            magnitude=magnitude,
        )

        # 7. Confirm the JSON output location.
        if not isinstance(exported_summary_path, Path):
            raise TypeError(
                "Summary exporter must return a pathlib.Path."
            )

        if exported_summary_path.resolve() != summary_path:
            raise ValueError(
                "Summary exporter returned an unexpected path."
            )

        if not summary_path.is_file():
            raise FileNotFoundError(summary_path)

    except Exception:
        try:
            _remove_created_files(
                (
                    positive_path,
                    negative_path,
                    summary_path,
                )
            )
        except OSError as cleanup_error:
            warnings.warn(
                "Stage 2 cleanup encountered an additional "
                f"filesystem error: {cleanup_error}",
                RuntimeWarning,
                stacklevel=2,
            )

        # Preserve the original Stage 2 failure.
        raise

    return Stage2RunResult(
        workflow_result=workflow_result,
        plot_result=plot_result,
        summary_path=summary_path,
    )
