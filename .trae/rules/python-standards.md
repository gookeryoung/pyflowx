# Python 开发规范

本规范结合 Python 最佳实践，作为编写与审查 Python 代码的统一标准。
详细操作指南见 `.agents/skills/` 下相应技能。

## 工具链（以 pyproject.toml 为准）

| 工具 | 用途 | 配置要点 |
|------|------|---------|
| **ruff** | lint + format | `line-length=120`，`target-version="py38"` |
| **pyrefly** | 类型检查 | `preset="strict"`，`python-version="3.8"` |
| **pytest** | 测试 | `asyncio_default_fixture_loop_scope="function"`，marker `slow` |
| **coverage** | 覆盖率 | `branch=true`，`fail_under=95`，`concurrency=["thread"]` |
| **pre-commit** | 提交前检查 | ruff `--fix` + trailing-whitespace + end-of-file-fixer |

验证（每次修改后必做）：

```bash
uvx --from pyflowx pymake tc
uvx --from pyflowx pymake cov
```

## 兼容性

- **最低 Python 3.8**：用 `from __future__ import annotations` 延迟注解求值；
  按版本用 `typing.List`(3.8) → 内置泛型(3.9) → `X | Y`(3.10) → `typing.override`(3.12)。
- **版本守卫**：`if sys.version_info >= (3, X):` 引入高版本 API；低版本回退分支加 `# pragma: no cover`。
- **零运行时依赖**：仅依赖标准库（3.8 需 `graphlib_backport`、`typing-extensions`）。
  新增依赖须审慎，优先用标准库。

## 类型注解

- **公共 API 必须有完整类型注解**，包括返回类型；私有函数也应有注解。
- 泛型用 `TypeVar`；PEP 696 `default=` 仅 3.13+ 标准库支持，3.8–3.12 用 `typing_extensions.TypeVar`。
- `Mapping`/`Sequence` 用于只读参数，`dict`/`list` 用于可变返回。
- `Any` 仅用于真正动态场景（如 `Context` 跨任务异构映射）；任务内部类型必须完全静态。
- 禁用裸 `# type: ignore`；确需时加具体规则码（如 `# type: ignore[union-attr]`）。
- **`TYPE_CHECKING` 守卫**：仅类型检查需要的导入放 `if TYPE_CHECKING:` 块内，避免循环依赖。
- **类型收窄**：用 `assert isinstance(x, Y)` 辅助 pyrefly 推断；`cast()` 仅用于类型系统无法表达的场景。

## 数据结构

- **不可变优先**：配置/描述类用 `@dataclass(frozen=True)`；可变类属性标注 `RUF012` 豁免。
- **缓存**：实例级用 `functools.cached_property`，按参数键控用 `functools.lru_cache`；
  不可哈希参数需 try/except 回退。修改被缓存数据源后必须手动清空缓存。
- **抽象基类**：接口用 `abc.ABC` + `@abstractmethod`（如 `StateBackend`）。
- **枚举**：状态/标志值用 `enum.Enum`（如 `TaskStatus`），禁止裸字符串/魔术数字；枚举值用 `UPPER_SNAKE`。
- **`__repr__`**：可变类实现 `__repr__`（含关键字段）；`frozen=True` dataclass 自动生成。

## 模块与导入

- **单一职责**：每模块只做一件事（`task.py` 数据结构、`executors.py` 执行、`command.py` 命令、`compose.py` 组合）。禁止跨职责边界。
- **导入顺序**（ruff isort）：`__future__` → 标准库 → 第三方 → 本地，各组间空行。
- **惰性导入**：仅为打破循环依赖时使用，函数体内导入并注释说明；顶层导入是默认。
- **`__all__`**：定义 `__all__` 显式声明导出符号，位置仅次于 `__future__` 之后。
- **禁用 star imports**：`from x import *` 污染命名空间、破坏类型检查（`__init__.py` 聚合经 `__all__` 控制为例外）。
- **避免 `utils.py`/`helpers.py`**：按职责归入对应模块。

## 函数设计

- **模块级函数优于 Mixin**：共享逻辑用模块级函数，类只持有状态与薄方法。
- **静态方法慎用**：纯函数直接放模块级。
- **参数 ≤ 5 个**为宜；超出用 dataclass 封装参数对象。
- **单一职责**：一个函数做一件事；过长函数考虑拆分。
- **异常范围要窄**：只捕获预期异常（如 `(TypeError, ValueError, KeyError, AttributeError)`），
  **禁止** `except Exception` 掩盖 bug；捕获后至少 `logger.warning` 记录。
- **可变默认参数**：`def f(x=[])` 是经典坑；用 `None` 哨兵或 `field(default_factory=list)`。

## 异常处理

- **自定义异常家族**：继承公共基类（如 `PyFlowXError`），按错误场景分类。
- **异常包装**：`raise NewError(...) from exc` 保留因果链。
- **不要吞异常**：捕获后必须处理（记录/包装/重抛），禁止空 `except: pass`。
- **钩子/回调异常**：第三方回调异常仅记录，不影响主流程。

## 并发与线程安全

- **进程全局状态**（`os.environ`/`os.chdir`）在并发场景下必须用全局锁（`threading.RLock`）序列化。
- **条件评估不可有可变状态**：组合条件（NOT/AND/OR）不得修改共享 `_reason`，避免竞态。
- **批量 I/O**：循环内多次写盘改为批量一次（`contextmanager` 包裹延迟落盘）。
- **信号量限流**：`concurrency_key` + `Semaphore` 按组限流。

