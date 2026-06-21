"""Python 构建工具模块.

完全替代传统的 Makefile,
提供更好的跨平台兼容性和 Python 生态集成.
"""

from __future__ import annotations

import pyflowx as px
from pyflowx.conditions import BuiltinConditions, Constants


def maturin_build_cmd() -> list[str]:
    """获取 maturin 构建命令（根据平台自动添加参数）.

    Returns
    -------
    list[str]
        完整的 maturin 构建命令列表.
    """
    base_cmd = ["maturin", "build", "-r"].copy()
    if Constants.IS_WINDOWS:
        base_cmd.extend(
            [
                "--target",
                "x86_64-win7-windows-msvc",
                "-Zbuild-std",
                "-i",
                "python3.8",
            ]
        )
    return base_cmd


def check(name: str) -> px.Condition:
    """检查指定工具是否已安装.

    Returns
    -------
    bool
        如果已安装则返回 True,否则返回 False.
    """
    return BuiltinConditions.HAS_INSTALLED(name)


uv_build: px.TaskSpec = px.TaskSpec("uv_build", cmd=["uv", "build"], conditions=(check("uv"),))
maturin_build: px.TaskSpec = px.TaskSpec("maturin_build", cmd=maturin_build_cmd(), conditions=(check("maturin"),))
uv_sync: px.TaskSpec = px.TaskSpec("uv_sync", cmd=["uv", "sync"], conditions=(check("uv"),))
git_clean: px.TaskSpec = px.TaskSpec("git_clean", cmd=["gitt", "c"], conditions=(check("gitt"),))
test: px.TaskSpec = px.TaskSpec(
    "test",
    cmd=[
        "pytest",
        "-m",
        "not slow",
        "-n",
        "8",
        "--dist",
        "loadfile",
        "--color=yes",
        "--durations=10",
    ],
    conditions=(check("pytest"),),
)
test_fast: px.TaskSpec = px.TaskSpec(
    "test_fast",
    cmd=[
        "pytest",
        "-m",
        "not slow",
        "--dist",
        "loadfile",
        "--color=yes",
        "--durations=10",
    ],
    conditions=(check("pytest"),),
)
test_coverage: px.TaskSpec = px.TaskSpec(
    "test_coverage",
    cmd=[
        "pytest",
        "--cov",
        "-n",
        "8",
        "--dist",
        "loadfile",
        "--tb=short",
        "-v",
        "--color=yes",
        "--durations=10",
    ],
    conditions=(check("pytest"),),
)
ruff_lint: px.TaskSpec = px.TaskSpec(
    "lint",
    cmd=[
        "ruff",
        "check",
        "--fix",
        "--unsafe-fixes",
    ],
    conditions=(check("ruff"),),
)
mypy_check: px.TaskSpec = px.TaskSpec("typecheck", cmd=["mypy", "."], conditions=(check("mypy"),))
ty_check: px.TaskSpec = px.TaskSpec("ty_check", cmd=["ty", "check", "."], conditions=(check("ty"),))
doc: px.TaskSpec = px.TaskSpec(
    "doc", cmd=["sphinx-build", "-b", "html", "docs", "docs/_build"], conditions=(check("sphinx-build"),)
)
hatch_publish: px.TaskSpec = px.TaskSpec("publish_python", cmd=["hatch", "publish"], conditions=(check("hatch"),))
twine_publish: px.TaskSpec = px.TaskSpec(
    "twine_publish",
    cmd=[
        "twine",
        "upload",
        "--disable-progress-bar",
    ],
    conditions=(check("twine"),),
)
tox: px.TaskSpec = px.TaskSpec("tox", cmd=["tox", "-p", "auto"], conditions=(check("tox"),))


def main():
    """
    ╔══════════════════════════════════════════════════════════╗
    ║                   PyMake 构建工具                    ║
    ╚══════════════════════════════════════════════════════════╝

    🔨 构建命令:
      pymake b    - 构建 Python 主包 (uv build)
      pymake bc   - 构建 Rust 核心模块 (maturin build)
      pymake ba   - 构建所有包 (先 Rust 后 Python)

    📦 安装命令 (开发模式):
      pymake sync   - 安装依赖包 (uv sync)

    🧹 清理命令:
      pymake c   - 清理所有构建产物

    🛠️  开发工具:
      pymake t      - 运行测试 (pytest)
      pymake tc     - 运行测试并生成覆盖率报告
      pymake tf     - 运行快速测试 (pytest -m not slow)
      pymake lint   - 代码格式化与检查 (ruff)
      pymake type   - 类型检查 (mypy, ty)
      pymake doc    - 构建文档 (sphinx)

    🔬 多版本测试:
      pymake tox           - 多版本 Python 测试 (3.8-3.14)
      pymake tox_install   - 安装所有 Python 版本 (仅安装不测试)

    📦 发布命令:
      pymake pb   - 发布到 PyPI (hatch publish)
      pymake pba  - 发布所有包 (先 Rust 后 Python)
      pymake pbc  - 发布 Rust 核心模块 (maturin publish)

    💡 常用工作流:
      1. 初始化开发环境: pymake ia
      2. 日常开发: pymake lint && pymake t
      3. 构建发布包: pymake ba
      4. 多版本兼容性测试: pymake tox
      5. 发布到 PyPI: pymake pb
      6. 清理重新开始: pymake ca && pymake ia

    📝 示例:
      pymake ba          # 构建所有包
      pymake ia          # 安装开发环境
      pymake t           # 运行测试
      pymake tox         # 多版本兼容性测试
      pymake lint        # 格式化代码
      pymake ca          # 清理所有构建产物
    """
    runner = px.CliRunner(
        strategy="sequential",
        description="PyMake - Python 构建工具 (替代 Makefile)",
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
            "t": px.Graph.from_specs([test]),
            "tc": px.Graph.from_specs([test, test_coverage]),
            "tf": px.Graph.from_specs([test_fast]),
            "lint": px.Graph.from_specs([ruff_lint]),
            "type": px.Graph.from_specs([mypy_check, ty_check]),
            "doc": px.Graph.from_specs([doc]),
            "pb": px.Graph.from_specs([twine_publish, hatch_publish]),
            "tox": px.Graph.from_specs([tox]),
        },
    )
    runner.run_cli()
