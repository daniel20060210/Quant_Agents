# tests/trading/test_reflection.py
# 验证 Reflection 的连续亏损计数、触发逻辑和 NEED_SCRIPT 标记处理
from datetime import date
from unittest.mock import MagicMock
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
