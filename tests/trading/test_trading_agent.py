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


def test_decide_entry_returns_buy():
    """decide_entry 解析 LLM 返回的 JSON，action=buy 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "buy", "reason": "均线金叉"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_entry(_make_bar(), "# skills", [])
    assert result["action"] == "buy"
    assert "reason" in result


def test_decide_entry_returns_hold():
    """decide_entry 解析 LLM 返回的 JSON，action=hold 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "hold", "reason": "无信号"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_entry(_make_bar(), "# skills", [])
    assert result["action"] == "hold"


def test_decide_exit_returns_close():
    """decide_exit 解析 LLM 返回的 JSON，action=close 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "close", "reason": "达到止盈目标"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_exit(_make_bar(), _make_position(), "# skills", [])
    assert result["action"] == "close"


def test_decide_exit_returns_hold():
    """decide_exit 解析 LLM 返回的 JSON，action=hold 时正确返回。"""
    agent = _make_agent()
    mock_response = json.dumps({"action": "hold", "reason": "继续持有"})
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.decide_exit(_make_bar(), _make_position(), "# skills", [])
    assert result["action"] == "hold"


def test_reflect_returns_string():
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
    agent._broker.check_stop_loss.return_value = True
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
