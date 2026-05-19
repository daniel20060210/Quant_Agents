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
    """交易Agent → 需求分析Agent"""
    task_description: str
    input_data: str
    output_format: str


@dataclass
class ScriptSpec:
    """需求分析Agent → 工程师Agent"""
    function_name: str
    parameters: List[Param]
    logic_description: str
    expected_output: str
    test_cases: List[TestCase]


@dataclass
class GeneratedScript:
    """工程师Agent → 测试Agent"""
    file_path: str
    code: str
    dependencies: List[str] = field(default_factory=list)


@dataclass
class TestReport:
    """测试Agent → 交易Agent"""
    passed: bool
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
