"""Tests for CliRunner: command dispatch, argument parsing, exit codes."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import patch

import pytest

import pyflowx as px
from pyflowx import CliExitCode
from pyflowx.errors import TaskFailedError

# 跨平台的 echo 命令
if sys.platform == "win32":
    ECHO_CMD = ["cmd", "/c", "echo"]
else:
    ECHO_CMD = ["echo"]


# ---------------------------------------------------------------------- #
# 辅助工厂
# ---------------------------------------------------------------------- #
def _echo_graph(name: str = "echo_task", msg: str = "hello") -> px.Graph:
    """构造一个单任务 echo 图, 用于执行成功场景."""
    return px.Graph.from_specs([px.TaskSpec(name, cmd=[*ECHO_CMD, msg])])


def _failing_graph() -> px.Graph:
    """构造一个必定失败的单任务图."""
    return px.Graph.from_specs(
        [
            px.TaskSpec(
                "fail",
                cmd=["python", "-c", "import sys; sys.exit(1)"],
            )
        ]
    )


def _multi_task_graph() -> px.Graph:
    """构造一个带依赖的多任务图."""
    return px.Graph.from_specs(
        [
            px.TaskSpec("a", cmd=[*ECHO_CMD, "a"]),
            px.TaskSpec("b", cmd=[*ECHO_CMD, "b"], depends_on=("a",)),
        ]
    )


# ---------------------------------------------------------------------- #
# 构造与校验
# ---------------------------------------------------------------------- #
class TestCliRunnerConstruction:
    """测试 CliRunner 的构造与参数校验."""

    def test_requires_at_least_one_command(self) -> None:
        """没有命令时应抛出 ValueError."""
        with pytest.raises(ValueError, match="至少需要一个命令"):
            _ = px.CliRunner()

    def test_accepts_single_graph(self) -> None:
        """单个命令应正常构造."""
        runner = px.CliRunner(graphs={"clean": _echo_graph()})
        assert runner.commands == ["clean"]

    def test_accepts_multiple_graphs(self) -> None:
        """多个命令应按插入顺序保留."""
        runner = px.CliRunner(
            graphs={
                "clean": _echo_graph("c", "clean"),
                "build": _echo_graph("b", "build"),
                "test": _echo_graph("t", "test"),
            }
        )
        assert runner.commands == ["clean", "build", "test"]

    def test_default_strategy_is_sequential(self) -> None:
        """默认策略应为 Strategy.SEQUENTIAL."""
        runner = px.CliRunner({"clean": _echo_graph()})
        assert runner.strategy == "sequential"

    def test_custom_strategy_string(self) -> None:
        """应支持通过字符串指定策略."""
        runner = px.CliRunner({"clean": _echo_graph()}, strategy="thread")
        assert runner.strategy == "thread"

    def test_custom_strategy_enum(self) -> None:
        """应支持通过 Strategy 枚举指定策略."""
        runner = px.CliRunner({"clean": _echo_graph()}, strategy="async")
        assert runner.strategy == "async"

    def test_default_verbose_is_true(self) -> None:
        """默认 verbose 应为 True."""
        runner = px.CliRunner({"clean": _echo_graph()})
        assert runner.verbose is True

    def test_custom_verbose_false(self) -> None:
        """应支持关闭 verbose."""
        runner = px.CliRunner({"clean": _echo_graph()}, verbose=False)
        assert runner.verbose is False

    def test_default_description_is_empty(self) -> None:
        """默认描述应为空字符串."""
        runner = px.CliRunner({"clean": _echo_graph()})
        assert runner.description == ""

    def test_custom_description(self) -> None:
        """应支持自定义描述."""
        runner = px.CliRunner({"clean": _echo_graph()}, description="My CLI")
        assert runner.description == "My CLI"


# ---------------------------------------------------------------------- #
# 属性与内省
# ---------------------------------------------------------------------- #
class TestCliRunnerProperties:
    """测试 CliRunner 的属性访问."""

    def test_commands_returns_list(self) -> None:
        """commands 应返回列表."""
        runner = px.CliRunner({"a": _echo_graph(), "b": _echo_graph()})
        assert isinstance(runner.commands, list)

    def test_graphs_contains_original_graphs(self) -> None:
        """graphs 应包含原始 Graph 实例."""
        g = _echo_graph()
        runner = px.CliRunner({"cmd": g})
        assert runner.graphs["cmd"] is g


# ---------------------------------------------------------------------- #
# 参数解析
# ---------------------------------------------------------------------- #
class TestCliRunnerParser:
    """测试参数解析器."""

    def test_create_parser_returns_argument_parser(self) -> None:
        """create_parser 应返回 ArgumentParser."""
        from argparse import ArgumentParser

        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        assert isinstance(parser, ArgumentParser)

    def test_parser_has_command_argument(self) -> None:
        """解析器应有 command 位置参数."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args(["clean"])
        assert parsed.command == "clean"

    def test_parser_command_is_optional(self) -> None:
        """command 应为可选参数."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args([])
        assert parsed.command is None

    def test_parser_has_strategy_option(self) -> None:
        """解析器应有 --strategy 选项."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args(["clean", "--strategy", "thread"])
        assert parsed.strategy == "thread"

    def test_parser_strategy_default(self) -> None:
        """--strategy 默认值应与构造时一致."""
        runner = px.CliRunner({"clean": _echo_graph()}, strategy="async")
        parser = runner.create_parser()
        parsed = parser.parse_args(["clean"])
        assert parsed.strategy == "async"

    def test_parser_has_dry_run_flag(self) -> None:
        """解析器应有 --dry-run 标志."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args(["clean", "--dry-run"])
        assert parsed.dry_run is True

    def test_parser_dry_run_default_false(self) -> None:
        """--dry-run 默认为 False."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args(["clean"])
        assert parsed.dry_run is False

    def test_parser_has_list_flag(self) -> None:
        """解析器应有 --list 标志."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args(["--list"])
        assert parsed.list is True

    def test_parser_has_quiet_flag(self) -> None:
        """解析器应有 --quiet 标志."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args(["clean", "--quiet"])
        assert parsed.quiet is True

    def test_parser_quiet_default_false(self) -> None:
        """--quiet 默认为 False."""
        runner = px.CliRunner({"clean": _echo_graph()})
        parser = runner.create_parser()
        parsed = parser.parse_args(["clean"])
        assert parsed.quiet is False

    def test_format_commands_help_contains_all_commands(self) -> None:
        """帮助文本应包含所有命令."""
        runner = px.CliRunner(
            {"clean": _echo_graph("c", "clean"), "build": _echo_graph("b", "build")},
        )
        help_text = runner._format_commands_help()
        assert "clean" in help_text
        assert "build" in help_text
        assert "可用命令" in help_text


