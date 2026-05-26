# tests/trading/test_data.py
# 验证 MarketDataFeed 的加载和迭代行为（mock MySQL，不依赖真实数据库）
from datetime import date
from unittest.mock import patch, MagicMock
import pytest
from trading.data import MarketDataFeed, DailyBar


def _make_rows():
    """构造模拟的数据库查询结果，按日期升序。"""
    return [
        (date(2020, 1, 2), 4000.0, 4050.0, 3980.0, 4020.0, 1000000),
        (date(2020, 1, 3), 4020.0, 4080.0, 4010.0, 4060.0, 1100000),
        (date(2020, 1, 6), 4060.0, 4100.0, 4040.0, 4090.0, 900000),
    ]


@pytest.fixture
def feed():
    """创建已加载数据的 MarketDataFeed（mock 数据库）。"""
    feed = MarketDataFeed()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = _make_rows()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("trading.data.get_connection", return_value=mock_conn):
        feed.load(date(2020, 1, 1), date(2020, 1, 31))
    return feed


def test_load_creates_daily_bars(feed):
    """load() 后，数据按日期升序加载为 DailyBar 列表。"""
    bars = list(feed)
    assert len(bars) == 3
    assert bars[0].trade_date == date(2020, 1, 2)
    assert bars[2].trade_date == date(2020, 1, 6)


def test_daily_bar_fields(feed):
    """DailyBar 包含正确的 open/high/low/close/volume 字段。"""
    bars = list(feed)
    bar = bars[0]
    assert bar.open == 4000.0
    assert bar.high == 4050.0
    assert bar.low == 3980.0
    assert bar.close == 4020.0
    assert bar.volume == 1000000


def test_current_returns_last_iterated_bar(feed):
    """迭代过程中，current() 返回当前 bar。"""
    it = iter(feed)
    next(it)  # 推进到第一个 bar
    assert feed.current().trade_date == date(2020, 1, 2)
    next(it)  # 推进到第二个 bar
    assert feed.current().trade_date == date(2020, 1, 3)


def test_iteration_is_ordered(feed):
    """迭代顺序严格按 trade_date 升序。"""
    dates = [bar.trade_date for bar in feed]
    assert dates == sorted(dates)
