# TradingAgent + Reflection Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 TradingAgent 决策循环和 Reflection 反思机制，TradingAgent 每日根据 skills.md 通过 LLM 决定开平仓，连续 3 笔亏损时强制触发反思。

**Architecture:** TradingAgent 继承 BaseAgent，持有 Broker/RiskManager/SkillsManager/MarketDataFeed，主循环逐日推进；Reflection 独立封装连续亏损计数和反思执行逻辑，通过依赖注入接收 TradingAgent 和 SkillsManager；ScriptAgentTeam 通过依赖注入传入，不在 trading/ 内直接 import agents/。

**Tech Stack:** Python 3.11+, DeepSeek LLM（通过 BaseAgent._call_llm），json（解析 LLM 输出），re（提取 NEED_SCRIPT 标记）

---

## 文件结构

| 操作 | 路径 | 职责 |
|------|------|------|
| 新建 | `trading/reflection.py` | Reflection：连续亏损计数 + 反思执行 + NEED_SCRIPT 处理 |
| 新建 | `trading/trading_agent.py` | TradingAgent：LLM 决策方法 + 主循环 |
| 修改 | `trading/__init__.py` | 新增 TradingAgent、Reflection 导出 |
| 新建 | `tests/trading/test_reflection.py` | Reflection 单元测试 |
| 新建 | `tests/trading/test_trading_agent.py` | TradingAgent 决策方法测试 |

---

## Task 1: 实现 Reflection

**Files:**
- Create: `trading/reflection.py`
- Create: `tests/trading/test_reflection.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/trading/test_reflection.py
# 验证 Reflection 的连续亏损计数、触发逻辑和 NEED_SCRIPT 标记处理
import re
from datetime import date
from unittest.mock import MagicMock, patch
import pytest
from trading.broker import Trade
from trading.reflection import Reflection


def _make_trade(pnl: float) -> Trade:
    """构造测试用 Trade，只关心 pnl 值。"""
    return Trade(
        entry_date=date(2020, 1, 2),
        exit_date=date(2020, 1, 3),
        direction="long",
        entry_price=100.0,
        exit_price=100.0 + pnl / 1000,
        pnl=pnl,
        pnl_pct=pnl / 100_000,
    )


@pytest.fixture
def reflection():
    """创建 Reflection，注入 mock agent 和 skills_mgr。"""
    mock_agent = MagicMock()
    mock_agent.reflect.return_value = "# 修改后的 skills\n- 新规则"
    mock_skills = MagicMock()
    mock_skills.read.return_value = "# 原始 skills"
    return Reflection(agent=mock_agent, skills_mgr=mock_skills)


def test_no_trigger_on_profit(reflection):
    """盈利交易不触发反思，计数不增加。"""
    trade = _make_trade(pnl=100.0)
    triggered = reflection.check_and_trigger(trade, [trade])
    assert triggered is False
    assert reflection._consecutive_losses == 0


def test_count_increments_on_loss(reflection):
    """亏损交易使计数 +1，未达阈值不触发。"""
    trade = _make_trade(pnl=-100.0)
    triggered = reflection.check_and_trigger(trade, [trade])
    assert triggered is False
    assert reflection._consecutive_losses == 1


def test_profit_resets_count(reflection):
    """亏损后盈利，计数重置为 0。"""
    loss = _make_trade(pnl=-100.0)
    profit = _make_trade(pnl=100.0)
    reflection.check_and_trigger(loss, [loss])
    reflection.check_and_trigger(profit, [profit])
    assert reflection._consecutive_losses == 0


def test_triggers_on_third_consecutive_loss(reflection):
    """连续 3 笔亏损触发反思，计数重置为 0。"""
    loss = _make_trade(pnl=-100.0)
    for _ in range(2):
        reflection.check_and_trigger(loss, [loss])
    triggered = reflection.check_and_trigger(loss, [loss])
    assert triggered is True
    assert reflection._consecutive_losses == 0


def test_reflect_called_with_losing_trades(reflection):
    """触发反思时，agent.reflect 被调用，skills_mgr.write 被调用。"""
    loss = _make_trade(pnl=-100.0)
    for _ in range(3):
        reflection.check_and_trigger(loss, [loss] * 3)
    reflection._agent.reflect.assert_called_once()
    reflection._skills_mgr.write.assert_called_once()


def test_need_script_tag_triggers_script_team():
    """skills 中含 NEED_SCRIPT 标记时，调用 script_team.run()。"""
    mock_agent = MagicMock()
    mock_agent.reflect.return_value = (
        "# skills\n<!-- NEED_SCRIPT: 计算布林带 -->"
    )
    mock_skills = MagicMock()
    mock_skills.read.return_value = "# 原始 skills"

    mock_script_team = MagicMock()
    from agents.models import GeneratedScript, TestReport
    mock_script_team.run.return_value = (
        GeneratedScript(file_path="scripts/generated/20260520/calc.py", code="pass"),
        TestReport(passed=True),
    )

    ref = Reflection(agent=mock_agent, skills_mgr=mock_skills, script_team=mock_script_team)
    loss = _make_trade(pnl=-100.0)
    for _ in range(3):
        ref.check_and_trigger(loss, [loss] * 3)

    mock_script_team.run.assert_called_once()


def test_no_script_team_no_error():
    """没有注入 script_team 时，即使有 NEED_SCRIPT 标记也不报错。"""
    mock_agent = MagicMock()
    mock_agent.reflect.return_value = "# skills\n<!-- NEED_SCRIPT: 计算布林带 -->"
    mock_skills = MagicMock()
    mock_skills.read.return_value = "# 原始 skills"

    ref = Reflection(agent=mock_agent, skills_mgr=mock_skills, script_team=None)
    loss = _make_trade(pnl=-100.0)
    for _ in range(3):
        ref.check_and_trigger(loss, [loss] * 3)
    # 不报错即通过
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/trading/test_reflection.py -v
```

