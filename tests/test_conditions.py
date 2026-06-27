"""Tests for conditions module."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pyflowx.conditions import (
    IS_LINUX,
    IS_MACOS,
    IS_POSIX,
    IS_WINDOWS,
    BuiltinConditions,
    Constants,
)

_CTX: dict[str, object] = {}


def test_constants_is_windows():
    assert (sys.platform == "win32") == Constants.IS_WINDOWS


def test_constants_is_linux():
    assert (sys.platform == "linux") == Constants.IS_LINUX


def test_constants_is_macos():
    assert (sys.platform == "darwin") == Constants.IS_MACOS


def test_constants_is_posix():
    assert (sys.platform != "win32") == Constants.IS_POSIX


def test_module_level_static_conditions():
    assert IS_WINDOWS(_CTX) == Constants.IS_WINDOWS
    assert IS_LINUX(_CTX) == Constants.IS_LINUX
    assert IS_MACOS(_CTX) == Constants.IS_MACOS
    assert IS_POSIX(_CTX) == Constants.IS_POSIX


def test_python_version_major_only():
    current_major = sys.version_info.major
    assert BuiltinConditions.PYTHON_VERSION(current_major)(_CTX) is True
    assert BuiltinConditions.PYTHON_VERSION(current_major + 1)(_CTX) is False


def test_python_version_with_minor():
    current_major = sys.version_info.major
    current_minor = sys.version_info.minor
    assert BuiltinConditions.PYTHON_VERSION(current_major, current_minor)(_CTX) is True
    assert BuiltinConditions.PYTHON_VERSION(current_major, current_minor + 1)(_CTX) is False


def test_python_version_at_least():
    current_major = sys.version_info.major
    current_minor = sys.version_info.minor
    assert BuiltinConditions.PYTHON_VERSION_AT_LEAST(current_major, current_minor)(_CTX) is True
    assert BuiltinConditions.PYTHON_VERSION_AT_LEAST(current_major - 1, 0)(_CTX) is True
    assert BuiltinConditions.PYTHON_VERSION_AT_LEAST(current_major + 1, 0)(_CTX) is False


def test_has_installed_true():
    condition = BuiltinConditions.HAS_INSTALLED("python3")
    assert condition(_CTX) is True


def test_has_installed_false():
    condition = BuiltinConditions.HAS_INSTALLED("nonexistent_app_12345")
    assert condition(_CTX) is False


def test_env_var_exists_true():
    with patch.dict(os.environ, {"TEST_VAR": "value"}):
        condition = BuiltinConditions.ENV_VAR_EXISTS("TEST_VAR")
        assert condition(_CTX) is True


def test_env_var_exists_false():
    condition = BuiltinConditions.ENV_VAR_EXISTS("NONEXISTENT_VAR_12345")
    assert condition(_CTX) is False


def test_env_var_equals_true():
    with patch.dict(os.environ, {"TEST_VAR": "expected_value"}):
        condition = BuiltinConditions.ENV_VAR_EQUALS("TEST_VAR", "expected_value")
        assert condition(_CTX) is True


def test_env_var_equals_false():
    with patch.dict(os.environ, {"TEST_VAR": "different_value"}):
        condition = BuiltinConditions.ENV_VAR_EQUALS("TEST_VAR", "expected_value")
        assert condition(_CTX) is False


def test_not():
    true_cond = BuiltinConditions.HAS_INSTALLED("python3")
    false_cond = BuiltinConditions.HAS_INSTALLED("nonexistent_app_12345")

    assert BuiltinConditions.NOT(true_cond)(_CTX) is False
    assert BuiltinConditions.NOT(false_cond)(_CTX) is True


def test_and_all_true():
    cond = BuiltinConditions.AND(
        BuiltinConditions.HAS_INSTALLED("python3"),
        BuiltinConditions.HAS_INSTALLED("python3"),
    )
    assert cond(_CTX) is True


def test_and_one_false():
    cond = BuiltinConditions.AND(
        BuiltinConditions.HAS_INSTALLED("python3"),
        BuiltinConditions.HAS_INSTALLED("nonexistent_app"),
    )
    assert cond(_CTX) is False


def test_or_all_false():
    cond = BuiltinConditions.OR(
        BuiltinConditions.HAS_INSTALLED("nonexistent1"),
        BuiltinConditions.HAS_INSTALLED("nonexistent2"),
    )
    assert cond(_CTX) is False


def test_or_one_true():
    cond = BuiltinConditions.OR(
        BuiltinConditions.HAS_INSTALLED("nonexistent1"),
        BuiltinConditions.HAS_INSTALLED("python3"),
    )
    assert cond(_CTX) is True


# ---------------------------------------------------------------------- #
# 上下文条件：基于上游依赖结果
# ---------------------------------------------------------------------- #
def test_dep_equals_true():
    ctx = {"upstream": 42}
    cond = BuiltinConditions.DEP_EQUALS("upstream", 42)
    assert cond(ctx) is True


def test_dep_equals_false():
    ctx = {"upstream": 99}
    cond = BuiltinConditions.DEP_EQUALS("upstream", 42)
    assert cond(ctx) is False


def test_dep_equals_missing_dep():
    cond = BuiltinConditions.DEP_EQUALS("missing", 42)
    assert cond({}) is False


def test_dep_matches_true():
    ctx = {"upstream": [1, 2, 3]}
    cond = BuiltinConditions.DEP_MATCHES("upstream", lambda v: len(v) == 3)
    assert cond(ctx) is True


def test_dep_matches_false():
    ctx = {"upstream": [1, 2]}
    cond = BuiltinConditions.DEP_MATCHES("upstream", lambda v: len(v) == 3)
    assert cond(ctx) is False


def test_dep_matches_exception_returns_false():
    ctx = {"upstream": ""}
    cond = BuiltinConditions.DEP_MATCHES("upstream", lambda v: v[0])
    assert cond(ctx) is False


def test_dep_present_true():
    ctx = {"upstream": "value"}
    cond = BuiltinConditions.DEP_PRESENT("upstream")
    assert cond(ctx) is True


def test_dep_present_false_none():
    # pyrefly: ignore [implicit-any-empty-container]
    ctx = {"upstream": None}
    cond = BuiltinConditions.DEP_PRESENT("upstream")
    assert cond(ctx) is False


def test_dep_present_false_missing():
    cond = BuiltinConditions.DEP_PRESENT("missing")
    assert cond({}) is False


def test_dep_truthy_true():
    ctx = {"upstream": [1]}
    cond = BuiltinConditions.DEP_TRUTHY("upstream")
    assert cond(ctx) is True


def test_dep_truthy_false():
    # pyrefly: ignore [implicit-any-empty-container]
    ctx = {"upstream": []}
    cond = BuiltinConditions.DEP_TRUTHY("upstream")
    assert cond(ctx) is False


def test_dep_truthy_missing():
    cond = BuiltinConditions.DEP_TRUTHY("missing")
    assert cond({}) is False


def test_logical_combination_with_dep_conditions():
    ctx = {"a": 1, "b": 0}
    cond = BuiltinConditions.AND(
        BuiltinConditions.DEP_EQUALS("a", 1),
        BuiltinConditions.NOT(BuiltinConditions.DEP_TRUTHY("b")),
    )
    assert cond(ctx) is True


# ---------------------------------------------------------------------- #
# IS_RUNNING: 跨平台 subprocess 检测
# ---------------------------------------------------------------------- #
def test_is_running_windows_found(monkeypatch: pytest.MonkeyPatch):
    """Windows 上 tasklist 检测到进程."""
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_WINDOWS", True)
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_LINUX", False)

    class MockResult:
        stdout = "explorer.exe\nother.exe"
        returncode = 0

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_, **__: MockResult(),
    )
    cond = BuiltinConditions.IS_RUNNING("explorer.exe")
    assert cond({}) is True


def test_is_running_windows_not_found(monkeypatch: pytest.MonkeyPatch):
    """Windows 上 tasklist 未检测到进程."""
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_WINDOWS", True)
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_LINUX", False)

    class MockResult:
        stdout = "other.exe"
        returncode = 0

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_, **__: MockResult(),
    )
    cond = BuiltinConditions.IS_RUNNING("explorer.exe")
    assert cond({}) is False


def test_is_running_linux_found(monkeypatch: pytest.MonkeyPatch):
    """Linux 上 pgrep 检测到进程."""
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_WINDOWS", False)
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_LINUX", True)

    class MockResult:
        returncode = 0

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_, **__: MockResult(),
    )
    cond = BuiltinConditions.IS_RUNNING("nginx")
    assert cond({}) is True


def test_is_running_linux_not_found(monkeypatch: pytest.MonkeyPatch):
    """Linux 上 pgrep 未检测到进程."""
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_WINDOWS", False)
    monkeypatch.setattr("pyflowx.conditions.Constants.IS_LINUX", True)

    class MockResult:
        returncode = 1

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_, **__: MockResult(),
    )
    cond = BuiltinConditions.IS_RUNNING("nonexistent")
    assert cond({}) is False


def test_dir_exists_true(tmp_path: Path):
    """DIR_EXISTS 检测路径存在."""
    cond = BuiltinConditions.DIR_EXISTS(tmp_path)
    assert cond({}) is True


def test_dir_exists_false(tmp_path: Path):
    """DIR_EXISTS 检测路径不存在."""
    missing = tmp_path / "nonexistent"
    cond = BuiltinConditions.DIR_EXISTS(missing)
    assert cond({}) is False
