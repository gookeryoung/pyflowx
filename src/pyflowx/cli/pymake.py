"""Python 构建工具模块.

完全替代传统的 Makefile,
提供更好的跨平台兼容性和 Python 生态集成.
"""

from __future__ import annotations

from pathlib import Path

import pyflowx as px


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
    DIRS_TO_IGNORE: list[str] = [".venv"]
    PYTHON_BUILD_DIRS: list[str] = ["dist", "build", "*.egg-info", "src/*.egg-info"]


conf = PymakeConfig()


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
      pymake pb   - 发布到 PyPI (先 Rust 后 Python)

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
      pymake lint         # 格式化代码
      pymake ca          # 清理所有构建产物
    """
    pymake_graph = px.Graph.from_specs(
        [
            px.TaskSpec("b", cmd=conf.BUILD_COMMAND),
            px.TaskSpec("bc", cmd=conf.MATURIN_BUILD_COMMAND),
            px.TaskSpec("ic", cmd=conf.DOC_BUILD_COMMAND),
        ]
    )
    px.run(pymake_graph)


# class PyMakeSkill(MapSkill):
#     """PyMake 构建技能."""

#     name: ClassVar[str] = "pymake"
#     description: ClassVar[str] = "Bitool PyMake - Python构建工具"

#     @override
#     def create_scheduler_map(
#         self,
#         args: argparse.Namespace,
#     ) -> dict[str, CommandScheduler] | None:
#         return {
#             # === 构建命令 ===
#             # 构建 Python 包
#             "b": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=conf.BUILD_COMMAND,
#                         allow_conditions=[_UV_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             # 构建 Rust 核心模块
#             "bc": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=_get_maturin_build_command(),
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[_MATURIN_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             # 构建双包（先 Rust 后 Python）
#             "ba": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         name="maturin_build",
#                         cmd=_get_maturin_build_command(),
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[_MATURIN_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                     RunCommand(
#                         name="uv_build",
#                         cmd=conf.BUILD_COMMAND,
#                         allow_conditions=[_UV_CONDITION],
#                         timeout=conf.TIMEOUT,
#                         dependencies=["maturin_build"],
#                     ),
#                 ],
#             ),
#             # === 安装命令（开发模式） ===
#             # 安装 Rust 核心模块
#             "ic": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=conf.MATURIN_DEV_COMMAND,
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[_MATURIN_CONDITION],
#                     ),
#                 ],
#             ),
#             # 安装 Python 主包
#             "ip": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=["uv", "pip", "install", "-e", "."],
#                         allow_conditions=[_UV_CONDITION],
#                         success_codes={0, 2},
#                     ),
#                 ],
#             ),
#             # 安装双包（开发模式）
#             "ia": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=conf.MATURIN_DEV_COMMAND,
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[_MATURIN_CONDITION],
#                     ),
#                     RunCommand(
#                         cmd=["uv", "pip", "install", "-e", "."],
#                         allow_conditions=[_UV_CONDITION],
#                         success_codes={0, 2},
#                     ),
#                 ],
#             ),
#             # === 清理命令 ===
#             # 清理 Python 构建产物
#             "cp": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=["rm", "-rf", *conf.PYTHON_BUILD_DIRS],
#                         allow_conditions=[_GIT_CONDITION],  # 使用 git clean 更安全
#                     ),
#                 ],
#             ),
#             # 清理 Rust 构建产物
#             "cc": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=["cargo", "clean"],
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[
#                             _MATURIN_CONDITION,
#                         ],  # 有 maturin 说明有 cargo
#                     ),
#                 ],
#             ),
#             # 清理所有构建产物
#             "ca": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=["cargo", "clean"],
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[_MATURIN_CONDITION],
#                     ),
#                     RunCommand(
#                         cmd=["git", "clean", "-xfd", "-e", *conf.DIRS_TO_IGNORE],
#                         allow_conditions=[_GIT_CONDITION],
#                     ),
#                 ],
#             ),
#             # === 开发工具 ===
#             # 运行测试, 跳过 slow, 并行模式
#             "t": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=[
#                             "pytest",
#                             "-m",
#                             "not slow",
#                             "-n",
#                             "8",
#                             "--dist",
#                             "loadfile",
#                             "--color=yes",
#                             "--durations=10",
#                         ],
#                         allow_conditions=[_PYTEST_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             # 运行测试, 非并行模式
#             "tf": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=[
#                             "pytest",
#                             "-m",
#                             "not slow",
#                             "--dist",
#                             "loadfile",
#                             "--color=yes",
#                             "--durations=10",
#                         ],
#                         allow_conditions=[_PYTEST_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             # 运行测试并生成覆盖率报告, 跳过 slow, 并行模式
#             # --dist loadfile: 按文件分发测试, 减少模块导入开销
#             "tc": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=[
#                             "pytest",
#                             "-m",
#                             "not slow",
#                             "--cov",
#                             "-n",
#                             "auto",
#                             "--dist",
#                             "loadfile",
#                             "--tb=short",
#                             "-v",
#                             "--color=yes",
#                             "--durations=10",
#                         ],
#                         allow_conditions=[_PYTEST_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             # 代码格式化与检查
#             "lint": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=[
#                             "ruff",
#                             "check",
#                             "--fix",
#                             "--unsafe-fixes",
#                         ],
#                         allow_conditions=[_RUFF_CONDITION],
#                         timeout=conf.TIMEOUT,
#                         cwd=Path(conf.PROJECT_ROOT),
#                     ),
#                 ],
#             ),
#             # 类型检查
#             "typecheck": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=["ty", "check", "src/bitool"],
#                         allow_conditions=[BuiltinConditions.HAS_APP_INSTALLED("ty")],
#                     ),
#                 ],
#             ),
#             # 构建文档
#             "doc": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=conf.DOC_BUILD_COMMAND,
#                         allow_conditions=[
#                             BuiltinConditions.HAS_APP_INSTALLED(conf.DOC_BUILD_TOOL),
#                         ],
#                     ),
#                 ],
#             ),
#             # 发布到 PyPI（先发布 Rust 核心模块，再发布 Python 主包）
#             "pb": CommandScheduler(
#                 commands=[
#                     # 发布 Python 主包（在项目根目录执行，依赖 Rust 发布成功）
#                     RunCommand(
#                         name="publish-python",
#                         cmd=["hatch", "publish"],
#                         cwd=Path(conf.PROJECT_ROOT),
#                         allow_conditions=[_HATCH_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             "pba": CommandScheduler(
#                 commands=[
#                     # 发布 Rust 核心模块（在 core 目录执行）
#                     RunCommand(
#                         name="publish-rust",
#                         # --disable-progress-bar: 避免 Windows GBK 控制台渲染 rich 进度条
#                         # 中的 \u2022 字符导致 UnicodeEncodeError
#                         cmd=[
#                             "twine",
#                             "upload",
#                             "--disable-progress-bar",
#                             conf.CORE_PATTERN,
#                         ],
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[_MATURIN_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                     RunCommand(
#                         name="publish-python",
#                         cmd=["hatch", "publish"],
#                         cwd=Path(conf.PROJECT_ROOT),
#                         allow_conditions=[_HATCH_CONDITION],
#                         timeout=conf.TIMEOUT,
#                         dependencies=["publish-rust"],
#                     ),
#                 ],
#             ),
#             "pbc": CommandScheduler(
#                 commands=[
#                     # 发布 Rust 核心模块（在 core 目录执行）
#                     RunCommand(
#                         name="publish-rust",
#                         cmd=["maturin", "publish"],
#                         cwd=Path(conf.CORE_DIR),
#                         allow_conditions=[_MATURIN_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             # === 多版本测试命令 ===
#             # 运行多版本 Python 测试 (tox)
#             "tox": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=["tox", "-p", "auto"],
#                         allow_conditions=[_TOX_CONDITION],
#                         timeout=conf.TIMEOUT,
#                     ),
#                 ],
#             ),
#             # 安装多版本 Python (仅安装不测试)
#             "tox-install": CommandScheduler(
#                 commands=[
#                     RunCommand(
#                         cmd=[
#                             "uv",
#                             "python",
#                             "install",
#                             "3.8",
#                             "3.9",
#                             "3.10",
#                             "3.11",
#                             "3.12",
#                             "3.13",
#                             "3.14",
#                         ],
#                         allow_conditions=[_UV_CONDITION],
#                         timeout=600,
#                     ),
#                 ],
#             ),
#         }


# def _get_maturin_build_command() -> list[str]:
#     """获取 maturin 构建命令（根据平台自动添加参数）.

#     Returns
#     -------
#     list[str]
#         完整的 maturin 构建命令列表.
#     """
#     base_cmd = conf.MATURIN_BUILD_COMMAND.copy()
#     if Constants.IS_WINDOWS:
#         base_cmd.extend(conf.MATURIN_BUILD_OPTIONS_WIN7)
#     return base_cmd


# # 命令条件判断
# _MATURIN_CONDITION = BuiltinConditions.HAS_APP_INSTALLED(conf.MATURIN_TOOL)
# _PYTEST_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("pytest")
# _UV_CONDITION = BuiltinConditions.HAS_APP_INSTALLED(conf.BUILD_TOOL)
# _HATCH_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("hatch")
# _RUFF_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("ruff")
# _GIT_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("git")
# _TOX_CONDITION = BuiltinConditions.HAS_APP_INSTALLED("tox")
