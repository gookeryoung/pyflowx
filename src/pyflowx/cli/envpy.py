"""Python 环境配置工具.

用于设置 pip 镜像源, 支持清华和阿里云等国内镜像源,
同时配置 UV 和 Conda 的镜像源.
"""

from __future__ import annotations

import os
from pathlib import Path

import pyflowx as px
from pyflowx.conditions import Constants

# ============================================================================
# 配置
# ============================================================================

PIP_INDEX_URLS: dict[str, str] = {
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple/",
}

PIP_TRUSTED_HOSTS: dict[str, str] = {
    "tsinghua": "pypi.tuna.tsinghua.edu.cn",
    "aliyun": "mirrors.aliyun.com",
}

UV_INDEX_URL: str = "https://mirrors.aliyun.com/pypi/simple/"
UV_PYTHON_INSTALL_MIRROR: str = "https://registry.npmmirror.com/-/binary/python-build-standalone"

CONDA_MIRROR_URLS: dict[str, list[str]] = {
    "tsinghua": [
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/",
    ],
    "aliyun": [
        "https://mirrors.aliyun.com/anaconda/pkgs/main/",
        "https://mirrors.aliyun.com/anaconda/pkgs/free/",
        "https://mirrors.aliyun.com/anaconda/cloud/conda-forge/",
    ],
}


# ============================================================================
# 辅助函数
# ============================================================================


def set_pip_mirror(mirror: str = "tsinghua", token: str | None = None) -> None:
    """设置 pip 镜像源.

    Parameters
    ----------
    mirror : str
        镜像源名称: tsinghua, aliyun
    token : str | None
        PyPI token for publishing
    """
    index_url = PIP_INDEX_URLS.get(mirror, PIP_INDEX_URLS["tsinghua"])
    trusted_host = PIP_TRUSTED_HOSTS.get(mirror, "")

    # 设置环境变量
    os.environ["PIP_INDEX_URL"] = index_url
    os.environ["UV_INDEX_URL"] = UV_INDEX_URL
    os.environ["UV_DEFAULT_INDEX"] = UV_INDEX_URL
    os.environ["UV_PYTHON_INSTALL_MIRROR"] = UV_PYTHON_INSTALL_MIRROR

    # 写入 pip 配置文件
    pip_dir = Path.home() / "pip"
    pip_dir.mkdir(exist_ok=True)
    pip_conf = pip_dir / ("pip.ini" if Constants.IS_WINDOWS else "pip.conf")
    pip_conf.write_text(f"[global]\nindex-url = {index_url}\n[install]\ntrusted-host = {trusted_host}\n")

    # 写入 conda 配置文件
    condarc = Path.home() / ".condarc"
    conda_urls = CONDA_MIRROR_URLS.get(mirror, CONDA_MIRROR_URLS["tsinghua"])
    condarc.write_text(
        "show_channel_urls: true\nchannels:\n" + "\n".join(f"  - {url}" for url in conda_urls) + "\n  - defaults\n"
    )

    # 写入 pypirc 配置文件 (如果有 token)
    if token:
        pypirc = Path.home() / ".pypirc"
        pypirc.write_text(
            f"[pypi]\nrepository: https://upload.pypi.org/legacy/\nusername: __token__\npassword: {token}\n"
        )

    print(f"已设置 pip 镜像源: {mirror} ({index_url})")


# ============================================================================
# TaskSpec 定义
# ============================================================================

envpy_tsinghua: px.TaskSpec = px.TaskSpec("envpy_tsinghua", fn=lambda: set_pip_mirror("tsinghua"))
envpy_aliyun: px.TaskSpec = px.TaskSpec("envpy_aliyun", fn=lambda: set_pip_mirror("aliyun"))


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """Python 环境配置工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="EnvPy - Python 环境配置工具",
        graphs={
            # 设置清华镜像源
            "t": px.Graph.from_specs([envpy_tsinghua]),
            # 设置阿里云镜像源
            "a": px.Graph.from_specs([envpy_aliyun]),
        },
    )
    runner.run_cli()
