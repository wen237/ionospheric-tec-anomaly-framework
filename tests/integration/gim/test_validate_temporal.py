"""Isolated regression tests for strict comparison logic, no project import needed."""
import ast
from pathlib import Path
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_SCRIPT = REPO_ROOT / "scripts" / "validation" / "gim" / "validate_temporal.py"

source = ast.parse(VALIDATION_SCRIPT.read_text(encoding="utf-8"))
node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'exact_equal')
module = ast.Module(body=[node], type_ignores=[])
namespace = {'np': np}
exec(compile(ast.fix_missing_locations(module), '<exact_equal>', 'exec'), namespace)
exact_equal = namespace['exact_equal']


def test_exact_equal_nan_masks():
    exact_equal('tec', np.array([1.0, np.nan]), np.array([1.0, np.nan]))


def test_exact_equal_rejects_ulp_difference():
    with pytest.raises(AssertionError, match='different finite values=1'):
        exact_equal('tec', np.array([10.3]), np.array([np.nextafter(10.3, np.inf)]))


def test_exact_equal_rejects_nan_mask_difference():
    with pytest.raises(AssertionError):
        exact_equal('tec', np.array([np.nan]), np.array([1.0]))


def test_exact_equal_rejects_epoch_difference():
    with pytest.raises(AssertionError):
        exact_equal('epochs', np.array(['2022-01-01'], dtype='datetime64[D]'), np.array(['2022-01-02'], dtype='datetime64[D]'))


def test_exact_equal_rejects_shape_difference():
    with pytest.raises(AssertionError, match='shape mismatch'):
        exact_equal('tec', np.array([1.0]), np.array([[1.0]]))
