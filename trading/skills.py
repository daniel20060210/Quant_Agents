# trading/skills.py
# Skills 管理：读写 trading/skills.md 行为准则文件。
# 反思时 TradingAgent 通过 LLM 生成新内容后调用 write() 覆盖。


class SkillsManager:
    """读写 skills.md 行为准则文件。支持注入自定义路径，便于测试。"""

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
