from dataclasses import dataclass, field
from typing import List


@dataclass
class Param:
    name: str
    type: str
    description: str


@dataclass
class TestCase:
    input: str
    expected_output: str


@dataclass
class ScriptRequest:
    """交易Agent 发给需求分析Agent 的任务描述。"""
    task_description: str  # 自然语言需求，如"计算20日布林带"
    input_data: str        # 数据来源描述
    output_format: str     # 期望的输出格式


@dataclass
class ScriptSpec:
    """需求分析Agent 输出的结构化规格书，供工程师Agent 编写代码。"""
    function_name: str
    parameters: List[Param]
    logic_description: str  # 重试时会追加上一版本的错误反馈
    expected_output: str
    test_cases: List[TestCase]


@dataclass
class GeneratedScript:
    """工程师Agent 生成的脚本，保存到 scripts/generated/<date>/ 目录。"""
    file_path: str
    code: str
    dependencies: List[str] = field(default_factory=list)  # 从 import 语句中提取的第三方包名


@dataclass
class TestReport:
    """测试Agent 的验收结论，passed=False 时 errors 会被注入下一轮工程师重试。"""
    passed: bool
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
