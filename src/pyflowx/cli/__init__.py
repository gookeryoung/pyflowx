"""CLI 工具模块.

提供各种命令行工具的入口点.
"""

from __future__ import annotations

# 自动格式化工具
from pyflowx.cli.autofmt import main as autofmt_main
from pyflowx.cli.bumpversion import main as bumpversion_main
from pyflowx.cli.clearscreen import main as clearscreen_main
from pyflowx.cli.envpy import main as envpy_main
from pyflowx.cli.envqt import main as envqt_main
from pyflowx.cli.envrs import main as envrs_main

# 文件工具
from pyflowx.cli.filedate import main as filedate_main
from pyflowx.cli.filelevel import main as filelevel_main
from pyflowx.cli.folderback import main as folderback_main
from pyflowx.cli.folderzip import main as folderzip_main

# Git 工具
from pyflowx.cli.gittool import main as gittool_main

# 仿真工具
from pyflowx.cli.lscalc import main as lscalc_main

# 打包工具
from pyflowx.cli.packtool import main as packtool_main

# PDF 工具
from pyflowx.cli.pdftool import main as pdftool_main

# 开发工具
from pyflowx.cli.piptool import main as piptool_main
from pyflowx.cli.pymake import main as pymake_main
from pyflowx.cli.screenshot import main as screenshot_main
from pyflowx.cli.sshcopyid import main as sshcopyid_main

# 系统工具
from pyflowx.cli.taskkill import main as taskkill_main
from pyflowx.cli.which import main as which_main

__all__ = [
    # 自动格式化工具
    "autofmt_main",
    "bumpversion_main",
    "clearscreen_main",
    "envpy_main",
    "envqt_main",
    "envrs_main",
    # 文件工具
    "filedate_main",
    "filelevel_main",
    "folderback_main",
    "folderzip_main",
    # Git 工具
    "gittool_main",
    # 仿真工具
    "lscalc_main",
    # 打包工具
    "packtool_main",
    # PDF 工具
    "pdftool_main",
    # 开发工具
    "piptool_main",
    "pymake_main",
    "screenshot_main",
    "sshcopyid_main",
    # 系统工具
    "taskkill_main",
    "which_main",
]
