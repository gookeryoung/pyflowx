"""pxp 性能分析器测试.

覆盖策略：
* HTML 渲染：to_html() 输出结构正确，含关键章节。
* pxp CLI：参数解析、脚本执行、报告生成、浏览器调用、错误处理。
* hook 注入：捕获 px.run() 调用，还原原始函数。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import pyflowx as px
from pyflowx.cli import profiler
from pyflowx.profiling import ProfileReport
from pyflowx.report import RunReport
from pyflowx.task import TaskResult, TaskSpec, TaskStatus


def _fn() -> int:
    return 1


def _spec(name: str, deps: tuple[str, ...] = ()) -> TaskSpec[Any]:
    return TaskSpec[Any](name, _fn, depends_on=deps)


def _result(
    name: str,
    start: datetime,
    duration: float,
    *,
    status: TaskStatus = TaskStatus.SUCCESS,
    attempts: int = 1,
) -> TaskResult[Any]:
    """构造带时间戳的 TaskResult."""
    end = start + timedelta(seconds=duration) if duration > 0 else start
    return TaskResult[Any](
        spec=_spec(name),
        status=status,
        value=None,
        attempts=attempts,
        started_at=start if duration > 0 or status != TaskStatus.SKIPPED else None,
        finished_at=end if duration > 0 or status != TaskStatus.SKIPPED else None,
    )


def _build_simple_profile() -> ProfileReport:
    """构造一个简单的 ProfileReport 用于测试 HTML 输出."""
    start = datetime(2024, 1, 1, 0, 0, 0)
    report = px.RunReport()
    report.results["a"] = _result("a", start, 1.0)
    report.results["b"] = _result("b", start + timedelta(seconds=1), 2.0)
    graph = px.Graph.from_specs([
        _spec("a"),
        _spec("b", deps=("a",)),
    ])
    return ProfileReport.from_report(report, graph)


class TestToHtml:
    """测试 ProfileReport.to_html()."""

    def test_to_html_contains_key_sections(self) -> None:
        """HTML 应包含所有关键章节标题。"""
        profile = _build_simple_profile()
        html = profile.to_html()

        assert "<!DOCTYPE html>" in html
        assert "PyFlowX 性能剖面报告" in html
        assert "图级指标" in html
        assert "关键路径" in html
        assert "任务时间线" in html
        assert "Top 瓶颈任务" in html
        assert "全部任务" in html

    def test_to_html_contains_metrics(self) -> None:
        """HTML 应包含图级指标数值。"""
        profile = _build_simple_profile()
        html = profile.to_html()

        # 总耗时 3.0s (a=1 + b=2)
        assert "3.000" in html
        # 任务名
        assert "a" in html
        assert "b" in html

    def test_to_html_contains_critical_path(self) -> None:
        """HTML 应包含关键路径任务链。"""
        profile = _build_simple_profile()
        html = profile.to_html()

        # 关键路径是 a -> b
        assert "<strong>a</strong>" in html
        assert "<strong>b</strong>" in html

    def test_to_html_contains_gantt_bars(self) -> None:
        """HTML 应包含甘特图条。"""
        profile = _build_simple_profile()
        html = profile.to_html()

        assert "gantt-row" in html
        assert "gantt-bar" in html
        # 每个非 SKIPPED 任务一个条
        assert html.count("gantt-bar") >= 2

    def test_to_html_empty_profile(self) -> None:
        """空报告的 HTML 应不崩溃。"""
        report = px.RunReport()
        graph = px.Graph()
        profile = ProfileReport.from_report(report, graph)
        html = profile.to_html()

        assert "PyFlowX 性能剖面报告" in html
        assert "(无)" in html

    def test_to_html_with_failed_task(self) -> None:
        """含 FAILED 任务的 HTML 应包含失败状态徽章。"""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0, status=TaskStatus.FAILED)
        graph = px.Graph.from_specs([_spec("a")])

        profile = ProfileReport.from_report(report, graph)
        html = profile.to_html()

        assert "failed" in html
        assert "badge" in html

    def test_to_html_with_skipped_task(self) -> None:
        """含 SKIPPED 任务的 HTML 不应在甘特图中显示该任务。"""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = TaskResult[Any](
            spec=_spec("b"),
            status=TaskStatus.SKIPPED,
            reason="skip",
        )
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)
        html = profile.to_html()

        # SKIPPED 任务的徽章应出现
        assert "skipped" in html

    def test_to_html_self_contained(self) -> None:
        """HTML 应自包含（无外部依赖）。"""
        profile = _build_simple_profile()
        html = profile.to_html()

        # 不引用外部资源
        assert "<link" not in html
        assert "<script src" not in html


class TestProfilerArgumentParsing:
    """测试 pxp CLI 参数解析。"""

    def test_default_export_is_html(self) -> None:
        """默认导出格式为 html。"""
        parser = profiler._build_parser()
        args, remaining = parser.parse_known_args(["pymake.py"])
        assert args.export == "html"
        assert args.no_browser is False
        assert args.output is None
        assert remaining == ["pymake.py"]

    def test_export_text(self) -> None:
        """-E text 应设置导出格式为 text。"""
        parser = profiler._build_parser()
        args, _ = parser.parse_known_args(["-E", "text", "pymake.py"])
        assert args.export == "text"

    def test_no_browser_flag(self) -> None:
        """--no-browser 应设置标志。"""
        parser = profiler._build_parser()
        args, _ = parser.parse_known_args(["--no-browser", "pymake.py"])
        assert args.no_browser is True

    def test_output_option(self) -> None:
        """-o 应设置输出路径。"""
        parser = profiler._build_parser()
        args, _ = parser.parse_known_args(["-o", "report.html", "pymake.py"])
        assert args.output == "report.html"

    def test_script_args_separated(self) -> None:
        """脚本参数应通过 remaining 分离。"""
        parser = profiler._build_parser()
        _, remaining = parser.parse_known_args(["pymake.py", "t", "--quiet"])
        assert remaining == ["pymake.py", "t", "--quiet"]

    def test_no_args_prints_help(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """无参数应打印帮助并以退出码 2 退出。"""
        monkeypatch.setattr(sys, "argv", ["pxp"])
        with pytest.raises(SystemExit) as exc_info:
            profiler.main()
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "usage" in captured.err.lower()


class TestCapturePxRun:
    """测试 _capture_px_run hook 注入。"""

    def test_capture_captures_run_call(self) -> None:
        """hook 应捕获 px.run() 调用的 graph 和 report。"""
        captured = profiler._capture_px_run()
        try:
            graph = px.Graph.from_specs([px.TaskSpec("a", lambda: 1)])
            px.run(graph, strategy="sequential")
            assert "graph" in captured
            assert "report" in captured
            assert captured["graph"] is graph
        finally:
            captured["_restore"]()

    def test_capture_restores_original(self) -> None:
        """还原后 px.run 和 RunReport.__init__ 应恢复为原函数。"""
        original_run = px.run
        original_init = RunReport.__init__
        captured = profiler._capture_px_run()
        # 注入期间 px.run 和 RunReport.__init__ 已被替换
        assert px.run is not original_run
        assert RunReport.__init__ is not original_init
        captured["_restore"]()
        # 还原后恢复
        assert px.run is original_run
        assert RunReport.__init__ is original_init

    def test_capture_via_runner_run(self) -> None:
        """hook 应捕获通过 CliRunner 执行的 run() 调用。"""
        from pyflowx import runner as runner_mod

        captured = profiler._capture_px_run()
        try:
            # 验证 runner.run 也被 patch（指向 patched_run）
            assert runner_mod.run is px.executors.run
            graph = px.Graph.from_specs([px.TaskSpec("a", lambda: 1)])
            runner_mod.run(graph, strategy="sequential")
            assert "report" in captured
        finally:
            captured["_restore"]()

    def test_capture_captures_report_on_failure(self) -> None:
        """run() 抛出 TaskFailedError 时仍应捕获 report 实例。"""
        from pyflowx.executors import TaskFailedError

        def failing() -> None:
            raise RuntimeError("boom")

        graph = px.Graph.from_specs([px.TaskSpec("a", failing)])
        captured = profiler._capture_px_run()
        try:
            with pytest.raises(TaskFailedError):
                px.run(graph, strategy="sequential")
            # 即使 run() 抛异常，report 也应被捕获（含已执行任务的结果）
            assert "report" in captured
            assert "graph" in captured
            assert captured["graph"] is graph
        finally:
            captured["_restore"]()


class TestRunTargetScript:
    """测试 _run_target_script。"""

    def test_run_simple_script(self, tmp_path: Path) -> None:
        """应能执行简单脚本并返回模块字典。"""
        script = tmp_path / "simple.py"
        script.write_text("x = 42\n", encoding="utf-8")

        result = profiler._run_target_script(script, [])
        assert result["x"] == 42

    def test_run_script_with_sys_exit(self, tmp_path: Path) -> None:
        """脚本调用 sys.exit 应抛 SystemExit。"""
        script = tmp_path / "exit.py"
        script.write_text("import sys; sys.exit(0)\n", encoding="utf-8")

        with pytest.raises(SystemExit):
            profiler._run_target_script(script, [])

    def test_run_script_sets_argv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """应正确设置 sys.argv。"""
        script = tmp_path / "argv.py"
        script.write_text(
            "import sys\nassert sys.argv[0] == __file__\nassert sys.argv[1:] == ['arg1', 'arg2']\n",
            encoding="utf-8",
        )
        profiler._run_target_script(script, ["arg1", "arg2"])

    def test_run_script_adds_dir_to_path(self, tmp_path: Path) -> None:
        """脚本所在目录应加入 sys.path。"""
        script = tmp_path / "pathcheck.py"
        script.write_text(
            "import sys, os\nassert os.path.dirname(__file__) in sys.path\n",
            encoding="utf-8",
        )
        profiler._run_target_script(script, [])


class TestOutputReport:
    """测试 _output_report。"""

    def test_output_text_format(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """text 格式应打印 describe() 到 stdout。"""
        profile = _build_simple_profile()
        profiler._output_report(profile, export="text", output=None, script_stem="test", no_browser=True)
        captured = capsys.readouterr()
        assert "PyFlowX 性能剖面报告" in captured.out
        assert "图级指标" in captured.out

    def test_output_html_default_filename(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTML 默认输出到 <script>_profile.html。"""
        monkeypatch.chdir(tmp_path)
        profile = _build_simple_profile()
        profiler._output_report(profile, export="html", output=None, script_stem="mymake", no_browser=True)

        out_file = tmp_path / "mymake_profile.html"
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "PyFlowX 性能剖面报告" in content

    def test_output_html_custom_path(self, tmp_path: Path) -> None:
        """HTML 应写入指定路径。"""
        out_file = tmp_path / "custom.html"
        profile = _build_simple_profile()
        profiler._output_report(profile, export="html", output=str(out_file), script_stem="test", no_browser=True)
        assert out_file.exists()
        assert "PyFlowX" in out_file.read_text(encoding="utf-8")

    def test_output_html_opens_browser(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """no_browser=False 应调用 webbrowser.open。"""
        monkeypatch.chdir(tmp_path)
        opened: list[str] = []
        monkeypatch.setattr(profiler.webbrowser, "open", opened.append)

        profile = _build_simple_profile()
        profiler._output_report(profile, export="html", output=None, script_stem="test", no_browser=False)

        assert len(opened) == 1
        assert opened[0].startswith("file://")

    def test_output_html_no_browser_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """no_browser=True 不应调用 webbrowser.open。"""
        monkeypatch.chdir(tmp_path)
        opened: list[str] = []
        monkeypatch.setattr(profiler.webbrowser, "open", opened.append)

        profile = _build_simple_profile()
        profiler._output_report(profile, export="html", output=None, script_stem="test", no_browser=True)

        assert len(opened) == 0


class TestProfilerMainIntegration:
    """main() 集成测试。"""

    def test_main_analyses_script_with_px_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() 应分析含 px.run() 的脚本并生成 HTML。"""
        script = tmp_path / "mytool.py"
        script.write_text(
            "import pyflowx as px\n"
            "graph = px.Graph.from_specs([\n"
            "    px.TaskSpec('a', lambda: 1),\n"
            "    px.TaskSpec('b', lambda: 2, depends_on=('a',)),\n"
            "])\n"
            "px.run(graph, strategy='sequential')\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "report.html"
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", "-o", str(out_file), str(script)])

        profiler.main()

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "PyFlowX 性能剖面报告" in content
        assert "任务时间线" in content

    def test_main_analyses_script_with_clirunner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() 应分析含 CliRunner 的脚本。"""
        script = tmp_path / "clirunner_tool.py"
        script.write_text(
            "import pyflowx as px\n"
            "runner = px.CliRunner(\n"
            "    aliases={'t': px.TaskSpec('t', lambda: 1)},\n"
            ")\n"
            "runner.run_cli(['t'])\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "report.html"
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", "-o", str(out_file), str(script)])

        profiler.main()

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "PyFlowX 性能剖面报告" in content

    def test_main_text_export(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main() -E text 应输出文本到 stdout。"""
        script = tmp_path / "simple.py"
        script.write_text(
            "import pyflowx as px\n"
            "graph = px.Graph.from_specs([px.TaskSpec('a', lambda: 1)])\n"
            "px.run(graph, strategy='sequential')\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(sys, "argv", ["pxp", "-E", "text", "--no-browser", str(script)])

        profiler.main()
        captured = capsys.readouterr()
        assert "PyFlowX 性能剖面报告" in captured.out

    def test_main_script_not_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """脚本不存在应以退出码 2 退出。"""
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", str(tmp_path / "nonexistent.py")])
        with pytest.raises(SystemExit) as exc_info:
            profiler.main()
        assert exc_info.value.code == 2

    def test_main_no_px_run_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """脚本未调用 px.run() 应以退出码 1 退出。"""
        script = tmp_path / "no_run.py"
        script.write_text("print('just printing')\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", str(script)])
        with pytest.raises(SystemExit) as exc_info:
            profiler.main()
        assert exc_info.value.code == 1

    def test_main_passes_script_args(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """应将脚本参数传递给目标脚本。"""
        script = tmp_path / "argcheck.py"
        script.write_text(
            "import sys\n"
            "assert sys.argv[1:] == ['myarg'], f'got {sys.argv[1:]}'\n"
            "import pyflowx as px\n"
            "px.run(px.Graph.from_specs([px.TaskSpec('a', lambda: 1)]), strategy='sequential')\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "report.html"
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", "-o", str(out_file), str(script), "myarg"])

        profiler.main()  # 不抛异常即成功

    def test_main_handles_script_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """脚本抛异常时应捕获并继续生成报告（如果有 report）。"""
        script = tmp_path / "raise.py"
        script.write_text(
            "import pyflowx as px\n"
            "px.run(px.Graph.from_specs([px.TaskSpec('a', lambda: 1)]), strategy='sequential')\n"
            "raise RuntimeError('after run')\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "report.html"
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", "-o", str(out_file), str(script)])

        profiler.main()  # 不抛异常即成功
        assert out_file.exists()

    def test_main_auto_calls_main_when_no_main_block(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """脚本无 __main__ 块但定义了 main() 时应自动调用。"""
        script = tmp_path / "no_main_block.py"
        script.write_text(
            "import pyflowx as px\n"
            "def main():\n"
            "    px.run(px.Graph.from_specs([px.TaskSpec('a', lambda: 1)]), strategy='sequential')\n"
            "# 无 if __name__ == '__main__' 块\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "report.html"
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", "-o", str(out_file), str(script)])

        profiler.main()
        assert out_file.exists()

    def test_main_auto_calls_main_with_clirunner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """脚本无 __main__ 块但定义了调用 CliRunner 的 main() 时应自动调用。"""
        script = tmp_path / "cli_tool.py"
        script.write_text(
            "import pyflowx as px\n"
            "def main():\n"
            "    runner = px.CliRunner(\n"
            "        aliases={'t': px.TaskSpec('t', lambda: 1)},\n"
            "    )\n"
            "    runner.run_cli(['t'])\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "report.html"
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", "-o", str(out_file), str(script), "t"])

        profiler.main()
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "PyFlowX 性能剖面报告" in content

    def test_main_no_main_function_exits_with_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """脚本无 main() 且未调用 px.run() 应以退出码 1 退出。"""
        script = tmp_path / "no_main.py"
        script.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["pxp", "--no-browser", str(script)])
        with pytest.raises(SystemExit) as exc_info:
            profiler.main()
        assert exc_info.value.code == 1


class TestTryCallMain:
    """测试 _try_call_main。"""

    def test_calls_main_when_present(self) -> None:
        """模块字典含 main 可调用对象时应调用它。"""
        called: list[bool] = []

        def fake_main() -> None:
            called.append(True)

        profiler._try_call_main({"main": fake_main})
        assert called == [True]

    def test_no_main_does_nothing(self) -> None:
        """模块字典不含 main 时不应报错。"""
        profiler._try_call_main({})  # 不抛异常即成功

    def test_non_callable_main_does_nothing(self) -> None:
        """main 不是可调用对象时不应报错。"""
        profiler._try_call_main({"main": "not a function"})  # 不抛异常即成功
