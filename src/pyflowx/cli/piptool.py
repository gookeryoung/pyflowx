"""pip 包管理工具模块.

提供 pip 包管理操作的封装,
支持安装、卸载、下载等功能.
"""

from __future__ import annotations

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
_PROTECTED_PACKAGES: frozenset[str] = frozenset(
    {
        "pyflowx",
        "bitool",
    }
)


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
# TaskSpec 定义
# ============================================================================

pip_install: px.TaskSpec = px.TaskSpec("pip_install", cmd=["pip", "install", "."])
pip_upgrade: px.TaskSpec = px.TaskSpec("pip_upgrade", cmd=["python", "-m", "pip", "install", "--upgrade", "pip"])


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """pip 工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="PipTool - pip 包管理工具",
        graphs={
            # 安装包
            "i": px.Graph.from_specs([pip_install]),
            # 升级 pip
            "up": px.Graph.from_specs([pip_upgrade]),
            # 卸载包 (需要参数)
            "u": px.Graph.from_specs(
                [
                    px.TaskSpec("pip_uninstall", fn=lambda: pip_uninstall([])),
                ]
            ),
            # 下载包
            "d": px.Graph.from_specs(
                [
                    px.TaskSpec("pip_download", fn=lambda: pip_download([])),
                ]
            ),
            # 冻结依赖
            "f": px.Graph.from_specs(
                [
                    px.TaskSpec("pip_freeze", fn=pip_freeze),
                ]
            ),
        },
    )
    runner.run_cli()