预期：`ImportError: cannot import name 'Reflection'`

- [ ] **Step 3: 实现 `trading/reflection.py`**

```python
# trading/reflection.py
# 反思机制：连续亏损计数，达到阈值时触发 LLM 反思并更新 skills.md。
# 可选调用 ScriptAgentTeam 处理 skills 中的 NEED_SCRIPT 标记。
import re
from trading.broker import Trade
from trading.skills import SkillsManager

# NEED_SCRIPT 标记的正则，用于从 skills 中提取脚本需求描述
_NEED_SCRIPT_RE = re.compile(r"<!--\s*NEED_SCRIPT:\s*(.+?)\s*-->")


class Reflection:
    """连续亏损计数器 + 反思执行器。每次平仓后调用 check_and_trigger()。"""

    # 连续亏损触发阈值，硬性规则
    CONSECUTIVE_LOSS_THRESHOLD: int = 3

    def __init__(self, agent, skills_mgr: SkillsManager, script_team=None):
        """
        Args:
            agent: TradingAgent 实例，提供 reflect() 方法。
            skills_mgr: SkillsManager，用于读写 skills.md。
            script_team: ScriptAgentTeam | None，可选，处理 NEED_SCRIPT 标记。
        """
        self._agent = agent
        self._skills_mgr = skills_mgr
        self._script_team = script_team
        self._consecutive_losses: int = 0  # 当前连续亏损计数

    def check_and_trigger(self, trade: Trade, recent_trades: list[Trade]) -> bool:
        """
        检查是否需要反思，需要则执行。

        Args:
            trade: 刚刚平仓的交易。
            recent_trades: 所有历史交易（含本次），用于传给 reflect()。

        Returns:
            True 表示触发了反思，False 表示未触发。
        """
        if trade.pnl < 0:
            self._consecutive_losses += 1
        else:
            # 盈利则重置连续亏损计数
            self._consecutive_losses = 0
            return False

        if self._consecutive_losses < self.CONSECUTIVE_LOSS_THRESHOLD:
            return False

        # 达到阈值，执行反思
        self._execute(recent_trades)
        self._consecutive_losses = 0  # 反思后重置计数
        return True

    def _execute(self, recent_trades: list[Trade]) -> None:
        """执行反思：调用 LLM 修改 skills，处理 NEED_SCRIPT 标记。"""
        # 取最近 CONSECUTIVE_LOSS_THRESHOLD 笔亏损交易作为反思素材
        losing_trades = [t for t in recent_trades if t.pnl < 0][-self.CONSECUTIVE_LOSS_THRESHOLD:]
        current_skills = self._skills_mgr.read()

        # LLM 分析亏损原因，返回修改后的 skills 全文
        new_skills = self._agent.reflect(losing_trades, current_skills)
        self._skills_mgr.write(new_skills)

        # 检测 NEED_SCRIPT 标记，有则调用脚本团队
        match = _NEED_SCRIPT_RE.search(new_skills)
        if match and self._script_team is not None:
            self._handle_script_request(match.group(1), new_skills)

    def _handle_script_request(self, description: str, current_skills: str) -> None:
        """处理 NEED_SCRIPT 标记：调用 ScriptAgentTeam，把结果追加到 skills。"""
        from agents.models import ScriptRequest
        request = ScriptRequest(
            task_description=description,
            input_data="csi300_daily 日线数据（MySQL）",
            output_format="文字分析结论",
        )
        script, report = self._script_team.run(request)
        # 将脚本路径和结论追加到 skills 末尾，供后续决策参考
        appendix = (
            f"\n\n## 脚本辅助分析结果\n"
            f"- 脚本路径：{script.file_path}\n"
            f"- 分析结论：{'通过' if report.passed else '未通过'}\n"
        )
        self._skills_mgr.write(current_skills + appendix)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/trading/test_reflection.py -v
```

