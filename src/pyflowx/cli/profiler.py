"""pxp —— PyFlowX 性能分析器.

分析包含 ``px`` 调用的 Python 脚本，生成工作流执行性能剖面报告。

工作原理
--------
1. 注入 hook：monkey-patch ``pyflowx.run`` / ``pyflowx.executors.run`` /
   ``pyflowx.runner.run``，捕获最后一次执行的 ``Graph`` 与 ``RunReport``。
2. 执行目标脚本：用 ``runpy.run_path`` 以 ``__main__`` 身份执行，
   捕获 ``SystemExit``（脚本可能调 ``sys.exit``）。
3. 生成报告：从捕获的 report + graph 构建 :class:`ProfileReport`，
   默认输出 HTML 并自动打开浏览器。

使用方式
--------
    # 分析 pymake.py，生成 HTML 报告并打开浏览器
    pxp pymake.py

    # 传递参数给被分析脚本（用 -- 分隔）
    pxp pymake.py -- t

    # 指定输出文件
    pxp pymake.py -o report.html

    # 不打开浏览器
    pxp pymake.py --no-browser

    # 输出纯文本报告
    pxp pymake.py -E text
"""

from __future__ import annotations

__all__ = ["main"]

import argparse
import runpy
import sys
import webbrowser
from pathlib import Path
from typing import Any

from .. import executors as _executors
from .. import runner as _runner
from ..profiling import ProfileReport
from ..report import RunReport


