"""Export paper-style spatial plots from a Stage 2 workflow result."""

from dataclasses import dataclass
from pathlib import Path
import math
import re

from src.spatial_verification.spatial_plot import (
    save_spatial_anomaly_plot,
)

from .spatial_verification_workflow import (
    SpatialVerificationWorkflowResult,
)


@dataclass(frozen=True)
class SpatialPlotExportResult:
    case_id: str
    output_dir: Path
    positive_plot: Path
    negative_plot: Path


def _validate_coordinates(
    latitude: float,
    longitude: float,
    magnitude: float,
) -> None:
    for name, value, minimum, maximum in (
        ("latitude", latitude, -90.0, 90.0),
        ("longitude", longitude, -180.0, 180.0),
    ):
        if isinstance(value, bool) or not isinstance(
            value, (int, float)
        ):
            raise TypeError(f"{name} must be numeric.")

        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite.")

        if not minimum <= value <= maximum:
            raise ValueError(f"{name} is outside its valid range.")

    if isinstance(magnitude, bool) or not isinstance(
        magnitude, (int, float)
    ):
        raise TypeError("magnitude must be numeric.")

    if not math.isfinite(magnitude) or magnitude <= 0:
        raise ValueError("magnitude must be finite and positive.")


def export_spatial_plots(
    workflow_result: SpatialVerificationWorkflowResult,
    *,
    output_dir: Path,
    epicenter_latitude: float,
    epicenter_longitude: float,
    magnitude: float,
) -> SpatialPlotExportResult:
    """Export positive and negative anomaly maps.

    Does not modify Stage 1 artifacts or scientific arrays.
    """
    if not isinstance(
        workflow_result,
        SpatialVerificationWorkflowResult,
    ):
        raise TypeError(
            "workflow_result must be a "
            "SpatialVerificationWorkflowResult."
        )

    if not isinstance(output_dir, Path):
        raise TypeError("output_dir must be a pathlib.Path.")

    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output_dir must be a directory.")

    _validate_coordinates(
        epicenter_latitude,
        epicenter_longitude,
        magnitude,
    )

    case_id = workflow_result.preparation_manifest.case_id

    # Case IDs are metadata, not trusted filesystem paths.
    # Use a safe filename component without changing the
    # original case ID stored in the result.
    safe_case_id = re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        case_id,
    )

    if not safe_case_id or not safe_case_id.strip("_"):
        raise ValueError("case_id has no valid filename characters.")

    window = workflow_result.window

    if window.selection_mode != "explicit":
        raise ValueError(
            "Only researcher-selected explicit windows are supported."
        )

    window_id = (
        f"{window.start_time:%Y%m%dT%H%M}_"
        f"{window.end_time:%Y%m%dT%H%M}"
    )

    prefix = f"{safe_case_id}_{window_id}"

    output_dir = output_dir.resolve()

    positive_path = (
        output_dir / f"{prefix}_positive_spatial.png"
    )
    negative_path = (
        output_dir / f"{prefix}_negative_spatial.png"
    )

    # V1 does not overwrite existing plots.
    # This also prevents partial replacement of an
    # already completed export.
    if positive_path.exists() or negative_path.exists():
        raise FileExistsError(
            "A spatial plot for this case and UTC window "
            "already exists."
        )

    created_paths = []

    try:
        for polarity, path in (
            ("positive", positive_path),
            ("negative", negative_path),
        ):
            # Record the target before invoking the writer so
            # a partially written PNG can also be cleaned up.
            created_paths.append(path)

            save_spatial_anomaly_plot(
                workflow_result.spatial_result,
                polarity=polarity,
                output_path=path,
                start_time=window.start_time,
                end_time=window.end_time,
                epicenter_latitude=epicenter_latitude,
                epicenter_longitude=epicenter_longitude,
                magnitude=magnitude,
            )
    except Exception:
        for path in created_paths:
            if path.is_file():
                path.unlink()
        raise

    return SpatialPlotExportResult(
        case_id=case_id,
        output_dir=output_dir,
        positive_plot=positive_path,
        negative_plot=negative_path,
    )
