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
            # 多头：止损价在入场价下方 MAX_LOSS_PCT 处
            return entry_price * (1 - self.MAX_LOSS_PCT)
        # 空头：止损价在入场价上方 MAX_LOSS_PCT 处
        return entry_price * (1 + self.MAX_LOSS_PCT)

    def validate_stop_loss(self, entry_price: float, stop_loss: float, direction: str) -> float:
        """
        校验止损价是否在 MAX_LOSS_PCT 以内。
        超出则强制修正为 calc_stop_loss() 的结果并返回修正值。
        """
        # 计算允许的最大亏损对应的止损边界
        limit = self.calc_stop_loss(entry_price, direction)
        if direction == "long":
            # 多头止损价不能低于 limit（亏损不能超过 2%）
            return max(stop_loss, limit)
        # 空头止损价不能高于 limit
        return min(stop_loss, limit)
