# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_inner_graph.py -v

# Run a single test
python -m pytest tests/test_inner_graph.py::test_inner_graph_passes_on_first_try -v

# Run script_agents sub-package tests
python -m pytest tests/script_agents/ -v

# Run trading package tests
python -m pytest tests/trading/ -v
```

## Environment

Copy `.env` and fill in your key before running anything:
```
DEEPSEEK_API_KEY=your_key_here
```

The project uses DeepSeek API via OpenAI-compatible client (`base_url=https://api.deepseek.com`). All agents inherit from `BaseAgent` which loads this key via `python-dotenv`.

## Architecture

This is a quantitative trading Agent system. The current implementation covers the **Script Agent Team** — a pipeline that generates and validates Python analysis scripts on demand.

### Script Agent Team (`agents/`)

Four LLM-backed agents coordinated by a LangGraph multi-graph:

```
ScriptAgentTeam.run(ScriptRequest)
  └── OuterGraph (graphs/outer_graph.py)
        ├── alignment_node      → RequirementAgent.clarify() + TradingAgentResponder.answer()
        │                         多轮需求对齐，最多 3 轮，输出 aligned_request
        ├── requirement_node    → RequirementAgent.analyze(aligned_request) → ScriptSpec
        └── inner_subgraph      → InnerGraph (graphs/inner_graph.py)
              ├── engineer_node → EngineerAgent: ScriptSpec → .py file
              └── test_node     → TestAgent: runs script + LLM review → TestReport
```

**Retry strategy:** engineer retries up to 2×; if still failing, outer graph re-runs requirement analysis once (skipping alignment). Max total LLM calls per request: `3 (alignment) + (1+1) × (3+1) = 11`.

**Package layout:**
- `agents/script_agents/` — 所有脚本生成相关 Agent（RequirementAgent、EngineerAgent、TestAgent、TradingAgentResponder）
- `agents/graphs/` — LangGraph 图定义（alignment_node、inner_graph、outer_graph、states）
- `agents/base_agent.py` — BaseAgent 基类，封装 DeepSeek 调用
- `agents/models.py` — 数据结构（ScriptRequest、ScriptSpec、GeneratedScript、TestReport）
- `agents/script_team.py` — 对外入口，`ScriptAgentTeam.run()` 接口

**State types** (`agents/graphs/states.py`):
- `OuterState` — request, aligned_request, alignment_history, spec, script, report, requirement_retries
- `InnerState` — spec, script, report, engineer_retries, last_errors

**Data flow** (`agents/models.py`):
`ScriptRequest` → `aligned_request`（含 Q&A 补充）→ `ScriptSpec` → `GeneratedScript`（saved to `scripts/generated/<date>/`）→ `TestReport`

### Database (`db/`)

MySQL connection helpers. Config in `db/config.py` (host/port/user/password/database). Used for HS300 market data — not yet wired into the Agent pipeline.

### Trading Agent (`trading/`)

Six modules coordinated by `TradingAgent.run()`:

```
TradingAgent.run()
  ├── MarketDataFeed   → 从 MySQL csi300_daily 逐日迭代
  ├── Broker           → 全仓模拟开平仓（初始资金 100,000）
  ├── RiskManager      → 硬性止损 ≤ 2%（注意：doc/架构.md 写的 1% 是旧值，以代码为准）
  ├── SkillsManager    → 读写 trading/skills.md（用户手动维护初始内容）
  ├── Reflection       → 连续 3 笔亏损强制触发，可写 <!-- NEED_SCRIPT: ... --> 标记调用 ScriptAgentTeam
  └── ScriptAgentTeam  → 通过依赖注入传入，trading/ 包不直接 import agents/
```

### Planned but not yet implemented

FastAPI 服务层、WebSocket 推送事件。见 `doc/架构.md`。

---

## Code Style

**Comments are required** on all code: file-header comment, class docstring, method docstring, inline comments for non-obvious logic.

## Testing Patterns

- Mock LLM calls: `patch.object(agent, "_call_llm", return_value=json.dumps({...}))`
- Mock DB: `patch("trading.data.get_connection", return_value=mock_conn)` with `mock_conn.cursor().__enter__` returning a mock cursor
- All tests use `MagicMock` for dependencies — no real API or DB calls
