"""命令行运行器：根据用户输入执行对应的任务流图.

verbose 模式
------------
``CliRunner`` 默认 ``verbose=True``, 会:
1. 打印任务生命周期 (开始/成功/失败/跳过) 到 stdout
2. 对 ``cmd`` 类任务, 显示执行的命令及其标准输出/标准错误

可通过构造参数 ``verbose=False`` 或命令行 ``--quiet`` 关闭.
"""

from __future__ import annotations

import argparse
import enum
import sys
from dataclasses import dataclass, field, replace
from typing import Any, Sequence, get_args

from .errors import PyFlowXError
from .executors import Strategy, run
from .graph import Graph
from .task import TaskSpec

__all__ = ["CliExitCode", "CliRunner"]


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
    new_specs: list[TaskSpec[Any]] = []
    for spec in graph.all_specs().values():
        if spec.verbose == verbose:
            new_specs.append(spec)
        else:
            new_specs.append(replace(spec, verbose=verbose))
    return Graph.from_specs(new_specs)


@dataclass(frozen=True)
class CliRunner:
    """命令行运行器: 根据用户输入执行对应的任务流图.

    将命令名映射到 Graph 实例.
    通过 ``sys.argv`` 解析用户输入的命令, 执行对应的图.

    Parameters
    ----------
    strategy : str | Strategy
        默认执行策略 (``Strategy.SEQUENTIAL`` / ``Strategy.THREAD`` /
        ``Strategy.ASYNC`` 或对应字符串). 可被命令行 ``--strategy`` 覆盖.
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
            clean=px.Graph.from_specs(
                [
                    px.TaskSpec("cargo_clean", cmd=["cargo", "clean"]),
                ]
            ),
            build=px.Graph.from_specs(
                [
                    px.TaskSpec("uv_build", cmd=["uv", "build"]),
                ]
            ),
        )
        runner.run()  # 解析 sys.argv

    指定策略与描述::

        runner = px.CliRunner(
            strategy=px.Strategy.THREAD,
        )
        runner.run(["test", "--strategy", "sequential"])
    """

    graphs: dict[str, Graph] = field(default_factory=dict)
    strategy: Strategy = field(default="sequential")
    description: str = field(default_factory=str)
    verbose: bool = field(default_factory=lambda: True)

    def __post_init__(self) -> None:
        if not self.graphs:
            raise ValueError("CliRunner 至少需要一个命令 (通过关键字参数提供)")

        # 解析并展开字符串引用
        self._resolve_graph_refs()

    def _resolve_graph_refs(self) -> None:
        """解析并展开图中的字符串引用.

        支持两种引用格式：
        1. "command_name" - 引用整个命令图
        2. "command_name.task_name" - 引用特定任务

        递归解析所有引用，直到所有图都只包含TaskSpec对象。
        """
        resolved_graphs: dict[str, Graph] = {}

        for cmd_name, graph in self.graphs.items():
            resolved_graph = self._expand_refs(graph, cmd_name)
            resolved_graphs[cmd_name] = resolved_graph

        # 更新graphs字典
        object.__setattr__(self, "graphs", resolved_graphs)

    def _expand_refs(self, graph: Graph, current_cmd: str) -> Graph:
        """展开图中的字符串引用.

        Parameters
        ----------
        graph : Graph
            包含可能的字符串引用的图
        current_cmd : str
            当前命令名（用于避免循环引用）

        Returns
        -------
        Graph
            展开后的图，只包含TaskSpec对象

        Note
        -----
        引用按顺序展开，后续引用的任务依赖于前面引用的任务完成。
        例如：["c", "tc", bump] 会展开为：
        - c的所有任务（无依赖）
        - tc的所有任务（依赖于c的最后一个任务）
        - bump任务（依赖于tc的最后一个任务）
        """
        # 检查是否有待解析的引用
        pending_refs = getattr(graph, "_pending_refs", None)
        if not pending_refs:
            return graph

        # 收集所有TaskSpec（按正确顺序：先引用，后原始TaskSpec）
        all_specs: list[TaskSpec[Any]] = []

        # 记录每个引用展开后的所有任务名，用于建立依赖链
        previous_ref_last_task: str | None = None

        # 先解析每个引用，并建立依赖关系
        for ref in pending_refs:
            expanded_specs = self._parse_ref(ref, current_cmd)

            # 如果有前面的引用，让当前引用的所有任务依赖于前面引用的最后一个任务
            if previous_ref_last_task and expanded_specs:
                # 为当前引用的每个任务添加依赖
                for i, task in enumerate(expanded_specs):
                    # 只为没有依赖的任务添加依赖，或者为第一个任务添加依赖
                    if i == 0 or not task.depends_on:
                        updated_task = replace(task, depends_on=tuple({*task.depends_on, previous_ref_last_task}))
                        expanded_specs[i] = updated_task

            # 记录当前引用的最后一个任务名
            if expanded_specs:
                previous_ref_last_task = expanded_specs[-1].name

            all_specs.extend(expanded_specs)

        # 然后添加原始图中的TaskSpec，并让它们按顺序执行
        original_specs = list(graph.all_specs().values())
        if original_specs:
            # 第一个原始TaskSpec依赖于最后一个引用的任务
            if previous_ref_last_task:
                first_original = original_specs[0]
                updated_first = replace(
                    first_original, depends_on=tuple({*first_original.depends_on, previous_ref_last_task})
                )
                all_specs.append(updated_first)
            else:
                # 如果没有引用，直接添加第一个原始TaskSpec
                all_specs.append(original_specs[0])

            # 后续的原始TaskSpec依赖于前一个原始TaskSpec
            for i in range(1, len(original_specs)):
                current_task = original_specs[i]
                previous_task_name = original_specs[i - 1].name
                # 更新依赖，确保顺序执行
                updated_task = replace(current_task, depends_on=tuple({*current_task.depends_on, previous_task_name}))
                all_specs.append(updated_task)

        # 创建新的图（不包含引用）
        return Graph.from_specs(all_specs)

    def _parse_ref(self, ref: str, current_cmd: str) -> list[TaskSpec[Any]]:
        """解析单个字符串引用.

        Parameters
        ----------
        ref : str
            引用字符串（如"tc"或"tc.lint"）
        current_cmd : str
            当前命令名（用于避免循环引用）

        Returns
        -------
        list[TaskSpec[Any]]
            解析后的TaskSpec列表

        Raises
        ------
        ValueError
            如果引用无效或存在循环引用
        """
        # 避免循环引用
        if ref == current_cmd:
            raise ValueError(f"循环引用: 命令 '{current_cmd}' 引用了自己")

        # 解析引用格式
        if "." in ref:
            # 特定任务引用: "command_name.task_name"
            cmd_name, task_name = ref.split(".", 1)
            if cmd_name not in self.graphs:
                raise ValueError(f"引用的命令 '{cmd_name}' 不存在")

            # 获取特定任务
            ref_graph = self.graphs[cmd_name]
            if task_name not in ref_graph.all_specs():
                raise ValueError(f"任务 '{task_name}' 不存在于命令 '{cmd_name}' 中")

            return [ref_graph.all_specs()[task_name]]
        else:
            # 整个命令图引用: "command_name"
            cmd_name = ref
            if cmd_name not in self.graphs:
                raise ValueError(f"引用的命令 '{cmd_name}' 不存在")

            # 获取整个图的所有任务
            ref_graph = self.graphs[cmd_name]

            # 递归展开引用（如果引用的图也有引用）
            ref_graph = self._expand_refs(ref_graph, cmd_name)

            return list(ref_graph.all_specs().values())

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #
    @property
    def commands(self) -> list[str]:
        """可用的命令列表 (按插入顺序)."""
        return list(self.graphs.keys())

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
            description=self.description or "PyFlowX CLI Runner",
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
            choices=list(get_args(Strategy)),
            default=self.strategy,
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
        _ = parser.add_argument(
            "--quiet",
            action="store_true",
            help="静默模式, 不显示执行过程 (覆盖默认 verbose)",
        )
        return parser

    def _format_commands_help(self) -> str:
        """格式化命令帮助文本."""
        return "可用命令:\n" + " | ".join(self.graphs.keys())

    # ------------------------------------------------------------------ #
    # 执行
    # ------------------------------------------------------------------ #
    def run(self, args: Sequence[str] | None = None) -> int:
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
        if parsed.command not in self.graphs:
            available = ", ".join(self.graphs.keys())
            print(
                f"错误: 未知命令 {parsed.command!r} (可用命令: {available})",
                file=sys.stderr,
            )
            return CliExitCode.FAILURE.value

        # 确定是否 verbose: --quiet 覆盖默认值
        verbose = self.verbose and not parsed.quiet

        # 对图应用 verbose 设置 (重建带 verbose 标记的 spec)
        graph = self.graphs[parsed.command]
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
            return CliExitCode.SUCCESS.value if report.success else CliExitCode.FAILURE.value
        except KeyboardInterrupt:
            print("\n操作已取消", file=sys.stderr)
            return CliExitCode.INTERRUPTED.value
        except PyFlowXError as e:
            print(f"错误: {e}", file=sys.stderr)
            return CliExitCode.FAILURE.value

    def run_cli(self, args: Sequence[str] | None = None) -> None:
        """运行并以退出码退出进程.

        作为 CLI 工具运行时的入口点, 等价于 ``sys.exit(self.run(args))``.

        Parameters
        ----------
        args : Sequence[str] | None
            参数列表, 默认使用 ``sys.argv[1:]``.
        """
        sys.exit(self.run(args))