预期：`7 passed`

---

## Task 2: 实现 TradingAgent

**Files:**
- Create: `trading/trading_agent.py`
- Create: `tests/trading/test_trading_agent.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/trading/test_trading_agent.py
# 验证 TradingAgent 的 LLM 决策方法（mock LLM，不依赖真实 API）
import json
from datetime import date
from unittest.mock import MagicMock, patch
import pytest
from trading.data import DailyBar
from trading.broker import Position, Trade
from trading.trading_agent import TradingAgent


def _make_bar(close=100.0, low=95.0, high=105.0):
    """构造测试用 DailyBar。"""
    return DailyBar(
        trade_date=date(2020, 1, 2),
        open=99.0, high=high, low=low, close=close, volume=1000
    )


def _make_position():
    """构造测试用 Position。"""
    return Position(
        entry_date=date(2020, 1, 2),
        entry_price=100.0,
        direction="long",
        stop_loss=98.0,
        size=1000.0,
    )


def _make_agent():
    """创建 TradingAgent，注入 mock 依赖。"""
    return TradingAgent(
        broker=MagicMock(),
        risk_manager=MagicMock(),
        skills_manager=MagicMock(),
        feed=MagicMock(),
    )


def test_decide_entry_returns_buy(monkeypatch):
    """decide_entry 解析 LLM 返回的 JSON，action=buy 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "buy", "reason": "均线金叉"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_entry(_make_bar(), "# skills", [])
    assert result["action"] == "buy"
    assert "reason" in result


def test_decide_entry_returns_hold(monkeypatch):
    """decide_entry 解析 LLM 返回的 JSON，action=hold 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "hold", "reason": "无信号"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_entry(_make_bar(), "# skills", [])
    assert result["action"] == "hold"


def test_decide_exit_returns_close(monkeypatch):
    """decide_exit 解析 LLM 返回的 JSON，action=close 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "close", "reason": "达到止盈目标"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_exit(_make_bar(), _make_position(), "# skills", [])
    assert result["action"] == "close"


def test_decide_exit_returns_hold(monkeypatch):
    """decide_exit 解析 LLM 返回的 JSON，action=hold 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "hold", "reason": "继续持有"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_exit(_make_bar(), _make_position(), "# skills", [])
    assert result["action"] == "hold"


def test_reflect_returns_string(monkeypatch):
    """reflect 返回修改后的 skills 字符串。"""
    agent = _make_agent()
    mock_response = "# 修改后的 skills\n- 新规则"
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.reflect([], "# 原始 skills")
    assert isinstance(result, str)
    assert len(result) > 0


def test_run_calls_decide_entry_when_no_position():
    """run() 空仓时调用 decide_entry。"""
    agent = _make_agent()
    bar = _make_bar()

    # mock feed 返回一个 bar
    agent._feed = [bar]
    agent._broker.current_position = None
    agent._broker.check_stop_loss.return_value = False
    agent._skills_manager.read.return_value = "# skills"

    with patch.object(agent, "decide_entry", return_value={"action": "hold", "reason": "test"}) as mock_entry:
        agent.run()

    mock_entry.assert_called_once()


def test_run_calls_decide_exit_when_has_position():
    """run() 有持仓时调用 decide_exit。"""
    agent = _make_agent()
    bar = _make_bar()

    agent._feed = [bar]
    agent._broker.current_position = _make_position()
    agent._broker.check_stop_loss.return_value = False
    agent._skills_manager.read.return_value = "# skills"

    with patch.object(agent, "decide_exit", return_value={"action": "hold", "reason": "test"}) as mock_exit:
        agent.run()

    mock_exit.assert_called_once()


def test_run_closes_on_stop_loss():
    """run() 触发止损时直接平仓，不调用 decide_exit。"""
    agent = _make_agent()
    bar = _make_bar()

    agent._feed = [bar]
    agent._broker.current_position = _make_position()
    agent._broker.check_stop_loss.return_value = True  # 触发止损
    agent._broker.close_position.return_value = Trade(
        entry_date=date(2020, 1, 2), exit_date=date(2020, 1, 3),
        direction="long", entry_price=100.0, exit_price=98.0,
        pnl=-2000.0, pnl_pct=-0.02,
    )
    agent._broker.trade_history = []

    with patch.object(agent, "decide_exit") as mock_exit:
        agent.run()

    mock_exit.assert_not_called()
    agent._broker.close_position.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/trading/test_trading_agent.py -v
```

