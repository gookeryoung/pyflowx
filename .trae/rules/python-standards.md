# Python 开发规范

本规范结合 Python 最佳实践，作为编写与审查 Python 代码的统一标准。

## 工具链（以 pyproject.toml 为准）

| 工具 | 用途 | 配置要点 |
|------|------|---------|
| **ruff** | lint + format | `line-length=120`，`target-version="py38"`，select 见 pyproject |
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

- **最低 Python 3.8**：使用 `from __future__ import annotations` 延迟注解求值；
  3.9 以下用 `typing.List`/`typing.Dict`/`typing.Union`，3.9+ 用内置泛型，
  3.10+ 用 `X | Y`，3.12+ 用 `typing.override`。
- **版本守卫**：`if sys.version_info >= (3, X):` 引入高版本 API，else 回退。
  低版本回退分支加 `# pragma: no cover`。
- **零运行时依赖**：仅依赖标准库（3.8 需 `graphlib_backport`、`typing-extensions`）。
  新增依赖须审慎，优先用标准库。

## 类型注解

- **所有公共 API 必须有完整类型注解**，包括返回类型。
- **私有函数也应有注解**，便于 pyrefly strict 通过。
- 泛型用 `TypeVar`；使用 PEP 696 `default=` 参数时，3.13+ 用 `typing.TypeVar`，
  3.8–3.12 用 `typing_extensions.TypeVar`（`default=` 在 3.13 才进入标准库）。
- `Mapping`/`Sequence` 用于只读参数，`dict`/`list` 用于可变返回。
- `Any` 仅用于真正动态的场景（如 `Context` 跨任务异构映射）；单个任务内部类型
  必须完全静态，由函数签名保证。
- 避免渐进式类型：不要用 `# type: ignore` 掩盖真实类型错误；确需时加
  具体规则码注释（如 `# type: ignore[union-attr]`）。
- **`TYPE_CHECKING` 守卫**：仅类型检查需要的导入（如为避免循环依赖、
  或仅注解用的重类型）放 `if TYPE_CHECKING:` 块内，运行期不导入：
  ```python
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from pyflowx.graph import Graph  # 仅注解使用
  ```
- **类型收窄**：分支内需要窄化类型时，用 `assert isinstance(x, Y)` 辅助
  pyrefly 推断；避免无谓的 `cast()`（运行期无检查，掩盖 bug）。
  `cast` 仅用于类型系统无法表达的场景（如第三方无类型存根）。

## 数据结构

- **不可变优先**：配置/描述类用 `@dataclass(frozen=True)`。
- **可变类属性**显式标注 `RUF012` 豁免（如配置默认值 `field(default_factory=...)`）。
- **缓存计算结果**用 `functools.cached_property`（实例级）或
  `functools.lru_cache`（按参数键控）；不可哈希参数需 try/except 回退。
- **缓存失效**：修改被缓存的数据源后必须手动清空缓存（如 `self._cache.clear()`），
  否则下游拿到陈旧数据。
- **抽象基类**：定义接口用 `abc.ABC` + `@abstractmethod`（如 `StateBackend`），
  强制子类实现关键方法；非抽象方法提供默认实现。
- **枚举**：状态/标志值用 `enum.Enum`（或 `IntEnum`/`Flag`，如 `TaskStatus`），
  禁止裸字符串/魔术数字；枚举值用 `UPPER_SNAKE`。
- **`__repr__`**：可变类实现 `__repr__`（含关键字段），便于调试与日志；
  `frozen=True` dataclass 自动生成，无需手写。

## 模块与导入

- **单一职责**：每个模块只做一件事（`task.py` 纯数据结构、`executors.py` 执行逻辑、
  `command.py` 命令执行、`compose.py` 图组合）。禁止跨职责边界放代码。
- **导入顺序**（ruff isort）：`__future__` → 标准库 → 第三方 → 本地，各组间空行。
- **惰性导入**：仅为打破循环依赖时使用，在函数体内导入，加注释说明原因。
  顶层导入是默认。
