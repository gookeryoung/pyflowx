"""性能剖面（ProfileReport）测试.

覆盖策略：
* 构造带时间戳的 RunReport + Graph，验证关键路径、并行度、瓶颈排序。
* 边界场景：空报告、单任务、无时间戳、SKIPPED 任务、图校验失败。
* 输出格式：to_dict / describe / top_bottlenecks / critical_tasks。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pyflowx as px
from pyflowx.profiling import ProfileReport, TaskProfile
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


def _skipped_result(name: str, reason: str = "skip") -> TaskResult[Any]:
    """构造 SKIPPED 结果（无时间戳）."""
    return TaskResult[Any](
        spec=_spec(name),
        status=TaskStatus.SKIPPED,
        reason=reason,
    )


class TestProfileReportConstruction:
    """测试 ProfileReport 构建."""

    def test_empty_report(self) -> None:
        """空报告应产生空剖面."""
        report = px.RunReport()
        graph = px.Graph()
        profile = ProfileReport.from_report(report, graph)
        assert len(profile.tasks) == 0
        assert profile.total_duration == 0.0
        assert profile.critical_path == ()
        assert profile.critical_path_duration == 0.0
        assert profile.avg_parallelism == 0.0
        assert profile.peak_parallelism == 0

    def test_single_task(self) -> None:
        """单任务：关键路径就是它自己，并行度为 1."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.5)
        graph = px.Graph.from_specs([_spec("a")])

        profile = ProfileReport.from_report(report, graph)

        assert len(profile.tasks) == 1
        assert profile.tasks[0].name == "a"
        assert profile.tasks[0].duration == 1.5
        assert profile.tasks[0].is_on_critical_path
        assert profile.total_duration == 1.5
        assert profile.critical_path == ("a",)
        assert profile.critical_path_duration == 1.5
        assert profile.avg_parallelism == 1.0
        assert profile.peak_parallelism == 1
        assert profile.parallelism_efficiency == 1.0

    def test_serial_chain(self) -> None:
        """串行链 a -> b -> c：关键路径为全部，效率 100%."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start + timedelta(seconds=1), 2.0)
        report.results["c"] = _result("c", start + timedelta(seconds=3), 1.5)
        graph = px.Graph.from_specs([
            _spec("a"),
            _spec("b", deps=("a",)),
            _spec("c", deps=("b",)),
        ])

        profile = ProfileReport.from_report(report, graph)

        assert profile.total_duration == 4.5
        assert profile.critical_path_duration == 4.5
        assert profile.critical_path == ("a", "b", "c")
        assert profile.parallelism_efficiency == 1.0
        assert profile.peak_parallelism == 1
        assert profile.avg_parallelism == 1.0

    def test_parallel_tasks(self) -> None:
        """并行任务 a, b 同时执行：关键路径取较长者，效率 < 1."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start, 2.0)
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)

        # wall-clock = 2.0, 关键路径 = 2.0 (b), 效率 = 1.0
        # 因为关键路径定义就是最长路径，与 wall-clock 相同
        assert profile.total_duration == 2.0
        assert profile.critical_path_duration == 2.0
        assert profile.critical_path == ("b",)
        assert profile.peak_parallelism == 2
        # 平均并行度 = (1.0 + 2.0) / 2.0 = 1.5
        assert profile.avg_parallelism == 1.5

    def test_parallel_with_join(self) -> None:
        """a, b 并行后 join 到 c：关键路径 a->c 或 b->c."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start, 3.0)
        report.results["c"] = _result("c", start + timedelta(seconds=3), 1.0)
        graph = px.Graph.from_specs([
            _spec("a"),
            _spec("b"),
            _spec("c", deps=("a", "b")),
        ])

        profile = ProfileReport.from_report(report, graph)

        # 关键路径 = b -> c (3 + 1 = 4)
        assert profile.critical_path_duration == 4.0
        assert profile.critical_path == ("b", "c")
        assert profile.tasks[0].is_on_critical_path is False  # a 不在关键路径
        # task("b") 在关键路径上
        assert profile.task("b").is_on_critical_path
        assert profile.task("c").is_on_critical_path

    def test_skipped_task_no_timestamp(self) -> None:
        """SKIPPED 任务无时间戳：不影响并行度计算."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _skipped_result("b")
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)

        # b 是 SKIPPED，duration=0
        assert profile.task("b").status == TaskStatus.SKIPPED
        assert profile.task("b").duration == 0.0
        assert profile.peak_parallelism == 1  # 只有 a 在跑


