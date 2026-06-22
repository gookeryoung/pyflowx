"""PyQt 环境配置工具.

用于设置 PyQt 相关环境变量, 安装依赖环境.
"""

from __future__ import annotations

import pyflowx as px
from pyflowx.conditions import Constants

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
    """PyQt 环境配置工具主函数."""
    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "envqt_install",
                cmd=["sudo", "apt", "install", "-y", *QT_LIBS],
                conditions=(lambda: Constants.IS_LINUX,),
                verbose=True,
            ),
            px.TaskSpec(
                "envqt_fonts",
                cmd=["sudo", "apt", "install", "-y", *CHINESE_FONTS],
                conditions=(lambda: Constants.IS_LINUX,),
                verbose=True,
            ),
        ],
    )
    px.run(graph, strategy="thread", verbose=True)
