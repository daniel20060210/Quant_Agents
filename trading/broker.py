# trading/broker.py
# 模拟券商：全仓模式，同一时间只持有一单，以收盘价开平仓。
# 止损价由 RiskManager 计算并传入，Broker 只负责执行和记录。
from dataclasses import dataclass
from datetime import date
from trading.data import DailyBar


@dataclass
class Position:
    """当前持仓信息。"""
    entry_date: date        # 开仓日期
    entry_price: float      # 开仓价（收盘价）
    direction: str          # "long" 或 "short"
    stop_loss: float        # 止损价，由 RiskManager 计算并传入
    size: float             # 持仓手数 = equity / entry_price


@dataclass
class Trade:
    """已平仓的交易记录。"""
    entry_date: date        # 开仓日期
    exit_date: date         # 平仓日期
    direction: str          # "long" 或 "short"
    entry_price: float      # 开仓价
    exit_price: float       # 平仓价
    pnl: float              # 盈亏金额
    pnl_pct: float          # 盈亏百分比（相对入场价）


class Broker:
    """模拟券商，管理资金和持仓，执行开平仓操作。全仓模式，同一时间只持有一单。"""

    # 初始资金
    initial_capital: float = 100_000

    def __init__(self):
        self._position: Position | None = None   # 当前持仓，None 表示空仓
        self._trade_history: list[Trade] = []    # 已平仓交易记录列表
        self._realized_pnl: float = 0.0          # 已实现盈亏累计，用于计算净值

    def open_position(self, bar: DailyBar, direction: str, stop_loss: float) -> Position:
        """以当日收盘价开仓，全仓买入。size = equity / close。

        Args:
            bar: 当日行情数据，以 bar.close 作为开仓价。
            direction: "long" 做多 或 "short" 做空。
            stop_loss: 止损价，由外部 RiskManager 计算后传入。

        Returns:
            新建的 Position 对象。
        """
        # 全仓：用当前净值除以收盘价得到持仓手数
        size = self.equity / bar.close
        self._position = Position(
            entry_date=bar.trade_date,
            entry_price=bar.close,
            direction=direction,
            stop_loss=stop_loss,
            size=size,
        )
        return self._position

    def close_position(self, bar: DailyBar) -> Trade:
        """以当日收盘价平仓，计算盈亏并记录到 trade_history。

        Args:
            bar: 当日行情数据，以 bar.close 作为平仓价。

        Returns:
            已完成的 Trade 记录。
        """
        pos = self._position
        exit_price = bar.close

        if pos.direction == "long":
            # 多头盈亏 = (出场价 - 入场价) * 持仓手数
            pnl = (exit_price - pos.entry_price) * pos.size
            pnl_pct = (exit_price - pos.entry_price) / pos.entry_price
        else:
            # 空头盈亏 = (入场价 - 出场价) * 持仓手数
            pnl = (pos.entry_price - exit_price) * pos.size
            pnl_pct = (pos.entry_price - exit_price) / pos.entry_price

        trade = Trade(
            entry_date=pos.entry_date,
            exit_date=bar.trade_date,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
        )
        # 累计已实现盈亏，更新净值
        self._realized_pnl += pnl
        self._trade_history.append(trade)
        self._position = None  # 清空持仓
        return trade

    def check_stop_loss(self, bar: DailyBar) -> bool:
        """判断当日行情是否触及止损价。多头看 low，空头看 high。

        Args:
            bar: 当日行情数据。

        Returns:
            True 表示触发止损，False 表示未触发或无持仓。
        """
        if self._position is None:
            return False
        pos = self._position
        if pos.direction == "long":
            # 多头：当日最低价触及或跌破止损价则触发
            return bar.low <= pos.stop_loss
        # 空头：当日最高价触及或突破止损价则触发
        return bar.high >= pos.stop_loss

    @property
    def current_position(self) -> Position | None:
        """当前持仓，空仓时为 None。"""
        return self._position

    @property
    def equity(self) -> float:
        """当前净值 = 初始资金 + 所有已平仓交易的盈亏之和。"""
        return self.initial_capital + self._realized_pnl

    @property
    def trade_history(self) -> list[Trade]:
        """已平仓交易记录列表（只读视图）。"""
        return self._trade_history
