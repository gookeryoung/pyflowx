from typing import TypedDict

import pyflowx as px


class EnvConfig(TypedDict):
    """环境配置项."""

    name: str
    value: str
    description: str


PIP_INDEX_URL_CONFIG: EnvConfig = {
    "name": "PIP_INDEX_URL",
    "value": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "description": "PIP索引URL",
}


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
    # 使用更安全的分步执行方式，便于调试和捕获错误
    graph = px.Graph.from_specs([
        # 下载镜像
        px.TaskSpec("download", cmd="curl -sSL https://linuxmirrors.cn/main.sh -o /tmp/linuxmirrors.sh", verbose=True),
        # 安装镜像
        px.TaskSpec("install", cmd="sudo bash /tmp/linuxmirrors.sh", verbose=True, depends_on=("download",)),
        # 安装 PyQt 相关依赖
        px.TaskSpec(
            "envqt_install", cmd=["sudo", "apt", "install", "-y", *QT_LIBS], verbose=True, depends_on=("install",)
        ),
        # 安装中文字体
        px.TaskSpec(
            "envqt_fonts", cmd=["sudo", "apt", "install", "-y", *CHINESE_FONTS], verbose=True, depends_on=("install",)
        ),
    ])
    px.run(graph, strategy="thread", verbose=True)