class TestWaitTime:
    """测试等待时间计算."""

    def test_no_deps_zero_wait(self) -> None:
        """无依赖任务等待时间为 0."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        graph = px.Graph.from_specs([_spec("a")])

        profile = ProfileReport.from_report(report, graph)

        assert profile.task("a").wait_time == 0.0

    def test_wait_after_dep_completes(self) -> None:
        """b 在 a 完成后等待 0.5s 才开始."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start + timedelta(seconds=1.5), 1.0)
        graph = px.Graph.from_specs([
            _spec("a"),
            _spec("b", deps=("a",)),
        ])

        profile = ProfileReport.from_report(report, graph)

        assert profile.task("b").wait_time == 0.5

    def test_wait_negative_clamped_to_zero(self) -> None:
        """b 在 a 完成前就开始（异常情况）应钳制为 0."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 2.0)
        # b 在 a 还没完成时就开始（不应该但可能发生）
        report.results["b"] = _result("b", start + timedelta(seconds=1), 1.0)
        graph = px.Graph.from_specs([
            _spec("a"),
            _spec("b", deps=("a",)),
        ])

        profile = ProfileReport.from_report(report, graph)

        # a 在 t=2 结束，b 在 t=1 开始，delta = -1，钳制为 0
        assert profile.task("b").wait_time == 0.0

    def test_skipped_task_zero_wait(self) -> None:
        """SKIPPED 任务等待时间为 0."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _skipped_result("b")
        graph = px.Graph.from_specs([
            _spec("a"),
            _spec("b", deps=("a",)),
        ])

        profile = ProfileReport.from_report(report, graph)

        assert profile.task("b").wait_time == 0.0


class TestCriticalPath:
    """测试关键路径分析."""

    def test_diamond_dependency(self) -> None:
        """菱形依赖：a -> b -> d, a -> c -> d，关键路径取较长分支."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start + timedelta(seconds=1), 3.0)
        report.results["c"] = _result("c", start + timedelta(seconds=1), 1.0)
        report.results["d"] = _result("d", start + timedelta(seconds=4), 1.0)
        graph = px.Graph.from_specs([
            _spec("a"),
            _spec("b", deps=("a",)),
            _spec("c", deps=("a",)),
            _spec("d", deps=("b", "c")),
        ])

        profile = ProfileReport.from_report(report, graph)

        # 关键路径：a -> b -> d = 1 + 3 + 1 = 5
        assert profile.critical_path_duration == 5.0
        assert profile.critical_path == ("a", "b", "d")

    def test_graph_validation_failure_returns_empty(self) -> None:
        """图校验失败（有环）应回退为空关键路径."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        # 手动构造带环的图（绕过校验）
        graph = px.Graph()
        graph.specs["a"] = _spec("a", deps=("b",))
        graph.specs["b"] = _spec("b", deps=("a",))
        graph.deps["a"] = ("b",)
        graph.deps["b"] = ("a",)

        profile = ProfileReport.from_report(report, graph)

        # layers() 抛 CycleError，回退为空
        assert profile.critical_path == ()
        assert profile.critical_path_duration == 0.0


