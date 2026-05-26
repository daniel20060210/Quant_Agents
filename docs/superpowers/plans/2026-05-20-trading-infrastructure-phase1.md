# 交易基础设施 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `trading/` 包，实现数据层、模拟券商、风控引擎、Skills 管理四个基础设施模块，供 TradingAgent（Phase 2）使用。

**Architecture:** `trading/` 是独立顶层包，与 `agents/` 平级。数据层从 MySQL `csi300_daily` 表加载沪深300日线数据；Broker 全仓模式模拟开平仓；RiskManager 硬性限制单笔亏损 ≤ 2%；SkillsManager 读写 `trading/skills.md` 行为准则文件。

**Tech Stack:** Python 3.11+, pymysql（复用 `db/connection.py`）

---

## 文件结构

| 操作 | 路径 | 职责 |
|------|------|------|
| 新建 | `trading/__init__.py` | 包导出 |
| 新建 | `trading/data.py` | `DailyBar` + `MarketDataFeed` |
| 新建 | 新建 | `trading/broker.py` | `Position` + `Trade` + `Broker` |
| 新建 | `trading/risk_manager.py` | `RiskManager` |
| 新建 | `trading/skills.py` | `SkillsManager` |
| 新建 | `trading/skills.md` | 初始行为准则（占位，用户手动填写） |
| 新建 | `tests/trading/__init__.py` | 测试子包 |
| 新建 | `tests/trading/test_data.py` | 数据层测试 |
| 新建 | `tests/trading/test_broker.py` | Broker 测试 |
| 新建 | `tests/trading/test_risk_manager.py` | RiskManager 测试 |
| 新建 | `tests/trading/test_skills.py` | SkillsManager 测试 |

---

## Task 1: 创建包骨架和 skills.md 占位文件

**Files:**
- Create: `trading/__init__.py`
- Create: `trading/skills.md`
- Create: `tests/trading/__init__.py`

- [ ] **Step 1: 创建目录和包文件**

```bash
mkdir -p trading tests/trading
touch trading/__init__.py tests/trading/__init__.py
```

- [ ] **Step 2: 创建 `trading/skills.md` 占位内容**

```markdown
# 交易行为准则（Skills）

## 入场条件
- （请在此填写你的入场规则）

## 出场条件
- （请在此填写你的出场规则）

## 仓位管理
- 每次全仓开仓
- 单笔亏损不超过 2%（硬性规则，由 RiskManager 强制执行）
```

- [ ] **Step 3: 更新 `trading/__init__.py`**

```python
# trading 包：交易基础设施，供 TradingAgent 使用
from .data import MarketDataFeed, DailyBar
from .broker import Broker, Position, Trade
from .risk_manager import RiskManager
from .skills import SkillsManager
```

- [ ] **Step 4: 验证包可导入**

```bash
python -c "import trading; print('ok')"
```

预期：`ok`（此时会报 ImportError，因为子模块还不存在，先跳过，Task 2 开始后再验证）

---

## Task 2: 实现 RiskManager

**Files:**
- Create: `trading/risk_manager.py`
- Create: `tests/trading/test_risk_manager.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/trading/test_risk_manager.py -v
```

预期：`ImportError: cannot import name 'RiskManager'`

- [ ] **Step 3: 实现 `trading/risk_manager.py`**

```python
# trading/risk_manager.py
# 风控引擎：硬性止损规则，单笔亏损不超过 2%，不可被任何 Agent 绕过。


class RiskManager:
    """硬性风控规则，强制限制单笔亏损上限。"""

    # 单笔最大亏损比例，硬性上限，不可配置
    MAX_LOSS_PCT: float = 0.02

    def calc_stop_loss(self, entry_price: float, direction: str) -> float:
        """
        按最大亏损比例计算止损价。

        多头：stop_loss = entry_price * (1 - MAX_LOSS_PCT)
        空头：stop_loss = entry_price * (1 + MAX_LOSS_PCT)
        """
        if direction == "long":
            return entry_price * (1 - self.MAX_LOSS_PCT)
        return entry_price * (1 + self.MAX_LOSS_PCT)

    def validate_stop_loss(self, entry_price: float, stop_loss: float, direction: str) -> float:
        """
        校验止损价是否在 MAX_LOSS_PCT 以内。
        超出则强制修正为 calc_stop_loss() 的结果并返回修正值。
        """
        limit = self.calc_stop_loss(entry_price, direction)
        if direction == "long":
            # 多头止损价不能低于 limit（亏损不能超过 2%）
            return max(stop_loss, limit)
        # 空头止损价不能高于 limit
        return min(stop_loss, limit)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/trading/test_risk_manager.py -v
```

