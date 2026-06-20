"""命令行运行器：根据用户输入执行对应的任务流图.

参考 bitool_skill 的 MapSkill 设计, 将命令名映射到 Graph 实例,
通过 argparse 解析用户输入的命令并执行对应的图.

与 bitool_skill.MapSkill 的区别:
- MapSkill 通过继承 + create_scheduler_map 构建命令映射
- CliRunner 通过关键字参数直接注入命令到图的映射, 更声明式
- CliRunner 复用 pyflowx 的 DAG 调度能力 (run/Graph/TaskSpec)
"""

from __future__ import annotations

import argparse
import enum
import sys
from typing import Dict, List, Optional, Sequence

from .errors import PyFlowXError
from .executors import Strategy, run
from .graph import Graph

__all__ = ["CliRunner", "CliExitCode"]


class CliExitCode(enum.IntEnum):
    """CliRunner 退出码."""

    SUCCESS = 0
    FAILURE = 1
    INTERRUPTED = 130  # 与 POSIX 信号中断一致


class CliRunner:
    """命令行运行器: 根据用户输入执行对应的任务流图.

    参考 bitool_skill 的 MapSkill 设计, 将命令名映射到 Graph 实例.
    通过 ``sys.argv`` 解析用户输入的命令, 执行对应的图.

    Parameters
    ----------
    strategy : str
        默认执行策略 (``"sequential"`` / ``"thread"`` / ``"async"``).
        可被命令行 ``--strategy`` 覆盖.
    description : str
        CLI 描述文本, 显示在 ``--help`` 中.
    **graphs : Graph
        命令名到图的映射. 每个 key 是一个命令名, value 是对应的
        :class:`~pyflowx.graph.Graph`.

    Examples
    --------
    基本用法::

        runner = px.CliRunner(
            clean=px.Graph.from_specs([
                px.TaskSpec("cargo_clean", cmd=["cargo", "clean"]),
            ]),
            build=px.Graph.from_specs([
                px.TaskSpec("uv_build", cmd=["uv", "build"]),
            ]),
        )
        runner.run()  # 解析 sys.argv

    指定策略与描述::

        runner = px.CliRunner(
            strategy="thread",
            description="My build tool",
            test=px.Graph.from_specs([...]),
        )
        runner.run(["test", "--strategy", "sequential"])
    """

    def __init__(self, *, strategy: Strategy = "sequential", description: str = "", graphs: Dict[str, Graph]) -> None:
        if not graphs:
            raise ValueError("CliRunner 至少需要一个命令 (通过关键字参数提供)")

        self._graphs: Dict[str, Graph] = dict(graphs)
        self._strategy: Strategy = strategy
        self._description: str = description

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #
    @property
    def commands(self) -> List[str]:
        """可用的命令列表 (按插入顺序)."""
        return list(self._graphs.keys())

    @property
    def graphs(self) -> Dict[str, Graph]:
        """命令名到图的映射 (只读副本)."""
        return dict(self._graphs)

    @property
    def strategy(self) -> Strategy:
        """默认执行策略."""
        return self._strategy

    @property
    def description(self) -> str:
        """CLI 描述文本."""
        return self._description

    # ------------------------------------------------------------------ #
    # 参数解析
    # ------------------------------------------------------------------ #
    def _prog_name(self) -> str:
        """从 sys.argv[0] 推导程序名."""
        import os

        return os.path.basename(sys.argv[0]) if sys.argv else "pyflowx"

    def create_parser(self) -> argparse.ArgumentParser:
        """创建参数解析器.

        子类可覆盖此方法以添加自定义参数. 覆盖时应保留 ``command``
        位置参数与 ``--strategy`` / ``--dry-run`` / ``--list`` 选项,
        否则 :meth:`run` 的默认逻辑可能失效.

        Returns
        -------
        argparse.ArgumentParser
            新创建的参数解析器实例.
        """
        parser = argparse.ArgumentParser(
            prog=self._prog_name(),
            description=self._description or "PyFlowX CLI Runner",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._format_commands_help(),
        )
        _ = parser.add_argument(
            "command",
            nargs="?",
            help="要执行的命令",
        )
        _ = parser.add_argument(
            "--strategy",
            choices=["sequential", "thread", "async"],
            default=self._strategy,
            help="执行策略 (默认: %(default)s)",
        )
        _ = parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只打印执行计划, 不实际运行",
        )
        _ = parser.add_argument(
            "--list",
            action="store_true",
            help="列出所有可用命令",
        )
        return parser

    def _format_commands_help(self) -> str:
        """格式化命令帮助文本."""
        lines = ["可用命令:"]
        for cmd in self._graphs:
            lines.append(f"  {cmd}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # 执行
    # ------------------------------------------------------------------ #
    def run(self, args: Optional[Sequence[str]] = None) -> int:
        """解析参数并执行对应的图.

        Parameters
        ----------
        args : Sequence[str] | None
            参数列表, 默认使用 ``sys.argv[1:]``.

        Returns
        -------
        int
            退出码 (0 成功, 1 失败, 130 中断).

        Raises
        ------
        SystemExit
            当 argparse 无法解析参数时 (与标准 argparse 行为一致).
        """
        parser = self.create_parser()
        parsed = parser.parse_args(args)

        # --list: 列出命令
        if parsed.list:
            print(self._format_commands_help())
            return CliExitCode.SUCCESS.value

        # 无命令: 显示帮助
        if not parsed.command:
            parser.print_help()
            return CliExitCode.FAILURE.value

        # 验证命令
        if parsed.command not in self._graphs:
            available = ", ".join(self._graphs.keys())
            print(
                f"错误: 未知命令 {parsed.command!r} (可用命令: {available})",
                file=sys.stderr,
            )
            return CliExitCode.FAILURE.value

        # 执行对应的图
        graph = self._graphs[parsed.command]
        try:
            report = run(
                graph,
                strategy=parsed.strategy,
                dry_run=parsed.dry_run,
            )
            return CliExitCode.SUCCESS.value if report.success else CliExitCode.FAILURE.value
        except KeyboardInterrupt:
            print("\n操作已取消", file=sys.stderr)
            return CliExitCode.INTERRUPTED.value
        except PyFlowXError as e:
            print(f"错误: {e}", file=sys.stderr)
            return CliExitCode.FAILURE.value

    def run_cli(self, args: Optional[Sequence[str]] = None) -> None:
        """运行并以退出码退出进程.

        作为 CLI 工具运行时的入口点, 等价于 ``sys.exit(self.run(args))``.

        Parameters
        ----------
        args : Sequence[str] | None
            参数列表, 默认使用 ``sys.argv[1:]``.
        """
        sys.exit(self.run(args))
