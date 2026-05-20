# 包结构重组 + 需求对齐节点 设计文档

**日期：** 2026-05-19
**范围：**
1. 将 `agents/` 下的三个 Agent 文件迁移到 `agents/script_agents/` 子包
2. 新增 `TradingAgentResponder` 和 `alignment_node`，在生成规格书前完成多轮需求对齐

---

## 背景

现有 `RequirementAgent` 直接将自然语言需求转为 `ScriptSpec`，缺乏对齐步骤，可能导致规格书颗粒度与交易Agent预期不符。本次改造在外层图中插入 `alignment_node`，通过 LLM 多轮问答对齐需求，再生成规格书。

---

## 包结构变化

### 迁移（无逻辑变化）

| 原路径 | 新路径 |
|--------|--------|
| `agents/requirement_agent.py` | `agents/script_agents/requirement_agent.py` |
| `agents/engineer_agent.py` | `agents/script_agents/engineer_agent.py` |
| `agents/test_agent.py` | `agents/script_agents/test_agent.py` |

原文件迁移后删除。

### 新增文件

| 文件 | 职责 |
|------|------|
| `agents/script_agents/__init__.py` | 子包导出 |
| `agents/script_agents/trading_agent_responder.py` | LLM 扮演交易Agent，自动回答 RequirementAgent 的疑问 |
| `agents/graphs/alignment_node.py` | 封装多轮对齐循环，输出 `aligned_request` |

### 修改文件

| 文件 | 改动 |
|------|------|
| `agents/graphs/states.py` | `OuterState` 新增 `alignment_history`、`aligned_request` |
| `agents/graphs/outer_graph.py` | 入口改为 `alignment_node`；`requirement_node` 改用 `aligned_request` |
| `agents/__init__.py` | 更新导出路径至 `script_agents` |
| `agents/graphs/__init__.py` | 导出 `build_alignment_node` |

### 最终目录结构

```
agents/
├── base_agent.py
├── models.py
├── script_team.py
├── script_agents/
│   ├── __init__.py
│   ├── requirement_agent.py
│   ├── engineer_agent.py
│   ├── test_agent.py
│   └── trading_agent_responder.py
├── graphs/
│   ├── __init__.py
│   ├── states.py
│   ├── alignment_node.py
│   ├── inner_graph.py
│   └── outer_graph.py
└── __init__.py
```

---

## 外层图流程变化

```
旧：[requirement_node] → [inner_subgraph] → 条件路由
新：[alignment_node] → [requirement_node] → [inner_subgraph] → 条件路由（不变）
```

---

## OuterState 新增字段

```python
class OuterState(TypedDict):
    request: ScriptRequest           # 原始请求，不变
    aligned_request: Optional[ScriptRequest]  # 对齐后的增强请求，requirement_node 使用此字段
    alignment_history: list[dict]    # 每轮 Q&A，格式：[{"questions": [...], "answers": [...]}]
    spec: Optional[ScriptSpec]
    script: Optional[GeneratedScript]
    report: Optional[TestReport]
    requirement_retries: int
```

---

## 新增组件设计

### TradingAgentResponder

```python
class TradingAgentResponder(BaseAgent):
    def answer(self, request: ScriptRequest, questions: list[str]) -> list[str]:
        """
        根据原始需求上下文，逐条回答 RequirementAgent 的疑问。
        System prompt：扮演熟悉量化交易系统的交易Agent，只根据需求上下文作答，不编造超出范围的信息。
        返回与 questions 等长的答案列表。
        """
```

### RequirementAgent 新增方法

```python
def clarify(self, request: ScriptRequest, history: list[dict]) -> list[str] | None:
    """
    判断当前是否还有疑问。
    - 返回 list[str]：有疑问，列出问题列表
    - 返回 None：无疑问，可以生成规格书
    输出为 JSON：{"has_questions": true/false, "questions": [...]}
    """
```

原有 `analyze(request)` 签名不变，但调用方改为传入 `aligned_request`。

### alignment_node 循环逻辑

```
进入节点（MAX_ALIGNMENT_ROUNDS = 3）
  └── RequirementAgent.clarify(request, history)
        ├── 有问题 且 rounds < MAX_ALIGNMENT_ROUNDS
        │     → TradingAgentResponder.answer(request, questions)
        │     → 追加 {"questions": [...], "answers": [...]} 到 history
        │     → rounds += 1，继续循环
        └── 无问题 或 rounds >= MAX_ALIGNMENT_ROUNDS
              → 将 history 中所有 Q&A 拼接追加到 task_description
              → 写入 aligned_request
              → 节点结束
```

拼接格式示例（追加到 `task_description` 末尾）：

```
【需求对齐补充信息】
Q: 均线周期是固定的还是参数化的？
A: 参数化，调用方传入。
Q: 输出是序列还是最新一个值？
A: 完整序列。
```

---

## 测试范围

| 测试文件 | 覆盖内容 |
|----------|---------|
| `tests/script_agents/test_requirement_agent.py` | `clarify()` 返回问题列表 / 返回 None |
| `tests/script_agents/test_trading_agent_responder.py` | `answer()` 返回等长答案列表 |
| `tests/test_alignment_node.py` | 无疑问直接结束；多轮循环；达到上限强制结束 |
| `tests/test_outer_graph.py` | 更新：验证 `aligned_request` 被正确传入 `requirement_node` |

---

## 对外接口

`ScriptAgentTeam.run(request)` 签名和返回值不变。
