# Phase 1：交易基础设施 设计文档

**日期：** 2026-05-20
**范围：** 新建 `trading/` 包，实现数据层、模拟券商、风控引擎、Skills 管理四个基础设施模块。这是 TradingAgent（Phase 2）的依赖基础，不包含任何 Agent 逻辑或 FastAPI 路由。

---

## 背景

TradingAgent 需要四个基础设施：
1. 从 MySQL 读取沪深300日线数据并逐日推进
2. 模拟开平仓、管理资金和持仓
3. 硬性止损规则（单笔亏损 ≤ 2%）
4. 读写 `skills.md` 行为准则文件

---

## 包结构

```
trading/
├── __init__.py
├── data.py          # MarketDataFeed：从 MySQL 加载日线数据，逐日迭代
├── broker.py        # Broker：模拟开平仓，管理资金和持仓
├── risk_manager.py  # RiskManager：硬性止损规则（≤2%）
├── skills.py        # SkillsManager：读写 skills.md
└── skills.md        # 手动维护的初始行为准则（由用户编写）

tests/trading/
├── __init__.py
├── test_data.py
├── test_broker.py
├── test_risk_manager.py
└── test_skills.py
```

---

## 数据层 `trading/data.py`

从 MySQL `csi300_daily` 表一次性加载数据到内存，按 `trade_date` 升序排列，提供逐日迭代接口。

```python
@dataclass
class DailyBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int

class MarketDataFeed:
    def load(self, start_date: date, end_date: date) -> None
        """从 MySQL 加载指定日期范围的日线数据。"""

    def __iter__(self) -> Iterator[DailyBar]
        """逐日推进，每次返回一个 DailyBar。"""

    def current(self) -> DailyBar
        """返回当前迭代位置的 DailyBar。"""
```

数据库连接复用 `db/connection.py` 的 `get_connection()`。

---

## 模拟券商 `trading/broker.py`

全仓模式（每次开仓用全部可用资金），同一时间只持有一单。止损触发时自动平仓。

```python
@dataclass
class Position:
    entry_date: date
    entry_price: float
    direction: str        # "long" 或 "short"
    stop_loss: float      # 由 RiskManager 计算，不可超过入场价 ±2%
    size: float           # 持仓手数（equity / entry_price）

@dataclass
class Trade:
    entry_date: date
    exit_date: date
    direction: str
    entry_price: float
    exit_price: float
    pnl: float            # 盈亏金额
    pnl_pct: float        # 盈亏百分比（相对入场价）

class Broker:
    initial_capital: float = 100_000

    def open_position(self, bar: DailyBar, direction: str, stop_loss: float) -> Position
        """以当日收盘价开仓，全仓买入。"""

    def close_position(self, bar: DailyBar) -> Trade
        """以当日收盘价平仓，记录交易历史。"""

    def check_stop_loss(self, bar: DailyBar) -> bool
        """判断当日 low（多头）或 high（空头）是否触及止损价。"""

    @property
    def current_position(self) -> Position | None

    @property
    def equity(self) -> float
        """当前净值 = 初始资金 + 所有已平仓交易的盈亏之和。"""

    @property
    def trade_history(self) -> list[Trade]
```

---

## 风控引擎 `trading/risk_manager.py`

硬性规则，不可被任何 Agent 绕过。

```python
class RiskManager:
    MAX_LOSS_PCT: float = 0.02  # 单笔最大亏损 2%

    def calc_stop_loss(self, entry_price: float, direction: str) -> float:
        """
        多头：stop_loss = entry_price * (1 - 0.02)
        空头：stop_loss = entry_price * (1 + 0.02)
        """

    def validate_stop_loss(self, entry_price: float, stop_loss: float, direction: str) -> float:
        """
        校验止损是否在 2% 以内。
        超出则强制修正为 MAX_LOSS_PCT 对应的止损价并返回修正值。
        """
```

---

## Skills 管理 `trading/skills.py`

读写 `trading/skills.md`，该文件由用户手动维护初始内容。反思时 TradingAgent 通过 LLM 生成新内容后调用 `write()`。

```python
class SkillsManager:
    skills_path: str = "trading/skills.md"

    def read(self) -> str:
        """读取当前 skills.md 全文，供 TradingAgent 决策时参考。"""

    def write(self, content: str) -> None:
        """覆盖写入新内容（反思后调用）。"""
```

---

## 测试范围

| 测试文件 | 覆盖内容 |
|----------|---------|
| `tests/trading/test_data.py` | load() 加载数据；迭代顺序正确；current() 返回当前 bar |
| `tests/trading/test_broker.py` | 开仓后持仓正确；平仓后 trade_history 更新；止损触发判断；equity 计算 |
| `tests/trading/test_risk_manager.py` | calc_stop_loss 多头/空头；validate_stop_loss 超出时强制修正 |
| `tests/trading/test_skills.py` | read() 返回文件内容；write() 覆盖写入后 read() 返回新内容 |

---

## 对外接口（供 Phase 2 使用）

```python
from trading.data import MarketDataFeed, DailyBar
from trading.broker import Broker, Position, Trade
from trading.risk_manager import RiskManager
from trading.skills import SkillsManager
```

FastAPI 路由层在 Phase 2 之后单独添加，不在本 Phase 范围内。
