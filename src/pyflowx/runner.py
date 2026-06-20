"""命令行运行器：根据用户输入执行对应的任务流图.

参考 bitool_skill 的 MapSkill 设计, 将命令名映射到 Graph 实例,
通过 argparse 解析用户输入的命令并执行对应的图.

与 bitool_skill.MapSkill 的区别:
- MapSkill 通过继承 + create_scheduler_map 构建命令映射
- CliRunner 通过关键字参数直接注入命令到图的映射, 更声明式
- CliRunner 复用 pyflowx 的 DAG 调度能力 (run/Graph/TaskSpec)

verbose 模式
------------
``CliRunner`` 默认 ``verbose=True``, 会:
1. 打印任务生命周期 (开始/成功/失败/跳过) 到 stdout
2. 对 ``cmd`` 类任务, 显示执行的命令及其标准输出/标准错误

可通过构造参数 ``verbose=False`` 或命令行 ``--quiet`` 关闭.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import sys
from typing import Dict, List, Optional, Sequence, Union

from .errors import PyFlowXError
from .executors import Strategy, _normalize_strategy, run
from .graph import Graph

__all__ = ["CliRunner", "CliExitCode"]


class CliExitCode(enum.IntEnum):
    """CliRunner 退出码."""

    SUCCESS = 0
    FAILURE = 1
    INTERRUPTED = 130  # 与 POSIX 信号中断一致


def _apply_verbose_to_graph(graph: Graph, verbose: bool) -> Graph:
    """创建新图, 其中所有 TaskSpec 的 verbose 字段被设置为指定值.

    使用 ``dataclasses.replace`` 在不可变的 TaskSpec 上创建带 verbose 标记的副本.
    依赖关系、标签等元数据全部保留.

    Parameters
    ----------
    graph : Graph
        原始图.
    verbose : bool
        要设置的 verbose 值.

    Returns
    -------
    Graph
        所有 spec 的 verbose 字段已更新的新图.
    """
    new_specs = []
    for spec in graph.all_specs().values():
        if spec.verbose == verbose:
            new_specs.append(spec)
        else:
            new_specs.append(dataclasses.replace(spec, verbose=verbose))
    return Graph.from_specs(new_specs)


class CliRunner:
    """命令行运行器: 根据用户输入执行对应的任务流图.

    参考 bitool_skill 的 MapSkill 设计, 将命令名映射到 Graph 实例.
    通过 ``sys.argv`` 解析用户输入的命令, 执行对应的图.

    Parameters
    ----------
    strategy : str | Strategy
        默认执行策略 (``Strategy.SEQUENTIAL`` / ``Strategy.THREAD`` /
        ``Strategy.ASYNC`` 或对应字符串). 可被命令行 ``--strategy`` 覆盖.
    description : str
        CLI 描述文本, 显示在 ``--help`` 中.
    verbose : bool
        是否显示详细执行过程. ``True`` 时打印任务生命周期和 subprocess 输出.
        默认 ``True``. 可被命令行 ``--quiet`` 关闭.
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
            strategy=px.Strategy.THREAD,
            description="My build tool",
            test=px.Graph.from_specs([...]),
        )
        runner.run(["test", "--strategy", "sequential"])
    """

    def __init__(
        self,
        *,
        strategy: Union[str, Strategy] = Strategy.SEQUENTIAL,
        description: str = "",
        verbose: bool = True,
        **graphs: Graph,
    ) -> None:
        if not graphs:
            raise ValueError("CliRunner 至少需要一个命令 (通过关键字参数提供)")
        # 校验所有值都是 Graph
        for name, graph in graphs.items():
            if not isinstance(graph, Graph):
                raise TypeError(
                    f"CliRunner 命令 {name!r} 的值必须是 Graph 实例, 实际是 {type(graph).__name__}"
                )
        self._graphs: Dict[str, Graph] = dict(graphs)
        self._strategy: Strategy = _normalize_strategy(strategy)
        self._description: str = description
        self._verbose: bool = verbose

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

    @property
    def verbose(self) -> bool:
        """是否显示详细执行过程."""
        return self._verbose

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
        位置参数与 ``--strategy`` / ``--dry-run`` / ``--list`` / ``--quiet``
        选项, 否则 :meth:`run` 的默认逻辑可能失效.

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
        parser.add_argument(
            "command",
            nargs="?",
            help="要执行的命令",
        )
        parser.add_argument(
            "--strategy",
            choices=[s.value for s in Strategy],
            default=self._strategy.value,
            help="执行策略 (默认: %(default)s)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只打印执行计划, 不实际运行",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="列出所有可用命令",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="静默模式, 不显示执行过程 (覆盖默认 verbose)",
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

        # 确定是否 verbose: --quiet 覆盖默认值
        verbose = self._verbose and not parsed.quiet

        # 对图应用 verbose 设置 (重建带 verbose 标记的 spec)
        graph = self._graphs[parsed.command]
        if verbose:
            graph = _apply_verbose_to_graph(graph, verbose=True)

        # 执行对应的图
        try:
            report = run(
                graph,
                strategy=parsed.strategy,
                dry_run=parsed.dry_run,
                verbose=verbose,
            )
            return (
                CliExitCode.SUCCESS.value
                if report.success
                else CliExitCode.FAILURE.value
            )
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
