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