# ---------------------------------------------------------------------- #
# 执行: 成功路径
# ---------------------------------------------------------------------- #
class TestCliRunnerRunSuccess:
    """测试 CliRunner.run 的成功执行路径."""

    def test_run_valid_command_returns_zero(self) -> None:
        """有效命令执行成功应返回 0."""
        runner = px.CliRunner({"clean": _echo_graph()})
        exit_code = runner.run(["clean"])
        assert exit_code == CliExitCode.SUCCESS.value

    def test_run_executes_correct_graph(self) -> None:
        """应执行用户指定的命令对应的图."""
        executed: list[str] = []

        def track_a() -> None:
            executed.append("a")

        def track_b() -> None:
            executed.append("b")

        runner = px.CliRunner(
            {
                "a": px.Graph.from_specs([px.TaskSpec("a", track_a)]),
                "b": px.Graph.from_specs([px.TaskSpec("b", track_b)]),
            }
        )
        _ = runner.run(["b"])
        assert executed == ["b"]

    def test_run_multi_task_graph(self) -> None:
        """应能执行带依赖的多任务图."""
        runner = px.CliRunner({"multi": _multi_task_graph()})
        exit_code = runner.run(["multi"])
        assert exit_code == CliExitCode.SUCCESS.value

    def test_run_with_strategy_override(self) -> None:
        """应支持通过 --strategy 覆盖默认策略."""
        runner = px.CliRunner({"echo": _echo_graph()})
        exit_code = runner.run(["echo", "--strategy", "thread"])
        assert exit_code == CliExitCode.SUCCESS.value

    def test_run_with_dry_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run 应只打印计划不执行."""
        runner = px.CliRunner({"echo": _echo_graph()})
        exit_code = runner.run(["echo", "--dry-run"])
        assert exit_code == CliExitCode.SUCCESS.value
        captured = capsys.readouterr()
        assert "Dry run" in captured.out


# ---------------------------------------------------------------------- #
# 执行: verbose 模式
# ---------------------------------------------------------------------- #
class TestCliRunnerVerbose:
    """测试 verbose 模式."""

    def test_verbose_default_prints_lifecycle(self, capsys: pytest.CaptureFixture[str]) -> None:
        """默认 verbose=True 应打印任务生命周期."""
        runner = px.CliRunner({"echo": _echo_graph()})
        _ = runner.run(["echo"])
        captured = capsys.readouterr()
        # verbose 模式下应打印任务生命周期
        assert "[verbose]" in captured.out

    def test_quiet_flag_disables_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--quiet 应关闭 verbose 输出."""
        runner = px.CliRunner({"echo": _echo_graph()})
        _ = runner.run(["echo", "--quiet"])
        captured = capsys.readouterr()
        # quiet 模式下不应有 [verbose] 前缀的输出
        assert "[verbose]" not in captured.out

    def test_verbose_false_constructor_disables_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        """构造时 verbose=False 应关闭 verbose 输出."""
        runner = px.CliRunner({"echo": _echo_graph()}, verbose=False)
        _ = runner.run(["echo"])
        captured = capsys.readouterr()
        assert "[verbose]" not in captured.out

    def test_verbose_prints_command_for_cmd_task(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose 模式下 cmd 任务应打印执行的命令."""
        runner = px.CliRunner({"echo": _echo_graph(msg="verbose-test")})
        _ = runner.run(["echo"])
        captured = capsys.readouterr()
        # 应打印执行的命令
        assert "执行命令" in captured.out or "执行 Shell" in captured.out
        # 应打印返回码
        assert "返回码" in captured.out

    def test_verbose_prints_success_lifecycle(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose 模式下成功任务应打印成功信息."""
        runner = px.CliRunner({"echo": _echo_graph()})
        _ = runner.run(["echo"])
        captured = capsys.readouterr()
        assert "成功" in captured.out

    def test_verbose_prints_skip_lifecycle(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose 模式下跳过的任务应打印跳过信息."""
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "skip_me",
                    cmd=[*ECHO_CMD, "skip"],
                    conditions=(lambda: False,),
                ),
            ]
        )
        runner = px.CliRunner({"skip": graph})
        _ = runner.run(["skip"])
        captured = capsys.readouterr()
        assert "跳过" in captured.out

    def test_verbose_prints_failure_lifecycle(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose 模式下失败任务应打印失败信息."""
        runner = px.CliRunner({"fail": _failing_graph()})
        _ = runner.run(["fail"])
        captured = capsys.readouterr()
        # 失败信息可能出现在 stdout (verbose) 或 stderr (PyFlowXError)
        combined = captured.out + captured.err
        assert "失败" in combined or "错误" in combined


# ---------------------------------------------------------------------- #
# 执行: 失败路径
# ---------------------------------------------------------------------- #
class TestCliRunnerRunFailure:
    """测试 CliRunner.run 的失败执行路径."""

    def test_run_unknown_command_returns_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """未知命令应返回 1 并打印错误."""
        runner = px.CliRunner({"clean": _echo_graph()})
        exit_code = runner.run(["unknown"])
        assert exit_code == CliExitCode.FAILURE.value
        captured = capsys.readouterr()
        assert "未知命令" in captured.err
        assert "clean" in captured.err

    def test_run_no_command_returns_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """无命令时应返回 1 并打印帮助."""
        runner = px.CliRunner({"clean": _echo_graph()})
        exit_code = runner.run([])
        assert exit_code == CliExitCode.FAILURE.value
        captured = capsys.readouterr()
        assert "可用命令" in captured.out or "可用命令" in captured.err

    def test_run_failing_task_returns_failure(self) -> None:
        """任务失败时应返回 1."""
        runner = px.CliRunner({"fail": _failing_graph()})
        exit_code = runner.run(["fail"])
        assert exit_code == CliExitCode.FAILURE.value

    def test_run_failing_task_prints_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """任务失败时应打印错误信息."""
        runner = px.CliRunner({"fail": _failing_graph()})
        _ = runner.run(["fail"])
        captured = capsys.readouterr()
        # PyFlowXError 信息应输出到 stderr
        assert "错误" in captured.err or "失败" in captured.err


# ---------------------------------------------------------------------- #
# 执行: --list 选项
# ---------------------------------------------------------------------- #
class TestCliRunnerList:
    """测试 --list 选项."""

    def test_list_returns_success(self) -> None:
        """--list 应返回 0."""
        runner = px.CliRunner({"clean": _echo_graph(), "build": _echo_graph()})
        exit_code = runner.run(["--list"])
        assert exit_code == CliExitCode.SUCCESS.value

    def test_list_prints_all_commands(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--list 应打印所有命令."""
        runner = px.CliRunner(
            {
                "clean": _echo_graph("c", "clean"),
                "build": _echo_graph("b", "build"),
                "test": _echo_graph("t", "test"),
            }
        )
        _ = runner.run(["--list"])
        captured = capsys.readouterr()
        assert "clean" in captured.out
        assert "build" in captured.out
        assert "test" in captured.out

    def test_list_does_not_execute_any_graph(self) -> None:
        """--list 不应执行任何图."""
        executed: list[str] = []

        def track() -> None:
            executed.append("ran")

        runner = px.CliRunner({"a": px.Graph.from_specs([px.TaskSpec("a", track)])})
        _ = runner.run(["--list"])
        assert executed == []


# ---------------------------------------------------------------------- #
# 错误处理
# ---------------------------------------------------------------------- #
class TestCliRunnerErrorHandling:
    """测试错误处理."""

    def test_keyboard_interrupt_returns_130(self, capsys: pytest.CaptureFixture[str]) -> None:
        """KeyboardInterrupt 应返回 130."""
        runner = px.CliRunner({"echo": _echo_graph()})

        def raise_interrupt(*_args: Any, **_kwargs: Any) -> None:
            raise KeyboardInterrupt

        with patch("pyflowx.runner.run", side_effect=raise_interrupt):
            exit_code = runner.run(["echo"])
        assert exit_code == CliExitCode.INTERRUPTED.value
        captured = capsys.readouterr()
        assert "取消" in captured.err

    def test_pyflowx_error_returns_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """PyFlowXError 应返回 1."""
        runner = px.CliRunner({"echo": _echo_graph()})

        def raise_error(*_args: Any, **_kwargs: Any) -> None:
            raise TaskFailedError("echo", RuntimeError("boom"), 1)

        with patch("pyflowx.runner.run", side_effect=raise_error):
            exit_code = runner.run(["echo"])
        assert exit_code == CliExitCode.FAILURE.value
        captured = capsys.readouterr()
        assert "错误" in captured.err

    def test_generic_exception_propagates(self) -> None:
        """非 PyFlowXError 的异常应向上传播."""

        class CustomError(Exception):
            pass

        runner = px.CliRunner({"echo": _echo_graph()})

        def raise_custom(*_args: Any, **_kwargs: Any) -> None:
            raise CustomError("unexpected")

        with patch("pyflowx.runner.run", side_effect=raise_custom), pytest.raises(CustomError):
            _ = runner.run(["echo"])


# ---------------------------------------------------------------------- #
# run_cli
# ---------------------------------------------------------------------- #
class TestCliRunnerRunCli:
    """测试 run_cli 方法."""

    def test_run_cli_calls_sys_exit(self) -> None:
        """run_cli 应调用 sys.exit."""
        runner = px.CliRunner({"echo": _echo_graph()})
        with pytest.raises(SystemExit) as exc_info:
            runner.run_cli(["echo"])
        assert exc_info.value.code == CliExitCode.SUCCESS.value

    def test_run_cli_exit_code_on_failure(self) -> None:
        """run_cli 失败时应以非零码退出."""
        runner = px.CliRunner({"fail": _failing_graph()})
        with pytest.raises(SystemExit) as exc_info:
            runner.run_cli(["fail"])
        assert exc_info.value.code == CliExitCode.FAILURE.value

    def test_run_cli_no_args_uses_sys_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_cli 无参数时应使用 sys.argv."""
        monkeypatch.setattr(sys, "argv", ["pymake", "echo"])
        runner = px.CliRunner({"echo": _echo_graph()})
        with pytest.raises(SystemExit) as exc_info:
            runner.run_cli()
        assert exc_info.value.code == CliExitCode.SUCCESS.value


# ---------------------------------------------------------------------- #
# 退出码枚举
# ---------------------------------------------------------------------- #
class TestCliExitCode:
    """测试 CliExitCode 枚举."""

    def test_success_is_zero(self) -> None:
        assert CliExitCode.SUCCESS.value == 0

    def test_failure_is_one(self) -> None:
        assert CliExitCode.FAILURE.value == 1

    def test_interrupted_is_130(self) -> None:
        assert CliExitCode.INTERRUPTED.value == 130

    def test_exit_codes_are_distinct(self) -> None:
        values = {e.value for e in CliExitCode}
        assert len(values) == 3


# ---------------------------------------------------------------------- #
# 集成测试
# ---------------------------------------------------------------------- #
class TestCliRunnerIntegration:
    """集成测试: CliRunner + Graph + TaskSpec + 条件."""

    def test_condition_skipped_command_succeeds(self) -> None:
        """条件不满足时任务跳过, 整体仍成功."""
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "skip_me",
                    cmd=[*ECHO_CMD, "should not run"],
                    conditions=(lambda: False,),
                ),
            ]
        )
        runner = px.CliRunner({"skip": graph})
        exit_code = runner.run(["skip"])
        assert exit_code == CliExitCode.SUCCESS.value

    def test_condition_met_command_succeeds(self) -> None:
        """条件满足时任务执行, 整体成功."""
        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "run_me",
                    cmd=[*ECHO_CMD, "should run"],
                    conditions=(lambda: True,),
                ),
            ]
        )
        runner = px.CliRunner({"run": graph})
        exit_code = runner.run(["run"])
        assert exit_code == CliExitCode.SUCCESS.value

    def test_diamond_dependency_graph(self) -> None:
        """菱形依赖图应正确执行."""
        order: list[str] = []

        def make(name: str) -> Any:
            def fn() -> str:
                order.append(name)
                return name

            return fn

        graph = px.Graph.from_specs(
            [
                px.TaskSpec("a", make("a")),
                px.TaskSpec("b", make("b"), depends_on=("a",)),
                px.TaskSpec("c", make("c"), depends_on=("a",)),
                px.TaskSpec("d", make("d"), depends_on=("b", "c")),
            ]
        )
        runner = px.CliRunner({"diamond": graph})
        exit_code = runner.run(["diamond"])
        assert exit_code == CliExitCode.SUCCESS.value
        assert order == ["a", "b", "c", "d"]

    def test_mixed_fn_and_cmd_commands(self) -> None:
        """混合 fn 和 cmd 的命令应都能执行."""
        runner = px.CliRunner(
            {
                "fn_cmd": px.Graph.from_specs([px.TaskSpec("fn", fn=lambda: "fn-result")]),
                "cmd_cmd": px.Graph.from_specs([px.TaskSpec("cmd", cmd=[*ECHO_CMD, "cmd-result"])]),
            }
        )
        assert runner.run(["fn_cmd"]) == CliExitCode.SUCCESS.value
        assert runner.run(["cmd_cmd"]) == CliExitCode.SUCCESS.value

    def test_command_with_cwd(self) -> None:
        """带 cwd 的命令应正确执行."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            if sys.platform == "win32":
                ls_cmd = ["cmd", "/c", "dir"]
            else:
                ls_cmd = ["ls"]

            graph = px.Graph.from_specs([px.TaskSpec("ls", cmd=ls_cmd, cwd=Path(tmpdir))])
            runner = px.CliRunner({"ls": graph})
            exit_code = runner.run(["ls"])
            assert exit_code == CliExitCode.SUCCESS.value


# ---------------------------------------------------------------------- #
# 构造校验 (补充覆盖)
# ---------------------------------------------------------------------- #
class TestCliRunnerConstructionValidation:
    """测试 CliRunner 的构造校验 (补充覆盖)."""

    def test_non_graph_value_raises_type_error(self) -> None:
        """非 Graph 值应抛出 TypeError (覆盖 runner.py line 119)."""
        with pytest.raises(TypeError, match="必须是 Graph 实例"):
            _ = px.CliRunner(graphs={"bad": "not a graph"})  # type: ignore[dict-item]

    def test_non_graph_value_dict_raises_type_error(self) -> None:
        """dict 中包含非 Graph 值应抛出 TypeError."""
        with pytest.raises(TypeError, match="必须是 Graph 实例"):
            _ = px.CliRunner(graphs={"good": _echo_graph(), "bad": 123})  # type: ignore[dict-item]


# ---------------------------------------------------------------------- #
# _apply_verbose_to_graph (补充覆盖)
# ---------------------------------------------------------------------- #
class TestApplyVerboseToGraph:
    """测试 _apply_verbose_to_graph 函数 (补充覆盖)."""

    def test_specs_with_matching_verbose_are_kept(self) -> None:
        """spec.verbose 已与目标值匹配时应保留原 spec (覆盖 runner.py line 57)."""
        from pyflowx.runner import _apply_verbose_to_graph

        # 创建 verbose=True 的 spec
        graph = px.Graph.from_specs([px.TaskSpec("a", cmd=[*ECHO_CMD, "a"], verbose=True)])
        # 应用 verbose=True, spec.verbose 已匹配, 应保留原 spec
        new_graph = _apply_verbose_to_graph(graph, verbose=True)
        new_spec = new_graph.spec("a")
        assert new_spec.verbose is True

    def test_specs_with_non_matching_verbose_are_replaced(self) -> None:
        """spec.verbose 与目标值不匹配时应替换 (覆盖 else 分支)."""
        from pyflowx.runner import _apply_verbose_to_graph

        # 创建 verbose=False 的 spec
        graph = px.Graph.from_specs([px.TaskSpec("a", cmd=[*ECHO_CMD, "a"], verbose=False)])
        # 应用 verbose=True, spec.verbose 不匹配, 应替换
        new_graph = _apply_verbose_to_graph(graph, verbose=True)
        new_spec = new_graph.spec("a")
        assert new_spec.verbose is True
