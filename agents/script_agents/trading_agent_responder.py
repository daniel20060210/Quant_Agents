# agents/script_agents/trading_agent_responder.py
# TradingAgentResponder：LLM 扮演交易Agent，根据原始需求上下文自动回答 RequirementAgent 的疑问。
# 用于 alignment_node 的多轮对齐循环中，无需人工介入。
import json
from agents.base_agent import BaseAgent
from agents.models import ScriptRequest

# 系统提示：让 LLM 扮演熟悉量化交易系统的交易Agent
SYSTEM_PROMPT = """你是一个熟悉量化交易系统的交易Agent。
你的职责是根据你提出的需求上下文，回答需求分析专家的疑问。
只根据需求上下文作答，不编造超出范围的信息。
输出必须是合法的 JSON，不要包含任何额外说明。"""


class TradingAgentResponder(BaseAgent):
    """LLM 扮演交易Agent，根据原始需求上下文自动回答 RequirementAgent 的疑问。
    
    answers 列表长度与 questions 严格对应，一一作答。
    """

    def answer(self, request: ScriptRequest, questions: list[str]) -> list[str]:
        """
        逐条回答疑问列表，返回与 questions 等长的答案列表。

        Args:
            request: 原始任务请求，提供需求上下文
            questions: RequirementAgent 提出的疑问列表

        Returns:
            与 questions 等长的答案列表。questions 为空时直接返回空列表，不调用 LLM。
        """
        # 无疑问时直接返回，避免不必要的 LLM 调用
        if not questions:
            return []

        # 将问题列表格式化为编号文本，便于 LLM 逐条作答
        questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

        user_prompt = f"""你提出了以下需求，需求分析专家对此有一些疑问，请逐条回答：

你的需求：
任务描述：{request.task_description}
输入数据：{request.input_data}
期望输出格式：{request.output_format}

需求分析专家的疑问：
{questions_text}

请以如下 JSON 格式输出（不要有任何额外文字），answers 列表长度必须与疑问数量相同：
{{
  "answers": ["回答1", "回答2", ...]
}}"""

        raw = self._call_llm(SYSTEM_PROMPT, user_prompt)
        data = json.loads(raw)
        return data["answers"]