预期：`ImportError: cannot import name 'TradingAgent'`

- [ ] **Step 3: 实现 `trading/trading_agent.py`**

```python
# trading/trading_agent.py
# TradingAgent：交易决策核心，每日根据 skills.md 通过 LLM 决定开平仓。
# 继承 BaseAgent 获得 DeepSeek LLM 调用能力。
import json
from agents.base_agent import BaseAgent
from trading.broker import Broker, Position, Trade
from trading.data import MarketDataFeed, DailyBar
from trading.risk_manager import RiskManager
from trading.skills import SkillsManager
from trading.reflection import Reflection

# 开仓决策的系统提示
_ENTRY_SYSTEM = """你是一个量化交易决策专家。
根据提供的行情数据和交易行为准则，决定是否开仓及方向。
输出必须是合法的 JSON，格式：{"action": "buy"/"sell"/"hold", "reason": "原因"}
不要包含任何额外说明。"""

# 平仓决策的系统提示
_EXIT_SYSTEM = """你是一个量化交易决策专家。
根据提供的行情数据、当前持仓和交易行为准则，决定是否平仓。
输出必须是合法的 JSON，格式：{"action": "close"/"hold", "reason": "原因"}
不要包含任何额外说明。"""

# 反思的系统提示
_REFLECT_SYSTEM = """你是一个量化交易策略优化专家。
分析连续亏损的原因，修改交易行为准则（skills.md）以避免类似错误。
直接输出修改后的完整 Markdown 内容，不要包含任何额外说明。
如果需要脚本辅助分析，在 skills 中加入标记：<!-- NEED_SCRIPT: <需求描述> -->"""


class TradingAgent(BaseAgent):
    """交易决策 Agent，每日根据 skills.md 通过 LLM 决定开平仓。"""

    def __init__(
        self,
        broker: Broker,
        risk_manager: RiskManager,
        skills_manager: SkillsManager,
        feed: MarketDataFeed,
        script_team=None,   # ScriptAgentTeam | None，反思时可选使用
        lookback: int = 10, # 传给 LLM 的历史行情窗口大小
    ):
        self._broker = broker
        self._risk_manager = risk_manager
        self._skills_manager = skills_manager
        self._feed = feed
        self._script_team = script_team
        self._lookback = lookback
        self._bar_history: list[DailyBar] = []  # 滚动保存最近 lookback 条行情

    def decide_entry(self, bar: DailyBar, skills: str, recent_bars: list[DailyBar]) -> dict:
        """
        空仓时决定是否开仓及方向。

        Returns:
            {"action": "buy"/"sell"/"hold", "reason": str}
        """
        bars_text = _format_bars(recent_bars)
        user_prompt = (
            f"交易行为准则：\n{skills}\n\n"
            f"最近行情（最新在最后）：\n{bars_text}\n\n"
            f"今日行情：日期={bar.trade_date} 开={bar.open} 高={bar.high} "
            f"低={bar.low} 收={bar.close} 量={bar.volume}\n\n"
            "请决定是否开仓。"
        )
        raw = self._call_llm(_ENTRY_SYSTEM, user_prompt)
        return json.loads(raw)

    def decide_exit(self, bar: DailyBar, position: Position, skills: str, recent_bars: list[DailyBar]) -> dict:
        """
        有持仓时决定是否平仓。

        Returns:
            {"action": "close"/"hold", "reason": str}
        """
        bars_text = _format_bars(recent_bars)
        user_prompt = (
            f"交易行为准则：\n{skills}\n\n"
            f"当前持仓：方向={position.direction} 入场价={position.entry_price} "
            f"止损价={position.stop_loss} 开仓日={position.entry_date}\n\n"
            f"最近行情（最新在最后）：\n{bars_text}\n\n"
            f"今日行情：日期={bar.trade_date} 开={bar.open} 高={bar.high} "
            f"低={bar.low} 收={bar.close} 量={bar.volume}\n\n"
            "请决定是否平仓。"
        )
        raw = self._call_llm(_EXIT_SYSTEM, user_prompt)
        return json.loads(raw)

    def reflect(self, losing_trades: list[Trade], skills: str) -> str:
        """
        分析连续亏损原因，返回修改后的 skills 全文（Markdown）。
        LLM 可在返回内容中写入 <!-- NEED_SCRIPT: ... --> 标记。
        """
        trades_text = "\n".join(
            f"- {t.entry_date}→{t.exit_date} {t.direction} "
            f"入场={t.entry_price:.2f} 出场={t.exit_price:.2f} "
            f"盈亏={t.pnl:.2f}({t.pnl_pct*100:.2f}%)"
            for t in losing_trades
        )
        user_prompt = (
            f"当前交易行为准则：\n{skills}\n\n"
            f"连续亏损的交易记录：\n{trades_text}\n\n"
            "请分析亏损原因并修改交易行为准则，返回完整的修改后 Markdown 内容。"
        )
        return self._call_llm(_REFLECT_SYSTEM, user_prompt)

    def run(self) -> None:
        """主循环：逐日推进，执行止损检查→平仓判断→开仓判断→反思检查。"""
        reflection = Reflection(
            agent=self,
            skills_mgr=self._skills_manager,
            script_team=self._script_team,
        )

        for bar in self._feed:
            # 更新历史行情窗口（滚动保留最近 lookback 条）
            self._bar_history.append(bar)
            if len(self._bar_history) > self._lookback:
                self._bar_history.pop(0)
            # 传给 LLM 的是不含当日的历史（当日单独传）
            recent_bars = self._bar_history[:-1]

            # 1. 止损检查（优先级最高，不经过 LLM）
            if self._broker.current_position and self._broker.check_stop_loss(bar):
                trade = self._broker.close_position(bar)
                reflection.check_and_trigger(trade, self._broker.trade_history)
                continue

            # 2. 有持仓 → LLM 决定是否平仓
            if self._broker.current_position:
                decision = self.decide_exit(
                    bar, self._broker.current_position,
                    self._skills_manager.read(), recent_bars,
                )
                if decision["action"] == "close":
                    trade = self._broker.close_position(bar)
                    reflection.check_and_trigger(trade, self._broker.trade_history)

            # 3. 空仓 → LLM 决定是否开仓
            else:
                decision = self.decide_entry(bar, self._skills_manager.read(), recent_bars)
                if decision["action"] in ("buy", "sell"):
                    direction = "long" if decision["action"] == "buy" else "short"
                    stop_loss = self._risk_manager.calc_stop_loss(bar.close, direction)
                    self._broker.open_position(bar, direction, stop_loss)


def _format_bars(bars: list[DailyBar]) -> str:
    """将 DailyBar 列表格式化为 LLM 可读的文本。"""
    if not bars:
        return "（无历史行情）"
    return "\n".join(
        f"{b.trade_date} 开={b.open} 高={b.high} 低={b.low} 收={b.close} 量={b.volume}"
        for b in bars
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/trading/test_trading_agent.py -v
```