- **`__all__`**：定义 `__all__`，显式声明导出符号。位置在模块顶部，仅次于 `__future__` 之后。
- **禁用 star imports**：`from x import *` 污染命名空间、隐藏依赖、
  破坏类型检查；显式列出导入符号，或用模块路径访问（`import x` → `x.foo`）。
  例外：`__init__.py` 聚合导出时可经 `__all__` 控制。
- **避免 `utils.py`、`helpers.py` 等杂项工具文件**：按职责归入对应模块，不要建杂项工具文件。

## 函数设计

- **模块级函数优于 Mixin**：共享逻辑用模块级函数，不要新建 Mixin 类。
  类只持有状态与薄方法，调用模块级函数。
- **静态方法慎用**：纯函数直接放模块级，不必塞进类里当 `@staticmethod`。
- **参数 ≤ 5 个**为宜；超出考虑用 dataclass 封装参数对象（ruff `PLR0913` 已忽略，
  但仍是设计信号）。
- **单一职责**：一个函数做一件事；过长函数（ruff `PLR0915` 已忽略但仍是信号）
  考虑拆分。
- **异常范围要窄**：只捕获预期异常（如 `(TypeError, ValueError, KeyError, AttributeError)`），
  **不要** `except Exception` 掩盖 bug。捕获后至少 `logger.warning` 记录。

## 异常处理

- **自定义异常家族**：继承公共基类（如 `PyFlowXError`），按错误场景分类。
- **异常包装**：低层异常用 `raise NewError(...) from exc` 保留因果链。
- **不要吞异常**：捕获后必须处理（记录/包装/重抛），不要空 `except: pass`。
- **钩子/回调异常**：第三方回调异常仅记录，不影响主流程（用 `_run_hooks` 模式）。

## 并发与线程安全

- **进程全局状态**（`os.environ`/`os.chdir`）在并发场景下必须用全局锁
  （`threading.RLock`）序列化"切换→执行→恢复"区间。
- **条件评估不可有可变状态**：组合条件（NOT/AND/OR）不得修改共享 `_reason`，
  避免竞态。
- **批量 I/O**：循环内多次写盘改为批量一次（用 `contextmanager` 包裹延迟落盘）。
- **信号量限流**：`concurrency_key` + `Semaphore` 按组限流，避免压垮下游。

## 测试

### 总则

- **覆盖率 ≥ 95%**（branch coverage），不得下降。
- **公共 API 优先测试**：测试用公共接口（`has`/`get`），不访问私有方法
  （如 `_expired`）。兼容旧测试的私有方法应删除并迁移测试。
  例外：`_store`/`_flush` 等内部状态在无法用公共 API 触发时（如模拟过期、
  故障注入），可临时访问私有属性，并在 docstring 注明原因。
- **命名**：`test_<被测对象>_<场景>`，如 `test_storage_key_cache_key_exception_returns_name`。
- **每个测试一个断言重点**；多个断言要语义相关。
- **slow 标记**：耗时测试加 `@pytest.mark.slow`，CI 可 `-m "not slow"` 跳过。
- **测试代码也跑 ruff**：`tests/**` 忽略 `ARG001`/`ARG002`（未用 fixture 参数）。
- **断言风格**：用原生 `assert` + 比较运算符（`assert x == 1`），
  不用 `self.assertEqual`；pytest 会生成更清晰的 diff。

### Mock 工具选择（强制）

**优先级**：`monkeypatch` > 内联 stub > `unittest.mock` > `pytest-mock`。

| 场景 | 工具 | 示例 |
|------|------|------|
| 替换模块属性 / 环境变量 / 工作目录 | `monkeypatch` | `monkeypatch.setattr(subprocess, "run", fake_run)` |
| `os.environ["KEY"]` 临时设置 | `monkeypatch.setenv` | `monkeypatch.setenv("LOCALAPPDATA", "C:\\...")` |
| 切换 cwd | `monkeypatch.chdir` | `monkeypatch.chdir(tmp_path)` |
| 一次性 stub 函数 | 内联 lambda / 闭包 | `ran = []; monkeypatch.setattr(subprocess, "run", lambda *c, **__: ran.append(c))` |
| 复杂 spy（记录调用次数/参数/返回序列） | `unittest.mock.MagicMock` | 仅当 lambda 不足以表达时 |
| `with patch(...)` 上下文 | **禁用**（用 monkeypatch） | monkeypatch 自动 teardown 更安全 |