class TestParallelism:
    """测试并行度计算."""

    def test_no_timestamps_zero_parallelism(self) -> None:
        """所有任务无时间戳：并行度为 0."""
        report = px.RunReport()
        report.results["a"] = TaskResult[Any](spec=_spec("a"), status=TaskStatus.SUCCESS)
        graph = px.Graph.from_specs([_spec("a")])

        profile = ProfileReport.from_report(report, graph)

        assert profile.avg_parallelism == 0.0
        assert profile.peak_parallelism == 0

    def test_zero_duration_excluded(self) -> None:
        """零耗时任务（end <= start）不参与并行度计算."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 0.0)  # 零耗时
        report.results["b"] = _result("b", start, 1.0)
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)

        # 只有 b 参与，峰值 = 1
        assert profile.peak_parallelism == 1

    def test_skipped_with_timestamps_excluded(self) -> None:
        """SKIPPED 任务即使带时间戳也不参与并行度计算."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        # SKIPPED 但带时间戳（异常但可能发生）
        report.results["a"] = _result("a", start, 1.0, status=TaskStatus.SKIPPED)
        report.results["b"] = _result("b", start, 1.0)
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)

        # a 是 SKIPPED，被排除；只有 b 参与
        assert profile.peak_parallelism == 1

    def test_peak_parallelism_three_tasks(self) -> None:
        """三个任务完全重叠：峰值并行度 = 3."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 3.0)
        report.results["b"] = _result("b", start, 3.0)
        report.results["c"] = _result("c", start, 3.0)
        graph = px.Graph.from_specs([_spec("a"), _spec("b"), _spec("c")])

        profile = ProfileReport.from_report(report, graph)

        assert profile.peak_parallelism == 3
        assert profile.avg_parallelism == 3.0


class TestQueries:
    """测试查询方法."""

    def test_task_lookup(self) -> None:
        """task(name) 应返回对应剖面."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start, 2.0)
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)

        assert profile.task("a").name == "a"
        assert profile.task("b").duration == 2.0

    def test_task_lookup_not_found(self) -> None:
        """task(name) 不存在应抛 KeyError."""
        report = px.RunReport()
        graph = px.Graph()
        profile = ProfileReport.from_report(report, graph)
        try:
            profile.task("missing")
        except KeyError:
            pass
        else:
            raise AssertionError("应抛出 KeyError")

    def test_top_bottlenecks(self) -> None:
        """top_bottlenecks 应按耗时降序返回."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start, 3.0)
        report.results["c"] = _result("c", start, 2.0)
        graph = px.Graph.from_specs([_spec("a"), _spec("b"), _spec("c")])

        profile = ProfileReport.from_report(report, graph)

        top3 = profile.top_bottlenecks(3)
        assert len(top3) == 3
        assert top3[0].name == "b"
        assert top3[1].name == "c"
        assert top3[2].name == "a"

    def test_top_bottlenecks_zero_or_negative(self) -> None:
        """n <= 0 应返回空元组."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        graph = px.Graph.from_specs([_spec("a")])
        profile = ProfileReport.from_report(report, graph)

        assert profile.top_bottlenecks(0) == ()
        assert profile.top_bottlenecks(-1) == ()

    def test_critical_tasks(self) -> None:
        """critical_tasks 应返回关键路径上的任务（按路径顺序）."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _result("b", start + timedelta(seconds=1), 3.0)
        report.results["c"] = _result("c", start + timedelta(seconds=1), 1.0)
        report.results["d"] = _result("d", start + timedelta(seconds=4), 1.0)
        graph = px.Graph.from_specs([
            _spec("a"),
            _spec("b", deps=("a",)),
            _spec("c", deps=("a",)),
            _spec("d", deps=("b", "c")),
        ])

        profile = ProfileReport.from_report(report, graph)

        # 关键路径 a -> b -> d
        critical = profile.critical_tasks()
        assert len(critical) == 3
        assert [t.name for t in critical] == ["a", "b", "d"]

    def test_failed_tasks(self) -> None:
        """failed_tasks 应返回 FAILED 状态的任务."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0, status=TaskStatus.FAILED)
        report.results["b"] = _result("b", start, 1.0)
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)

        failed = profile.failed_tasks()
        assert len(failed) == 1
        assert failed[0].name == "a"

    def test_skipped_tasks(self) -> None:
        """skipped_tasks 应返回 SKIPPED 状态的任务."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        report.results["b"] = _skipped_result("b")
        graph = px.Graph.from_specs([_spec("a"), _spec("b")])

        profile = ProfileReport.from_report(report, graph)

        skipped = profile.skipped_tasks()
        assert len(skipped) == 1
        assert skipped[0].name == "b"


class TestOutputFormats:
    """测试输出格式."""

    def test_to_dict_structure(self) -> None:
        """to_dict 应返回包含所有字段的字典."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.5)
        graph = px.Graph.from_specs([_spec("a")])

        profile = ProfileReport.from_report(report, graph)
        d = profile.to_dict()

        assert "tasks" in d
        assert "total_duration_seconds" in d
        assert "critical_path_duration_seconds" in d
        assert "critical_path" in d
        assert "avg_parallelism" in d
        assert "peak_parallelism" in d
        assert "parallelism_efficiency" in d
        assert "bottlenecks" in d
        assert len(d["tasks"]) == 1
        assert d["tasks"][0]["name"] == "a"
        assert d["tasks"][0]["status"] == "success"
        assert d["tasks"][0]["duration_seconds"] == 1.5
        assert d["tasks"][0]["is_on_critical_path"] is True

    def test_describe_contains_key_sections(self) -> None:
        """describe 应包含关键章节标题."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        graph = px.Graph.from_specs([_spec("a")])

        profile = ProfileReport.from_report(report, graph)
        text = profile.describe()

        assert "PyFlowX 性能剖面报告" in text
        assert "【图级指标】" in text
        assert "【关键路径】" in text
        assert "【Top" in text
        assert "【全部任务】" in text
        assert "a" in text

    def test_describe_empty_report(self) -> None:
        """空报告的 describe 应不崩溃且包含章节标题."""
        report = px.RunReport()
        graph = px.Graph()
        profile = ProfileReport.from_report(report, graph)
        text = profile.describe()

        assert "【图级指标】" in text
        assert "(无)" in text

    def test_repr(self) -> None:
        """__repr__ 应包含关键指标."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        report = px.RunReport()
        report.results["a"] = _result("a", start, 1.0)
        graph = px.Graph.from_specs([_spec("a")])

        profile = ProfileReport.from_report(report, graph)
        r = repr(profile)

        assert "ProfileReport" in r
        assert "tasks=1" in r
        assert "total=1.000s" in r

    def test_task_profile_to_dict(self) -> None:
        """TaskProfile.to_dict 应返回正确字段."""
        tp = TaskProfile(
            name="x",
            status=TaskStatus.SUCCESS,
            duration=1.5,
            attempts=2,
            wait_time=0.3,
            is_on_critical_path=True,
            deps=("a", "b"),
        )
        d = tp.to_dict()

        assert d["name"] == "x"
        assert d["status"] == "success"
        assert d["duration_seconds"] == 1.5
        assert d["attempts"] == 2
        assert d["wait_time_seconds"] == 0.3
        assert d["is_on_critical_path"] is True
        assert d["deps"] == ["a", "b"]


