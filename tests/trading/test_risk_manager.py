# tests/trading/test_risk_manager.py
# 验证 RiskManager 的止损计算和校验逻辑
import pytest
from trading.risk_manager import RiskManager


@pytest.fixture
def rm():
    return RiskManager()


def test_calc_stop_loss_long(rm):
    """多头止损 = 入场价 * (1 - 0.02)"""
    stop = rm.calc_stop_loss(entry_price=100.0, direction="long")
    assert abs(stop - 98.0) < 1e-9


def test_calc_stop_loss_short(rm):
    """空头止损 = 入场价 * (1 + 0.02)"""
    stop = rm.calc_stop_loss(entry_price=100.0, direction="short")
    assert abs(stop - 102.0) < 1e-9


def test_validate_stop_loss_within_limit_long(rm):
    """多头止损在 2% 以内，不修正，原值返回"""
    result = rm.validate_stop_loss(entry_price=100.0, stop_loss=99.0, direction="long")
    assert abs(result - 99.0) < 1e-9


def test_validate_stop_loss_exceeds_limit_long(rm):
    """多头止损超出 2%（止损价太低），强制修正为 98.0"""
    result = rm.validate_stop_loss(entry_price=100.0, stop_loss=95.0, direction="long")
    assert abs(result - 98.0) < 1e-9


def test_validate_stop_loss_within_limit_short(rm):
    """空头止损在 2% 以内，不修正"""
    result = rm.validate_stop_loss(entry_price=100.0, stop_loss=101.0, direction="short")
    assert abs(result - 101.0) < 1e-9


def test_validate_stop_loss_exceeds_limit_short(rm):
    """空头止损超出 2%（止损价太高），强制修正为 102.0"""
    result = rm.validate_stop_loss(entry_price=100.0, stop_loss=105.0, direction="short")
    assert abs(result - 102.0) < 1e-9
