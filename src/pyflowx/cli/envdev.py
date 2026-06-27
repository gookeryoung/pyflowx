from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal, get_args

import pyflowx as px
from pyflowx.tasks.system import Constants, setenv_group, write_file

# ============================================================================
# Mirror 配置
# ============================================================================
DOWNLOAD_MIRROR_SCRIPT: str = "curl -sSL https://linuxmirrors.cn/main.sh -o /tmp/linuxmirrors.sh"
INSTALL_MIRROR_SCRIPT: str = "sudo bash /tmp/linuxmirrors.sh"

# ============================================================================
# Python 配置
# ============================================================================
PyMirrorType = Literal["tsinghua", "aliyun"]

PIP_INDEX_URLS: dict[PyMirrorType, str] = {
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple/",
}

PIP_TRUSTED_HOSTS: dict[PyMirrorType, str] = {
    "tsinghua": "pypi.tuna.tsinghua.edu.cn",
    "aliyun": "mirrors.aliyun.com",
}
PIP_CONFIG_PATH = Path.home() / ".pip" / "pip.conf" if not Constants.IS_WINDOWS else Path.home() / "pip" / "pip.ini"

UV_INDEX_URLS: dict[PyMirrorType, str] = {
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple/",
}
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
    python_envs: dict[str, str] = {
        "PIP_INDEX_URL": PIP_INDEX_URLS[python_mirror],
        "PIP_TRUSTED_HOSTS": PIP_TRUSTED_HOSTS[python_mirror],
        "UV_INDEX_URL": UV_INDEX_URLS[python_mirror],
        "UV_PYTHON_INSTALL_MIRROR": UV_PYTHON_INSTALL_MIRROR,
        "UV_HTTP_TIMEOUT": "600",
        "UV_LINK_MODE": "copy",
    }

    conda_mirror_urls = CONDA_MIRROR_URLS[args.conda_mirror]

    # 确保配置文件目录存在
    PIP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONDA_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 使用更安全的分步执行方式，便于调试和捕获错误
    graph = px.Graph.from_specs([
        # 下载镜像
        px.TaskSpec("download_mirror", cmd=DOWNLOAD_MIRROR_SCRIPT, verbose=True),
        # 安装镜像
        px.TaskSpec("install_mirror", cmd=INSTALL_MIRROR_SCRIPT, verbose=True, depends_on=("download_mirror",)),
        # 安装 PyQt 相关依赖
        px.TaskSpec(
            "install_qt_libs",
            cmd=["sudo", "apt", "install", "-y", *QT_LIBS],
            verbose=True,
            depends_on=("install_mirror",),
        ),
        # 安装中文字体
        px.TaskSpec(
            "install_fonts",
            cmd=["sudo", "apt", "install", "-y", *CHINESE_FONTS],
            verbose=True,
            depends_on=("install_mirror",),
        ),
        # 设置 Python 环境变量
        *setenv_group(python_envs),
        # 写入 Python 配置
        write_file(
            str(PIP_CONFIG_PATH),
            f"[global]\nindex-url = {PIP_INDEX_URLS[python_mirror]}\ntrusted-host = {PIP_TRUSTED_HOSTS[python_mirror]}",
        ),
        # 写入 Conda 配置
        write_file(
            str(CONDA_CONFIG_PATH),
            "show_channel_urls: true\nchannels:" + "\n".join(conda_mirror_urls) + "\n - defaults",
        ),
    ])
    px.run(graph, strategy="thread", verbose=True)