预期：`6 passed`

---

## Task 3: 实现 SkillsManager

**Files:**
- Create: `trading/skills.py`
- Create: `tests/trading/test_skills.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/trading/test_skills.py
# 验证 SkillsManager 的读写行为
import os
import tempfile
import pytest
from trading.skills import SkillsManager


@pytest.fixture
def skills_manager(tmp_path):
    """使用临时文件，避免污染真实 skills.md"""
    path = str(tmp_path / "skills.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 初始内容\n- 规则A\n")
    return SkillsManager(skills_path=path)


def test_read_returns_file_content(skills_manager):
    """read() 返回 skills.md 的完整内容。"""
    content = skills_manager.read()
    assert "初始内容" in content
    assert "规则A" in content


def test_write_overwrites_content(skills_manager):
    """write() 覆盖写入后，read() 返回新内容。"""
    new_content = "# 新内容\n- 规则B\n"
    skills_manager.write(new_content)
    assert skills_manager.read() == new_content


def test_write_then_read_roundtrip(skills_manager):
    """多次写入后，read() 始终返回最新内容。"""
    skills_manager.write("第一次")
    skills_manager.write("第二次")
    assert skills_manager.read() == "第二次"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/trading/test_skills.py -v
```

预期：`ImportError: cannot import name 'SkillsManager'`

- [ ] **Step 3: 实现 `trading/skills.py`**

```python
# trading/skills.py
# Skills 管理：读写 trading/skills.md 行为准则文件。
# 反思时 TradingAgent 通过 LLM 生成新内容后调用 write() 覆盖。


class SkillsManager:
    """读写 skills.md 行为准则文件。"""

    def __init__(self, skills_path: str = "trading/skills.md"):
        # 支持注入自定义路径，便于测试时使用临时文件
        self.skills_path = skills_path

    def read(self) -> str:
        """读取当前 skills.md 全文，供 TradingAgent 决策时参考。"""
        with open(self.skills_path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, content: str) -> None:
        """覆盖写入新内容（反思后调用）。"""
        with open(self.skills_path, "w", encoding="utf-8") as f:
            f.write(content)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/trading/test_skills.py -v
```

预期：`3 passed`

---

## Task 4: 实现数据层 MarketDataFeed

**Files:**
- Create: `trading/data.py`
- Create: `tests/trading/test_data.py`

注意：`test_data.py` 的测试需要 mock MySQL 连接，不依赖真实数据库。

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/trading/test_data.py -v
```

预期：`ImportError: cannot import name 'MarketDataFeed'`

- [ ] **Step 3: 实现 `trading/data.py`**

```python
# trading/data.py
# 数据层：从 MySQL csi300_daily 表加载沪深300日线数据，提供逐日迭代接口。
from dataclasses import dataclass
from datetime import date
from typing import Iterator
from db.connection import get_connection


@dataclass
class DailyBar:
    """单日行情数据，对应 csi300_daily 表的一行。"""
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataFeed:
    """从 MySQL 加载日线数据，支持逐日迭代。数据一次性加载到内存。"""

    def __init__(self):
        self._bars: list[DailyBar] = []
        self._current_index: int = -1  # 当前迭代位置，-1 表示未开始

    def load(self, start_date: date, end_date: date) -> None:
        """从 MySQL 加载指定日期范围的日线数据，按 trade_date 升序排列。"""
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT trade_date, open, high, low, close, volume "
                "FROM csi300_daily "
                "WHERE trade_date BETWEEN %s AND %s "
                "ORDER BY trade_date ASC",
                (start_date, end_date),
            )
            rows = cursor.fetchall()
        conn.close()

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
        self._current_index = -1

    def __iter__(self) -> Iterator[DailyBar]:
        """逐日推进，每次 yield 一个 DailyBar，同时更新 current_index。"""
        for i, bar in enumerate(self._bars):
            self._current_index = i
            yield bar

    def current(self) -> DailyBar:
        """返回当前迭代位置的 DailyBar。必须在迭代开始后调用。"""
        if self._current_index < 0:
            raise RuntimeError("尚未开始迭代，请先调用 iter(feed) 并 next()")
        return self._bars[self._current_index]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/trading/test_data.py -v
