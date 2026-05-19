# LangGraph 脚本Agent团队 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 LangGraph 多图嵌套替换 `ScriptAgentTeam` 的手写循环，实现工程师重试2次→升级需求重跑1次的容错流程，对外接口不变。

**Architecture:** 外层图 `ScriptTeamGraph` 管理需求分析节点和内层子图的调度；内层子图 `EngineerTestGraph` 管理工程师节点和测试节点的重试循环。两层图各有独立的 TypedDict 状态，通过 `script_team.py` 薄包装对外暴露原有接口。

**Tech Stack:** Python 3.11+, langgraph, openai（DeepSeek 兼容），现有 agents 三个 Agent 类不变。

---

## 文件结构

| 操作 | 路径 | 职责 |
|------|------|------|
| 新建 | `agents/graphs/__init__.py` | 包入口 |
| 新建 | `agents/graphs/states.py` | `OuterState` / `InnerState` TypedDict |
| 新建 | `agents/graphs/inner_graph.py` | `EngineerTestGraph`：工程师+测试+重试 |
| 新建 | `agents/graphs/outer_graph.py` | `ScriptTeamGraph`：需求分析+内层子图+升级重跑 |
| 替换 | `agents/script_team.py` | 薄包装，委托给 `ScriptTeamGraph` |
| 更新 | `agents/__init__.py` | 导出不变，内部引用不变 |
| 新建 | `tests/test_inner_graph.py` | 内层图单元测试 |
| 新建 | `tests/test_outer_graph.py` | 外层图单元测试 |
| 新建 | `tests/test_script_team.py` | 集成测试（mock LLM） |

---

## Task 1: 安装依赖并创建 graphs 包

**Files:**
- Modify: `agents/graphs/__init__.py`（新建）

- [ ] **Step 1: 安装 langgraph**

```bash
pip install langgraph
```

预期输出：`Successfully installed langgraph-...`

- [ ] **Step 2: 验证安装**

```bash
python -c "import langgraph; print(langgraph.__version__)"
```

预期输出：版本号，无报错。

- [ ] **Step 3: 创建 graphs 包**

创建 `agents/graphs/__init__.py`，内容：

```python
from .inner_graph import build_inner_graph
from .outer_graph import build_outer_graph
```

- [ ] **Step 4: 提交**

```bash
git add agents/graphs/__init__.py
git commit -m "chore: add langgraph dependency and graphs package"
```

---

## Task 2: 定义图状态 TypedDict

**Files:**
- Create: `agents/graphs/states.py`
- Create: `tests/test_states.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_states.py`：

```python
from agents.graphs.states import OuterState, InnerState
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_request():
    return ScriptRequest(
        task_description="计算均线",
        input_data="收盘价列表",
        output_format="float列表",
    )


def _make_spec():
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线",
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def test_outer_state_defaults():
    state: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    assert state["requirement_retries"] == 0
    assert state["spec"] is None


def test_inner_state_defaults():
    state: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    assert state["engineer_retries"] == 0
    assert state["last_errors"] == []
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_states.py -v
```

预期：`ImportError: cannot import name 'OuterState'`

- [ ] **Step 3: 实现 states.py**

创建 `agents/graphs/states.py`：

```python
from typing import TypedDict, Optional
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport


class OuterState(TypedDict):
    request: ScriptRequest
    spec: Optional[ScriptSpec]
    script: Optional[GeneratedScript]
    report: Optional[TestReport]
    requirement_retries: int


class InnerState(TypedDict):
    spec: ScriptSpec
    script: Optional[GeneratedScript]
    report: Optional[TestReport]
    engineer_retries: int
    last_errors: list[str]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_states.py -v
```

预期：`2 passed`

- [ ] **Step 5: 提交**

```bash
git add agents/graphs/states.py tests/test_states.py
git commit -m "feat: add OuterState and InnerState TypedDict for LangGraph"
```

---

## Task 3: 实现内层子图 EngineerTestGraph

**Files:**
- Create: `agents/graphs/inner_graph.py`
- Create: `tests/test_inner_graph.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_inner_graph.py`：

