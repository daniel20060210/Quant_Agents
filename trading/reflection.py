# trading/reflection.py
# 反思机制：连续亏损计数，达到阈值时触发 LLM 反思并更新 skills.md。
# 可选调用 ScriptAgentTeam 处理 skills 中的 NEED_SCRIPT 标记。
import re
from trading.broker import Trade
from trading.skills import SkillsManager

# NEED_SCRIPT 标记的正则，用于从 skills 中提取脚本需求描述
_NEED_SCRIPT_RE = re.compile(r"<!--\s*NEED_SCRIPT:\s*(.+?)\s*-->")


class Reflection:
    """连续亏损计数器 + 反思执行器。每次平仓后调用 check_and_trigger()。"""

    # 连续亏损触发阈值，硬性规则
    CONSECUTIVE_LOSS_THRESHOLD: int = 3

    def __init__(self, agent, skills_mgr: SkillsManager, script_team=None):
        """
        Args:
            agent: TradingAgent 实例，提供 reflect() 方法。
            skills_mgr: SkillsManager，用于读写 skills.md。
            script_team: ScriptAgentTeam | None，可选，处理 NEED_SCRIPT 标记。
        """
        self._agent = agent
        self._skills_mgr = skills_mgr
        self._script_team = script_team
        self._consecutive_losses: int = 0  # 当前连续亏损计数

    def check_and_trigger(self, trade: Trade, recent_trades: list[Trade]) -> bool:
        """
        检查是否需要反思，需要则执行。

        Args:
            trade: 刚刚平仓的交易。
            recent_trades: 所有历史交易（含本次），用于传给 reflect()。

        Returns:
            True 表示触发了反思，False 表示未触发。
        """
        if trade.pnl < 0:
            self._consecutive_losses += 1
        else:
            # 盈利则重置连续亏损计数
            self._consecutive_losses = 0
            return False

        if self._consecutive_losses < self.CONSECUTIVE_LOSS_THRESHOLD:
            return False

        # 达到阈值，执行反思
        self._execute(recent_trades)
        self._consecutive_losses = 0  # 反思后重置计数
        return True

    def _execute(self, recent_trades: list[Trade]) -> None:
        """执行反思：调用 LLM 修改 skills，处理 NEED_SCRIPT 标记。"""
        # 取最近 CONSECUTIVE_LOSS_THRESHOLD 笔亏损交易作为反思素材
        losing_trades = [t for t in recent_trades if t.pnl < 0][-self.CONSECUTIVE_LOSS_THRESHOLD:]
        current_skills = self._skills_mgr.read()

        # LLM 分析亏损原因，返回修改后的 skills 全文
        new_skills = self._agent.reflect(losing_trades, current_skills)
        self._skills_mgr.write(new_skills)

        # 检测 NEED_SCRIPT 标记，有则调用脚本团队
        match = _NEED_SCRIPT_RE.search(new_skills)
        if match and self._script_team is not None:
            self._handle_script_request(match.group(1), new_skills)

    def _handle_script_request(self, description: str, current_skills: str) -> None:
        """处理 NEED_SCRIPT 标记：调用 ScriptAgentTeam，把结果追加到 skills。"""
        # 延迟导入避免 trading/ 直接依赖 agents/ 包
        from agents.models import ScriptRequest
        request = ScriptRequest(
            task_description=description,
            input_data="csi300_daily 日线数据（MySQL）",
            output_format="文字分析结论",
        )
        script, report = self._script_team.run(request)
        # 将脚本路径和结论追加到 skills 末尾，供后续决策参考
        appendix = (
            f"\n\n## 脚本辅助分析结果\n"
            f"- 脚本路径：{script.file_path}\n"
            f"- 分析结论：{'通过' if report.passed else '未通过'}\n"
        )
        self._skills_mgr.write(current_skills + appendix)
