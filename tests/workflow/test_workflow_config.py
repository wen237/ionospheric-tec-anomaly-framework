from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.workflow.workflow_config import WorkflowConfig


def make_config(**overrides):
    values = {
        "case_id": "afghanistan_2022",
        "output_dir": Path("outputs"),
        "temporal_data_dir": Path("data/temporal"),
        "statistical_data_dir": Path("data/statistical"),
        "spatial_dataset_dir": Path("data/gim"),
    }

    values.update(overrides)

    return WorkflowConfig(**values)


def test_valid_config():
    config = make_config()

    assert config.case_id == "afghanistan_2022"
    assert config.output_dir == Path("outputs")


def test_reject_empty_case_id():
    with pytest.raises(ValueError, match="must not be empty"):
        make_config(case_id="  ")


def test_reject_invalid_case_id():
    with pytest.raises(ValueError, match="case_id may contain"):
        make_config(case_id="../afghanistan")


def test_reject_non_string_case_id():
    with pytest.raises(TypeError, match="case_id"):
        make_config(case_id=2022)


def test_reject_non_path_input():
    with pytest.raises(TypeError, match="output_dir"):
        make_config(output_dir="outputs")


def test_config_is_immutable():
    config = make_config()

    with pytest.raises(FrozenInstanceError):
        config.case_id = "another_case"