```python
from unittest.mock import MagicMock, patch
from agents.graphs.inner_graph import build_inner_graph
from agents.graphs.states import InnerState
from agents.models import ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_spec(feedback=""):
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线" + feedback,
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def _make_script():
    return GeneratedScript(file_path="scripts/generated/20260519/calc_ma.py", code="def calc_ma(): pass")


def test_inner_graph_passes_on_first_try():
    """测试Agent第一次就通过时，图直接结束"""
    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.return_value = TestReport(passed=True)

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_engineer.write_script.call_count == 1
    assert mock_tester.test.call_count == 1


def test_inner_graph_retries_engineer_on_failure():
    """测试Agent失败时，工程师最多重试2次"""
    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.side_effect = [
        TestReport(passed=False, errors=["错误A"]),
        TestReport(passed=False, errors=["错误B"]),
        TestReport(passed=True),
    ]

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_engineer.write_script.call_count == 3


def test_inner_graph_exhausts_retries():
    """工程师重试2次后仍失败，图结束并返回失败报告"""
    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.return_value = TestReport(passed=False, errors=["持续错误"])

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    result = graph.invoke(init)

    assert result["report"].passed is False
    assert mock_engineer.write_script.call_count == 3  # 初次 + 2次重试


def test_inner_graph_injects_errors_into_spec():
    """重试时，上次错误应注入到 spec.logic_description"""
    injected_specs = []

    def capture_spec(spec):
        injected_specs.append(spec.logic_description)
        return _make_script()

    mock_engineer = MagicMock()
    mock_engineer.write_script.side_effect = capture_spec

    mock_tester = MagicMock()
    mock_tester.test.side_effect = [
        TestReport(passed=False, errors=["错误X"]),
        TestReport(passed=True),
    ]

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    graph.invoke(init)

    assert "错误X" in injected_specs[1]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_inner_graph.py -v
```

预期：`ImportError: cannot import name 'build_inner_graph'`

- [ ] **Step 3: 实现 inner_graph.py**

创建 `agents/graphs/inner_graph.py`：

```python
from langgraph.graph import StateGraph, END
from agents.graphs.states import InnerState
from agents.engineer_agent import EngineerAgent
from agents.test_agent import TestAgent

ENGINEER_RETRIES_LIMIT = 2


def build_inner_graph(
    engineer_agent: EngineerAgent | None = None,
    test_agent: TestAgent | None = None,
):
    engineer = engineer_agent or EngineerAgent()
    tester = test_agent or TestAgent()

    def engineer_node(state: InnerState) -> InnerState:
        spec = state["spec"]
        if state["last_errors"]:
            feedback = "\n\n【上一版本的问题，请修正】\n错误：\n"
            feedback += "\n".join(f"- {e}" for e in state["last_errors"])
            from agents.models import ScriptSpec
            spec = ScriptSpec(
                function_name=spec.function_name,
                parameters=spec.parameters,
                logic_description=spec.logic_description + feedback,
                expected_output=spec.expected_output,
                test_cases=spec.test_cases,
            )
        script = engineer.write_script(spec)
        return {**state, "spec": spec, "script": script}

    def test_node(state: InnerState) -> InnerState:
        report = tester.test(state["script"], state["spec"])
        return {**state, "report": report}

    def route_after_test(state: InnerState) -> str:
        if state["report"].passed:
            return "end"
        if state["engineer_retries"] < ENGINEER_RETRIES_LIMIT:
            return "retry_engineer"
        return "exhausted"

    def increment_retries(state: InnerState) -> InnerState:
        return {
            **state,
            "engineer_retries": state["engineer_retries"] + 1,
            "last_errors": state["report"].errors,
        }

    builder = StateGraph(InnerState)
    builder.add_node("engineer_node", engineer_node)
    builder.add_node("test_node", test_node)
    builder.add_node("increment_retries", increment_retries)

    builder.set_entry_point("engineer_node")
    builder.add_edge("engineer_node", "test_node")
    builder.add_conditional_edges(
        "test_node",
        route_after_test,
        {"end": END, "retry_engineer": "increment_retries", "exhausted": END},
    )
    builder.add_edge("increment_retries", "engineer_node")

    return builder.compile()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_inner_graph.py -v
```

预期：`4 passed`

- [ ] **Step 5: 提交**

```bash
git add agents/graphs/inner_graph.py tests/test_inner_graph.py
git commit -m "feat: implement EngineerTestGraph inner subgraph with retry logic"
```

---

## Task 4: 实现外层图 ScriptTeamGraph

**Files:**
- Create: `agents/graphs/outer_graph.py`
- Create: `tests/test_outer_graph.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_outer_graph.py`：

