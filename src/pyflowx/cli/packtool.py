"""Python 打包工具模块.

提供 Python 项目打包的常用功能封装,
支持源码打包、依赖打包、嵌入式 Python 安装等功能.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pyflowx as px

# ============================================================================
# 配置
# ============================================================================

DEFAULT_BUILD_DIR = ".pypack"
DEFAULT_DIST_DIR = "dist"
DEFAULT_LIB_DIR = "libs"
DEFAULT_CACHE_DIR = ".cache/pypack"

IGNORE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".venv",
    ".idea",
    ".vscode",
    "*.egg-info",
    "dist",
    "build",
    ".pytest_cache",
    ".tox",
    ".mypy_cache",
]


# ============================================================================
# 辅助函数
# ============================================================================


def pack_source(project_dir: Path, output_dir: Path) -> None:
    """打包项目源码.

    Parameters
    ----------
    project_dir : Path
        项目目录
    output_dir : Path
        输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 检测项目名称
    pyproject_file = project_dir / "pyproject.toml"
    project_name = project_dir.name

    if pyproject_file.exists():
        try:
            import tomllib

            content = pyproject_file.read_text(encoding="utf-8")
            data = tomllib.loads(content)
            project_name = data.get("project", {}).get("name", project_name)
        except ImportError:
            pass

    # 打包源码
    source_dir = output_dir / "src" / project_name
    source_dir.mkdir(parents=True, exist_ok=True)

    # 复制文件
    src_subdir = project_dir / "src"
    if src_subdir.exists():
        shutil.copytree(
            src_subdir,
            source_dir / "src",
            ignore=shutil.ignore_patterns(*IGNORE_PATTERNS),
            dirs_exist_ok=True,
        )
    else:
        for item in project_dir.iterdir():
            if item.name in IGNORE_PATTERNS or item.name.startswith("."):
                continue
            dst_item = source_dir / item.name
            if item.is_dir():
                shutil.copytree(
                    item,
                    dst_item,
                    ignore=shutil.ignore_patterns(*IGNORE_PATTERNS),
                    dirs_exist_ok=True,
                )
            else:
                shutil.copy2(item, dst_item)

    print(f"源码打包完成: {source_dir}")


def pack_dependencies(lib_dir: Path, dependencies: list[str]) -> None:
    """打包项目依赖.

    Parameters
    ----------
    lib_dir : Path
        依赖库目录
    dependencies : list[str]
        依赖列表
    """
    lib_dir.mkdir(parents=True, exist_ok=True)

    if not dependencies:
        print("没有依赖需要打包")
        return

    # 使用 pip 安装依赖到目标目录
    cmd = [
        "pip",
        "install",
        "--target",
        str(lib_dir),
        "--no-compile",
        "--no-warn-script-location",
    ]
    cmd.extend(dependencies)

    subprocess.run(cmd, check=True)
    print(f"依赖打包完成: {lib_dir}")


def pack_wheel(project_dir: Path, output_dir: Path) -> None:
    """打包项目为 wheel 文件.

    Parameters
    ----------
    project_dir : Path
        项目目录
    output_dir : Path
        输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 使用 pip wheel 打包
    cmd = [
        "pip",
        "wheel",
        "--no-deps",
        "--wheel-dir",
        str(output_dir),
        str(project_dir),
    ]

    subprocess.run(cmd, check=True)
    print(f"Wheel 打包完成: {output_dir}")


def install_embed_python(version: str, output_dir: Path) -> None:
    """安装嵌入式 Python.

    Parameters
    ----------
    version : str
        Python 版本 (如: 3.10, 3.11)
    output_dir : Path
        输出目录
    """
    import platform

    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建下载 URL
    arch = platform.machine().lower()
    if arch in ["x86_64", "amd64"]:
        arch = "amd64"
    elif arch in ["arm64", "aarch64"]:
        arch = "arm64"

    # 解析完整版本号
    version_map = {
        "3.8": "3.8.10",
        "3.9": "3.9.13",
        "3.10": "3.10.11",
        "3.11": "3.11.9",
        "3.12": "3.12.4",
    }
    full_version = version_map.get(version, f"{version}.0")

    # Windows 嵌入式 Python 下载 URL
    url = f"https://www.python.org/ftp/python/{full_version}/python-{full_version}-embed-{arch}.zip"

    # 下载并解压
    cache_file = Path(DEFAULT_CACHE_DIR) / f"python-{full_version}-embed-{arch}.zip"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    if not cache_file.exists():
        print(f"正在下载嵌入式 Python {full_version}...")
        import urllib.request

        urllib.request.urlretrieve(url, cache_file)
        print(f"下载完成: {cache_file}")

    # 解压
    with zipfile.ZipFile(cache_file, "r") as zf:
        zf.extractall(output_dir)

    print(f"嵌入式 Python 安装完成: {output_dir}")


def create_zip_package(source_dir: Path, output_file: Path) -> None:
    """创建 ZIP 打包文件.

    Parameters
    ----------
    source_dir : Path
        源目录
    output_file : Path
        输出文件
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in source_dir.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(source_dir)
                zf.write(file, arcname)

    print(f"ZIP 打包完成: {output_file}")


def clean_build_dir(build_dir: Path) -> None:
    """清理构建目录.

    Parameters
    ----------
    build_dir : Path
        构建目录
    """
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print(f"清理完成: {build_dir}")
    else:
        print(f"目录不存在: {build_dir}")


# ============================================================================
# TaskSpec 定义
# ============================================================================

# 源码打包
pack_source_default: px.TaskSpec = px.TaskSpec("pack_source", fn=lambda: pack_source(Path(), Path(DEFAULT_BUILD_DIR)))

# 依赖打包
pack_deps_default: px.TaskSpec = px.TaskSpec("pack_deps", fn=lambda: pack_dependencies(Path(DEFAULT_LIB_DIR), []))

# Wheel 打包
pack_wheel_default: px.TaskSpec = px.TaskSpec("pack_wheel", fn=lambda: pack_wheel(Path(), Path(DEFAULT_DIST_DIR)))

# 嵌入式 Python 安装
install_embed_default: px.TaskSpec = px.TaskSpec(
    "install_embed", fn=lambda: install_embed_python("3.10", Path("python"))
)

# ZIP 打包
create_zip_default: px.TaskSpec = px.TaskSpec("create_zip", fn=lambda: create_zip_package(Path(), Path("package.zip")))

# 清理构建目录
clean_build: px.TaskSpec = px.TaskSpec("clean_build", fn=lambda: clean_build_dir(Path(DEFAULT_BUILD_DIR)))


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """Python 打包工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="PackTool - Python 打包工具",
        graphs={
            # 源码打包
            "src": px.Graph.from_specs([pack_source_default]),
            # 依赖打包
            "deps": px.Graph.from_specs([pack_deps_default]),
            # Wheel 打包
            "wheel": px.Graph.from_specs([pack_wheel_default]),
            # 嵌入式 Python 安装
            "embed": px.Graph.from_specs([install_embed_default]),
            # ZIP 打包
            "zip": px.Graph.from_specs([create_zip_default]),
            # 清理构建目录
            "clean": px.Graph.from_specs([clean_build]),
            # 完整打包流程
            "all": px.Graph.from_specs([
                pack_source_default,
                pack_deps_default,
                pack_wheel_default,
            ]),
        },
    )
    runner.run_cli()
