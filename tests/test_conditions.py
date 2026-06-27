"""Tests for conditions module."""

import os
import sys
from unittest.mock import patch

from pyflowx.conditions import (
    BuiltinConditions,
    Constants,
)


def test_constants_is_windows():
    """Test Constants.IS_WINDOWS is correct."""
    assert (sys.platform == "win32") == Constants.IS_WINDOWS


def test_constants_is_linux():
    """Test Constants.IS_LINUX is correct."""
    assert (sys.platform == "linux") == Constants.IS_LINUX


def test_constants_is_macos():
    """Test Constants.IS_MACOS is correct."""
    assert (sys.platform == "darwin") == Constants.IS_MACOS


def test_constants_is_posix():
    """Test Constants.IS_POSIX is correct."""
    assert (sys.platform != "win32") == Constants.IS_POSIX



def test_builtin_conditions_python_version_major_only():
    """Test BuiltinConditions.PYTHON_VERSION with major only."""
    # Test with current Python version
    current_major = sys.version_info.major
    assert BuiltinConditions.PYTHON_VERSION(current_major) is True
    assert BuiltinConditions.PYTHON_VERSION(current_major + 1) is False


def test_builtin_conditions_python_version_with_minor():
    """Test BuiltinConditions.PYTHON_VERSION with major and minor."""
    current_major = sys.version_info.major
    current_minor = sys.version_info.minor
    assert BuiltinConditions.PYTHON_VERSION(current_major, current_minor) is True
    assert BuiltinConditions.PYTHON_VERSION(current_major, current_minor + 1) is False


def test_builtin_conditions_python_version_at_least():
    """Test BuiltinConditions.PYTHON_VERSION_AT_LEAST."""
    current_major = sys.version_info.major
    current_minor = sys.version_info.minor
    # Current version should be at least itself
    assert BuiltinConditions.PYTHON_VERSION_AT_LEAST(current_major, current_minor) is True
    # Current version should be at least an older version
    assert BuiltinConditions.PYTHON_VERSION_AT_LEAST(current_major - 1, 0) is True
    # Current version should NOT be at least a newer version
    assert BuiltinConditions.PYTHON_VERSION_AT_LEAST(current_major + 1, 0) is False


def test_builtin_conditions_HAS_INSTALLED_true():
    """Test BuiltinConditions.HAS_INSTALLED when app exists."""
    # Python should always be available
    condition = BuiltinConditions.HAS_INSTALLED("python")
    assert condition() is True


def test_builtin_conditions_HAS_INSTALLED_false():
    """Test BuiltinConditions.HAS_INSTALLED when app doesn't exist."""
    condition = BuiltinConditions.HAS_INSTALLED("nonexistent_app_12345")
    assert condition() is False


def test_builtin_conditions_env_var_exists_true():
    """Test BuiltinConditions.ENV_VAR_EXISTS when variable exists."""
    with patch.dict(os.environ, {"TEST_VAR": "value"}):
        condition = BuiltinConditions.ENV_VAR_EXISTS("TEST_VAR")
        assert condition() is True


def test_builtin_conditions_env_var_exists_false():
    """Test BuiltinConditions.ENV_VAR_EXISTS when variable doesn't exist."""
    condition = BuiltinConditions.ENV_VAR_EXISTS("NONEXISTENT_VAR_12345")
    assert condition() is False


def test_builtin_conditions_env_var_equals_true():
    """Test BuiltinConditions.ENV_VAR_EQUALS when value matches."""
    with patch.dict(os.environ, {"TEST_VAR": "expected_value"}):
        condition = BuiltinConditions.ENV_VAR_EQUALS("TEST_VAR", "expected_value")
        assert condition() is True


def test_builtin_conditions_env_var_equals_false():
    """Test BuiltinConditions.ENV_VAR_EQUALS when value doesn't match."""
    with patch.dict(os.environ, {"TEST_VAR": "different_value"}):
        condition = BuiltinConditions.ENV_VAR_EQUALS("TEST_VAR", "expected_value")
        assert condition() is False


def test_builtin_conditions_not():
    """Test BuiltinConditions.NOT."""
    true_condition = lambda: True  # noqa: E731
    false_condition = lambda: False  # noqa: E731

    not_true = BuiltinConditions.NOT(true_condition)
    assert not_true() is False

    not_false = BuiltinConditions.NOT(false_condition)
    assert not_false() is True


def test_builtin_conditions_and_all_true():
    """Test BuiltinConditions.AND when all conditions are true."""
    true_condition = lambda: True  # noqa: E731
    condition = BuiltinConditions.AND(true_condition, true_condition, true_condition)
    assert condition() is True


def test_builtin_conditions_and_one_false():
    """Test BuiltinConditions.AND when one condition is false."""
    true_condition = lambda: True  # noqa: E731
    false_condition = lambda: False  # noqa: E731
    condition = BuiltinConditions.AND(true_condition, false_condition, true_condition)
    assert condition() is False


def test_builtin_conditions_or_all_false():
    """Test BuiltinConditions.OR when all conditions are false."""
    false_condition = lambda: False  # noqa: E731
    condition = BuiltinConditions.OR(false_condition, false_condition, false_condition)
    assert condition() is False


def test_builtin_conditions_or_one_true():
    """Test BuiltinConditions.OR when one condition is true."""
    true_condition = lambda: True  # noqa: E731
    false_condition = lambda: False  # noqa: E731
    condition = BuiltinConditions.OR(false_condition, true_condition, false_condition)
    assert condition() is True