def _build_parser() -> argparse.ArgumentParser:
    """构建参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="pxp",
        description="PyFlowX 性能分析器：分析包含 px 调用的脚本，生成性能剖面报告。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  pxp pymake.py              # 分析并打开 HTML 报告\n"
            "  pxp pymake.py -- t         # 传递参数 t 给脚本\n"
            "  pxp pymake.py -E text      # 输出纯文本报告\n"
            "  pxp pymake.py -o out.html  # 指定输出文件\n"
        ),
    )
    _ = parser.add_argument(
        "--export",
        "-E",
        choices=["html", "text"],
        default="html",
        help="导出格式（默认: html）",
    )
    _ = parser.add_argument(
        "--no-browser",
        action="store_true",
        help="不自动打开浏览器（仅 HTML 格式有效）",
    )
    _ = parser.add_argument(
        "-o",
        "--output",
        help="输出文件路径（默认: <script>_profile.html）",
    )
    return parser


def _capture_px_run() -> dict[str, Any]:
    """注入 hook 捕获 px.run() 调用。

    返回一个字典，``run()`` 执行后填充 ``graph`` 与 ``report``。
    同时返回还原函数用于 finally 块。

    Note
    -----
    需同时 patch 三处引用：
    * ``pyflowx.executors.run`` —— 实际实现
    * ``pyflowx.runner.run`` —— ``CliRunner`` 直接 import 的引用
    * ``pyflowx.run`` —— 顶层包导出的引用（用户脚本常用 ``px.run()``）

    另外 patch ``RunReport.__init__`` 以捕获 ``run()`` 内部创建的 report 实例。
    这对于 ``run()`` 抛出 ``TaskFailedError`` 的场景至关重要：此时 ``run()``
    不会正常返回 report，但 report 对象已在内部创建并填充了已执行任务的结果。
    通过 ``capture_enabled`` 标志确保只在 ``patched_run`` 调用期间捕获。
    """
    captured: dict[str, Any] = {}
    original_exec_run = _executors.run
    original_runner_run = _runner.run
    # 惰性获取顶层 pyflowx.run 引用（避免循环导入）
    import pyflowx as px_mod

    original_px_run = px_mod.run
    original_report_init = RunReport.__init__
    capture_enabled = [False]

    def patched_report_init(self: RunReport, *args: Any, **kwargs: Any) -> None:
        original_report_init(self, *args, **kwargs)
        if capture_enabled[0]:
            captured["report"] = self

    RunReport.__init__ = patched_report_init  # type: ignore[assignment]

    def patched_run(graph: Any, *args: Any, **kwargs: Any) -> RunReport:
        captured["graph"] = graph
        capture_enabled[0] = True
        try:
            report = original_exec_run(graph, *args, **kwargs)
            # 正常返回时确保 captured["report"] 是返回的 report
            captured["report"] = report
            return report
        finally:
            capture_enabled[0] = False

    # patch 所有引用 run 的入口
    _executors.run = patched_run  # type: ignore[assignment]
    _runner.run = patched_run  # type: ignore[assignment]
    px_mod.run = patched_run  # type: ignore[assignment]

    def _restore() -> None:
        _executors.run = original_exec_run  # type: ignore[assignment]
        _runner.run = original_runner_run  # type: ignore[assignment]
        px_mod.run = original_px_run  # type: ignore[assignment]
        RunReport.__init__ = original_report_init  # type: ignore[assignment]

    captured["_restore"] = _restore
    return captured


def _run_target_script(script: Path, script_args: list[str]) -> dict[str, Any]:
    """执行目标脚本。

    将脚本所在目录加入 ``sys.path``，设置 ``sys.argv``，然后用
    ``runpy.run_path`` 以 ``__main__`` 身份执行。捕获 ``SystemExit``。

    Returns
    -------
    dict[str, Any]
        脚本模块的全局变量字典（含 ``main`` 等定义）。
    """
    sys.argv = [str(script), *script_args]
    script_dir = str(script.parent.resolve())
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    return runpy.run_path(str(script), run_name="__main__")


def _try_call_main(module_globals: dict[str, Any]) -> None:
    """若模块定义了 ``main`` 可调用对象，调用它。

    用于脚本无 ``if __name__ == "__main__"`` 块的场景（如通过 entry points
    注册的 CLI 工具脚本）。``main`` 通常调用 ``CliRunner.run_cli()``，
    后者读取 ``sys.argv[1:]`` 执行对应命令。
    """
    main_fn = module_globals.get("main")
    if callable(main_fn):
        main_fn()


def _output_report(
    profile: ProfileReport,
    export: str,
    output: str | None,
    script_stem: str,
    no_browser: bool,
) -> None:
    """输出性能报告。"""
    if export == "text":
        print(profile.describe())
        return

    # HTML 格式
    html = profile.to_html()
    if output:
        out_path = Path(output)
    else:
        out_path = Path.cwd() / f"{script_stem}_profile.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"HTML 报告已生成: {out_path}")

    if not no_browser:
        try:
            webbrowser.open(f"file://{out_path.resolve()}")
        except Exception as e:
            print(f"警告：无法打开浏览器: {e}", file=sys.stderr)


def main() -> None:
    """pxp CLI 入口。"""
    parser = _build_parser()
    pxp_args, remaining = parser.parse_known_args()

    if not remaining:
        parser.print_help()
        sys.exit(2)

    script_str = remaining[0]
    script_args = remaining[1:]
    script_path = Path(script_str).resolve()

    if not script_path.is_file():
        print(f"错误：脚本不存在: {script_path}", file=sys.stderr)
        sys.exit(2)

    # 注入 hook
    captured = _capture_px_run()

    # 执行目标脚本
    print(f"正在分析: {script_path}")
    if script_args:
        print(f"脚本参数: {script_args}")
    print("-" * 60)

    module_globals: dict[str, Any] = {}
    try:
        module_globals = _run_target_script(script_path, script_args)
    except SystemExit:
        # 脚本调用了 sys.exit，正常情况
        pass
    except Exception as e:
        print(f"警告：脚本执行抛出异常: {e}", file=sys.stderr)

    # 若脚本执行未捕获到 run()，尝试调用模块的 main() 函数
    # （适用于无 ``if __name__ == "__main__"`` 块的 CLI 脚本）
    if captured.get("report") is None and module_globals:
        try:
            _try_call_main(module_globals)
        except SystemExit:
            pass
        except Exception as e:
            print(f"警告：调用 main() 抛出异常: {e}", file=sys.stderr)

    # 还原 hook
    restore = captured.pop("_restore", None)
    if restore is not None:
        restore()

    # 检查是否捕获到 run() 调用
    report = captured.get("report")
    graph = captured.get("graph")
    if report is None or graph is None:
        print("错误：未捕获到 px.run() 调用，无法生成性能报告", file=sys.stderr)
        print("请确保脚本通过 px.run() 或 CliRunner 执行任务流图。", file=sys.stderr)
        sys.exit(1)

    # 生成报告
    profile = ProfileReport.from_report(report, graph)
    _output_report(
        profile,
        export=pxp_args.export,
        output=pxp_args.output,
        script_stem=script_path.stem,
        no_browser=pxp_args.no_browser,
    )


if __name__ == "__main__":
    main()
