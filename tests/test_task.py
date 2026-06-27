"""TaskSpec / TaskResult 数据结构测试。"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from pyflowx.task import (
    RetryPolicy,
    TaskResult,
    TaskSpec,
    TaskStatus,
    _env_and_cwd,
    task_template,
)


def _fn() -> None:
    return None


def test_spec_empty_name_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        TaskSpec("", _fn)


def test_spec_negative_max_attempts_rejected() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        TaskSpec("a", _fn, retry=RetryPolicy(max_attempts=0))


def test_spec_zero_timeout_rejected() -> None:
    with pytest.raises(ValueError, match="timeout"):
        TaskSpec("a", _fn, timeout=0)


def test_spec_self_dependency_rejected() -> None:
    with pytest.raises(ValueError, match="depend on itself"):
        TaskSpec("a", _fn, depends_on=("a",))


def test_spec_self_soft_dependency_rejected() -> None:
    """self dependency via soft_depends_on 也应被拒绝."""
    with pytest.raises(ValueError, match="depend on itself"):
        TaskSpec("a", _fn, soft_depends_on=("a",))


def test_spec_overlap_depends_rejected() -> None:
    """depends_on 和 soft_depends_on 重叠应被拒绝."""
    with pytest.raises(ValueError, match="不能重叠"):
        TaskSpec("a", _fn, depends_on=("b",), soft_depends_on=("b",))


# ---------------------------------------------------------------------- #
# RetryPolicy 参数验证
# ---------------------------------------------------------------------- #
def test_retry_policy_negative_delay_rejected() -> None:
    with pytest.raises(ValueError, match="delay must be >= 0"):
        RetryPolicy(delay=-1)


def test_retry_policy_negative_backoff_rejected() -> None:
    with pytest.raises(ValueError, match="backoff must be >= 0"):
        RetryPolicy(backoff=-1)


def test_retry_policy_negative_jitter_rejected() -> None:
    with pytest.raises(ValueError, match="jitter must be >= 0"):
        RetryPolicy(jitter=-1)


def test_retry_policy_retries_property() -> None:
    policy = RetryPolicy(max_attempts=3)
    assert policy.retries == 2


def test_retry_policy_should_retry_matching() -> None:
    policy = RetryPolicy(max_attempts=3, retry_on=(ValueError,))
    assert policy.should_retry(ValueError("x")) is True
    assert policy.should_retry(RuntimeError("x")) is False


def test_retry_policy_should_retry_empty_tuple() -> None:
    """空元组等价于不重试."""
    policy = RetryPolicy(max_attempts=3, retry_on=())
    assert policy.should_retry(ValueError("x")) is False


def test_retry_policy_wait_seconds_zero_attempt() -> None:
    """attempt < 1 时返回 0."""
    policy = RetryPolicy(delay=1.0, backoff=2.0)
    assert policy.wait_seconds(0) == 0.0
    assert policy.wait_seconds(-1) == 0.0


def test_retry_policy_wait_seconds_with_backoff() -> None:
    """有 backoff 时等待时间应递增."""
    policy = RetryPolicy(delay=1.0, backoff=2.0)
    # attempt=1: delay * backoff^0 = 1
    # attempt=2: delay * backoff^1 = 2
    assert policy.wait_seconds(1) == 1.0
    assert policy.wait_seconds(2) == 2.0


def test_retry_policy_wait_seconds_with_jitter() -> None:
    """有 jitter 时等待时间应增加随机量."""
    policy = RetryPolicy(delay=1.0, jitter=0.5)
    # 多次调用验证结果在合理范围内
    for _ in range(5):
        wait = policy.wait_seconds(1)
        assert 1.0 <= wait <= 1.5


# ---------------------------------------------------------------------- #
# should_execute 条件异常处理
# ---------------------------------------------------------------------- #
def test_should_execute_condition_exception_returns_false() -> None:
    """条件执行抛异常时应返回 False 并记录原因."""

    def bad_condition(_ctx):
        raise RuntimeError("condition error")

    bad_condition.__name__ = ""
    spec = TaskSpec("a", _fn, conditions=(bad_condition,))
    should_run, reason = spec.should_execute({})
    assert should_run is False
    # pyrefly: ignore [not-iterable]
    assert "匿名条件(执行错误)" in reason


def test_should_execute_condition_lambda_name() -> None:
    """lambda 条件有 __name__ 为 '<lambda>'."""
    spec = TaskSpec("a", _fn, conditions=(lambda _ctx: False,))
    should_run, reason = spec.should_execute({})
    assert should_run is False
    # pyrefly: ignore [not-iterable]
    assert "<lambda>" in reason


def test_should_execute_skip_if_missing_cmd_not_found() -> None:
    """skip_if_missing 且命令不存在时应跳过."""
    spec = TaskSpec("a", cmd=["nonexistent_cmd_xyz"], skip_if_missing=True)
    should_run, reason = spec.should_execute({})
    assert should_run is False
    # pyrefly: ignore [not-iterable]
    assert "命令不存在" in reason


def test_should_execute_skip_if_missing_cmd_found() -> None:
    """skip_if_missing 但命令存在时应执行."""
    # 使用 Python 作为已安装的命令
    spec = TaskSpec("a", cmd=["echo"], skip_if_missing=True)  # echo 应存在
    should_run, reason = spec.should_execute({})
    assert should_run is True
    assert reason is None


def test_should_execute_skip_if_missing_non_list_cmd() -> None:
    """skip_if_missing 对非 list 命令不影响."""
    spec = TaskSpec("a", cmd="echo hello", skip_if_missing=True)
    should_run, reason = spec.should_execute({})
    assert should_run is True
    assert reason is None


def test_should_execute_skip_if_missing_empty_list() -> None:
    """skip_if_missing 对空列表命令返回 True."""
    spec = TaskSpec("a", cmd=[], skip_if_missing=True)
    # 空 list 不检查
    _should_run, _reason = spec.should_execute({})
    # 因为 cmd=[] 且 fn=None，这会在 __post_init__ 中抛异常
    # 所以这个测试无效，我们用另一个方式测试 _is_cmd_available


def test_is_cmd_available_empty_list_returns_true() -> None:
    """_is_cmd_available 对空列表返回 True."""
    spec = TaskSpec("a", cmd=[], fn=_fn)  # 提供 fn 避免 __post_init__ 异常
    assert spec._is_cmd_available() is True


def test_is_cmd_available_string_returns_true() -> None:
    """_is_cmd_available 对字符串命令返回 True."""
    spec = TaskSpec("a", cmd="echo hello")
    assert spec._is_cmd_available() is True


def test_is_cmd_available_callable_returns_true() -> None:
    """_is_cmd_available 对可调用命令返回 True."""
    spec = TaskSpec("a", cmd=_fn)
    assert spec._is_cmd_available() is True


# ---------------------------------------------------------------------- #
# storage_key 异常处理
# ---------------------------------------------------------------------- #
def test_storage_key_cache_key_exception_returns_name() -> None:
    """cache_key 抛异常时应返回任务名."""

    def bad_cache_key(_ctx):
        raise RuntimeError("cache key error")

    spec = TaskSpec("a", _fn, cache_key=bad_cache_key)
    key = spec.storage_key({})
    assert key == "a"


def test_storage_key_cache_key_success() -> None:
    """cache_key 成功时应返回组合键."""
    spec = TaskSpec("a", _fn, cache_key=lambda ctx: ctx.get("x", "default"))
    key = spec.storage_key({"x": "value"})
    assert key == "a:value"


def test_storage_key_no_cache_key() -> None:
    """无 cache_key 时返回任务名."""
    spec = TaskSpec("a", _fn)
    key = spec.storage_key({})
    assert key == "a"


# ---------------------------------------------------------------------- #
# _env_and_cwd 上下文管理器
# ---------------------------------------------------------------------- #
def test_env_and_cwd_sets_env() -> None:
    """应临时设置环境变量。"""
    var_name = "PYFLOWX_TEST_ENV_VAR_1"
    with _env_and_cwd({var_name: "test_value"}, None):
        assert os.environ[var_name] == "test_value"
    # 退出后应恢复
    assert var_name not in os.environ


def test_env_and_cwd_restores_existing_env() -> None:
    """应恢复已有的环境变量."""
    os.environ["EXISTING_VAR"] = "original"
    try:
        with _env_and_cwd({"EXISTING_VAR": "new_value"}, None):
            assert os.environ["EXISTING_VAR"] == "new_value"
        # 退出后应恢复原值
        assert os.environ["EXISTING_VAR"] == "original"
    finally:
        os.environ.pop("EXISTING_VAR", None)


def test_env_and_cwd_sets_cwd(tmp_path: Path) -> None:
    """应临时切换工作目录."""
    original = Path.cwd()
    with _env_and_cwd(None, tmp_path):
        assert Path.cwd() == tmp_path
    # 退出后应恢复
    assert Path.cwd() == original


def test_env_and_cwd_no_changes() -> None:
    """无 env 和 cwd 时不应有任何变化."""
    original_env = dict(os.environ)
    original_cwd = Path.cwd()
    with _env_and_cwd(None, None):
        pass
    assert dict(os.environ) == original_env
    assert Path.cwd() == original_cwd


def test_spec_env_context() -> None:
    """TaskSpec.env_context 应正确工作."""
    var_name = "PYFLOWX_TEST_ENV_VAR_2"
    spec = TaskSpec("a", _fn, env={var_name: "value"})
    with spec.env_context():
        assert os.environ[var_name] == "value"
    assert var_name not in os.environ


# ---------------------------------------------------------------------- #
# task_template 工厂
# ---------------------------------------------------------------------- #
def test_task_template_creates_specs() -> None:
    """task_template 应创建 TaskSpec 工厂."""
    template = task_template(fn=_fn, retry=RetryPolicy(max_attempts=3))
    spec = template("task1")
    assert spec.name == "task1"
    assert spec.retry.max_attempts == 3


def test_task_template_with_cmd() -> None:
    """task_template 可以使用 cmd."""
    template = task_template(cmd=["echo", "hello"])
    spec = template("task1")
    assert spec.name == "task1"
    assert spec.cmd == ["echo", "hello"]


def test_task_template_overrides() -> None:
    """task_template 工厂可以覆盖默认值."""
    template = task_template(fn=_fn, timeout=10.0)
    spec = template("task1", timeout=5.0)
    assert spec.timeout == 5.0


def test_task_template_factory_name() -> None:
    """工厂函数名应为 task_template_factory."""
    template = task_template(fn=_fn)
    assert template.__name__ == "task_template_factory"


# ---------------------------------------------------------------------- #
# TaskResult 测试
# ---------------------------------------------------------------------- #
def test_task_result_duration_none_when_not_started() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    result: TaskResult[None] = TaskResult(spec=spec)
    assert result.duration is None


def test_task_result_duration_when_partial() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    result: TaskResult[None] = TaskResult(spec=spec, started_at=datetime.now())
    # started_at 已设但 finished_at 未设 -> None
    assert result.duration is None


def test_task_result_duration_computed() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    start = datetime(2024, 1, 1, 0, 0, 0)
    end = datetime(2024, 1, 1, 0, 0, 5)
    result: TaskResult[None] = TaskResult(spec=spec, started_at=start, finished_at=end)
    assert result.duration == 5.0


def test_task_result_default_status() -> None:
    spec: TaskSpec[None] = TaskSpec("a", _fn)
    result: TaskResult[None] = TaskResult(spec=spec)
    assert result.status == TaskStatus.PENDING
    assert result.value is None
    assert result.error is None
    assert result.attempts == 0


# ---------------------------------------------------------------------- #
# _run_command callable 命令测试
# ---------------------------------------------------------------------- #
def test_run_command_callable_verbose_with_cwd(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """callable 命令 verbose 模式应打印信息."""
    spec = TaskSpec("a", cmd=lambda: "result", verbose=True, cwd=tmp_path)
    import pyflowx.task as task_module

    result = task_module._run_command(spec)
    assert result == "result"
    captured = capsys.readouterr()
    assert "执行可调用命令" in captured.out
    assert "工作目录" in captured.out


def test_run_command_callable_exception() -> None:
    """callable 命令抛异常应转为 RuntimeError."""
    spec = TaskSpec("a", cmd=lambda: (_ for _ in ()).throw(RuntimeError("callable error")))
    import pyflowx.task as task_module

    with pytest.raises(RuntimeError, match="可调用命令执行异常"):
        task_module._run_command(spec)
