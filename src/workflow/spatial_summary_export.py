"""Build and export Stage 2 spatial summary JSON."""

from pathlib import Path
import math

import numpy as np

from src.spatial_verification.spatial_grid import (
    orient_gim_grid,
)

from .spatial_plot_export import SpatialPlotExportResult
from .spatial_summary import (
    SPATIAL_SUMMARY_SCHEMA_VERSION,
    SpatialSummary,
    save_spatial_summary,
)
from .spatial_verification_workflow import (
    SpatialVerificationWorkflowResult,
)


def _relative_artifact_path(
    path: Path,
    root: Path,
    name: str,
) -> str:
    """Return a safe POSIX path relative to the output root."""

    if not isinstance(path, Path):
        raise TypeError(f"{name} must be a pathlib.Path.")

    resolved = path.resolve()

    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be inside the Stage 1 output root."
        ) from exc

    if not relative.parts:
        raise ValueError(f"{name} must refer to a file.")

    return relative.as_posix()


def _maximum_anomaly(
    ratio: np.ndarray,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> dict:
    """Find all maximum anomaly cells in geographic coordinates."""

    ratio = np.asarray(ratio)

    if ratio.shape != (71, 73):
        raise ValueError("Spatial ratio must have shape (71, 73).")

    if not np.issubdtype(ratio.dtype, np.number):
        raise TypeError("Spatial ratio must be numeric.")

    if not np.all(np.isfinite(ratio)):
        raise ValueError("Spatial ratio must contain finite values.")

    if np.any((ratio < 0.0) | (ratio > 100.0)):
        raise ValueError("Spatial ratio must be between 0 and 100.")

    latitudes = np.asarray(latitudes)
    longitudes = np.asarray(longitudes)

    if latitudes.shape != (71,) or longitudes.shape != (73,):
        raise ValueError("Invalid GIM coordinate dimensions.")

    expected_latitudes = np.linspace(-87.5, 87.5, 71)
    expected_longitudes = np.linspace(-180.0, 180.0, 73)

    if not np.array_equal(latitudes, expected_latitudes):
        raise ValueError("Unexpected GIM latitude coordinates.")

    if not np.array_equal(longitudes, expected_longitudes):
        raise ValueError("Unexpected GIM longitude coordinates.")

    # Match the same orientation used by spatial_plot.py.
    oriented = orient_gim_grid(ratio)

    maximum = float(np.max(oriented))

    if maximum == 0.0:
        return {
            "maximum_ratio_percent": 0.0,
            "maximum_grid_points": [],
        }

    # Match the maximum-cell selection used by the V1 plot.
    peak_rows, peak_cols = np.where(
        np.isclose(oriented, maximum)
    )

    points = [
        {
            "latitude": float(latitudes[row]),
            "longitude": float(longitudes[col]),
        }
        for row, col in zip(peak_rows, peak_cols)
    ]

    return {
        "maximum_ratio_percent": maximum,
        "maximum_grid_points": points,
    }


def build_spatial_summary(
    workflow_result: SpatialVerificationWorkflowResult,
    plot_result: SpatialPlotExportResult,
    *,
    epicenter_latitude: float,
    epicenter_longitude: float,
    magnitude: float,
) -> SpatialSummary:
    """Build a validated summary without writing any files."""

    if not isinstance(
        workflow_result, SpatialVerificationWorkflowResult
    ):
        raise TypeError("Invalid spatial workflow result.")

    if not isinstance(plot_result, SpatialPlotExportResult):
        raise TypeError("Invalid spatial plot export result.")

    manifest = workflow_result.preparation_manifest
    window = workflow_result.window
    spatial = workflow_result.spatial_result

    if window.selection_mode != "explicit":
        raise ValueError(
            "Spatial Summary V1 requires an explicit UTC window."
        )

    if plot_result.case_id != manifest.case_id:
        raise ValueError(
            "Plot export case_id does not match the manifest."
        )

    if spatial.window_steps != (
        int(
            (window.end_time - window.start_time).total_seconds()
            // 3600
        )
        + 1
    ):
        raise ValueError(
            "Spatial result does not match the selected UTC window."
        )

    root = workflow_result.preparation_manifest_path.resolve().parent

    preparation_path = _relative_artifact_path(
        workflow_result.preparation_manifest_path,
        root,
        "preparation_manifest",
    )
    positive_path = _relative_artifact_path(
        plot_result.positive_plot,
        root,
        "positive_plot",
    )
    negative_path = _relative_artifact_path(
        plot_result.negative_plot,
        root,
        "negative_plot",
    )

    if not plot_result.positive_plot.is_file():
        raise FileNotFoundError(plot_result.positive_plot)

    if not plot_result.negative_plot.is_file():
        raise FileNotFoundError(plot_result.negative_plot)

    if not workflow_result.preparation_manifest_path.is_file():
        raise FileNotFoundError(
            workflow_result.preparation_manifest_path
        )

    spatial_anomalies = {
        "positive": _maximum_anomaly(
            spatial.positive_ratio,
            spatial.latitudes,
            spatial.longitudes,
        ),
        "negative": _maximum_anomaly(
            spatial.negative_ratio,
            spatial.latitudes,
            spatial.longitudes,
        ),
    }

    return SpatialSummary(
        schema_version=SPATIAL_SUMMARY_SCHEMA_VERSION,
        case_id=manifest.case_id,
        start_time=window.start_time,
        end_time=window.end_time,
        window_steps=spatial.window_steps,
        epicenter_latitude=epicenter_latitude,
        epicenter_longitude=epicenter_longitude,
        magnitude=magnitude,
        reference_days=workflow_result.reference_days,
        k=workflow_result.k,
        spatial_anomalies=spatial_anomalies,
        preparation_manifest=preparation_path,
        positive_plot=positive_path,
        negative_plot=negative_path,
    )


def export_spatial_summary(
    workflow_result: SpatialVerificationWorkflowResult,
    plot_result: SpatialPlotExportResult,
    *,
    epicenter_latitude: float,
    epicenter_longitude: float,
    magnitude: float,
) -> Path:
    """Export one summary JSON beside the spatial PNG files."""

    summary = build_spatial_summary(
        workflow_result,
        plot_result,
        epicenter_latitude=epicenter_latitude,
        epicenter_longitude=epicenter_longitude,
        magnitude=magnitude,
    )

    window_id = (
        f"{summary.start_time:%Y%m%dT%H%M}_"
        f"{summary.end_time:%Y%m%dT%H%M}"
    )

    filename = (
        f"{summary.case_id}_{window_id}_spatial_summary.json"
    )

    output_path = plot_result.output_dir.resolve() / filename

    root = workflow_result.preparation_manifest_path.resolve().parent

    # Ensure that the summary is exported within the same
    # Stage 1 output root as the referenced artifacts.
    _relative_artifact_path(
        output_path,
        root,
        "spatial_summary",
    )

    # Do not overwrite a previous scientific result.
    if output_path.exists():
        raise FileExistsError(
            f"Spatial summary already exists: {output_path}"
        )

    save_spatial_summary(summary, output_path)

    return output_path
