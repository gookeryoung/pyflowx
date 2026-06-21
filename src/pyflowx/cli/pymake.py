"""Python 构建工具模块.

完全替代传统的 Makefile,
提供更好的跨平台兼容性和 Python 生态集成.
"""

from __future__ import annotations

import pyflowx as px
from pyflowx.conditions import Constants


def maturin_build_cmd() -> list[str]:
    """获取 maturin 构建命令（根据平台自动添加参数）.

    Returns
    -------
    list[str]
        完整的 maturin 构建命令列表.
    """
    command = ["maturin", "build", "-r"].copy()
    if Constants.IS_WINDOWS:
        command.extend(
            [
                "--target",
                "x86_64-win7-windows-msvc",
                "-Zbuild-std",
                "-i",
                "python3.8",
            ]
        )
    return command


uv_build: px.TaskSpec = px.TaskSpec("uv_build", cmd=["uv", "build"])
maturin_build: px.TaskSpec = px.TaskSpec("maturin_build", cmd=maturin_build_cmd())
uv_sync: px.TaskSpec = px.TaskSpec("uv_sync", cmd=["uv", "sync"])
git_clean: px.TaskSpec = px.TaskSpec("git_clean", cmd=["gitt", "c"])
test: px.TaskSpec = px.TaskSpec(
    "test", cmd=["pytest", "-m", "not slow", "-n", "8", "--dist", "loadfile", "--color=yes", "--durations=10"]
)
test_fast: px.TaskSpec = px.TaskSpec(
    "test_fast", cmd=["pytest", "-m", "not slow", "--dist", "loadfile", "--color=yes", "--durations=10"]
)
test_coverage: px.TaskSpec = px.TaskSpec(
    "test_coverage",
    cmd=["pytest", "--cov", "-n", "8", "--dist", "loadfile", "--tb=short", "-v", "--color=yes", "--durations=10"],
)
ruff_lint: px.TaskSpec = px.TaskSpec("lint", cmd=["ruff", "check", "--fix", "--unsafe-fixes"])
ruff_format: px.TaskSpec = px.TaskSpec("format", cmd=["ruff", "format", "--check", "."], depends_on=("lint",))
mypy_check: px.TaskSpec = px.TaskSpec("typecheck", cmd=["mypy", "."])
ty_check: px.TaskSpec = px.TaskSpec("ty_check", cmd=["ty", "check", "."])
doc: px.TaskSpec = px.TaskSpec("doc", cmd=["sphinx-build", "-b", "html", "docs", "docs/_build"])
hatch_publish: px.TaskSpec = px.TaskSpec("publish_python", cmd=["hatch", "publish"])
twine_publish: px.TaskSpec = px.TaskSpec("twine_publish", cmd=["twine", "upload", "--disable-progress-bar"])
tox: px.TaskSpec = px.TaskSpec("tox", cmd=["tox", "-p", "auto"])


def main():
    """
    ╔══════════════════════════════════════════════════════════╗
    ║                   PyMake 构建工具                    ║
    ╚══════════════════════════════════════════════════════════╝

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
    runner = px.CliRunner(
        strategy="thread",
        description="PyMake - Python 构建工具",
        graphs={
            # 构建命令
            "b": px.Graph.from_specs([uv_build]),
            "bc": px.Graph.from_specs([maturin_build]),
            "ba": px.Graph.from_specs([uv_build, maturin_build]),
            # 安装命令
            "sync": px.Graph.from_specs([uv_sync]),
            # 清理命令
            "c": px.Graph.from_specs([git_clean]),
            # 开发工具
            "cov": px.Graph.from_specs([test_coverage]),
            "doc": px.Graph.from_specs([doc]),
            "lint": px.Graph.from_specs([ruff_lint, ruff_format]),
            "pb": px.Graph.from_specs([twine_publish, hatch_publish]),
            "t": px.Graph.from_specs([test]),
            "tf": px.Graph.from_specs([test_fast]),
            "tc": px.Graph.from_specs([mypy_check, ty_check]),
            "tox": px.Graph.from_specs([tox]),
        },
    )
    runner.run_cli()
