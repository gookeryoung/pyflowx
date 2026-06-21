"""进程终止工具.

跨平台进程终止工具, 支持按名称终止进程.
用法: taskkill proc_name [proc_name ...]
"""

from __future__ import annotations

import argparse
import sys

import pyflowx as px
from pyflowx.conditions import Constants


def main() -> None:
    """进程终止工具主函数."""
    parser = argparse.ArgumentParser(
        description="TaskKill - 进程终止工具",
        usage="taskkill <process_name> [process_name ...]",
    )
    parser.add_argument(
        "process_names",
        type=str,
        nargs="+",
        help="进程名称 (如: chrome.exe python node)",
    )
    parser.add_argument(
        "--strategy",
        choices=["sequential", "thread"],
        default="sequential",
        help="执行策略 (默认: sequential)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印执行计划, 不实际运行",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式, 不显示执行过程",
    )

    args = parser.parse_args()

    # 动态创建 TaskSpec
    specs: list[px.TaskSpec] = []
    for proc_name in args.process_names:
        if Constants.IS_WINDOWS:
            cmd = ["taskkill", "/f", "/im", f"{proc_name}*"]
        else:
            cmd = ["pkill", "-f", f"{proc_name}*"]

        spec = px.TaskSpec(
            name=f"kill_{proc_name}",
            cmd=cmd,
            verbose=not args.quiet,
        )
        specs.append(spec)

    # 创建 Graph 并执行
    graph = px.Graph.from_specs(specs)

    try:
        report = px.run(
            graph,
            strategy=args.strategy,
            dry_run=args.dry_run,
            verbose=not args.quiet,
        )
        sys.exit(0 if report.success else 1)
    except KeyboardInterrupt:
        print("\n操作已取消", file=sys.stderr)
        sys.exit(130)
    except px.PyFlowXError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