**禁止**：
- 不用 `pytest-mock` 的 `mocker` fixture（项目虽在 dev 依赖声明，但实际
  测试代码未使用；为保持风格统一，新代码继续用 `monkeypatch`）。
- 不用 `unittest.mock.patch` 装饰器（`@patch("x.y")`），它隐藏依赖且
  与 pytest fixture 模式不兼容；用 `monkeypatch.setattr` 替代。
- 不用 `mock.patch.object` 作为上下文管理器，除非被测代码本身就是
  contextmanager（此时用 `monkeypatch.setattr` 仍更简单）。

### monkeypatch 使用规范

- **类型注解**：fixture 参数标注 `monkeypatch: pytest.MonkeyPatch`。
- **作用域**：monkeypatch 自动在测试结束时撤销，**禁止**手动
  `monkeypatch.setattr(x, "y", original)` 恢复（多余且容易遗漏）。
  例外：在单个测试内需要中途恢复时，用 `monkeypatch.undo()` 全量撤销。
- **替换目标**：替换"被测代码看到的对象"，而非全局对象本身。
  - 错误：`monkeypatch.setattr("os.path.exists", fake)` —— 替换全局，
    影响其他模块。
  - 正确：`monkeypatch.setattr(pyflowx.command.shutil, "which", fake)` ——
    替换被测模块引用的 `shutil.which`。
- **属性 vs 字符串路径**：优先属性访问形式 `monkeypatch.setattr(obj, "attr", val)`
  而非字符串路径 `monkeypatch.setattr("pkg.mod.obj.attr", val)`，
  前者有 IDE 跳转与重构支持。
- **记录调用**：用闭包 `ran: list[tuple] = []` + `lambda *a, **k: ran.append((a, k))`
  替代 `MagicMock`，可读性更好且无需导入。

### Stub 与 Spy 模式

- **轻量 stub**：内联定义 `class MockResult: returncode = 0; stdout = ""`，
  替代 `MagicMock(return_value=...)`，类型明确且不引入 mock 依赖。
- **状态收集**：闭包 + list 比 `mock.call_args_list` 更易断言：
  ```python
  calls: list[list[str]] = []


  def fake_run(cmd: list[str], **_: Any) -> MockResult:
      calls.append(cmd)
      return MockResult()


  monkeypatch.setattr(subprocess, "run", fake_run)
  assert calls == [["clear"]]
  ```
- **副作用序列**：需要按调用次数返回不同值时，用 `itertools.cycle` 或
  手动计数器，而非 `side_effect=[...]`（mock 专有 API）。
- **异常注入**：`def raise_oserror(*a, **k): raise OSError("...")`，
  用 `pytest.raises(OSError)` 验证，而非 `side_effect=OSError`。

### 异常断言

- **`pytest.raises`**：必填 `match=` 正则（除非异常消息完全不可预测），
  避免误捕获同类异常：
  ```python
  with pytest.raises(StorageError, match="cannot write"):
      b.save("a", 1)
  ```
- **异常链**：验证 `__cause__` 时用 `exc_info.value.__cause__`，
  确认 `raise X from Y` 因果链完整。
- **禁止** `try/except + assert False`：用 `pytest.raises` 替代。

### Fixture 规范

- **`tmp_path`**：处理临时文件，自动清理，禁止 `tempfile.mkdtemp()` 手动管理。
- **`monkeypatch`**：环境变量、cwd、模块属性 mock（见上）。
- **`capsys`/`capfd`**：捕获 stdout/stderr，验证日志或命令输出。
- **autouse fixture**：仅在全局必需时用（如 `conftest.py` 的
  `packtool_tmp_workdir` 自动切到 tmp_path）；否则显式声明参数。
- **fixture 命名**：`snake_case`，描述"提供什么"而非"测试什么"
  （`sample_graph` 优于 `test_data`）。
- **fixture 作用域**：默认 `function`；`module`/`session` 仅当构造昂贵且
  只读时，并加注释说明无副作用。

### asyncio 测试

