"""Python 构建工具模块.

完全替代传统的 Makefile,
提供更好的跨平台兼容性和 Python 生态集成.
"""

from __future__ import annotations

import pyflowx as px
from pyflowx.conditions import Constants

MATURIN_BUILD_COMMAND = ["maturin", "build", "-r"]
if Constants.IS_WINDOWS:
    MATURIN_BUILD_COMMAND.extend(["--target", "x86_64-win7-windows-msvc", "-Zbuild-std", "-i", "python3.8"])

# 扁平注册所有任务（px.cmd 自动从命令前两段推导 name）
tasks: list[px.TaskSpec] = [
    px.cmd(["uv", "build"]),
    px.cmd(MATURIN_BUILD_COMMAND),
    px.cmd(["uv", "sync"]),
    px.cmd(["gitt", "c"], name="git_clean"),
    px.cmd(
        ["pytest", "-m", "not slow", "-n", "8", "--dist", "loadfile", "--color=yes", "--durations=10"],
        name="test",
    ),
    px.cmd(
        ["pytest", "-m", "not slow", "--dist", "loadfile", "--color=yes", "--durations=10"],
        name="test_fast",
    ),
    px.cmd(
        ["pytest", "--cov", "-n", "8", "--dist", "loadfile", "--tb=short", "-v", "--color=yes", "--durations=10"],
        name="test_coverage",
    ),
    px.cmd(["pyrefly", "check", "."]),
    px.cmd(["git", "add", "-A"], name="git_add_all"),
    px.cmd(["bumpversion"]),
    px.cmd(["bumpversion", "minor"]),
    px.cmd(["git", "push"]),
    px.cmd(["git", "push", "--tags"], name="git_push_tags"),
    px.cmd(["hatch", "publish"], name="publish_python"),
    px.cmd(["twine", "upload", "--disable-progress-bar"], name="twine_publish"),
]

# 单任务别名（alias 名与任务名相同）：直接内联 TaskSpec，避免 str 自引用
aliases: dict[str, str | list[str | px.TaskSpec] | px.TaskSpec | px.Graph] = {
    # 构建命令
    "b": "uv_build",
    "bc": "maturin_build",
    "ba": ["b", "bc"],
    # 安装命令
    "sync": "uv_sync",
    # 清理命令
    "c": "git_clean",
    # 开发工具
    "bump": ["c", "tc", "git_add_all", "bumpversion"],
    "bumpmi": "bumpversion_minor",
    "cov": ["git_clean", "test_coverage"],
    "doc": px.cmd(["sphinx-build", "-b", "html", "docs", "docs/_build"], name="doc"),
    "lint": px.cmd(["ruff", "check", "--fix", "--unsafe-fixes"], name="lint"),
    "pb": ["twine_publish", "publish_python"],
    "t": "test",
    "tf": "test_fast",
    "tc": ["pyrefly_check", "lint"],
    "tox": px.cmd(["tox", "-p", "auto"], name="tox"),
    # 发布命令
    "p": ["git_clean", "git_push", "git_push_tags"],
}


def main() -> None:
    """pymake 构建工具.

    🔨 构建命令:
      pymake b    - 构建 Python 主包 (uv build)
      pymake bc   - 构建 Rust 核心模块 (maturin build)
      pymake ba   - 构建所有包 (先 Python 后 Rust)

    📦 安装命令 (开发模式):
      pymake sync   - 安装依赖包 (uv sync)

    🧹 清理命令:
      pymake c   - 清理所有构建产物 (gitt c)

    🛠️  开发工具:
      pymake t      - 运行测试 (pytest)
      pymake tc     - 运行测试并生成覆盖率报告
      pymake tf     - 运行快速测试 (pytest -m not slow)
      pymake lint   - 代码格式化与检查 (ruff)
      pymake type   - 类型检查 (mypy, ty)
      pymake doc    - 构建文档 (sphinx)

    🔬 多版本测试:
      pymake tox   - 多版本 Python 测试 (tox -p auto)

    📦 发布命令:
      pymake pb   - 发布到 PyPI (twine + hatch)

    🔖 版本管理:
      pymake bump  - 自动升级版本号并提交修改 (清理 + 检查 + 格式化 + git add + bumpversion)

    💡 常用工作流:
      1. 日常开发: pymake lint && pymake t
      2. 构建发布包: pymake ba
      3. 多版本兼容性测试: pymake tox
      4. 发布到 PyPI: pymake pb

    📝 示例:
      pymake ba          # 构建所有包
      pymake sync        # 安装依赖
      pymake t           # 运行测试
      pymake tox         # 多版本兼容性测试
      pymake lint        # 格式化代码
      pymake type        # 类型检查
    """
    runner = px.CliRunner(strategy="sequential", description="PyMake - Python 构建工具", tasks=tasks, aliases=aliases)
    runner.run_cli()
