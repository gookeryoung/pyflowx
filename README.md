# PyFlowX

> 轻量、类型安全的 DAG 任务调度器。

[![CI](https://github.com/gookeryoung/pyflowx/actions/workflows/ci.yml/badge.svg)](https://github.com/gookeryoung/pyflowx/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyflowx.svg)](https://pypi.org/project/pyflowx/)
[![Python](https://img.shields.io/pypi/pyversions/pyflowx.svg)](https://pypi.org/project/pyflowx/)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/gookeryoung/pyflowx)
[![License](https://img.shields.io/pypi/l/pyflowx.svg)](https://github.com/gookeryoung/pyflowx/blob/main/LICENSE)

PyFlowX 把"任务依赖"这件事做到极致简单：**参数名就是依赖声明**。无需装饰器、
无需样板包装器，写一个普通函数，框架按参数名自动注入上游结果。

## 特性

- **零样板** —— 参数名即依赖，框架自动注入上游结果
- **四种执行策略** —— `sequential`（调试）/ `thread`（I/O 密集同步）/ `async`（I/O 密集异步）/ `dependency`（依赖驱动，最大化并行）
- **类型安全** —— `TaskSpec[T]` 把返回类型一路传到 `RunReport`，mypy strict 通过
- **DAG 校验** —— 构建时即时校验重名、缺失依赖、环
- **自动分层** —— Kahn 算法分组，同层任务可并行
- **重试与超时** —— 每个任务独立配置 `RetryPolicy`（max_attempts/delay/backoff/jitter/retry_on）与 `timeout`
- **软依赖** —— `soft_depends_on` 仅用于上下文注入，不参与拓扑分层
- **并发限制** —— `concurrency_key` + `concurrency_limits` 按组限流
- **任务钩子** —— `TaskHooks`（pre_run/post_run/on_failure）生命周期回调
- **断点续跑** —— `MemoryBackend` / `JSONBackend`，成功结果可缓存复用；`batch()` 批量落盘
- **缓存键** —— `cache_key` 函数基于输入计算稳定键，使不同输入产生独立缓存
- **命令任务** —— `cmd` 参数直接执行外部命令，支持列表/shell/可调用对象
- **条件执行** —— `conditions` 参数按平台、环境变量、应用安装等条件跳过任务
- **图组合** —— `compose` / `GraphComposer` 编程式展开多图字符串引用
- **任务模板** —— `task_template` 工厂批量生成相似 TaskSpec
- **图级默认值** —— `GraphDefaults` 统一配置 retry/timeout/concurrency 等
- **CLI 运行器** —— `CliRunner` 把多个图映射为命令行子命令，替代 Makefile
- **可观测** —— `on_event` 回调（RUNNING/SUCCESS/FAILED/SKIPPED）、`dry_run` 预览、`verbose` 生命周期日志、Mermaid 可视化
- **零运行时依赖** —— 仅依赖标准库（3.8 需 `graphlib_backport`）
- **97% 测试覆盖** —— 分支覆盖率 >= 95%

## 安装

```bash
pip install pyflowx
```

或使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv add pyflowx
```

## 快速上手

```python
import pyflowx as px


def extract() -> list[int]:
    return [1, 2, 3]


# 参数名 extract 自动匹配上游任务名 → 自动注入
def double(extract: list[int]) -> list[int]:
    return [x * 2 for x in extract]


graph = px.Graph.from_specs([
    px.TaskSpec("extract", extract),
    px.TaskSpec("double", double, ("extract",)),
])

report = px.run(graph, strategy="sequential")
print(report["double"])  # [2, 4, 6]
```

## 核心概念

### TaskSpec —— 任务描述

`TaskSpec` 是不可变的任务描述符（`Generic[T]`，返回类型一路传到 `RunReport`），是唯一需要配置的东西：

```python
px.TaskSpec(
    name="fetch_user",  # 唯一标识
    fn=fetch_user,  # 同步或异步函数
    cmd=["curl", "..."],  # 或: 执行命令（覆盖 fn）
    depends_on=("auth",),  # 硬依赖（参与拓扑分层）
    soft_depends_on=("cache",),  # 软依赖（仅注入，不参与分层）
    args=(uid,),  # 静态位置参数（追加在注入参数后）
    kwargs={"timeout": 30},  # 静态关键字参数
    retry=px.RetryPolicy(max_attempts=3, delay=1.0, backoff=2.0),  # 重试策略
    timeout=30.0,  # 超时秒数（None = 不限制）
    tags=("api", "user"),  # 自由标签，用于子图过滤
    conditions=(is_prod,),  # 条件函数列表（全部为 True 才执行）
    priority=10,  # 同层内优先级（高优先执行，默认 0）
    concurrency_key="db",  # 并发分组键（配合 concurrency_limits 限流）
    cache_key=lambda ctx: str(ctx.get("uid")),  # 缓存键函数（不同输入独立缓存）
    hooks=px.TaskHooks(pre_run=..., post_run=..., on_failure=...),  # 生命周期钩子
    cwd=Path("/tmp"),  # 命令工作目录（仅 cmd 模式）
    env={"DEBUG": "1"},  # 环境变量覆盖（fn 与 cmd 模式均生效）
    verbose=True,  # 打印命令输出（仅 cmd 模式）
    skip_if_missing=True,  # 命令不存在时自动跳过（仅 list[str] cmd）
    allow_upstream_skip=False,  # 上游 SKIPPED/FAILED 时是否仍执行
    continue_on_error=False,  # 本任务失败是否不中断整体
)
```

支持两种任务形态：

- **函数任务**（`fn`）：普通 Python 函数，参数名驱动自动注入
- **命令任务**（`cmd`）：执行外部命令，支持 `list[str]`、`str`（shell）、`Callable` 三种形态

`skip_if_missing=True` 时，`list[str]` 类型的 `cmd` 会通过 `shutil.which` 检查命令是否存在，不存在则跳过任务（标记为 `SKIPPED`）而非失败。适用于构建工具场景，避免因未安装某些工具而导致整个图执行失败。

### Graph —— DAG 构建

```python
# 图级默认值：TaskSpec 字段为 None 时回退
defaults = px.GraphDefaults(retry=px.RetryPolicy(max_attempts=2), timeout=60.0)

graph = px.Graph.from_specs([...], defaults=defaults)  # 整批校验（推荐）
# 或增量构建
graph = px.Graph(defaults=defaults)
graph.add(px.TaskSpec("a", fn_a))
graph.add(px.TaskSpec("b", fn_b, ("a",)))

graph.validate()  # 显式校验（环检测）
graph.layers()  # 拓扑分层（run() 入口已统一校验，直接调用需自行先 validate）
graph.to_mermaid()  # Mermaid 可视化
graph.describe()  # 人类可读摘要
graph.subgraph(("api",))  # 按标签切片
graph.subgraph_by_names(("a", "b"))  # 按名称切片
graph.map("fetch", [1, 2, 3], lambda i: TaskSpec(f"fetch_{i}", ...))  # 批量 fan-out
```

### 图组合 —— compose

`compose` / `GraphComposer` 把带字符串引用的多个图展开为纯 `Graph`：

```python
graphs = {
    "build": px.Graph.from_specs([px.TaskSpec("b", cmd=["echo", "b"])]),
    "all": px.Graph.from_specs(["build", px.TaskSpec("t", cmd=["echo", "t"])]),
}
resolved = px.compose(graphs)  # "all" 图中的 "build" 引用被展开
```

引用格式：`"command_name"`（整个图）或 `"command_name.task_name"`（特定任务）。
`CliRunner` 内部自动调用 `compose`。

### 任务模板 —— task_template

`task_template` 工厂批量生成相似 TaskSpec：

```python
fetch = px.task_template(
    fn=fetch_url,
    retry=px.RetryPolicy(max_attempts=5),
    timeout=30.0,
    tags=("api",),
)
graph = px.Graph.from_specs([
    fetch("users", url="https://api.example.com/users"),
    fetch("posts", url="https://api.example.com/posts"),
])
```

### run —— 执行

```python
report = px.run(
    graph,
    strategy="async",  # sequential | thread | async | dependency
    max_workers=8,  # thread 策略的线程池大小
    concurrency_limits={"db": 2},  # 按 concurrency_key 限流
    dry_run=False,  # True = 仅打印计划
    verbose=False,  # True = 打印任务生命周期日志
    on_event=callback,  # 状态转换回调（RUNNING/SUCCESS/FAILED/SKIPPED）
    state=px.JSONBackend("state.json"),  # 断点续跑后端
    continue_on_error=False,  # True = 单任务失败不中断整体
)
```

### RunReport —— 结果

```python
report["task_name"]  # 任务返回值
report.result_of("task_name")  # 完整 TaskResult
report.success  # 整体是否成功
report.summary()  # 统计字典
report.failed_tasks()  # 失败任务名列表
report.describe()  # 人类可读报告
```

## 上下文注入规则

按顺序求值：

1. **标注为 `Context`** 的参数 → 接收完整上游结果映射
2. **名称匹配依赖** 的参数 → 接收该依赖的结果（含软依赖，缺失时注入默认值）
3. **`**kwargs`** 参数 → 接收所有依赖结果（dict）
4. **`TaskSpec.args` / `kwargs`** → 为非依赖参数提供静态值

```python
from typing import Any, Dict


def aggregate(ctx: px.Context) -> Dict[str, Any]:
    """ctx 包含所有 depends_on 任务的返回值。"""
    return dict(ctx)


def merge(fetch_a: str, fetch_b: str) -> str:
    """fetch_a / fetch_b 自动注入。"""
    return fetch_a + fetch_b


def fetch_user(uid: int) -> dict:  # uid 来自 TaskSpec.args
    ...
```

## 执行策略对比

| 策略 | 并发模型 | 适用场景 | 同步任务 | 异步任务 |
|------|---------|---------|---------|---------|
| `sequential` | 串行 | 调试、CPU 密集 | 直接调用 | 事件循环 |
| `thread` | 线程池 | I/O 密集同步 | 线程池 | 不支持 |
| `async` | 事件循环 | I/O 密集异步 | 卸载到线程池 | 事件循环 |
| `dependency` | 依赖驱动 | 最大化并行度 | 卸载到线程池 | 事件循环 |

所有策略都遵循 `RetryPolicy`、`timeout`、上下文注入、状态后端、`concurrency_limits`，
并发出 `TaskEvent`（RUNNING/SUCCESS/FAILED/SKIPPED）。`dependency` 策略无层屏障：
任务在其所有硬依赖完成后立即启动。

## 命令任务

`TaskSpec` 的 `cmd` 参数支持执行外部命令，无需包装 Python 函数：

```python
graph = px.Graph.from_specs([
    # 命令列表（推荐，参数无需转义）
    px.TaskSpec("list_files", cmd=["ls", "-la"]),
    # shell 字符串（支持管道、重定向）
    px.TaskSpec("check_git", cmd="git status | head"),
    # 带工作目录与超时
    px.TaskSpec("build", cmd=["make", "all"], cwd=Path("/project"), timeout=300),
    # 命令不存在时自动跳过（而非失败）
    px.TaskSpec("optional_tool", cmd=["maturin", "build"], skip_if_missing=True),
])
```

`verbose=True` 时打印执行的命令、工作目录、返回码与输出；`verbose=False` 时静默执行（失败信息仍包含 stderr）。

`skip_if_missing=True` 时，`list[str]` 类型的 `cmd` 会通过 `shutil.which` 检查命令是否存在，不存在则跳过任务（标记为 `SKIPPED`）而非失败。适用于构建工具场景，避免因未安装某些工具而导致整个图执行失败。对于 `str`（shell）和 `Callable` 类型的 `cmd`，此参数无效。

## 条件执行

`conditions` 参数让任务按条件跳过（标记为 `SKIPPED`）：

```python
from pyflowx.conditions import IS_WINDOWS, BuiltinConditions

graph = px.Graph.from_specs([
    # 仅在 Windows 上运行
    px.TaskSpec("win_only", cmd=["dir"], conditions=(IS_WINDOWS,)),
    # 仅在 git 已安装时运行
    px.TaskSpec(
        "git_check",
        cmd=["git", "--version"],
        conditions=(BuiltinConditions.HAS_INSTALLED("git"),),
    ),
    # 组合条件
    px.TaskSpec(
        "prod_deploy",
        fn=deploy,
        conditions=(
            BuiltinConditions.ENV_VAR_EQUALS("ENV", "prod"),
            BuiltinConditions.HAS_INSTALLED("docker"),
        ),
    ),
])
```

内置条件：`IS_WINDOWS` / `IS_LINUX` / `IS_MACOS` / `IS_POSIX` / `PYTHON_VERSION` / `HAS_INSTALLED` / `ENV_VAR_EXISTS` / `ENV_VAR_EQUALS` / `NOT` / `AND` / `OR`。

## CLI 运行器

`CliRunner` 把多个 Graph 映射为命令行子命令，适合构建项目专属构建工具（替代 Makefile）：

```python
runner = px.CliRunner(
    strategy="sequential",
    description="My Build Tool",
    graphs={
        "clean": clean_graph,
        "build": build_graph,
        "test": test_graph,
    },
)
runner.run_cli()  # 解析 sys.argv 并执行
```

命令行用法：

```bash
python build.py clean           # 执行 clean 图
python build.py build --strategy thread   # 覆盖执行策略
python build.py test --dry-run  # 仅打印执行计划
python build.py --list          # 列出所有命令
python build.py --quiet         # 静默模式
```

`verbose=True`（默认）时打印任务生命周期（开始/成功/失败/跳过）与命令输出；`--quiet` 关闭。

## 示例

仓库 `examples/` 目录包含完整示例：

- [`etl_pipeline.py`](examples/etl_pipeline.py) —— ETL 流水线（sequential）
- [`parallel_run.py`](examples/parallel_run.py) —— 并行执行对比（thread vs sequential）
- [`async_aggregation.py`](examples/async_aggregation.py) —— 异步聚合 + Context 注入

运行：

```bash
python examples/etl_pipeline.py
python examples/parallel_run.py
python examples/async_aggregation.py
```

## 断点续跑

```python
from pyflowx import JSONBackend

# 第一次运行：成功结果写入 state.json
backend = JSONBackend("state.json", ttl=3600)  # ttl 秒数，过期条目自动忽略
report = px.run(graph, strategy="sequential", state=backend)

# 第二次运行：已缓存任务自动跳过（状态为 SKIPPED）
report = px.run(graph, strategy="sequential", state=backend)
```

`run()` 内部以 `backend.batch()` 包裹整个执行：所有 `save` 延迟到运行结束时统一落盘一次
（`JSONBackend` 从 O(N²) 降为 O(N) 磁盘写入；`MemoryBackend` 为 no-op）。

**缓存键**：默认存储键为任务名。配置 `cache_key` 函数后，键为 `"name:cache_key_value"`，
使不同输入产生独立缓存条目：

```python
px.TaskSpec(
    "fetch_user",
    fn=fetch_user,
    cache_key=lambda ctx: str(ctx.get("uid")),  # 不同 uid 独立缓存
)
```

## 错误处理

所有错误都是 `PyFlowXError` 的子类：

| 错误 | 触发时机 |
|------|---------|
| `DuplicateTaskError` | 任务名重复注册 |
| `MissingDependencyError` | 依赖了不存在的任务 |
| `CycleError` | 依赖图存在环 |
| `TaskFailedError` | 任务耗尽重试后仍失败 |
| `TaskTimeoutError` | 任务超时 |
| `InjectionError` | 上下文注入无法满足签名 |
| `StorageError` | 状态后端持久化失败 |

```python
try:
    report = px.run(graph, strategy="async")
except px.TaskFailedError as exc:
    print(f"{exc.task} 失败: {exc.cause}（尝试 {exc.attempts} 次）")
except px.PyFlowXError:
    # 捕获整个错误家族
    raise
```

## 与其他库对比

| 特性 | PyFlowX | Airflow | Prefect | Dask |
|------|---------|---------|---------|------|
| 零样板 | 参数名即依赖 | 装饰器 + XCom | 装饰器 | 装饰器 |
| 运行时依赖 | 仅标准库 | 重型 | 中型 | 中型 |
| 类型安全 | mypy strict | 弱 | 中 | 中 |
| 异步原生 | 是 | 否 | 部分 | 否 |
| 断点续跑 | 内置 | 需配置 | 需配置 | 需配置 |
| 学习曲线 | 极低 | 高 | 中 | 中 |
| 适用规模 | 单机 | 集群 | 单机/集群 | 集群 |

PyFlowX 专注于**单机 DAG 调度**的极致简洁，适合 ETL、数据处理、CI 流水线等场景。

## 高级特性

### 并发限制

按 `concurrency_key` 分组限流，避免压垮下游资源：

```python
graph = px.Graph.from_specs([
    px.TaskSpec("q1", fn=query_db, concurrency_key="db"),
    px.TaskSpec("q2", fn=query_db, concurrency_key="db"),
    px.TaskSpec("q3", fn=query_db, concurrency_key="db"),
])
# 同一时刻最多 2 个 "db" 组任务运行
px.run(graph, strategy="async", concurrency_limits={"db": 2})
```

### 任务钩子

`TaskHooks` 在任务生命周期触发（异常仅记录，不影响任务状态）：

```python
hooks = px.TaskHooks(
    pre_run=lambda spec: print(f"start {spec.name}"),
    post_run=lambda spec, value: print(f"done {spec.name}"),
    on_failure=lambda spec, exc: alert(spec.name, exc),
)
px.TaskSpec("task", fn=work, hooks=hooks)
```

### 优先级

同层内按 `priority` 降序执行（稳定排序）：

```python
px.TaskSpec("low", fn=work, priority=0)
px.TaskSpec("high", fn=work, priority=10)  # 同层内先执行
```

## 开发

```bash
# 安装开发依赖
uv sync --extra dev

# 运行测试（含覆盖率，阈值 95%）
uv run pytest --cov=pyflowx --cov-fail-under=95

# 类型检查
uv run mypy

# 代码风格
uv run ruff check src tests examples
uv run ruff format --check src tests examples
```

## 模块结构

| 模块 | 职责 |
|------|------|
| `task.py` | 纯数据结构：`TaskSpec`、`RetryPolicy`、`TaskHooks`、`TaskStatus` |
| `graph.py` | DAG 构建、校验、分层、可视化 |
| `compose.py` | 多图组合：`GraphComposer` / `compose` |
| `context.py` | 上下文注入：参数名→依赖解析 |
| `command.py` | 命令执行：`run_command`（list/shell/Callable） |
| `conditions.py` | 条件执行：内置条件与组合器 |
| `executors.py` | 执行器与 `run` 入口：四种策略共享模块级辅助 |
| `storage.py` | 状态后端：`MemoryBackend` / `JSONBackend`（batch flush） |
| `runner.py` | CLI 运行器：`CliRunner` |
| `report.py` | 运行结果：`RunReport` / `TaskResult` |
| `errors.py` | 错误家族：`PyFlowXError` 子类 |

## 许可证

MIT
