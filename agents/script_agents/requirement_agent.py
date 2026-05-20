# agents/script_agents/requirement_agent.py
# 需求分析Agent：负责将交易Agent的自然语言需求转化为结构化规格书。
# 新增 clarify() 方法，在生成规格书前与交易Agent进行多轮问答对齐。
import json
from agents.base_agent import BaseAgent
from agents.models import ScriptRequest, ScriptSpec, Param, TestCase

# 生成规格书时使用的系统提示
SYSTEM_PROMPT = """你是一个量化交易系统的需求分析专家。
你的职责是将交易Agent的自然语言需求转化为清晰的脚本规格书，供工程师Agent编写代码。
输出必须是合法的 JSON，不要包含任何额外说明。"""

# 判断是否有疑问时使用的系统提示
CLARIFY_SYSTEM_PROMPT = """你是一个量化交易系统的需求分析专家。
你的职责是判断交易Agent的需求描述是否足够清晰，如有疑问则提出，否则返回无疑问。
输出必须是合法的 JSON，不要包含任何额外说明。"""


class RequirementAgent(BaseAgent):
    """将自然语言需求转化为结构化 ScriptSpec，供 EngineerAgent 使用。
    
    新增 clarify() 方法，在 analyze() 之前调用，用于多轮需求对齐。
    """

    def clarify(self, request: ScriptRequest, history: list[dict]) -> list[str] | None:
        """
        判断当前需求描述是否足够清晰，是否还有疑问。

        Args:
            request: 原始任务请求
            history: 已有的问答历史，格式 [{"questions": [...], "answers": [...]}]

        Returns:
            list[str]: 有疑问时返回问题列表
            None: 无疑问，可以直接生成规格书
        """
        # 将历史问答格式化为文本，供 LLM 参考
        history_text = ""
        for i, round_ in enumerate(history, 1):
            history_text += f"\n第{i}轮问答：\n"
            for q, a in zip(round_["questions"], round_["answers"]):
                history_text += f"  Q: {q}\n  A: {a}\n"

        user_prompt = f"""请判断以下需求描述是否足够清晰，可以直接编写脚本规格书。

任务描述：{request.task_description}
输入数据：{request.input_data}
期望输出格式：{request.output_format}
{f"已有问答记录：{history_text}" if history else ""}

请以如下 JSON 格式输出（不要有任何额外文字）：
{{
  "has_questions": true或false,
  "questions": ["疑问1", "疑问2"]
}}

如果没有疑问，questions 返回空列表。"""

        raw = self._call_llm(CLARIFY_SYSTEM_PROMPT, user_prompt)
        data = json.loads(raw)

        # has_questions 为 true 且有实际问题时才返回问题列表
        if data["has_questions"] and data["questions"]:
            return data["questions"]
        return None

    def analyze(self, request: ScriptRequest) -> ScriptSpec:
        """调用 LLM 生成规格书，解析 JSON 后返回 ScriptSpec。
        
        调用方应传入经过对齐的 aligned_request，而非原始 request。
        """
        user_prompt = f"""请根据以下需求生成脚本规格书：

任务描述：{request.task_description}
输入数据：{request.input_data}
期望输出格式：{request.output_format}

请以如下 JSON 格式输出（不要有任何额外文字）：
{{
  "function_name": "函数名（snake_case）",
  "parameters": [
    {{"name": "参数名", "type": "类型", "description": "说明"}}
  ],
  "logic_description": "详细的逻辑描述",
  "expected_output": "输出格式说明",
  "test_cases": [
    {{"input": "输入示例", "expected_output": "期望输出示例"}}
  ]
}}"""

        raw = self._call_llm(SYSTEM_PROMPT, user_prompt)
        data = json.loads(raw)

        return ScriptSpec(
            function_name=data["function_name"],
            parameters=[Param(**p) for p in data["parameters"]],
            logic_description=data["logic_description"],
            expected_output=data["expected_output"],
            test_cases=[TestCase(**tc) for tc in data["test_cases"]],
        )
