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
from pathlib import Path
from typing import Any, Sequence, get_args

from .compose import GraphComposer
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

    Note
    -----
    自 ``_wrap_cmd`` 不再闭包捕获 ``verbose`` 后，此函数不再是必需的——
    直接翻转 ``spec.verbose`` 即可生效。保留是为了向后兼容现有调用与测试。
    TaskSpec 仍是 frozen dataclass，故仍用 ``replace`` 创建副本。

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


@dataclass
class CliRunner:
    """命令行运行器: 根据用户输入执行对应的任务流图.

    将命令别名映射到 Graph 实例. 通过 ``sys.argv`` 解析用户输入的命令,
    执行对应的图.

    Parameters
    ----------
    aliases : dict[str, str | list[str] | Graph]
        命令别名到任务引用的映射. 每个值可以是:
        * ``str`` —— 单个任务名 (引用 ``tasks`` 中注册的任务),
          生成单任务图.
        * ``list[str]`` —— 任务名列表, 自动 :meth:`Graph.chain` 建立链式依赖,
          即后一个任务依赖前一个.
        * :class:`~pyflowx.graph.Graph` —— 直接使用该图 (用于复杂场景, 如
          自定义 ``conditions``、并行分支等).
    tasks : list[TaskSpec]
        扁平注册的任务列表. ``aliases`` 中的字符串引用这些任务名.
        未被任何 alias 引用的任务不会被执行.
    strategy : str | Strategy
        默认执行策略. 可被命令行 ``--strategy`` 覆盖.
    description : str
        CLI 帮助文本.
    verbose : bool
        是否显示详细执行过程. 默认 ``True``, 可被命令行 ``--quiet`` 关闭.

    Examples
    --------
    简单场景 (tasks + aliases)::

        runner = px.CliRunner(
            tasks=[
                px.cmd(["uv", "build"]),                      # name="uv_build"
                px.cmd(["maturin", "build"], name="maturin_build"),
                px.cmd(["ruff", "check", "--fix"], name="lint"),
            ],
            aliases={
                "b": "uv_build",
                "ba": ["uv_build", "maturin_build"],   # chain: maturin 依赖 uv
                "lint": "lint",
            },
        )
        runner.run()

    复杂场景 (直接用 Graph)::

        runner = px.CliRunner(
            aliases={
                "a": px.Graph.from_specs([
                    px.TaskSpec("add", cmd=["git", "add", "."], conditions=(...)),
                    px.TaskSpec("commit", cmd=["git", "commit"], depends_on=("add",)),
                ]),
            },
        )
    """

    aliases: dict[str, str | list[str | TaskSpec[Any]] | TaskSpec[Any] | Graph] = field(default_factory=dict)
    tasks: list[TaskSpec[Any]] = field(default_factory=list)
    strategy: Strategy = field(default="dependency")
    description: str = field(default_factory=str)
    verbose: bool = field(default_factory=lambda: True)
    # 解析后的命令→图映射，__post_init__ 填充
    graphs: dict[str, Graph] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if not self.aliases:
            raise ValueError("CliRunner 至少需要一个别名 (通过 aliases= 提供)")

        # 1. 把 tasks 注册为虚拟命令图（每个 task 一个图），加入 raw_graphs
        #    使 GraphComposer 能解析对它们的字符串引用
        raw_graphs: dict[str, Graph] = {}
        for spec in self.tasks:
            if spec.name in raw_graphs:
                raise ValueError(f"任务名重复: {spec.name!r}")
            raw_graphs[spec.name] = Graph.from_specs([spec])

        # 2. 把每个 alias 转为 Graph（alias 名可与 task 名相同，覆盖 task 注册）
        for alias, value in self.aliases.items():
            raw_graphs[alias] = self._alias_to_graph(alias, value)

        # 3. 解析图间字符串引用（str / list[str] 引用其他 alias 或任务）
        self.graphs = GraphComposer(raw_graphs).resolve_all()

    @staticmethod
    def _alias_to_graph(
        alias: str,
        value: str | list[str | TaskSpec[Any]] | TaskSpec[Any] | Graph,
    ) -> Graph:
        """把 alias 的值转换为 Graph.

        * ``str`` —— 对其他 alias 或已注册任务名的引用, 由 GraphComposer 展开.
        * ``TaskSpec`` —— 单个内联任务, 生成单任务图.
        * ``list[str | TaskSpec]`` —— 引用/任务混合列表, GraphComposer 展开时
          自动让后续引用依赖前面 (chain 语义). 元素为 alias 名、任务名或
          :class:`TaskSpec` 对象 (内联任务).
        * ``Graph`` —— 原样返回 (用于复杂场景: conditions、并行分支等).
        """
        if isinstance(value, Graph):
            return value
        if isinstance(value, TaskSpec):
            return Graph.from_specs([value])
        if isinstance(value, str):
            # 字符串引用，用 _pending_refs 占位，GraphComposer 后续展开
            return Graph.from_specs([value])  # type: ignore[arg-type]
        if isinstance(value, list):
            if not value:
                raise ValueError(f"别名 {alias!r} 的任务列表为空")
            for item in value:
                if not isinstance(item, (str, TaskSpec)):
                    raise TypeError(f"别名 {alias!r} 的列表元素类型无效: {type(item).__name__}, 预期 str 或 TaskSpec")
            # str/TaskSpec 混合列表，由 GraphComposer 展开（自动建立 chain 依赖）
            return Graph.from_specs(value)
        raise TypeError(
            f"别名 {alias!r} 的值类型无效: {type(value).__name__}, 预期 str/TaskSpec/list[str|TaskSpec]/Graph"
        )

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #
    @property
    def commands(self) -> list[str]:
        """可用的命令列表 (按 aliases 定义顺序, 不含 tasks 中未引用的任务)."""
        return list(self.aliases.keys())

    # ------------------------------------------------------------------ #
    # 参数解析
    # ------------------------------------------------------------------ #
    def _prog_name(self) -> str:
        """从 sys.argv[0] 推导程序名."""
        return Path(sys.argv[0]).name if sys.argv else "pyflowx"

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

        # 验证命令（必须是已注册的 alias，不接受裸任务名）
        if parsed.command not in self.aliases:
            available = ", ".join(self.commands)
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
