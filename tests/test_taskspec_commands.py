"""测试 TaskSpec 的命令和条件执行功能."""

import sys
from pathlib import Path
from typing import Any

import pytest

import pyflowx as px
from pyflowx.conditions import (
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    BuiltinConditions,
)

# 跨平台的 echo 命令
if sys.platform == "win32":
    ECHO_CMD = ["cmd", "/c", "echo"]
else:
    ECHO_CMD = ["echo"]


def test_taskspec_with_cmd_list():
    """测试使用命令列表的 TaskSpec."""
    graph = px.Graph.from_specs(
        [
            px.TaskSpec("echo_test", cmd=[*ECHO_CMD, "hello"]),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert "echo_test" in report.results
    assert report.results["echo_test"].status == px.TaskStatus.SUCCESS


def test_taskspec_with_cmd_string():
    """测试使用 shell 命令字符串的 TaskSpec."""
    if sys.platform == "win32":
        shell_cmd = 'cmd /c "echo hello from shell"'
    else:
        shell_cmd = "echo 'hello from shell'"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("shell_test", cmd=shell_cmd),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert "shell_test" in report.results
    assert report.results["shell_test"].status == px.TaskStatus.SUCCESS


def test_taskspec_with_conditions_skip():
    """测试条件不满足时任务被跳过."""

    # 创建一个永远不会满足的条件
    def never_true():
        return False

    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "should_skip",
                cmd=[*ECHO_CMD, "this should not run"],
                conditions=(never_true,),
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert "should_skip" in report.results
    assert report.results["should_skip"].status == px.TaskStatus.SKIPPED


def test_taskspec_with_conditions_execute():
    """测试条件满足时任务正常执行."""

    # 创建一个总是满足的条件
    def always_true():
        return True

    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "should_run",
                cmd=[*ECHO_CMD, "this should run"],
                conditions=(always_true,),
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert "should_run" in report.results
    assert report.results["should_run"].status == px.TaskStatus.SUCCESS


def test_platform_conditions():
    """测试平台条件."""
    if sys.platform == "win32":
        win_cmd = ["cmd", "/c", "echo", "Windows"]
        posix_cmd = ["echo", "POSIX"]
    else:
        win_cmd = ["echo", "Windows"]
        posix_cmd = ["echo", "POSIX"]

    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "win_task",
                cmd=win_cmd,
                conditions=(IS_WINDOWS,),
            ),
            px.TaskSpec(
                "linux_task",
                cmd=posix_cmd,
                conditions=(IS_LINUX,),
            ),
            px.TaskSpec(
                "macos_task",
                cmd=posix_cmd,
                conditions=(IS_MACOS,),
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success

    # 检查只有当前平台的任务执行了
    if sys.platform == "win32":
        assert report.results["win_task"].status == px.TaskStatus.SUCCESS
        assert report.results["linux_task"].status == px.TaskStatus.SKIPPED
        assert report.results["macos_task"].status == px.TaskStatus.SKIPPED
    elif sys.platform == "linux":
        assert report.results["win_task"].status == px.TaskStatus.SKIPPED
        assert report.results["linux_task"].status == px.TaskStatus.SUCCESS
        assert report.results["macos_task"].status == px.TaskStatus.SKIPPED
    elif sys.platform == "darwin":
        assert report.results["win_task"].status == px.TaskStatus.SKIPPED
        assert report.results["linux_task"].status == px.TaskStatus.SKIPPED
        assert report.results["macos_task"].status == px.TaskStatus.SUCCESS


def test_app_installed_conditions():
    """测试应用安装条件."""
    # 测试 python 应该总是安装的
    if sys.platform == "win32":
        python_cmd = ["python", "--version"]
    else:
        python_cmd = ["python3", "--version"]

    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "python_check",
                cmd=python_cmd,
                conditions=(BuiltinConditions.HAS_APP_INSTALLED("python"),),
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert "python_check" in report.results
    # python 应该总是安装的
    assert report.results["python_check"].status == px.TaskStatus.SUCCESS


def test_combined_conditions():
    """测试组合条件."""
    # AND 条件
    and_condition = BuiltinConditions.AND(
        lambda: True,
        lambda: True,
    )

    # OR 条件
    or_condition = BuiltinConditions.OR(
        lambda: True,
        lambda: False,
    )

    # NOT 条件
    not_condition = BuiltinConditions.NOT(lambda: False)

    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "and_test",
                cmd=[*ECHO_CMD, "AND"],
                conditions=(and_condition,),
            ),
            px.TaskSpec(
                "or_test",
                cmd=[*ECHO_CMD, "OR"],
                conditions=(or_condition,),
            ),
            px.TaskSpec(
                "not_test",
                cmd=[*ECHO_CMD, "NOT"],
                conditions=(not_condition,),
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["and_test"].status == px.TaskStatus.SUCCESS
    assert report.results["or_test"].status == px.TaskStatus.SUCCESS
    assert report.results["not_test"].status == px.TaskStatus.SUCCESS


def test_taskspec_with_cwd():
    """测试工作目录设置."""
    if sys.platform == "win32":
        ls_cmd = ["cmd", "/c", "dir"]
    else:
        ls_cmd = ["ls", "-la"]

    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "list_current",
                cmd=ls_cmd,
                cwd=Path.cwd(),
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert "list_current" in report.results
    assert report.results["list_current"].status == px.TaskStatus.SUCCESS


@pytest.mark.slow
def test_taskspec_with_timeout():
    """测试超时设置."""
    graph = px.Graph.from_specs(
        [
            # 短时间任务应该成功
            px.TaskSpec(
                "short_task",
                cmd=["python", "-c", "import time; time.sleep(0.1)"],
                timeout=1.0,
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert "short_task" in report.results
    assert report.results["short_task"].status == px.TaskStatus.SUCCESS


def test_taskspec_dependency_with_conditions():
    """测试依赖和条件的组合."""
    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "first",
                cmd=[*ECHO_CMD, "first"],
                conditions=(lambda: True,),
            ),
            px.TaskSpec(
                "second",
                cmd=[*ECHO_CMD, "second"],
                depends_on=("first",),
                conditions=(lambda: True,),
            ),
            px.TaskSpec(
                "third",
                cmd=[*ECHO_CMD, "third"],
                depends_on=("second",),
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["first"].status == px.TaskStatus.SUCCESS
    assert report.results["second"].status == px.TaskStatus.SUCCESS
    assert report.results["third"].status == px.TaskStatus.SUCCESS


def test_taskspec_mixed_fn_and_cmd():
    """测试混合使用 fn 和 cmd."""

    def my_function():
        return "result from function"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("fn_task", fn=my_function),
            px.TaskSpec("cmd_task", cmd=[*ECHO_CMD, "from command"]),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["fn_task"].status == px.TaskStatus.SUCCESS
    assert report.results["fn_task"].value == "result from function"
    assert report.results["cmd_task"].status == px.TaskStatus.SUCCESS


def test_taskspec_cmd_overrides_fn():
    """测试 cmd 参数优先于 fn 参数."""

    def my_function():
        return "should not run"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec(
                "cmd_priority",
                fn=my_function,
                cmd=[*ECHO_CMD, "cmd takes priority"],
            ),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["cmd_priority"].status == px.TaskStatus.SUCCESS
    # cmd 应该被执行，而不是 fn
    assert report.results["cmd_priority"].value is None


def test_taskspec_callable_cmd():
    """测试 cmd 参数使用可调用对象."""

    def my_callable():
        return "callable result"

    graph = px.Graph.from_specs(
        [
            px.TaskSpec("callable_cmd", cmd=my_callable),
        ]
    )

    report = px.run(graph, strategy="sequential")
    assert report.success
    assert report.results["callable_cmd"].status == px.TaskStatus.SUCCESS
    assert report.results["callable_cmd"].value == "callable result"


# ---------------------------------------------------------------------- #
# verbose 模式测试
# ---------------------------------------------------------------------- #
class TestTaskSpecVerbose:
    """测试 TaskSpec 的 verbose 字段."""

    def test_verbose_default_is_false(self) -> None:
        """verbose 默认应为 False."""
        spec: px.TaskSpec[Any] = px.TaskSpec[Any]("a", cmd=[*ECHO_CMD, "hi"])
        assert spec.verbose is False

    def test_verbose_true_prints_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose=True 时应打印执行的命令."""
        graph = px.Graph.from_specs([px.TaskSpec("echo", cmd=[*ECHO_CMD, "verbose-output"], verbose=True)])
        _ = px.run(graph, strategy="sequential")
        captured = capsys.readouterr()
        assert "执行命令" in captured.out
        assert "返回码" in captured.out

    def test_verbose_false_silent(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose=False 时不应打印命令信息."""
        graph = px.Graph.from_specs([px.TaskSpec[Any]("echo", cmd=[*ECHO_CMD, "silent"], verbose=False)])
        _ = px.run(graph, strategy="sequential")
        captured = capsys.readouterr()
        assert "执行命令" not in captured.out
        assert "返回码" not in captured.out

    def test_verbose_true_shell_cmd(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose=True 时 shell 命令也应打印执行信息."""
        if sys.platform == "win32":
            shell_cmd = 'cmd /c "echo shell-verbose"'
        else:
            shell_cmd = "echo 'shell-verbose'"

        graph = px.Graph.from_specs([px.TaskSpec("shell", cmd=shell_cmd, verbose=True)])
        _ = px.run(graph, strategy="sequential")
        captured = capsys.readouterr()
        assert "执行 Shell" in captured.out

    def test_verbose_prints_cwd(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose=True 且设置了 cwd 时应打印工作目录."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            graph = px.Graph.from_specs([px.TaskSpec[Any]("ls", cmd=ECHO_CMD, cwd=Path(tmpdir), verbose=True)])
            _ = px.run(graph, strategy="sequential")
            captured = capsys.readouterr()
            assert "工作目录" in captured.out

    def test_verbose_failure_includes_returncode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """verbose=True 时失败也应打印返回码."""
        from pyflowx.errors import TaskFailedError

        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "fail",
                    cmd=["python", "-c", "import sys; sys.exit(1)"],
                    verbose=True,
                )
            ]
        )
        with pytest.raises(TaskFailedError):
            _ = px.run(graph, strategy="sequential")
        captured = capsys.readouterr()
        assert "返回码" in captured.out


# ---------------------------------------------------------------------- #
# _wrap_cmd 错误路径测试
# ---------------------------------------------------------------------- #
class TestTaskSpecCmdErrors:
    """测试 _wrap_cmd 的错误处理路径."""

    def test_cmd_list_file_not_found(self) -> None:
        """命令不存在时应抛出 RuntimeError."""
        from pyflowx.errors import TaskFailedError

        graph = px.Graph.from_specs([px.TaskSpec("missing", cmd=["this-command-does-not-exist-xyz"])])
        with pytest.raises(TaskFailedError) as exc_info:
            _ = px.run(graph, strategy="sequential")
        # 错误信息应包含命令未找到
        assert "命令未找到" in str(exc_info.value.cause) or "not found" in str(exc_info.value.cause).lower()

    def test_cmd_list_failure_includes_stderr(self) -> None:
        """命令失败时错误信息应包含 stderr."""
        from pyflowx.errors import TaskFailedError

        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "fail",
                    cmd=[
                        "python",
                        "-c",
                        "import sys; sys.stderr.write('error-msg'); sys.exit(1)",
                    ],
                )
            ]
        )
        with pytest.raises(TaskFailedError) as exc_info:
            _ = px.run(graph, strategy="sequential")
        # 非 verbose 模式下, stderr 应包含在错误信息中
        assert "error-msg" in str(exc_info.value.cause)

    def test_cmd_string_file_not_found(self) -> None:
        """shell 命令不存在时应抛出 RuntimeError."""
        from pyflowx.errors import TaskFailedError

        graph = px.Graph.from_specs([px.TaskSpec("missing", cmd="this-command-does-not-exist-xyz-123")])
        with pytest.raises(TaskFailedError):
            _ = px.run(graph, strategy="sequential")

    def test_cmd_string_failure(self) -> None:
        """shell 命令失败时应抛出 RuntimeError."""
        from pyflowx.errors import TaskFailedError

        graph = px.Graph.from_specs([px.TaskSpec("fail", cmd='python -c "import sys; sys.exit(1)"')])
        with pytest.raises(TaskFailedError) as exc_info:
            _ = px.run(graph, strategy="sequential")
        assert "Shell 命令执行失败" in str(exc_info.value.cause)

    @pytest.mark.slow
    def test_cmd_timeout_raises(self) -> None:
        """命令超时应抛出 RuntimeError."""
        from pyflowx.errors import TaskFailedError

        graph = px.Graph.from_specs(
            [
                px.TaskSpec(
                    "slow",
                    cmd=["python", "-c", "import time; time.sleep(5)"],
                    timeout=0.1,
                )
            ]
        )
        with pytest.raises(TaskFailedError) as exc_info:
            _ = px.run(graph, strategy="sequential")
        assert "超时" in str(exc_info.value.cause)

    @pytest.mark.slow
    def test_cmd_string_timeout_raises(self) -> None:
        """shell 命令超时应抛出 RuntimeError."""
        from pyflowx.errors import TaskFailedError

        graph = px.Graph.from_specs([px.TaskSpec("slow", cmd='python -c "import time; time.sleep(5)"', timeout=0.1)])
        with pytest.raises(TaskFailedError) as exc_info:
            _ = px.run(graph, strategy="sequential")
        assert "超时" in str(exc_info.value.cause)

    def test_no_fn_no_cmd_raises(self) -> None:
        """没有 fn 和 cmd 时应抛出 ValueError."""
        with pytest.raises(ValueError, match="必须提供 fn 或 cmd"):
            _ = px.TaskSpec("empty")