class TestIntegrationWithRun:
    """与真实 run() 集成测试."""

    def test_profile_from_real_run(self) -> None:
        """从真实 run() 结果构建剖面."""
        graph = px.Graph.from_specs([
            px.TaskSpec("a", lambda: 1),
            px.TaskSpec("b", lambda: 2, depends_on=("a",)),
            px.TaskSpec("c", lambda: 3, depends_on=("a",)),
        ])
        report = px.run(graph, strategy="sequential")

        profile = ProfileReport.from_report(report, graph)

        assert len(profile.tasks) == 3
        assert profile.critical_path_duration > 0
        # sequential 策略下并行度应为 1
        assert profile.peak_parallelism == 1

    def test_profile_from_thread_run(self) -> None:
        """从 thread 策略 run() 结果构建剖面，验证并行度 > 1."""
        import time

        def slow() -> int:
            time.sleep(0.05)
            return 1

        graph = px.Graph.from_specs([
            px.TaskSpec("a", slow),
            px.TaskSpec("b", slow),
            px.TaskSpec("c", slow),
        ])
        report = px.run(graph, strategy="thread", max_workers=3)

        profile = ProfileReport.from_report(report, graph)

        # 三个任务并行，峰值应 >= 2（可能因调度时机不到 3）
        assert profile.peak_parallelism >= 2
        assert profile.critical_path_duration > 0
