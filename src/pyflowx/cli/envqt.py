"""PyQt 环境配置工具.

用于设置 PyQt 相关环境变量, 安装依赖环境.
"""

from __future__ import annotations

import pyflowx as px
from pyflowx.conditions import Constants

# ============================================================================
# Qt 依赖列表
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


# ============================================================================
# TaskSpec 定义
# ============================================================================


# 条件: 仅在 Unix 系统上执行
def is_linux() -> bool:
    """判断是否为 Linux 系统."""
    return Constants.IS_LINUX and not Constants.IS_MACOS


envqt_install: px.TaskSpec = px.TaskSpec(
    "envqt_install",
    cmd=["sudo", "apt", "install", "-y", *QT_LIBS],
    conditions=(is_linux,),
)

envqt_fonts: px.TaskSpec = px.TaskSpec(
    "envqt_fonts",
    cmd=["sudo", "apt", "install", "-y", *CHINESE_FONTS],
    conditions=(is_linux,),
)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """PyQt 环境配置工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="EnvQt - PyQt 环境配置工具",
        graphs={
            # 安装 Qt 依赖
            "i": px.Graph.from_specs([envqt_install]),
            # 安装中文字体
            "f": px.Graph.from_specs([envqt_fonts]),
            # 安装全部
            "a": px.Graph.from_specs([envqt_install, envqt_fonts]),
        },
    )
    runner.run_cli()
