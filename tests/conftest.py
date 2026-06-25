from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def packtool_tmp_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """自动切换到临时工作目录，防止测试污染项目根目录.

    Args:
        tmp_path: pytest 提供的临时目录
        monkeypatch: pytest 的 monkeypatch 工具
    """
    monkeypatch.chdir(tmp_path)
