# tests/trading/test_broker.py
# 验证 Broker 的开平仓、止损判断和净值计算
from datetime import date
import pytest
from trading.data import DailyBar
from trading.broker import Broker, Position, Trade


def _bar(trade_date=date(2020, 1, 2), open=100.0, high=105.0, low=95.0, close=102.0, volume=1000):
    """构造测试用 DailyBar。"""
    return DailyBar(trade_date=trade_date, open=open, high=high, low=low, close=close, volume=volume)


@pytest.fixture
def broker():
    return Broker()


def test_initial_state(broker):
    """初始状态：无持仓，净值等于初始资金。"""
    assert broker.current_position is None
    assert broker.equity == 100_000
    assert broker.trade_history == []


def test_open_long_position(broker):
    """开多仓后，持仓方向为 long，入场价为收盘价，size = equity / close。"""
    bar = _bar(close=100.0)
    pos = broker.open_position(bar, direction="long", stop_loss=98.0)
    assert pos.direction == "long"
    assert pos.entry_price == 100.0
    assert pos.stop_loss == 98.0
    assert abs(pos.size - 1000.0) < 1e-6  # 100_000 / 100.0
    assert broker.current_position is pos


def test_open_short_position(broker):
    """开空仓后，持仓方向为 short。"""
    bar = _bar(close=100.0)
    pos = broker.open_position(bar, direction="short", stop_loss=102.0)
    assert pos.direction == "short"


def test_close_long_position_profit(broker):
    """平多仓盈利：exit_price > entry_price，pnl > 0。"""
    open_bar = _bar(close=100.0)
    broker.open_position(open_bar, direction="long", stop_loss=98.0)

    close_bar = _bar(trade_date=date(2020, 1, 3), close=110.0)
    trade = broker.close_position(close_bar)

    assert trade.exit_price == 110.0
    assert trade.pnl > 0
    assert abs(trade.pnl_pct - 0.1) < 1e-6  # (110-100)/100
    assert broker.current_position is None
    assert len(broker.trade_history) == 1


def test_close_long_position_loss(broker):
    """平多仓亏损：exit_price < entry_price，pnl < 0。"""
    open_bar = _bar(close=100.0)
    broker.open_position(open_bar, direction="long", stop_loss=98.0)

    close_bar = _bar(trade_date=date(2020, 1, 3), close=98.0)
    trade = broker.close_position(close_bar)

    assert trade.pnl < 0
    assert abs(trade.pnl_pct - (-0.02)) < 1e-6


def test_equity_after_trade(broker):
    """平仓后净值 = 初始资金 + pnl。"""
    open_bar = _bar(close=100.0)
    broker.open_position(open_bar, direction="long", stop_loss=98.0)
    close_bar = _bar(trade_date=date(2020, 1, 3), close=110.0)
    trade = broker.close_position(close_bar)

    assert abs(broker.equity - (100_000 + trade.pnl)) < 1e-6


def test_check_stop_loss_long_triggered(broker):
    """多头：当日 low <= stop_loss，触发止损。"""
    open_bar = _bar(close=100.0)
    broker.open_position(open_bar, direction="long", stop_loss=98.0)

    # low=97.0 <= stop_loss=98.0，触发
    bar = _bar(low=97.0, high=105.0)
    assert broker.check_stop_loss(bar) is True


def test_check_stop_loss_long_not_triggered(broker):
    """多头：当日 low > stop_loss，不触发。"""
    open_bar = _bar(close=100.0)
    broker.open_position(open_bar, direction="long", stop_loss=98.0)

    bar = _bar(low=99.0, high=105.0)
    assert broker.check_stop_loss(bar) is False


def test_check_stop_loss_short_triggered(broker):
    """空头：当日 high >= stop_loss，触发止损。"""
    open_bar = _bar(close=100.0)
    broker.open_position(open_bar, direction="short", stop_loss=102.0)

    bar = _bar(low=95.0, high=103.0)
    assert broker.check_stop_loss(bar) is True


def test_check_stop_loss_no_position(broker):
    """无持仓时，check_stop_loss 返回 False。"""
    bar = _bar()
    assert broker.check_stop_loss(bar) is False