预期：`8 passed`

---

## Task 3: 更新 trading/__init__.py 并全量验证

**Files:**
- Modify: `trading/__init__.py`

- [ ] **Step 1: 更新 `trading/__init__.py`**

```python
# trading 包：交易基础设施，供 TradingAgent 使用。
# 包含数据层、模拟券商、风控引擎、Skills 管理、交易Agent、反思机制六个模块。
from .data import MarketDataFeed, DailyBar
from .broker import Broker, Position, Trade
from .risk_manager import RiskManager
from .skills import SkillsManager
from .trading_agent import TradingAgent
from .reflection import Reflection
```

- [ ] **Step 2: 验证包可导入**

```bash
python -c "from trading import TradingAgent, Reflection; print('ok')"
```

预期：`ok`

- [ ] **Step 3: 运行全量测试**

```bash
python -m pytest tests/trading/ -v
```

预期：至少 38 passed（23 + 7 + 8）

- [ ] **Step 4: 语法检查新文件**

```bash
python -c "
import ast
files = [
    'trading/trading_agent.py',
    'trading/reflection.py',
    'trading/__init__.py',
]
for f in files:
    ast.parse(open(f, encoding='utf-8').read())
    print(f'OK  {f}')
"
```

预期：每行输出 `OK  <path>`，无报错
