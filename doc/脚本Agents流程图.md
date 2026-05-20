# 脚本Agents流程图

## 整体流程

```
交易Agent
  │
  │  ScriptRequest(task_description, input_data, output_format)
  ▼
ScriptAgentTeam.run()
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        外层图 OuterGraph                         │
│                                                                 │
│  ┌───────────────────────────────��──────────────────────────┐  │
│  │                   alignment_node（需求对齐）               │  │
│  │                                                          │  │
│  │   ┌─────────────────────────────────────────────────┐   │  │
│  │   │  循环（最多 MAX_ALIGNMENT_ROUNDS = 3 次）          │   │  │
│  │   │                                                 │   │  │
│  │   │  RequirementAgent.clarify(request, history)     │   │  │
│  │   │         │                                       │   │  │
│  │   │         ├── 有疑问 ──▶ TradingAgentResponder     │   │  │
│  │   │         │              .answer(request,         │   │  │
│  │   │         │               questions)              │   │  │
│  │   │         │              │                        │   │  │
│  │   │         │              ▼                        │   │  │
│  │   │         │         追加到 history                 │   │  │
│  │   │         │         继续下一轮                      │   │  │
│  │   │         │                                       │   │  │
│  │   │         └── 无疑问 / 达到上限 ──▶ 退出循环         │   │  │
│  │   └─────────────────────────────────────────────────┘   │  │
│  │                                                          │  │
│  │   将 history 中所有 Q&A 拼接追加到 task_description        │  │
│  │   输出 aligned_request                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               requirement_node（生成规格书）               │  │
│  │                                                          │  │
│  │   RequirementAgent.analyze(aligned_request)              │  │
│  │   输出 ScriptSpec                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                内层子图 InnerGraph                         │  │
│  │                                                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  循环（工程师最多重试 ENGINEER_RETRIES_LIMIT = 2 次）  │  │  │
│  │  │                                                    │  │  │
│  │  │  engineer_node                                     │  │  │
│  │  │  EngineerAgent.write_script(spec)                  │  │  │
│  │  │  （重试时 spec.logic_description 追加上次错误）       │  │  │
│  │  │         │                                          │  │  │
│  │  │         ▼                                          │  │  │
│  │  │  test_node                                         │  │  │
│  │  │  TestAgent.test(script, spec)                      │  │  │
│  │  │  ① 运行脚本（subprocess，超时 30s）                  │  │  │
│  │  │  ② LLM 审查代码 + 运行结果                           │  │  │
│  │  │         │                                          │  │  │
│  │  │         ├── passed=True  ──▶ 退出循环               │  │  │
│  │  │         │                                          │  │  │
│  │  │         └── passed=False                           │  │  │
│  │  │               ├── retries < 2 ──▶ increment        │  │  │
│  │  │               │                  retries，继续      │  │  │
│  │  │               └── retries >= 2 ──▶ 退出循环（失败）  │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│              route_after_inner 条件路由                          │
│                           │                                     │
│         ┌─────────────────┼──────────────────┐                 │
│         │                 │                  │                  │
│    passed=True     passed=False         passed=False            │
│         │          retries < 1          retries >= 1            │
│         ▼                │                   │                  │
│        END               ▼                   ▼                  │
│                 increment_requirement        END                │
│                 _retries                  （返回失败报告）        │
│                          │                                      │
│                          ▼                                      │
│                  requirement_node（重跑）                        │
│                  （跳过 alignment，直接用原 aligned_request）      │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
(GeneratedScript, TestReport)
  │
  ▼
交易Agent
```

---

## 数据结构流转

```
ScriptRequest
  task_description: str   ← 自然语言需求
  input_data: str         ← 数据来源描述
  output_format: str      ← 期望输出格式
      │
      │ alignment_node 追加 Q&A 补充信息
      ▼
aligned_request（ScriptRequest）
  task_description: str   ← 原始描述 + 【需求对齐补充信息】Q&A
      │
      │ RequirementAgent.analyze()
      ▼
ScriptSpec
  function_name: str
  parameters: List[Param]
  logic_description: str  ← 重试时追加上次测试错误
  expected_output: str
  test_cases: List[TestCase]
      │
      │ EngineerAgent.write_script()
      ▼
GeneratedScript
  file_path: str          ← scripts/generated/<YYYYMMDD>/<function_name>.py
  code: str
  dependencies: List[str]
      │
      │ TestAgent.test()
      ▼
TestReport
  passed: bool
  errors: List[str]       ← 失败时注入下一轮工程师节点
  suggestions: List[str]
```

---

## 重试策略汇总

| 层级 | 触发条件 | 上限 | 常量 |
|------|---------|------|------|
| 需求对齐（alignment_node） | RequirementAgent 有疑问 | 3 轮 | `MAX_ALIGNMENT_ROUNDS = 3` |
| 工程师重试（inner_graph） | TestAgent 测试不通过 | 2 次 | `ENGINEER_RETRIES_LIMIT = 2` |
| 需求重跑（outer_graph） | 内层全部失败 | 1 次 | `REQUIREMENT_RETRIES_LIMIT = 1` |

---

## 文件对应关系

| 节点 / 组件 | 文件 |
|------------|------|
| `alignment_node` | `agents/graphs/alignment_node.py` |
| `RequirementAgent` | `agents/script_agents/requirement_agent.py` |
| `TradingAgentResponder` | `agents/script_agents/trading_agent_responder.py` |
| `requirement_node` | `agents/graphs/outer_graph.py` |
| `EngineerAgent` | `agents/script_agents/engineer_agent.py` |
| `TestAgent` | `agents/script_agents/test_agent.py` |
| `inner_graph` | `agents/graphs/inner_graph.py` |
| `outer_graph` | `agents/graphs/outer_graph.py` |
| `OuterState / InnerState` | `agents/graphs/states.py` |
| `ScriptAgentTeam` | `agents/script_team.py` |
| 数据结构 | `agents/models.py` |
