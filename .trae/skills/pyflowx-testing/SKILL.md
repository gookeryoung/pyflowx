---
name: "pyflowx-testing"
description: "PyFlowX 项目的测试编写规范与 mock 使用指南。在编写或审查测试、选择 mock 工具、设计 fixture、处理 asyncio 测试时调用。"
---

# PyFlowX 测试规范

本技能是 `.trae/rules/python-standards.md` 测试章节的详细展开。
规则文件仅保留硬约束指针，本文件提供完整操作指南。

## 总则

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

## Mock 工具选择（强制）

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

## monkeypatch 使用规范

- **类型注解**：fixture 参数标注 `monkeypatch: pytest.MonkeyPatch`。
- **作用域**：monkeypatch 自动在测试结束时撤销，**禁止**手动
  `monkeypatch.setattr(x, "y", original)` 恢复（多余且容易遗漏）。
  例外：在单个测试内需要中途恢复时，用 `monkeypatch.undo()` 全量撤销。
- **替换目标**：替换"被测代码看到的对象"，而非全局对象本身。
  - 错误：`monkeypatch.setattr("os.path.exists", fake)` —— 替换全局，影响其他模块。
  - 正确：`monkeypatch.setattr(pyflowx.command.shutil, "which", fake)` ——
    替换被测模块引用的 `shutil.which`。
- **属性 vs 字符串路径**：优先属性访问形式 `monkeypatch.setattr(obj, "attr", val)`
  而非字符串路径 `monkeypatch.setattr("pkg.mod.obj.attr", val)`，
  前者有 IDE 跳转与重构支持。
- **记录调用**：用闭包 `ran: list[tuple] = []` + `lambda *a, **k: ran.append((a, k))`
  替代 `MagicMock`，可读性更好且无需导入。

## Stub 与 Spy 模式

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

## 异常断言

- **`pytest.raises`**：必填 `match=` 正则（除非异常消息完全不可预测），
  避免误捕获同类异常：
  ```python
  with pytest.raises(StorageError, match="cannot write"):
      b.save("a", 1)
  ```
- **异常链**：验证 `__cause__` 时用 `exc_info.value.__cause__`，
  确认 `raise X from Y` 因果链完整。
- **禁止** `try/except + assert False`：用 `pytest.raises` 替代。

## Fixture 规范

- **`tmp_path`**：处理临时文件，自动清理，禁止 `tempfile.mkdtemp()` 手动管理。
- **`monkeypatch`**：环境变量、cwd、模块属性 mock（见上）。
- **`capsys`/`capfd`**：捕获 stdout/stderr，验证日志或命令输出。
- **autouse fixture**：仅在全局必需时用（如 `conftest.py` 的
  `packtool_tmp_workdir` 自动切到 tmp_path）；否则显式声明参数。
- **fixture 命名**：`snake_case`，描述"提供什么"而非"测试什么"
  （`sample_graph` 优于 `test_data`）。
- **fixture 作用域**：默认 `function`；`module`/`session` 仅当构造昂贵且
  只读时，并加注释说明无副作用。

## asyncio 测试

- **fixture `loop_scope="function"`**（pyproject 已配置默认值）。
- **async 测试**：`async def test_x():`，pytest-asyncio 自动驱动。
- **await 检查**：测试异步函数必须 `await` 结果，禁止仅验证返回 coroutine 对象。
- **异步 mock**：用 `AsyncMock`（3.8+ 在 `unittest.mock`）或
  `async def fake(): return value`，禁用 `MagicMock(return_value=coro)`。

## 参数化

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

## 测试组织

- **文件命名**：`test_<被测模块>.py`（`test_storage.py` 对应 `storage.py`）。
- **类分组**：仅在测试逻辑强相关时用 `class TestXxx:` 分组；默认用模块级函数。
- **docstring**：每个测试函数一句话说明"测试什么场景"，复杂场景补充"为什么"。
- **setup/teardown**：优先 fixture；`setup_method`/`teardown_method` 仅在
  无法用 fixture 表达时（罕见）。
