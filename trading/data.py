# trading/data.py
# 数据层：从 MySQL csi300_daily 表加载沪深300日线数据，提供逐日迭代接口。
# 数据一次性加载到内存（约2000条），按 trade_date 升序排列。
from dataclasses import dataclass
from datetime import date
from typing import Iterator
from db.connection import get_connection


@dataclass
class DailyBar:
    """单日行情数据，对应 csi300_daily 表的一行。"""
    trade_date: date   # 交易日期
    open: float        # 开盘价
    high: float        # 最高价
    low: float         # 最低价
    close: float       # 收盘价
    volume: int        # 成交量


class MarketDataFeed:
    """从 MySQL 加载日线数据，支持逐日迭代。数据一次性加载到内存。"""

    def __init__(self):
        self._bars: list[DailyBar] = []
        self._current_index: int = -1  # 当前迭代位置，-1 表示未开始

    def load(self, start_date: date, end_date: date) -> None:
        """从 MySQL 加载指定日期范围的日线数据，按 trade_date 升序排列。"""
        conn = get_connection()
        with conn.cursor() as cursor:
            # 查询指定日期范围内的所有日线数据，按日期升序
            cursor.execute(
                "SELECT trade_date, open, high, low, close, volume "
                "FROM csi300_daily "
                "WHERE trade_date BETWEEN %s AND %s "
                "ORDER BY trade_date ASC",
                (start_date, end_date),
            )
            rows = cursor.fetchall()
        conn.close()

        # 将查询结果转换为 DailyBar 对象列表
        self._bars = [
            DailyBar(
                trade_date=row[0],
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(row[5]),
            )
            for row in rows
        ]
        # 重置迭代位置，支持重复调用 load()
        self._current_index = -1

    def __iter__(self) -> Iterator[DailyBar]:
        """逐日推进，每次 yield 一个 DailyBar，同时更新 current_index。"""
        for i, bar in enumerate(self._bars):
            self._current_index = i  # 更新当前位置，使 current() 可用
            yield bar

    def current(self) -> DailyBar:
        """返回当前迭代位置的 DailyBar。必须在迭代开始后调用。"""
        if self._current_index < 0:
            raise RuntimeError("尚未开始迭代，请先调用 iter(feed) 并 next()")
        return self._bars[self._current_index]
