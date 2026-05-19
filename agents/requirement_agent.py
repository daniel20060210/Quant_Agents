import json
from .base_agent import BaseAgent
from .models import ScriptRequest, ScriptSpec, Param, TestCase

SYSTEM_PROMPT = """你是一个量化交易系统的需求分析专家。
你的职责是将交易Agent的自然语言需求转化为清晰的脚本规格书，供工程师Agent编写代码。
输出必须是合法的 JSON，不要包含任何额外说明。"""


class RequirementAgent(BaseAgent):
    """将自然语言需求转化为结构化 ScriptSpec，供 EngineerAgent 使用。"""

    def analyze(self, request: ScriptRequest) -> ScriptSpec:
        """调用 LLM 生成规格书，解析 JSON 后返回 ScriptSpec。"""
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
