# LangGraph 脚本Agent团队改造设计

**日期：** 2026-05-19  
**范围：** 将 `agents/script_team.py` 的手写循环替换为 LangGraph 多图嵌套实现

---

## 背景

现有 `ScriptAgentTeam` 用 Python for 循环协调三个 Agent（需求分析 → 工程师 → 测试），重试逻辑硬编码在 `run()` 方法中。改用 LangGraph 后，流程变为显式有向图，状态可序列化，节点职责清晰，后续扩展（并行、人工干预等）更容易。

---

## 重试策略

选用策略 C：工程师节点最多重试 2 次；若仍失败，升级到外层重跑需求分析节点 1 次；再失败则返回失败报告。

---

## 图结构

### 外层图 `ScriptTeamGraph`

```
[requirement_node] → [inner_subgraph] → 条件边
                                          ├─ passed            → END
                                          ├─ retry_requirement → [requirement_node]（requirement_retries < 1）
                                          └─ failed            → END
```

### 内层子图 `EngineerTestGraph`

```
[engineer_node] → [test_node] → 条件边
                                  ├─ passed          → END
                                  ├─ retry_engineer  → [engineer_node]（engineer_retries < 2）
                                  └─ exhausted       → END
```

---

## 状态定义

**外层状态 `OuterState`（TypedDict）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `request` | `ScriptRequest` | 原始任务请求 |
| `spec` | `ScriptSpec \| None` | 需求分析输出 |
| `script` | `GeneratedScript \| None` | 最终生成脚本 |
| `report` | `TestReport \| None` | 最终测试报告 |
| `requirement_retries` | `int` | 需求分析已重跑次数，上限 1 |

**内层状态 `InnerState`（TypedDict）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `spec` | `ScriptSpec` | 来自外层的规格书 |
| `script` | `GeneratedScript \| None` | 工程师输出 |
| `report` | `TestReport \| None` | 测试输出 |
| `engineer_retries` | `int` | 工程师已重试次数，上限 2 |
| `last_errors` | `list[str]` | 上次测试错误，注入工程师节点 |

---

## 节点职责

### 外层节点

- **`requirement_node`**：调用 `RequirementAgent.analyze(state.request)`，写入 `state.spec`
- **`inner_subgraph`**：以当前 `state.spec` 初始化内层图并运行，将结果写回 `state.script` 和 `state.report`

### 外层条件边（`route_after_inner`）

- `report.passed` → `"end"`
- `not report.passed` 且 `requirement_retries < 1` → `"requirement_node"`（`requirement_retries += 1`）
- 否则 → `"end"`

### 内层节点

- **`engineer_node`**：调用 `EngineerAgent.write_script(spec)`，若 `last_errors` 非空则先注入错误反馈到 `spec.logic_description`
- **`test_node`**：调用 `TestAgent.test(script, spec)`，写入 `state.report`

### 内层条件边（`route_after_test`）

- `report.passed` → `"end"`
- `not report.passed` 且 `engineer_retries < 2` → `"engineer_node"`（`engineer_retries += 1`，更新 `last_errors`）
- 否则 → `"end"`

---

## 文件结构

```
agents/
├── base_agent.py          # 不变
├── models.py              # 不变（TypedDict 状态定义放 graphs/states.py）
├── requirement_agent.py   # 不变
├── engineer_agent.py      # 不变
├── test_agent.py          # 不变
├── graphs/
│   ├── __init__.py
│   ├── states.py          # OuterState / InnerState TypedDict
│   ├── inner_graph.py     # EngineerTestGraph
│   └── outer_graph.py     # ScriptTeamGraph
├── script_team.py         # 替换为薄包装，对外接口不变
└── __init__.py            # 更新导出
```

---

## 对外接口（不变）

```python
team = ScriptAgentTeam()
script, report = team.run(ScriptRequest(
    task_description="...",
    input_data="...",
    output_format="...",
))
```

---

## 依赖

新增：`langgraph`（`pip install langgraph`）  
现有依赖不变。
