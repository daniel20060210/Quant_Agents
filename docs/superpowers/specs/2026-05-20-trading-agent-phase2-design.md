# Phase 2：TradingAgent + Reflection 设计文档

**日期：** 2026-05-20
**范围：** 新建 `trading/trading_agent.py` 和 `trading/reflection.py`，实现交易决策循环、LLM 决策方法和反思机制。依赖 Phase 1 的四个基础设施模块。

---

## 背景

Phase 1 提供了数据层、Broker、RiskManager、SkillsManager 四个基础设施。Phase 2 在此基础上实现：
1. TradingAgent：每日决策循环，LLM 根据 skills.md 决定开仓/平仓
2. Reflection：连续 3 笔亏损时强制触发，LLM 修改 skills，可选调用脚本辅助

---

## 文件结构

```
trading/
├── trading_agent.py    # TradingAgent：决策循环 + LLM 决策方法
├── reflection.py       # Reflection：反思触发和执行
└── __init__.py         # 更新导出

tests/trading/
├── test_trading_agent.py   # 决策方法测试（mock LLM）
└── test_reflection.py      # 反思触发逻辑测试
```

---

## TradingAgent `trading/trading_agent.py`

继承 `agents.base_agent.BaseAgent`，使用 DeepSeek LLM 做决策。

### 构造参数

```python
def __init__(
    self,
    broker: Broker,
    risk_manager: RiskManager,
    skills_manager: SkillsManager,
    feed: MarketDataFeed,
    script_team: ScriptAgentTeam | None = None,  # 可选，反思时使用
    lookback: int = 10,  # 传给 LLM 的历史行情窗口大小
)
```

### LLM 决策方法

```python
def decide_entry(self, bar: DailyBar, skills: str, recent_bars: list[DailyBar]) -> dict:
    """
    空仓时决定是否开仓及方向。
    返回 {"action": "buy"/"sell"/"hold", "reason": str}
    LLM 输出 JSON，action 只能是这三个值之一。
    """

def decide_exit(self, bar: DailyBar, position: Position, skills: str, recent_bars: list[DailyBar]) -> dict:
    """
    有持仓时决定是否平仓。
    返回 {"action": "close"/"hold", "reason": str}
    """

def reflect(self, losing_trades: list[Trade], skills: str) -> str:
    """
    分析连续亏损原因，返回修改后的 skills 全文（Markdown）。
    LLM 可在返回的 skills 中写入特殊标记：
    <!-- NEED_SCRIPT: <需求描述> -->
    表示需要脚本辅助决策，run() 检测到后调用 ScriptAgentTeam。
    """
```

### 主循环 `run()`

```python
def run(self) -> None:
    """逐日推进，执行完整交易循环。"""
    reflection = Reflection(
        agent=self,
        skills_mgr=self._skills_manager,
        script_team=self._script_team,
    )

    for bar in self._feed:
        recent_bars = self._get_recent_bars(bar)

        # 1. 止损检查（优先级最高，不经过 LLM）
        if self._broker.current_position and self._broker.check_stop_loss(bar):
            trade = self._broker.close_position(bar)
            reflection.check_and_trigger(trade, self._broker.trade_history)
            continue

        # 2. 有持仓 → LLM 决定是否平仓
        if self._broker.current_position:
            decision = self.decide_exit(
                bar, self._broker.current_position,
                self._skills_manager.read(), recent_bars
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
```

---

## Reflection `trading/reflection.py`

### 连续亏损计数器

- 平仓盈利（`pnl >= 0`）→ 重置为 0
- 平仓亏损（`pnl < 0`）→ +1，达到 `CONSECUTIVE_LOSS_THRESHOLD = 3` 时触发反思并重置为 0

### 反思流程

```
check_and_trigger(trade, recent_trades)
  │
  ├── 更新连续亏损计数
  │
  └── 计数 >= 3？
        │
        ├── 否 → 返回 False
        │
        └── 是 → 执行反思
                  1. 收集最近 3 笔亏损交易
                  2. agent.reflect(losing_trades, skills_mgr.read()) → new_skills
                  3. skills_mgr.write(new_skills)
                  4. 检测 <!-- NEED_SCRIPT: ... --> 标记
                       有 → ScriptAgentTeam.run(ScriptRequest(...))
                             把脚本结果追加到 skills 末尾
                       无 → 结束
                  5. 重置计数器
                  6. 返回 True
```

### 接口

```python
class Reflection:
    CONSECUTIVE_LOSS_THRESHOLD: int = 3  # 连续亏损触发阈值

    def __init__(
        self,
        agent,                              # TradingAgent（避免循环导入用 Any）
        skills_mgr: SkillsManager,
        script_team=None,                   # ScriptAgentTeam | None
    )

    def check_and_trigger(self, trade: Trade, recent_trades: list[Trade]) -> bool:
        """检查是否需要反思，需要则执行，返回是否触发了反思。"""
```

---

## 脚本工具集成

反思时 LLM 可在返回的 skills 中写入：
```
<!-- NEED_SCRIPT: 计算最近20日布林带，判断当前价格位置 -->
```

`Reflection` 检测到此标记后：
1. 提取需求描述
2. 调用 `ScriptAgentTeam.run(ScriptRequest(task_description=..., input_data="csi300_daily 日线数据", output_format="文字分析结论"))`
3. 将返回的 `TestReport` 中的脚本路径和结论追加到 skills 末尾

---

## 测试范围

| 测试文件 | 覆盖内容 |
|----------|---------|
| `tests/trading/test_trading_agent.py` | decide_entry 返回合法 action；decide_exit 返回合法 action；reflect 返回字符串 |
| `tests/trading/test_reflection.py` | 连续亏损计数正确；未达阈值不触发；达到阈值触发并重置；触发时调用 agent.reflect 和 skills_mgr.write；检测 NEED_SCRIPT 标记时调用 script_team |

---

## 对外接口

```python
from trading.trading_agent import TradingAgent
from trading.reflection import Reflection
```

`ScriptAgentTeam` 通过依赖注入传入，不在 trading/ 包内直接 import agents/。