- **fixture `loop_scope="function"`**（pyproject 已配置默认值）。
- **async 测试**：`async def test_x():`，pytest-asyncio 自动驱动。
- **await 检查**：测试异步函数必须 `await` 结果，禁止仅验证返回 coroutine 对象。
- **异步 mock**：用 `AsyncMock`（3.8+ 在 `unittest.mock`）或
  `async def fake(): return value`，禁用 `MagicMock(return_value=coro)`。

### 参数化

- **`@pytest.mark.parametrize`**：用 `ids` 参数提供可读标识：
  ```python
  @pytest.mark.parametrize(
      ("strategy", "expected_workers"),
      [("sequential", 1), ("thread", 8), ("async", 1)],
      ids=["seq", "thread-8", "async"],
  )
  ```
- **参数命名**：参数元组用有意义名称，而非 `("a", "b")`。
- **组合爆炸**：参数组合 > 20 时拆分测试，避免单个测试函数臃肿。

### 测试组织

- **文件命名**：`test_<被测模块>.py`（`test_storage.py` 对应 `storage.py`）。
- **类分组**：仅在测试逻辑强相关时用 `class TestXxx:` 分组；默认用模块级函数。
- **docstring**：每个测试函数一句话说明"测试什么场景"，复杂场景补充"为什么"。
- **setup/teardown**：优先 fixture；`setup_method`/`teardown_method` 仅在
  无法用 fixture 表达时（罕见）。

## 代码风格

- **行宽 120**（ruff formatter 处理，无需手动对齐）。
- **docstring**：公共 API 必须有 docstring；模块顶部 docstring 说明职责与设计要点。
  中文叙述 + 英文代码注释是本项目既有风格，保持一致。
- **命名**：`snake_case` 函数/变量，`PascalCase` 类，`UPPER_SNAKE` 常量，
  `_leading_underscore` 私有。
- **字符串引号**：ruff 默认双引号。
- **末尾换行**：文件以单 `\n` 结尾（pre-commit `end-of-file-fixer` 强制）。
- **无尾随空格**（pre-commit `trailing-whitespace` 强制）。
- **不用 emoji**：除非用户明确要求。

## Pythonic 风格

- **`is` 比较 `None`/`True`/`False`**：单例用 `is`，值用 `==`。
  `if x is None:` 正确；`if x == None:` 禁止（PEP 8 E711/E712）。
- **EAFP 优于 LBYL**：先尝试再处理异常，而非先检查再执行：
  ```python
  # 不好（LBYL，竞态窗口）
  if os.path.exists(path):
      with open(path) as f:
          ...
  # 好（EAFP）
  try:
      with open(path) as f:
          ...
  except FileNotFoundError:
      ...
  ```
  例外：检查成本低且无竞态时（如 `if not items:` 跳过空集合）可用 LBYL。
- **truthiness**：用 `if items:` / `if not items:` 而非
  `if len(items) > 0:` / `if items != []`。空容器/空串/0/None 均为假。
- **字符串格式化**：首选 f-string（`f"{name=}"` 调试格式 3.8+）；
  `format()` 用于模板/延迟绑定；`%` 仅用于 `logging` 延迟格式化（见"日志"）。
- **推导式**：list/dict/set 推导式优于 `map`+`filter`；但推导式 > 2 层时
  拆为显式循环（可读性优先）。
- **`enumerate` 索引**：需要索引时用 `for i, x in enumerate(seq)`，
  禁止 `for i in range(len(seq))`。
- **`zip` 并行**：并行迭代用 `zip(a, b)`；需要索引对齐用
  `zip(a, b, strict=True)`（3.10+，长度不等抛 ValueError）。
- **解包**：`a, b = pair` 优于 `a = pair[0]; b = pair[1]`；
  忽略值用 `_`（`a, _ = pair`）。
- **海象运算符 `:=`**（3.8+）：赋值+判断合一，避免重复求值：
  ```python
  if (n := len(data)) > threshold:
      logger.info("data size %d exceeds %d", n, threshold)
  ```
  但不滥用：简单赋值仍用普通 `=`。

## 日志

