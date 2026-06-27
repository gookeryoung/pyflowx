"""pip 包管理工具模块.

提供 pip 包管理操作的封装,
支持安装、卸载、下载等功能.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
from pathlib import Path

import pyflowx as px

# ============================================================================
# 配置
# ============================================================================

PACKAGE_DIR = "packages"
REQUIREMENTS_FILE = "requirements.txt"

# 受保护的包名集合
_PROTECTED_PACKAGES: frozenset[str] = frozenset({
    "pyflowx",
    "bitool",
})


# ============================================================================
# 辅助函数
# ============================================================================


def _get_installed_packages() -> list[str]:
    """获取当前环境中所有已安装的包名."""
    try:
        result = subprocess.run(
            ["pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True,
        )
        packages: list[str] = []
        for line in result.stdout.strip().split("\n"):
            if line and "==" in line:
                pkg_name = line.split("==")[0].strip()
                packages.append(pkg_name)
    except (subprocess.SubprocessError, OSError):
        return []
    return packages


def _expand_wildcard_packages(pattern: str) -> list[str]:
    """展开通配符模式为实际的包名列表."""
    if not any(char in pattern for char in ["*", "?", "[", "]"]):
        return [pattern]

    installed_packages = _get_installed_packages()
    matched = [pkg for pkg in installed_packages if fnmatch.fnmatchcase(pkg.lower(), pattern.lower())]
    return matched


def _filter_protected_packages(packages: list[str]) -> list[str]:
    """过滤掉受保护的包名."""
    safe = [p for p in packages if p.lower() not in {p.lower() for p in _PROTECTED_PACKAGES}]
    filtered = [p for p in packages if p.lower() in {p.lower() for p in _PROTECTED_PACKAGES}]
    if filtered:
        print(f"跳过受保护的包: {', '.join(filtered)}")
    return safe


def pip_uninstall(pkg_names: list[str]) -> None:
    """卸载包."""
    packages_to_uninstall: list[str] = []
    for pattern in pkg_names:
        packages_to_uninstall.extend(_expand_wildcard_packages(pattern))

    packages_to_uninstall = _filter_protected_packages(packages_to_uninstall)

    if not packages_to_uninstall:
        return

    subprocess.run(["pip", "uninstall", "-y", *packages_to_uninstall], check=True)


def pip_reinstall(pkg_names: list[str], offline: bool = False) -> None:
    """重新安装包."""
    safe_pkgs = _filter_protected_packages(pkg_names)
    if not safe_pkgs:
        print("所有指定的包均为受保护包, 跳过重装")
        return

    subprocess.run(["pip", "uninstall", "-y", *safe_pkgs], check=True)

    options = ["--no-index", "--find-links", "."] if offline else []
    subprocess.run(["pip", "install", *options, *safe_pkgs], check=True)


def pip_download(pkg_names: list[str], offline: bool = False) -> None:
    """下载包."""
    options = ["--no-index", "--find-links", "."] if offline else []
    subprocess.run(
        ["pip", "download", *pkg_names, *options, "-d", PACKAGE_DIR],
        check=True,
    )


def pip_freeze() -> None:
    """冻结依赖."""
    result = subprocess.run(
        ["pip", "freeze", "--exclude-editable"],
        capture_output=True,
        text=True,
        check=True,
    )
    Path(REQUIREMENTS_FILE).write_text(result.stdout)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """pip 工具主函数."""
    parser = argparse.ArgumentParser(
        description="PipTool - pip 包管理工具",
        usage="piptool <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 安装命令
    install_parser = subparsers.add_parser("i", help="安装包")
    install_parser.add_argument("packages", nargs="+", help="要安装的包名")

    # 卸载命令
    uninstall_parser = subparsers.add_parser("u", help="卸载包")
    uninstall_parser.add_argument("packages", nargs="+", help="要卸载的包名 (支持通配符)")

    # 重装命令
    reinstall_parser = subparsers.add_parser("r", help="重新安装包")
    reinstall_parser.add_argument("packages", nargs="+", help="要重装的包名")
    reinstall_parser.add_argument("--offline", action="store_true", help="使用离线模式")

    # 下载命令
    download_parser = subparsers.add_parser("d", help="下载包")
    download_parser.add_argument("packages", nargs="+", help="要下载的包名")
    download_parser.add_argument("--offline", action="store_true", help="使用离线模式")

    # 升级 pip 命令
    subparsers.add_parser("up", help="升级 pip")

    # 冻结依赖命令
    subparsers.add_parser("f", help="冻结依赖到 requirements.txt")

    args = parser.parse_args()

    if args.command == "i":
        graph = px.Graph.from_specs([px.TaskSpec("pip_install", cmd=["pip", "install", *args.packages], verbose=True)])
    elif args.command == "u":
        graph = px.Graph.from_specs([
            px.TaskSpec("pip_uninstall", fn=pip_uninstall, args=(args.packages,), verbose=True)
        ])
    elif args.command == "r":
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "pip_reinstall",
                fn=pip_reinstall,
                args=(args.packages,),
                kwargs={"offline": args.offline},
                verbose=True,
            )
        ])
    elif args.command == "d":
        graph = px.Graph.from_specs([
            px.TaskSpec(
                "pip_download",
                fn=pip_download,
                args=(args.packages,),
                kwargs={"offline": args.offline},
                verbose=True,
            )
        ])
    elif args.command == "up":
        graph = px.Graph.from_specs([
            px.TaskSpec("pip_upgrade", cmd=["python", "-m", "pip", "install", "--upgrade", "pip"], verbose=True)
        ])
    elif args.command == "f":
        graph = px.Graph.from_specs([px.TaskSpec("pip_freeze", fn=pip_freeze, verbose=True)])
    else:
        parser.print_help()
        return

    px.run(graph, strategy="thread")
