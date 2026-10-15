"""Export Framework A+B+C preparation outputs and manifest."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .clustering_summary import save_clustering_summary
from .preparation_manifest import (
    SCHEMA_VERSION,
    PreparationManifest,
    save_preparation_manifest,
)
from .preparation_workflow import PreparationWorkflowRunResult


@dataclass(frozen=True)
class PreparationExportResult:
    """Paths and manifest produced by preparation export."""

    summary_path: Path
    manifest_path: Path
    manifest: PreparationManifest


def _safe_relative_path(path: Path, root: Path) -> str:
    """Require an output file inside the configured output directory."""

    if not isinstance(path, Path):
        raise TypeError("Output file path must be a Path.")

    resolved_root = root.resolve()
    resolved_path = path.resolve()

    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            "Output file must be inside config.output_dir."
        ) from exc

    if relative == Path("."):
        raise ValueError("Output path must identify a file.")

    return relative.as_posix()


def export_preparation(
    result: PreparationWorkflowRunResult,
    *,
    analysis_parameters: dict,
    data_sources: dict,
    created_at: datetime | None = None,
) -> PreparationExportResult:
    """Export clustering summary and a Schema v1 manifest.

    Framework D and UTC window selection are not executed here.
    """

    if not isinstance(result, PreparationWorkflowRunResult):
        raise TypeError(
            "result must be a PreparationWorkflowRunResult."
        )

    config = result.preparation.config

    if not isinstance(analysis_parameters, dict):
        raise TypeError("analysis_parameters must be a dictionary.")

    if not isinstance(data_sources, dict):
        raise TypeError("data_sources must be a dictionary.")

    if created_at is None:
        created_at = datetime.now(timezone.utc)

    # Validate timestamp and metadata before writing files.
    if not isinstance(created_at, datetime):
        raise TypeError("created_at must be a datetime.")

    if (
        created_at.utcoffset() is None
        or created_at.utcoffset().total_seconds() != 0
    ):
        raise ValueError("created_at must be timezone-aware UTC.")

    plot_path = result.preparation.temporal_plot_path

    if not isinstance(plot_path, Path):
        raise TypeError("temporal_plot_path must be a Path.")

    if not plot_path.is_file():
        raise FileNotFoundError(
            f"Temporal plot does not exist: {plot_path}"
        )

    summary_path = (
        config.output_dir
        / "clustering"
        / f"{config.case_id}_clustering_summary.json"
    )

    manifest_path = (
        config.output_dir
        / "preparation_manifest.json"
    )

    plot_relative = _safe_relative_path(
        plot_path, config.output_dir
    )
    summary_relative = _safe_relative_path(
        summary_path, config.output_dir
    )
    _safe_relative_path(
        manifest_path, config.output_dir
    )

    # Build the manifest first so metadata validation happens
    # before any new output file is written.
    manifest = PreparationManifest(
        schema_version=SCHEMA_VERSION,
        case_id=config.case_id,
        created_at=created_at,
        temporal_plot=plot_relative,
        clustering_summary=summary_relative,
        analysis_parameters=analysis_parameters,
        data_sources=data_sources,
    )

    # Summary is saved before the manifest, ensuring that a
    # successful manifest export references an existing summary.
    save_clustering_summary(
        result=result,
        output_path=summary_path,
    )

    if not summary_path.is_file():
        raise FileNotFoundError(
            "Clustering summary was not created."
        )

    save_preparation_manifest(
        manifest=manifest,
        path=manifest_path,
    )

    return PreparationExportResult(
        summary_path=summary_path,
        manifest_path=manifest_path,
        manifest=manifest,
    )