- **用 `logging.getLogger(__name__)`**：每个模块独立 logger，禁用 `print` 调试残留
  （提交前用 `git diff` 检查）。
- **结构化上下文**：用 `extra={...}` 传字段，而非字符串拼接；
  `logger.warning("task %r failed: %s", name, exc)` 优于 f-string（延迟格式化）。
- **日志级别**：`DEBUG` 详细诊断、`INFO` 关键流程、`WARNING` 可恢复异常、
  `ERROR` 需人工介入。捕获预期异常至少 `logger.warning` 并附 `exc_info=True`
  当需要堆栈时。
- **禁止日志密码/密钥**：脱敏后再记录。

## 可变默认参数

- **经典坑**：`def f(x=[])` / `def f(x={})` 的默认值在函数定义时求值一次，
  后续调用共享同一对象，导致跨调用状态泄漏。
- **哨兵模式**：用 `None` 作默认，函数体内初始化：
  ```python
  def f(items: list[int] | None = None) -> list[int]:
      if items is None:
          items = []
  ```
- **dataclass**：用 `field(default_factory=list)`（已在"数据结构"提及，
  普通函数同样适用此原则）。

## 路径处理

- **优先 `pathlib.Path`**：用 `Path("a") / "b"` 而非 `os.path.join("a", "b")`；
  ruff `PTH` 规则已启用并强制。
- **禁止字符串拼接路径**：`"a/" + name` 跨平台不安全（分隔符、注入风险）。
- **类型注解**：参数与返回用 `Path`，仅在边界（如 `os.environ`、CLI argv）
  接受 `str` 后立即 `Path(s)` 包装。
- **临时文件**：测试用 `tmp_path` fixture；生产代码用
  `tempfile.NamedTemporaryFile` 或 `contextlib.ExitStack` 管理。

## 资源管理

- **`with` 语句**：文件、锁、连接、临时目录一律用 `with` 或
  `contextlib.contextmanager`，确保异常路径也释放。
- **自定义资源**：实现 `__enter__`/`__exit__`；多个资源用
  `contextlib.ExitStack` 动态管理。
- **显式关闭**：长生命周期对象（连接池、线程池）实现 `close()` 并在
  `__del__` 或 `atexit` 兜底，但优先 `with`。
- **批量操作**：循环内多次 acquire/release 改为批量一次（如
  `backend.batch()` 包裹整个执行，见"并发与线程安全"）。

## 安全

- **禁用 `eval`/`exec`**：处理不可信输入时绝不使用；用 `ast.literal_eval`
  解析字面量，或专用解析器。
- **`subprocess`**：禁用 `shell=True` 除非命令完全可信；优先 `list[str]`
  形式 `cmd`，避免 shell 注入。
- **凭证不入仓**：密钥、token、密码放 `.env` 或环境变量，`.gitignore`
  必须包含 `.env`；代码中用 `os.environ.get("KEY")` 读取。
- **日志脱敏**：记录请求/响应时移除 `Authorization`、`password` 等字段。
- **依赖审计**：`uv lock` 后审阅新增依赖；避免引入已知 CVE 的包。

## 性能要点

- **避免重复计算**：循环内的 `resolved_spec`/`inspect.signature` 等查询应缓存
  或预构建映射（如 `{name: spec}`）。
- **避免双重查找**：`has(k)` + `get(k)` 改为单次 `get(k)` + `KeyError` 回退。
- **统一校验**：入口校验一次，下游路径不重复校验（如 `run()` 统一 `validate()`，
  `layers()` 不再重复）。
- **事件 emit**：任务生命周期必须 emit `RUNNING` → `SUCCESS`/`FAILED`/`SKIPPED`，
  不要留死分支（`# pragma: no cover` 是清理信号，应激活或删除）。

## Git 与提交

- **不自动提交**：除非用户明确要求。
- **不自动 push**：除非用户明确要求。
- **不修改 git config**。
- **不运行破坏性命令**（`push --force`/`reset --hard`/`clean -f`）除非用户明确要求。
- **staging**：按文件名添加，不用 `git add -A`/`git add .`，避免误加敏感文件。
- **commit message**：简洁，聚焦"为什么"而非"是什么"；遵循仓库既有风格。