## 测试

详细操作指南见 `.agents/skills/pyflowx-testing` 技能。硬约束：

- **覆盖率 ≥ 95%**（branch coverage），不得下降。
- **公共 API 优先测试**：用公共接口（`has`/`get`），不访问私有方法；
  故障注入等场景可临时访问私有属性，docstring 注明原因。
- **命名**：`test_<被测对象>_<场景>`。
- **断言**：原生 `assert x == 1`，禁用 `self.assertEqual`；`pytest.raises` 必填 `match=`。
- **Mock 优先级**：`monkeypatch` > 内联 stub > `unittest.mock` > `pytest-mock`。
  禁用 `@patch` 装饰器、`mock.patch.object` 上下文、`pytest-mock` 的 `mocker` fixture。
- **fixture**：`tmp_path`/`monkeypatch`/`capsys` 优先；autouse 仅全局必需时用。
- **slow 标记**：耗时测试加 `@pytest.mark.slow`，CI 可 `-m "not slow"` 跳过。
- **测试代码也跑 ruff**：`tests/**` 忽略 `ARG001`/`ARG002`。

## 代码风格

- **行宽 120**（ruff formatter 处理）。
- **docstring**：公共 API 必须有；中文叙述 + 中文注释是本项目既有风格。
- **打印和日志**：使用中文打印和日志，避免使用英文。
- **命名**：`snake_case` 函数/变量，`PascalCase` 类，`UPPER_SNAKE` 常量，`_leading_underscore` 私有。
- **字符串引号**：ruff 默认双引号。
- **末尾单 `\n`**、**无尾随空格**（pre-commit 强制）。
- **不用 emoji**：除非用户明确要求。

## Pythonic 风格

- **`is` 比较 `None`/`True`/`False`**：单例用 `is`，值用 `==`（PEP 8 E711/E712）。
- **EAFP 优于 LBYL**：先尝试再处理异常，而非先检查再执行（避免竞态窗口）。
- **truthiness**：`if items:` 优于 `if len(items) > 0:`。
- **字符串格式化**：首选 f-string；`%` 仅用于 `logging` 延迟格式化。
- **推导式**优于 `map`+`filter`；> 2 层拆为显式循环。
- **`enumerate`** 替代 `range(len())`；**`zip`** 并行迭代（3.10+ 用 `strict=True`）。
- **解包** `a, b = pair` 优于索引访问；忽略值用 `_`。
- **海象运算符 `:=`**（3.8+）：赋值+判断合一，但不滥用。

## 日志

- **`logging.getLogger(__name__)`**：每模块独立 logger，禁用 `print` 调试残留。
- **结构化上下文**：`extra={...}` 传字段；`logger.warning("task %r failed: %s", name, exc)` 优于 f-string（延迟格式化）。
- **日志级别**：`DEBUG` 诊断 / `INFO` 关键流程 / `WARNING` 可恢复异常 / `ERROR` 需人工介入。
- **禁止日志密码/密钥**：脱敏后再记录。

## 路径与资源

- **优先 `pathlib.Path`**：`Path("a") / "b"` 而非 `os.path.join`（ruff `PTH` 强制）；
  禁止字符串拼接路径。类型注解用 `Path`，边界 `str` 立即包装。
- **`with` 语句**：文件、锁、连接、临时目录一律用 `with` 或 `contextlib.contextmanager`；
  多资源用 `contextlib.ExitStack`。
- **显式关闭**：长生命周期对象（连接池、线程池）实现 `close()`，但优先 `with`。
- **批量操作**：循环内多次 acquire/release 改为批量一次。

## 安全

- **禁用 `eval`/`exec`**：处理不可信输入时绝不使用；用 `ast.literal_eval` 或专用解析器。
- **`subprocess`**：禁用 `shell=True` 除非命令完全可信；优先 `list[str]` 形式。
- **凭证不入仓**：密钥/token/密码放 `.env` 或环境变量，`.gitignore` 必须包含 `.env`。
- **日志脱敏**：记录请求/响应时移除 `Authorization`、`password` 等字段。
- **依赖审计**：`uv lock` 后审阅新增依赖，避免引入已知 CVE 的包。

## 性能要点

- **避免重复计算**：循环内查询应缓存或预构建映射（如 `{name: spec}`）。
- **避免双重查找**：`has(k)` + `get(k)` 改为单次 `get(k)` + `KeyError` 回退。
- **统一校验**：入口校验一次，下游路径不重复（如 `run()` 统一 `validate()`，`layers()` 不再重复）。
- **事件 emit**：任务生命周期必须 emit `RUNNING` → `SUCCESS`/`FAILED`/`SKIPPED`，
  不要留死分支（`# pragma: no cover` 是清理信号，应激活或删除）。

## Git 与提交

- **不自动提交/push**：除非用户明确要求。
- **不修改 git config**。
- **不运行破坏性命令**（`push --force`/`reset --hard`/`clean -f`）除非用户明确要求。
- **staging**：按文件名添加，不用 `git add -A`/`git add .`，避免误加敏感文件。
- **commit message**：简洁，聚焦"为什么"而非"是什么"；遵循仓库既有风格。
