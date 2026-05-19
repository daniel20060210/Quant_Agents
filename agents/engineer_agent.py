import os
import textwrap
from datetime import datetime
from .base_agent import BaseAgent
from .models import ScriptSpec, GeneratedScript

SYSTEM_PROMPT = """你是一个量化交易系统的Python工程师。
你的职责是根据规格书编写高质量、可直接运行的Python脚本。
只输出纯Python代码，不要包含任何说明文字或markdown代码块标记。"""


class EngineerAgent(BaseAgent):
    """工程师Agent：根据规格书编写Python脚本"""

    output_dir = "scripts/generated"

    def write_script(self, spec: ScriptSpec) -> GeneratedScript:
        user_prompt = f"""请根据以下规格书编写Python脚本：

函数名：{spec.function_name}
参数：{[f"{p.name}: {p.type} - {p.description}" for p in spec.parameters]}
逻辑描述：{spec.logic_description}
期望输出：{spec.expected_output}
测试用例：{[(tc.input, tc.expected_output) for tc in spec.test_cases]}

要求：
1. 只输出纯Python代码，不要有任何说明或markdown标记
2. 函数必须有类型注解
3. 包含必要的 import 语句
4. 代码末尾添加 if __name__ == "__main__": 示例调用"""

        code = self._call_llm(SYSTEM_PROMPT, user_prompt)
        code = self._strip_markdown(code)

        file_path = self._save_script(spec.function_name, code)
        dependencies = self._extract_imports(code)

        return GeneratedScript(
            file_path=file_path,
            code=code,
            dependencies=dependencies,
        )

    def _strip_markdown(self, code: str) -> str:
        lines = code.strip().splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines)

    def _save_script(self, function_name: str, code: str) -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        dir_path = os.path.join(self.output_dir, date_str)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{function_name}.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        return file_path

    def _extract_imports(self, code: str) -> list[str]:
        deps = []
        for line in code.splitlines():
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                module = line.split()[1].split(".")[0]
                if module not in ("os", "sys", "re", "json", "math", "datetime",
                                  "collections", "itertools", "functools", "typing"):
                    deps.append(module)
        return list(set(deps))
