from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal, get_args

import pyflowx as px
from pyflowx.conditions import BuiltinConditions
from pyflowx.tasks.system import setenv_group, write_file

# ============================================================================
# Mirror 配置
# ============================================================================
DOWNLOAD_MIRROR_SCRIPT: str = "curl -sSL https://linuxmirrors.cn/main.sh -o /tmp/linuxmirrors.sh"
INSTALL_MIRROR_SCRIPT: str = "sudo bash /tmp/linuxmirrors.sh"

# ============================================================================
# Python 配置
# ============================================================================
PyMirrorType = Literal["tsinghua", "aliyun", "huaweicloud", "ustc", "zju"]

PIP_INDEX_URLS: dict[PyMirrorType, str] = {
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple/",
    "huaweicloud": "https://mirrors.huaweicloud.com/repository/pypi/simple/",
    "ustc": "https://pypi.mirrors.ustc.edu.cn/simple/",
    "zju": "https://mirrors.zju.edu.cn/pypi/simple/",
}

PIP_TRUSTED_HOSTS: dict[PyMirrorType, str] = {
    "tsinghua": "pypi.tuna.tsinghua.edu.cn",
    "aliyun": "mirrors.aliyun.com",
    "huaweicloud": "mirrors.huaweicloud.com",
    "ustc": "pypi.mirrors.ustc.edu.cn",
    "zju": "mirrors.zju.edu.cn",
}
PIP_CONFIG_PATH = Path.home() / ".pip" / "pip.conf" if BuiltinConditions.IS_LINUX() else Path.home() / "pip" / "pip.ini"

UV_INDEX_URLS = PIP_INDEX_URLS
UV_PYTHON_INSTALL_MIRROR: str = "https://registry.npmmirror.com/-/binary/python-build-standalone"

# ============================================================================
# Conda 配置
# ============================================================================
CondaMirrorType = Literal["tsinghua", "ustc", "bsfu", "aliyun"]

CONDA_MIRROR_URLS: dict[CondaMirrorType, list[str]] = {
    "tsinghua": [
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/pro/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/bioconda/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/menpo/",
        "https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/pytorch/",
    ],
    "ustc": [
        "https://mirrors.ustc.edu.cn/anaconda/pkgs/main/",
        "https://mirrors.ustc.edu.cn/anaconda/pkgs/free/",
        "https://mirrors.ustc.edu.cn/anaconda/pkgs/r/",
        "https://mirrors.ustc.edu.cn/anaconda/pkgs/msys2/",
        "https://mirrors.ustc.edu.cn/anaconda/pkgs/pro/",
        "https://mirrors.ustc.edu.cn/anaconda/pkgs/dev/",
        "https://mirrors.ustc.edu.cn/anaconda/cloud/conda-forge/",
        "https://mirrors.ustc.edu.cn/anaconda/cloud/bioconda/",
        "https://mirrors.ustc.edu.cn/anaconda/cloud/menpo/",
        "https://mirrors.ustc.edu.cn/anaconda/cloud/pytorch/",
    ],
    "bsfu": [
        "https://mirrors.bsfu.edu.cn/anaconda/pkgs/main/",
        "https://mirrors.bsfu.edu.cn/anaconda/pkgs/free/",
        "https://mirrors.bsfu.edu.cn/anaconda/pkgs/r/",
        "https://mirrors.bsfu.edu.cn/anaconda/pkgs/msys2/",
        "https://mirrors.bsfu.edu.cn/anaconda/pkgs/pro/",
        "https://mirrors.bsfu.edu.cn/anaconda/pkgs/dev/",
        "https://mirrors.bsfu.edu.cn/anaconda/cloud/conda-forge/",
        "https://mirrors.bsfu.edu.cn/anaconda/cloud/bioconda/",
        "https://mirrors.bsfu.edu.cn/anaconda/cloud/menpo/",
        "https://mirrors.bsfu.edu.cn/anaconda/cloud/pytorch/",
    ],
    "aliyun": [
        "https://mirrors.aliyun.com/anaconda/pkgs/main/",
        "https://mirrors.aliyun.com/anaconda/pkgs/free/",
        "https://mirrors.aliyun.com/anaconda/pkgs/r/",
        "https://mirrors.aliyun.com/anaconda/pkgs/msys2/",
        "https://mirrors.aliyun.com/anaconda/pkgs/pro/",
        "https://mirrors.aliyun.com/anaconda/pkgs/dev/",
        "https://mirrors.aliyun.com/anaconda/cloud/conda-forge/",
        "https://mirrors.aliyun.com/anaconda/cloud/bioconda/",
        "https://mirrors.aliyun.com/anaconda/cloud/menpo/",
        "https://mirrors.aliyun.com/anaconda/cloud/pytorch/",
    ],
}
CONDA_CONFIG_PATH = Path.home() / ".condarc"


