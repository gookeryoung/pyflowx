"""Python 构建工具模块.

完全替代传统的 Makefile,
提供更好的跨平台兼容性和 Python 生态集成.
"""

from __future__ import annotations

from pathlib import Path

import pyflowx as px
from pyflowx.conditions import BuiltinConditions, Constants


class PymakeConfig:
    """PyMake 配置类."""

    # 项目根目录
    PROJECT_ROOT: str = str(Path(__file__).parent.parent.parent.parent)
    CORE_DIR: str = f"{PROJECT_ROOT}/bitool-core"
    CORE_PATTERN: str = f"{CORE_DIR}/target/bitool_core-*-cp*.whl"
    TIMEOUT: int = 600

    # Python 构建
    BUILD_TOOL: str = "uv"
    BUILD_COMMAND: list[str] = [BUILD_TOOL, "build"]

    # Rust 构建 (maturin)
    MATURIN_TOOL: str = "maturin"
    MATURIN_BUILD_COMMAND: list[str] = ["maturin", "build", "-r"]
    MATURIN_DEV_COMMAND: list[str] = ["maturin", "develop"]
    MATURIN_BUILD_OPTIONS_WIN7: list[str] = [
        "--target",
        "x86_64-win7-windows-msvc",
        "-Zbuild-std",
        "-i",
        "python3.8",
    ]

    # 文档
    DOC_BUILD_TOOL: str = "sphinx-build"
    DOC_BUILD_COMMAND: list[str] = ["sphinx-build", "-b", "html", "docs", "docs/_build"]

    # 清理
    DIRS_TO_IGNORE: list[str] = [".venv", ".git", ".tox"]
    PYTHON_BUILD_DIRS: list[str] = ["dist", "build", "*.egg-info", "src/*.egg-info"]


conf = PymakeConfig()


def _get_maturin_build_command() -> list[str]:
    """获取 maturin 构建命令（根据平台自动添加参数）.

    Returns
    -------
    list[str]
        完整的 maturin 构建命令列表.
    """
    base_cmd = conf.MATURIN_BUILD_COMMAND.copy()
    if Constants.IS_WINDOWS:
        base_cmd.extend(conf.MATURIN_BUILD_OPTIONS_WIN7)
    return base_cmd


# 命令条件判断
_MATURIN_CONDITION = BuiltinConditions.HAS_APP_INSTALLED(conf.MATURIN_TOOL)
_PYTEST_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("pytest")
_UV_CONDITION = BuiltinConditions.HAS_APP_INSTALLED(conf.BUILD_TOOL)
_HATCH_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("hatch")
_RUFF_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("ruff")
_GIT_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("git")
_TOX_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("tox")


