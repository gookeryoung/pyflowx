"""LS-DYNA 计算工具.

用于管理 LS-DYNA 仿真计算任务,
支持启动、监控和管理计算进程.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pyflowx as px
from pyflowx.conditions import Constants

# ============================================================================
# 配置
# ============================================================================

LS_DYNA_COMMANDS: dict[str, list[str]] = {
    "windows": ["ls-dyna_mpp", "i=input.k", "ncpu=4"],
    "linux": ["ls-dyna_mpp", "i=input.k", "ncpu=8"],
    "macos": ["ls-dyna_mpp", "i=input.k", "ncpu=4"],
}

DEFAULT_INPUT_FILE: str = "input.k"
DEFAULT_NCPU: int = 4


# ============================================================================
# 辅助函数
# ============================================================================


def get_ls_dyna_command(input_file: str, ncpu: int) -> list[str]:
    """获取 LS-DYNA 命令.

    Parameters
    ----------
    input_file : str
        输入文件路径
    ncpu : int
        CPU 核心数

    Returns
    -------
    list[str]
        LS-DYNA 命令列表
    """
    if Constants.IS_WINDOWS or Constants.IS_MACOS:
        return ["ls-dyna_mpp", f"i={input_file}", f"ncpu={ncpu}"]
    else:
        return ["ls-dyna_mpp", f"i={input_file}", f"ncpu={ncpu}"]


def run_ls_dyna(input_file: str, ncpu: int = DEFAULT_NCPU) -> None:
    """运行 LS-DYNA 计算.

    Parameters
    ----------
    input_file : str
        输入文件路径
    ncpu : int
        CPU 核心数
    """
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"输入文件不存在: {input_path}")
        return

    cmd = get_ls_dyna_command(input_file, ncpu)
    try:
        subprocess.run(cmd, check=True)
        print(f"LS-DYNA 计算完成: {input_file}")
    except FileNotFoundError:
        print("未找到 ls-dyna_mpp 命令")
    except subprocess.CalledProcessError as e:
        print(f"LS-DYNA 计算失败: {e}")


def run_ls_dyna_mpi(input_file: str, ncpu: int = DEFAULT_NCPU) -> None:
    """运行 LS-DYNA MPI 计算.

    Parameters
    ----------
    input_file : str
        输入文件路径
    ncpu : int
        CPU 核心数
    """
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"输入文件不存在: {input_path}")
        return

    cmd = ["mpirun", "-np", str(ncpu), "ls-dyna_mpp", f"i={input_file}"]
    try:
        subprocess.run(cmd, check=True)
        print(f"LS-DYNA MPI 计算完成: {input_file}")
    except FileNotFoundError:
        print("未找到 mpirun 或 ls-dyna_mpp 命令")
    except subprocess.CalledProcessError as e:
        print(f"LS-DYNA MPI 计算失败: {e}")


def check_ls_dyna_status() -> None:
    """检查 LS-DYNA 进程状态."""
    try:
        if Constants.IS_WINDOWS:
            result = subprocess.run(
                ["tasklist", "/fi", "imagename eq ls-dyna_mpp.exe"],
                capture_output=True,
                text=True,
                check=True,
            )
            print(result.stdout)
        else:
            result = subprocess.run(
                ["pgrep", "-f", "ls-dyna"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                print(f"运行中的 LS-DYNA 进程 PID: {result.stdout.strip()}")
            else:
                print("没有运行中的 LS-DYNA 进程")
    except subprocess.CalledProcessError as e:
        print(f"检查进程状态失败: {e}")


# ============================================================================
# CLI Runner
# ============================================================================


def main() -> None:
    """LS-DYNA 计算工具主函数."""
    parser = argparse.ArgumentParser(
        description="LSCalc - LS-DYNA 计算工具",
        usage="lscalc <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 运行计算命令
    run_parser = subparsers.add_parser("run", help="运行 LS-DYNA 计算")
    run_parser.add_argument("input_file", help="输入文件路径")
    run_parser.add_argument("--ncpu", type=int, default=DEFAULT_NCPU, help="CPU 核心数")

    # 运行 MPI 计算命令
    mpi_parser = subparsers.add_parser("mpi", help="运行 LS-DYNA MPI 计算")
    mpi_parser.add_argument("input_file", help="输入文件路径")
    mpi_parser.add_argument("--ncpu", type=int, default=DEFAULT_NCPU, help="CPU 核心数")

    # 检查进程状态命令
    subparsers.add_parser("status", help="检查 LS-DYNA 进程状态")

    args = parser.parse_args()

    if args.command == "run":
        graph = px.Graph.from_specs(
            [px.TaskSpec("run_ls_dyna", fn=run_ls_dyna, args=(args.input_file,), kwargs={"ncpu": args.ncpu})]
        )
    elif args.command == "mpi":
        graph = px.Graph.from_specs(
            [px.TaskSpec("run_ls_dyna_mpi", fn=run_ls_dyna_mpi, args=(args.input_file,), kwargs={"ncpu": args.ncpu})]
        )
    elif args.command == "status":
        graph = px.Graph.from_specs([px.TaskSpec("check_ls_dyna_status", fn=check_ls_dyna_status)])
    else:
        parser.print_help()
        return

    px.run(graph, strategy="thread")
