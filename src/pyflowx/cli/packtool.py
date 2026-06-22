"""Python 打包工具模块.

提供 Python 项目打包的常用功能封装,
支持源码打包、依赖打包、嵌入式 Python 安装等功能.
"""

from __future__ import annotations

import argparse
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
# CLI Runner
# ============================================================================


def main() -> None:
    """Python 打包工具主函数."""
    parser = argparse.ArgumentParser(
        description="PackTool - Python 打包工具",
        usage="packtool <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 源码打包命令
    src_parser = subparsers.add_parser("src", help="打包项目源码")
    src_parser.add_argument("--project-dir", type=str, default=".", help="项目目录")
    src_parser.add_argument("--output-dir", type=str, default=DEFAULT_BUILD_DIR, help="输出目录")

    # 依赖打包命令
    deps_parser = subparsers.add_parser("deps", help="打包项目依赖")
    deps_parser.add_argument("--lib-dir", type=str, default=DEFAULT_LIB_DIR, help="依赖库目录")
    deps_parser.add_argument("dependencies", nargs="*", help="依赖列表")

    # Wheel 打包命令
    wheel_parser = subparsers.add_parser("wheel", help="打包项目为 wheel 文件")
    wheel_parser.add_argument("--project-dir", type=str, default=".", help="项目目录")
    wheel_parser.add_argument("--output-dir", type=str, default=DEFAULT_DIST_DIR, help="输出目录")

    # 嵌入式 Python 安装命令
    embed_parser = subparsers.add_parser("embed", help="安装嵌入式 Python")
    embed_parser.add_argument("--version", type=str, default="3.10", help="Python 版本")
    embed_parser.add_argument("--output-dir", type=str, default="python", help="输出目录")

    # ZIP 打包命令
    zip_parser = subparsers.add_parser("zip", help="创建 ZIP 打包文件")
    zip_parser.add_argument("--source-dir", type=str, default=".", help="源目录")
    zip_parser.add_argument("--output-file", type=str, default="package.zip", help="输出文件")

    # 清理命令
    subparsers.add_parser("clean", help="清理构建目录")

    args = parser.parse_args()

    if args.command == "src":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pack_source",
                    fn=pack_source,
                    args=(Path(args.project_dir), Path(args.output_dir)),
                )
            ]
        )
    elif args.command == "deps":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pack_deps",
                    fn=pack_dependencies,
                    args=(Path(args.lib_dir), args.dependencies),
                )
            ]
        )
    elif args.command == "wheel":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "pack_wheel",
                    fn=pack_wheel,
                    args=(Path(args.project_dir), Path(args.output_dir)),
                )
            ]
        )
    elif args.command == "embed":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "install_embed",
                    fn=install_embed_python,
                    args=(args.version, Path(args.output_dir)),
                )
            ]
        )
    elif args.command == "zip":
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "create_zip",
                    fn=create_zip_package,
                    args=(Path(args.source_dir), Path(args.output_file)),
                )
            ]
        )
    elif args.command == "clean":
        graph = px.Graph.from_specs([px.TaskSpec("clean_build", fn=clean_build_dir, args=(Path(DEFAULT_BUILD_DIR),))])
    else:
        parser.print_help()
        return

    px.run(graph, strategy="thread")