```python
from unittest.mock import MagicMock
from agents.graphs.outer_graph import build_outer_graph
from agents.graphs.states import OuterState
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_request():
    return ScriptRequest(
        task_description="计算均线",
        input_data="收盘价列表",
        output_format="float列表",
    )


def _make_spec():
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线",
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def _make_script():
    return GeneratedScript(file_path="scripts/generated/20260519/calc_ma.py", code="def calc_ma(): pass")


def test_outer_graph_success_first_try():
    """内层子图第一次就通过，外层直接结束"""
    mock_req = MagicMock()
    mock_req.analyze.return_value = _make_spec()

    mock_inner = MagicMock()
    mock_inner.invoke.return_value = {
        "spec": _make_spec(),
        "script": _make_script(),
        "report": TestReport(passed=True),
        "engineer_retries": 0,
        "last_errors": [],
    }

    graph = build_outer_graph(requirement_agent=mock_req, inner_graph=mock_inner)
    init: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_req.analyze.call_count == 1
    assert mock_inner.invoke.call_count == 1


def test_outer_graph_retries_requirement_on_inner_failure():
    """内层失败时，外层重跑需求分析一次"""
    mock_req = MagicMock()
    mock_req.analyze.return_value = _make_spec()

    mock_inner = MagicMock()
    mock_inner.invoke.side_effect = [
        {
            "spec": _make_spec(),
            "script": _make_script(),
            "report": TestReport(passed=False, errors=["持续错误"]),
            "engineer_retries": 2,
            "last_errors": ["持续错误"],
        },
        {
            "spec": _make_spec(),
            "script": _make_script(),
            "report": TestReport(passed=True),
            "engineer_retries": 0,
            "last_errors": [],
        },
    ]

    graph = build_outer_graph(requirement_agent=mock_req, inner_graph=mock_inner)
    init: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_req.analyze.call_count == 2
    assert mock_inner.invoke.call_count == 2


def test_outer_graph_fails_after_requirement_retry_exhausted():
    """需求重跑1次后内层仍失败，外层返回失败报告"""
    mock_req = MagicMock()
    mock_req.analyze.return_value = _make_spec()

    mock_inner = MagicMock()
    mock_inner.invoke.return_value = {
        "spec": _make_spec(),
        "script": _make_script(),
        "report": TestReport(passed=False, errors=["无法修复"]),
        "engineer_retries": 2,
        "last_errors": ["无法修复"],
    }

    graph = build_outer_graph(requirement_agent=mock_req, inner_graph=mock_inner)
    init: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    result = graph.invoke(init)

    assert result["report"].passed is False
    assert mock_req.analyze.call_count == 2   # 初次 + 1次重跑
    assert mock_inner.invoke.call_count == 2
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_outer_graph.py -v
```

预期：`ImportError: cannot import name 'build_outer_graph'`

- [ ] **Step 3: 实现 outer_graph.py**

创建 `agents/graphs/outer_graph.py`：

```python
from langgraph.graph import StateGraph, END
from agents.graphs.states import OuterState, InnerState
from agents.requirement_agent import RequirementAgent

REQUIREMENT_RETRIES_LIMIT = 1


def build_outer_graph(
    requirement_agent: RequirementAgent | None = None,
    inner_graph=None,
):
    req_agent = requirement_agent or RequirementAgent()
    inner = inner_graph or _default_inner()

    def requirement_node(state: OuterState) -> OuterState:
        spec = req_agent.analyze(state["request"])
        return {**state, "spec": spec}

    def inner_subgraph_node(state: OuterState) -> OuterState:
        inner_init: InnerState = {
            "spec": state["spec"],
            "script": None,
            "report": None,
            "engineer_retries": 0,
            "last_errors": [],
        }
        result = inner.invoke(inner_init)
        return {
            **state,
            "script": result["script"],
            "report": result["report"],
        }

    def route_after_inner(state: OuterState) -> str:
        if state["report"].passed:
            return "end"
        if state["requirement_retries"] < REQUIREMENT_RETRIES_LIMIT:
            return "retry_requirement"
        return "end"

    def increment_requirement_retries(state: OuterState) -> OuterState:
        return {**state, "requirement_retries": state["requirement_retries"] + 1}

    builder = StateGraph(OuterState)
    builder.add_node("requirement_node", requirement_node)
    builder.add_node("inner_subgraph", inner_subgraph_node)
    builder.add_node("increment_requirement_retries", increment_requirement_retries)

    builder.set_entry_point("requirement_node")
    builder.add_edge("requirement_node", "inner_subgraph")
    builder.add_conditional_edges(
        "inner_subgraph",
        route_after_inner,
        {"end": END, "retry_requirement": "increment_requirement_retries"},
    )
    builder.add_edge("increment_requirement_retries", "requirement_node")

    return builder.compile()


def _default_inner():
    from agents.graphs.inner_graph import build_inner_graph
    return build_inner_graph()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_outer_graph.py -v
```

预期：`3 passed`

- [ ] **Step 5: 提交**

```bash
git add agents/graphs/outer_graph.py tests/test_outer_graph.py
git commit -m "feat: implement ScriptTeamGraph outer graph with requirement retry"
```

