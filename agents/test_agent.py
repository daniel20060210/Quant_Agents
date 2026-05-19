import subprocess
import sys
import json
from .base_agent import BaseAgent
from .models import GeneratedScript, ScriptSpec, TestReport

SYSTEM_PROMPT = """你是一个量化交易系统的测试工程师。
你的职责是审查Python脚本的代码质量，并结合运行结果判断脚本是否符合规格要求。
输出必须是合法的 JSON，不要包含任何额外说明。"""


class TestAgent(BaseAgent):
    """运行脚本并通过 LLM 审查代码质量，输出 TestReport。"""

    def test(self, script: GeneratedScript, spec: ScriptSpec) -> TestReport:
        """先实际运行脚本，再让 LLM 结合运行结果做代码审查。"""
        run_result = self._run_script(script.file_path)
        report = self._review(script, spec, run_result)
        return report

    def _run_script(self, file_path: str) -> dict:
        """subprocess 运行脚本，捕获 stdout/stderr，超时 30s。"""
        try:
            result = subprocess.run(
                [sys.executable, file_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:2000],
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "执行超时（>30s）"}
        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    def _review(self, script: GeneratedScript, spec: ScriptSpec, run_result: dict) -> TestReport:
        """将代码、规格和运行结果一起发给 LLM，要求返回 JSON 格式的审查结论。"""
        user_prompt = f"""请审查以下Python脚本是否符合规格要求：

【规格要求】
函数名：{spec.function_name}
逻辑描述：{spec.logic_description}
期望输出：{spec.expected_output}
测试用例：{[(tc.input, tc.expected_output) for tc in spec.test_cases]}

【脚本代码】
{script.code}

【运行结果】
返回码：{run_result["returncode"]}
标准输出：{run_result["stdout"]}
错误输出：{run_result["stderr"]}

请以如下 JSON 格式输出（不要有任何额外文字）：
{{
  "passed": true或false,
  "errors": ["错误1", "错误2"],
  "suggestions": ["改进建议1", "改进建议2"]
}}"""

        raw = self._call_llm(SYSTEM_PROMPT, user_prompt)
        data = json.loads(raw)

        return TestReport(
            passed=data["passed"],
            errors=data.get("errors", []),
            suggestions=data.get("suggestions", []),
        )