# ============================================================================
# Qt 配置
# ============================================================================

QT_LIBS: list[str] = [
    "build-essential",
    "libgl1",
    "libegl1",
    "libglib2.0-0",
    "libfontconfig1",
    "libfreetype6",
    "libxkbcommon0",
    "libdbus-1-3",
    "libxcb-xinerama0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-xfixes0",
    "libxcb-cursor0",
]

CHINESE_FONTS: list[str] = [
    "fonts-noto-cjk",
    "fonts-wqy-microhei",
    "fonts-wqy-zenhei",
    "fonts-noto-color-emoji",
]


def main() -> None:
    """主函数."""
    parser = argparse.ArgumentParser(description="环境开发工具")
    parser.add_argument(
        "--python-mirror",
        nargs="?",
        type=str,
        default="tsinghua",
        choices=get_args(PyMirrorType),
        help="Python 镜像源",
    )
    parser.add_argument(
        "--conda-mirror",
        nargs="?",
        type=str,
        default="tsinghua",
        choices=get_args(CondaMirrorType),
        help="Conda 镜镜像源",
    )
    args = parser.parse_args()

    python_mirror = args.python_mirror
    conda_mirror_urls = CONDA_MIRROR_URLS[args.conda_mirror]

    # 确保配置文件目录存在
    PIP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONDA_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 使用 conditions 自动控制任务执行
    graph = px.Graph.from_specs([
        # 系统镜像配置（仅 Linux 且未配置国内镜像）
        px.TaskSpec(
            "download_mirror",
            cmd=DOWNLOAD_MIRROR_SCRIPT,
            conditions=(
                BuiltinConditions.IS_LINUX(),
                BuiltinConditions.NOT(
                    BuiltinConditions.OR(
                        *[
                            BuiltinConditions.FILE_CONTENT_EXISTS(f, m)
                            for f in [
                                "/etc/apt/sources.list",
                                "/etc/apt/sources.list.d/ubuntu.sources",
                            ]
                            for m in get_args(PyMirrorType)
                        ],
                    )
                ),
            ),
            verbose=True,
        ),
        px.TaskSpec(
            "install_mirror",
            cmd=INSTALL_MIRROR_SCRIPT,
            depends_on=("download_mirror",),
            verbose=True,
        ),
        # 安装 Qt 依赖（仅 Linux）
        px.TaskSpec(
            "install_qt_libs",
            cmd=["sudo", "apt", "install", "-y", *QT_LIBS],
            conditions=(BuiltinConditions.IS_LINUX(),),
            depends_on=("install_mirror",),
            allow_upstream_skip=True,
            verbose=True,
        ),
        # 安装中文字体（仅 Linux）
        px.TaskSpec(
            "install_fonts",
            cmd=["sudo", "apt", "install", "-y", *CHINESE_FONTS],
            conditions=(BuiltinConditions.IS_LINUX(),),
            depends_on=("install_mirror",),
            allow_upstream_skip=True,
            verbose=True,
        ),
        # 设置 Python 环境变量
        *setenv_group({
            "PIP_INDEX_URL": PIP_INDEX_URLS[python_mirror],
            "PIP_TRUSTED_HOSTS": PIP_TRUSTED_HOSTS[python_mirror],
            "UV_INDEX_URL": UV_INDEX_URLS[python_mirror],
            "UV_PYTHON_INSTALL_MIRROR": UV_PYTHON_INSTALL_MIRROR,
            "UV_HTTP_TIMEOUT": "600",
            "UV_LINK_MODE": "copy",
        }),
        # 写入 Python 配置（仅当未配置）
        write_file(
            str(PIP_CONFIG_PATH),
            f"[global]\nindex-url = {PIP_INDEX_URLS[python_mirror]}\ntrusted-host = {PIP_TRUSTED_HOSTS[python_mirror]}",
        ),
        # 写入 Conda 配置（仅当未配置）
        write_file(
            str(CONDA_CONFIG_PATH),
            "show_channel_urls: true\nchannels:\n  - " + "\n  - ".join(conda_mirror_urls) + "\n  - defaults",
        ),
    ])
    px.run(graph, strategy="thread", verbose=True)