---

## Task 5: 替换 script_team.py 为薄包装

**Files:**
- Modify: `agents/script_team.py`
- Create: `tests/test_script_team.py`

- [ ] **Step 1: 写集成测试**

创建 `tests/test_script_team.py`：

```python
from unittest.mock import MagicMock, patch
from agents.script_team import ScriptAgentTeam
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_spec():
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线",
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def _make_script():
    return GeneratedScript(file_path="scripts/generated/20260519/calc_ma.py", code="def calc_ma(): pass")


def test_script_team_run_returns_script_and_report():
    """ScriptAgentTeam.run() 返回 (GeneratedScript, TestReport) 元组"""
    mock_req = MagicMock()
    mock_req.analyze.return_value = _make_spec()

    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.return_value = TestReport(passed=True)

    team = ScriptAgentTeam(
        requirement_agent=mock_req,
        engineer_agent=mock_engineer,
        test_agent=mock_tester,
    )
    request = ScriptRequest(
        task_description="计算均线",
        input_data="收盘价列表",
        output_format="float列表",
    )
    script, report = team.run(request)

    assert isinstance(script, GeneratedScript)
    assert isinstance(report, TestReport)
    assert report.passed is True
```

- [ ] **Step 2: 运行测试，确认当前实现通过（基线）**

```bash
python -m pytest tests/test_script_team.py -v
```

预期：`1 passed`（旧实现也满足此接口）

- [ ] **Step 3: 替换 script_team.py**

完整替换 `agents/script_team.py`：

```python
from agents.models import ScriptRequest, GeneratedScript, TestReport
from agents.requirement_agent import RequirementAgent
from agents.engineer_agent import EngineerAgent
from agents.test_agent import TestAgent
from agents.graphs.inner_graph import build_inner_graph
from agents.graphs.outer_graph import build_outer_graph
from agents.graphs.states import OuterState


class ScriptAgentTeam:
    """脚本Agent团队：LangGraph 多图嵌套实现，对外接口不变"""

    def __init__(
        self,
        requirement_agent: RequirementAgent | None = None,
        engineer_agent: EngineerAgent | None = None,
        test_agent: TestAgent | None = None,
    ):
        inner = build_inner_graph(
            engineer_agent=engineer_agent,
            test_agent=test_agent,
        )
        self._graph = build_outer_graph(
            requirement_agent=requirement_agent,
            inner_graph=inner,
        )

    def run(self, request: ScriptRequest) -> tuple[GeneratedScript, TestReport]:
        init: OuterState = {
            "request": request,
            "spec": None,
            "script": None,
            "report": None,
            "requirement_retries": 0,
        }
        result = self._graph.invoke(init)
        return result["script"], result["report"]
```

- [ ] **Step 4: 运行全部测试，确认通过**

```bash
python -m pytest tests/ -v
```

预期：所有测试通过，无失败。

- [ ] **Step 5: 提交**

```bash
git add agents/script_team.py tests/test_script_team.py
git commit -m "feat: replace ScriptAgentTeam with LangGraph multi-graph implementation"
```

---

## Task 6: 更新 graphs/__init__.py 和 agents/__init__.py

**Files:**
- Modify: `agents/graphs/__init__.py`
- Modify: `agents/__init__.py`

- [ ] **Step 1: 更新 graphs/__init__.py**

```python
from .inner_graph import build_inner_graph
from .outer_graph import build_outer_graph
from .states import OuterState, InnerState
```

- [ ] **Step 2: 确认 agents/__init__.py 导出不变**

`agents/__init__.py` 当前内容：

```python
from .base_agent import BaseAgent
from .requirement_agent import RequirementAgent
from .engineer_agent import EngineerAgent
from .test_agent import TestAgent
from .script_team import ScriptAgentTeam
from .models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport, Param, TestCase
```

无需修改，导出接口完全不变。

- [ ] **Step 3: 运行全部测试**

```bash
python -m pytest tests/ -v
```

预期：所有测试通过。

- [ ] **Step 4: 语法检查所有新文件**

```bash
python -c "
import ast
files = [
    'agents/graphs/__init__.py',
    'agents/graphs/states.py',
    'agents/graphs/inner_graph.py',
    'agents/graphs/outer_graph.py',
    'agents/script_team.py',
]
for f in files:
    ast.parse(open(f, encoding='utf-8').read())
    print(f'OK  {f}')
"
```

预期：每行输出 `OK  <path>`，无报错。

- [ ] **Step 5: 提交**

```bash
git add agents/graphs/__init__.py
git commit -m "chore: finalize graphs package exports"
```
