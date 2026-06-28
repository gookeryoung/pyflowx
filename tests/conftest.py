from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 将 tests 目录加入 sys.path，使进程池测试能 import _proc_helper 模块级辅助函数。
# 进程池 pickle 要求被调用函数为模块级，conftest.py 在 xdist worker 中也会执行。
_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)


@pytest.fixture(autouse=True)
def packtool_tmp_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """自动切换到临时工作目录，防止测试污染项目根目录.

    Args:
        tmp_path: pytest 提供的临时目录
        monkeypatch: pytest 的 monkeypatch 工具
    """
    monkeypatch.chdir(tmp_path)