```

预期：`4 passed`

---

## Task 5: 实现 Broker

**Files:**
- Create: `trading/broker.py`
- Create: `tests/trading/test_broker.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/trading/test_broker.py -v
```

预期：`ImportError: cannot import name 'Broker'`

- [ ] **Step 3: 实现 `trading/broker.py`**

```python
# trading/broker.py
# 模拟券商：全仓模式，同一时间只持有一单，以收盘价开平仓。
from dataclasses import dataclass, field
from datetime import date
from trading.data import DailyBar


@dataclass
class Position:
    """当前持仓信息。"""
    entry_date: date
    entry_price: float
    direction: str      # "long" 或 "short"
    stop_loss: float    # 由 RiskManager 计算并校验，不可超过入场价 ±2%
    size: float         # 持仓手数 = equity / entry_price


@dataclass
class Trade:
    """已平仓的交易记录。"""
    entry_date: date
    exit_date: date
    direction: str
    entry_price: float
    exit_price: float
    pnl: float          # 盈亏金额
    pnl_pct: float      # 盈亏百分比（相对入场价）


class Broker:
    """模拟券商，管理资金和持仓，执行开平仓操作。"""

    # 初始资金，全仓模式
    initial_capital: float = 100_000

    def __init__(self):
        self._position: Position | None = None
        self._trade_history: list[Trade] = []
        # 已实现盈亏累计，用于计算当前净值
        self._realized_pnl: float = 0.0

    def open_position(self, bar: DailyBar, direction: str, stop_loss: float) -> Position:
        """以当日收盘价开仓，全仓买入。size = equity / close。"""
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
        """以当日收盘价平仓，计算盈亏并记录到 trade_history。"""
        pos = self._position
        exit_price = bar.close

        if pos.direction == "long":
            pnl = (exit_price - pos.entry_price) * pos.size
            pnl_pct = (exit_price - pos.entry_price) / pos.entry_price
        else:
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
        self._realized_pnl += pnl
        self._trade_history.append(trade)
        self._position = None
        return trade

    def check_stop_loss(self, bar: DailyBar) -> bool:
        """判断当日行情是否触及止损价。多头看 low，空头看 high。"""
        if self._position is None:
            return False
        pos = self._position
        if pos.direction == "long":
            return bar.low <= pos.stop_loss
        return bar.high >= pos.stop_loss

    @property
    def current_position(self) -> Position | None:
        return self._position

    @property
    def equity(self) -> float:
        """当前净值 = 初始资金 + 所有已平仓交易的盈亏之和。"""
        return self.initial_capital + self._realized_pnl

    @property
    def trade_history(self) -> list[Trade]:
        return self._trade_history
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/trading/test_broker.py -v
```

预期：`9 passed`

---

## Task 6: 更新 trading/__init__.py 并运行全量测试

**Files:**
- Modify: `trading/__init__.py`

- [ ] **Step 1: 确认 `trading/__init__.py` 内容正确**

```python
# trading 包：交易基础设施，供 TradingAgent 使用
from .data import MarketDataFeed, DailyBar
from .broker import Broker, Position, Trade
from .risk_manager import RiskManager
from .skills import SkillsManager
```

- [ ] **Step 2: 验证包可导入**

```bash
python -c "from trading import MarketDataFeed, Broker, RiskManager, SkillsManager; print('ok')"
```

预期：`ok`

- [ ] **Step 3: 运行全量测试**

```bash
python -m pytest tests/trading/ -v
```

预期：`22 passed`（6 + 3 + 4 + 9）

- [ ] **Step 4: 语法检查所有新文件**

```bash
python -c "
import ast
files = [
    'trading/__init__.py',
    'trading/data.py',
    'trading/broker.py',
    'trading/risk_manager.py',
    'trading/skills.py',
]
for f in files:
    ast.parse(open(f, encoding='utf-8').read())
    print(f'OK  {f}')
"
```

预期：每行输出 `OK  <path>`，无报错
