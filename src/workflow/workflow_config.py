"""Configuration contract for scientific workflow integration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkflowConfig:
    """Shared paths and case identity for a two-stage workflow."""

    case_id: str
    output_dir: Path
    temporal_data_dir: Path
    statistical_data_dir: Path
    spatial_dataset_dir: Path

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str):
            raise TypeError("case_id must be a string.")

        if not self.case_id.strip():
            raise ValueError("case_id must not be empty.")

        if not all(
            char.isalnum() or char in ("-", "_")
            for char in self.case_id
        ):
            raise ValueError(
                "case_id may contain only letters, numbers, "
                "hyphens, and underscores."
            )

        path_fields = (
            "output_dir",
            "temporal_data_dir",
            "statistical_data_dir",
            "spatial_dataset_dir",
        )

        for name in path_fields:
            value = getattr(self, name)

            if not isinstance(value, Path):
                raise TypeError(f"{name} must be a Path object.")

            if not str(value).strip():
                raise ValueError(f"{name} must not be empty.")