def _build_graphs() -> dict[str, px.Graph]:
    """构建所有命令对应的任务流图.

    将原本的 CommandScheduler/RunCommand 模式转换为 Graph/TaskSpec 模式,
    每个 Graph 是一个独立的任务流, 由 CliRunner 根据用户输入选择执行.
    """
    return {
        # === 构建命令 ===
        # 构建 Python 包
        "b": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "uv_build",
                    cmd=conf.BUILD_COMMAND,
                    conditions=(_UV_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # 构建 Rust 核心模块
        "bc": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "maturin_build",
                    cmd=_get_maturin_build_command(),
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # 构建双包（先 Rust 后 Python）
        "ba": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "maturin_build",
                    cmd=_get_maturin_build_command(),
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
                px.TaskSpec(
                    "uv_build",
                    cmd=conf.BUILD_COMMAND,
                    conditions=(_UV_CONDITION,),
                    timeout=conf.TIMEOUT,
                    depends_on=("maturin_build",),
                ),
            ]
        ),
        # === 安装命令（开发模式） ===
        # 安装 Rust 核心模块
        "ic": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "maturin_dev",
                    cmd=conf.MATURIN_DEV_COMMAND,
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                ),
            ]
        ),
        # 安装 Python 主包
        "ip": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "uv_install",
                    cmd=["uv", "pip", "install", "-e", "."],
                    conditions=(_UV_CONDITION,),
                ),
            ]
        ),
        # 安装双包（开发模式）
        "ia": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "maturin_dev",
                    cmd=conf.MATURIN_DEV_COMMAND,
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                ),
                px.TaskSpec(
                    "uv_install",
                    cmd=["uv", "pip", "install", "-e", "."],
                    conditions=(_UV_CONDITION,),
                    depends_on=("maturin_dev",),
                ),
            ]
        ),
        # === 清理命令 ===
        # 清理 Python 构建产物
        "cp": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "git_clean_python",
                    cmd=["git", "clean", "-xfd", "-e", *conf.DIRS_TO_IGNORE],
                    conditions=(_GIT_CONDITION,),
                ),
            ]
        ),
        # 清理 Rust 构建产物
        "cc": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "cargo_clean",
                    cmd=["cargo", "clean"],
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                ),
            ]
        ),
        # 清理所有构建产物
        "ca": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "cargo_clean",
                    cmd=["cargo", "clean"],
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                ),
                px.TaskSpec(
                    "git_clean",
                    cmd=["git", "clean", "-xfd", "-e", *conf.DIRS_TO_IGNORE],
                    conditions=(_GIT_CONDITION,),
                ),
            ]
        ),
        # === 开发工具 ===
        # 运行测试, 跳过 slow, 并行模式
        "t": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pytest",
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
                    conditions=(_PYTEST_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # 运行测试, 非并行模式
        "tf": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pytest",
                    cmd=[
                        "pytest",
                        "-m",
                        "not slow",
                        "--dist",
                        "loadfile",
                        "--color=yes",
                        "--durations=10",
                    ],
                    conditions=(_PYTEST_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # 运行测试并生成覆盖率报告, 跳过 slow, 并行模式
        "tc": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pytest_cov",
                    cmd=[
                        "pytest",
                        "-m",
                        "not slow",
                        "--cov",
                        "-n",
                        "auto",
                        "--dist",
                        "loadfile",
                        "--tb=short",
                        "-v",
                        "--color=yes",
                        "--durations=10",
                    ],
                    conditions=(_PYTEST_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # 代码格式化与检查
        "lint": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "ruff_check",
                    cmd=[
                        "ruff",
                        "check",
                        "--fix",
                        "--unsafe-fixes",
                    ],
                    conditions=(_RUFF_CONDITION,),
                    timeout=conf.TIMEOUT,
                    cwd=Path(conf.PROJECT_ROOT),
                ),
            ]
        ),
        # 类型检查
        "typecheck": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "ty_check",
                    cmd=["ty", "check", "src/bitool"],
                    conditions=(BuiltinConditions.HAS_APP_INSTALLED("ty"),),
                ),
            ]
        ),
        # 构建文档
        "doc": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "sphinx_build",
                    cmd=conf.DOC_BUILD_COMMAND,
                    conditions=(
                        BuiltinConditions.HAS_APP_INSTALLED(conf.DOC_BUILD_TOOL),
                    ),
                ),
            ]
        ),
        # === 发布命令 ===
        # 发布 Python 主包到 PyPI
        "pb": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "publish_python",
                    cmd=["hatch", "publish"],
                    cwd=Path(conf.PROJECT_ROOT),
                    conditions=(_HATCH_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # 发布所有包（先 Rust 后 Python）
        "pba": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "publish_rust",
                    cmd=[
                        "twine",
                        "upload",
                        "--disable-progress-bar",
                        conf.CORE_PATTERN,
                    ],
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
                px.TaskSpec(
                    "publish_python",
                    cmd=["hatch", "publish"],
                    cwd=Path(conf.PROJECT_ROOT),
                    conditions=(_HATCH_CONDITION,),
                    timeout=conf.TIMEOUT,
                    depends_on=("publish_rust",),
                ),
            ]
        ),
        # 发布 Rust 核心模块 (maturin publish)
        "pbc": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "publish_rust",
                    cmd=["maturin", "publish"],
                    cwd=Path(conf.CORE_DIR),
                    conditions=(_MATURIN_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # === 多版本测试命令 ===
        # 运行多版本 Python 测试 (tox)
        "tox": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "tox_run",
                    cmd=["tox", "-p", "auto"],
                    conditions=(_TOX_CONDITION,),
                    timeout=conf.TIMEOUT,
                ),
            ]
        ),
        # 安装多版本 Python (仅安装不测试)
        "tox-install": px.Graph.from_specs(
            [
                px.TaskSpec(
                    "uv_python_install",
                    cmd=[
                        "uv",
                        "python",
                        "install",
                        "3.8",
                        "3.9",
                        "3.10",
                        "3.11",
                        "3.12",
                        "3.13",
                        "3.14",
                    ],
                    conditions=(_UV_CONDITION,),
                    timeout=600,
                ),
            ]
        ),
    }


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
      pymake ic   - 安装 Rust 核心模块 (maturin develop)
      pymake ip   - 安装 Python 主包 (uv pip install -e .)
      pymake ia   - 安装所有包 (开发模式，推荐)

    🧹 清理命令:
      pymake cp   - 清理 Python 构建产物
      pymake cc   - 清理 Rust 构建产物 (cargo clean)
      pymake ca   - 清理所有构建产物

    🛠️  开发工具:
      pymake t      - 运行测试 (pytest)
      pymake tc     - 运行测试并生成覆盖率报告
      pymake lint   - 代码格式化与检查 (ruff)
      pymake typecheck - 类型检查 (ty)
      pymake doc    - 构建文档 (sphinx)

    🔬 多版本测试:
      pymake tox           - 多版本 Python 测试 (3.8-3.14)
      pymake tox-install   - 安装所有 Python 版本 (仅安装不测试)

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
        description="PyMake - Python 构建工具 (替代 Makefile)",
        **_build_graphs(),
    )
    runner.run_cli()
