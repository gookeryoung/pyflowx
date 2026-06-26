"""Rust 环境配置工具.

配置 Rustup 和 Cargo 的国内镜像源,
加速 Rust 工具链和依赖包的下载.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Literal, get_args

import pyflowx as px

# ============================================================================
# 配置
# ============================================================================

RUSTUP_MIRRORS: dict[str, dict[str, str]] = {
    "aliyun": {
        "RUSTUP_DIST_SERVER": "https://mirrors.aliyun.com/rustup",
        "RUSTUP_UPDATE_ROOT": "https://mirrors.aliyun.com/rustup/rustup",
        "TOML_REGISTRY": "https://mirrors.aliyun.com/crates.io-index/",
    },
    "ustc": {
        "RUSTUP_DIST_SERVER": "https://mirrors.ustc.edu.cn/rust-static",
        "RUSTUP_UPDATE_ROOT": "https://mirrors.ustc.edu.cn/rust-static/rustup",
        "TOML_REGISTRY": "https://mirrors.ustc.edu.cn/crates.io-index/",
    },
    "tsinghua": {
        "RUSTUP_DIST_SERVER": "https://mirrors.tuna.tsinghua.edu.cn/rustup",
        "RUSTUP_UPDATE_ROOT": "https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup",
        "TOML_REGISTRY": "https://mirrors.tuna.tsinghua.edu.cn/crates.io-index/",
    },
}

UsableRustVersion = Literal["stable", "nightly", "beta"]
UsableMirror = Literal["aliyun", "ustc", "tsinghua"]

DEFAULT_RUST_VERSION: UsableRustVersion = "stable"
DEFAULT_MIRROR: UsableMirror = "tsinghua"


# ============================================================================
# 辅助函数
# ============================================================================


def set_rust_mirror(mirror: UsableMirror = DEFAULT_MIRROR) -> None:
    """设置 Rust 镜像源.

    Parameters
    ----------
    mirror : str
        镜像源名称: aliyun, ustc, tsinghua
    """
    mirror_dict = RUSTUP_MIRRORS.get(mirror, RUSTUP_MIRRORS[DEFAULT_MIRROR])
    server = mirror_dict["RUSTUP_DIST_SERVER"]
    update_root = mirror_dict["RUSTUP_UPDATE_ROOT"]
    toml_registry = mirror_dict["TOML_REGISTRY"]

    # 设置环境变量
    os.environ["RUSTUP_DIST_SERVER"] = server
    os.environ["RUSTUP_UPDATE_ROOT"] = update_root

    # 写入 cargo 配置
    cargo_dir = Path.home() / ".cargo"
    cargo_dir.mkdir(exist_ok=True)
    cargo_config = cargo_dir / "config.toml"
    cargo_config.write_text(
        f"""[source.crates-io]
replace-with = '{mirror}'

[source.{mirror}]
registry = "sparse+{toml_registry}"

[registries.{mirror}]
index = "sparse+{toml_registry}"
"""
    )

    print(f"已设置 Rust 镜像源: {mirror}")


def install_rust(version: UsableRustVersion = DEFAULT_RUST_VERSION) -> None:
    """安装 Rust 工具链.

    Parameters
    ----------
    version : str
        Rust 版本: stable, nightly, beta
    """
    try:
        subprocess.run(["rustup", "toolchain", "install", version], check=True)
        print(f"已安装 Rust {version}")
    except FileNotFoundError:
        print("未找到 rustup，请先安装 Rust: https://rustup.rs")
        raise


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """Rust 环境配置工具主函数."""
    parser = argparse.ArgumentParser(
        description="EnvRs - Rust 环境配置工具",
        usage="envrs <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 设置镜像源命令
    mirror_parser = subparsers.add_parser("mirror", help="设置 Rust 镜像源")
    mirror_parser.add_argument(
        "name",
        nargs="?",
        default=DEFAULT_MIRROR,
        choices=get_args(UsableMirror),
        help=f"镜像源名称 ({get_args(UsableMirror)})",
    )

    # 安装 Rust 命令
    install_parser = subparsers.add_parser("install", help="安装 Rust 工具链")
    install_parser.add_argument(
        "version",
        nargs="?",
        default=DEFAULT_RUST_VERSION,
        choices=get_args(UsableRustVersion),
        help=f"Rust 版本 ({get_args(UsableRustVersion)})",
    )

    args = parser.parse_args()

    if args.command == "mirror":
        graph = px.Graph.from_specs([
            px.TaskSpec("set_rust_mirror", fn=set_rust_mirror, args=(args.name,), verbose=True)
        ])
    elif args.command == "install":
        graph = px.Graph.from_specs([
            px.TaskSpec("install_rust", cmd=["rustup", "toolchain", "install", args.version], verbose=True)
        ])
    else:
        parser.print_help()
        return

    px.run(graph, strategy="thread", verbose=True)
