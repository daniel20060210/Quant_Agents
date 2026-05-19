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

Three LLM-backed agents coordinated by a LangGraph multi-graph:

```
ScriptAgentTeam.run(ScriptRequest)
  └── OuterGraph (outer_graph.py)
        ├── requirement_node  → RequirementAgent: natural language → ScriptSpec (JSON)
        └── inner_subgraph    → InnerGraph (inner_graph.py)
              ├── engineer_node → EngineerAgent: ScriptSpec → .py file
              └── test_node     → TestAgent: runs script + LLM review → TestReport
```

**Retry strategy:** engineer retries up to 2×; if still failing, outer graph re-runs requirement analysis once. Max total LLM calls per request: `(1 + 1) × (3 + 1) = 8`.

**State types** (`agents/graphs/states.py`):
- `OuterState` — request, spec, script, report, requirement_retries
- `InnerState` — spec, script, report, engineer_retries, last_errors

**Data flow** (`agents/models.py`):
`ScriptRequest` → `ScriptSpec` → `GeneratedScript` (saved to `scripts/generated/<date>/`) → `TestReport`

### Database (`db/`)

MySQL connection helpers. Config in `db/config.py` (host/port/user/password/database). Used for HS300 market data — not yet wired into the Agent pipeline.

### Planned but not yet implemented

See `doc/架构.md` for the full system design including: `TradingAgent`, `RiskManager` (hard ≤1% stop-loss), `Reflection` (triggers on 3 consecutive losses or 6% drawdown), `FastAPI` service layer, and WebSocket push events.
