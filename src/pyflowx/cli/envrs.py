"""Rust 环境配置工具.

配置 Rustup 和 Cargo 的国内镜像源,
加速 Rust 工具链和依赖包的下载.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

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

DEFAULT_PYTHON_VERSION: str = "nightly"
DEFAULT_MIRROR: str = "aliyun"


# ============================================================================
# 辅助函数
# ============================================================================


def set_rust_mirror(mirror: str = "aliyun") -> None:
    """设置 Rust 镜像源.

    Parameters
    ----------
    mirror : str
        镜像源名称: aliyun, ustc, tsinghua
    """
    mirror_dict = RUSTUP_MIRRORS.get(mirror, RUSTUP_MIRRORS["aliyun"])
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


def install_rust(version: str = "nightly") -> None:
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
# TaskSpec 定义
# ============================================================================

envrs_aliyun: px.TaskSpec = px.TaskSpec("envrs_aliyun", fn=lambda: set_rust_mirror("aliyun"))
envrs_ustc: px.TaskSpec = px.TaskSpec("envrs_ustc", fn=lambda: set_rust_mirror("ustc"))
envrs_tsinghua: px.TaskSpec = px.TaskSpec("envrs_tsinghua", fn=lambda: set_rust_mirror("tsinghua"))

rust_install_stable: px.TaskSpec = px.TaskSpec("rust_install_stable", cmd=["rustup", "toolchain", "install", "stable"])
rust_install_nightly: px.TaskSpec = px.TaskSpec(
    "rust_install_nightly", cmd=["rustup", "toolchain", "install", "nightly"]
)


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """Rust 环境配置工具主函数."""
    runner = px.CliRunner(
        strategy="thread",
        description="EnvRs - Rust 环境配置工具",
        graphs={
            # 设置阿里云镜像源
            "a": px.Graph.from_specs([envrs_aliyun]),
            # 设置中科大镜像源
            "u": px.Graph.from_specs([envrs_ustc]),
            # 设置清华镜像源
            "t": px.Graph.from_specs([envrs_tsinghua]),
            # 安装 stable 版本
            "s": px.Graph.from_specs([rust_install_stable]),
            # 安装 nightly 版本
            "n": px.Graph.from_specs([rust_install_nightly]),
        },
    )
    runner.run_cli()
