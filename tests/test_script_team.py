# tests/test_script_team.py
# ScriptAgentTeam 的集成测试，验证对外接口 run() 的行为。
# 所有 Agent 均通过 MagicMock 替换，不产生真实 LLM 调用。
from unittest.mock import MagicMock
from agents.script_team import ScriptAgentTeam
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_spec():
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线",
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def _make_script():
    return GeneratedScript(
        file_path="scripts/generated/20260519/calc_ma.py",
        code="def calc_ma(): pass",
    )


def test_script_team_run_returns_script_and_report():
    """ScriptAgentTeam.run() 应返回 (GeneratedScript, TestReport) 元组，接口不因内部重构而改变。"""
    mock_req = MagicMock()
    mock_req.clarify.return_value = None  # 无疑问，跳过对齐轮次
    mock_req.analyze.return_value = _make_spec()

    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.return_value = TestReport(passed=True)

    team = ScriptAgentTeam(
        requirement_agent=mock_req,
        engineer_agent=mock_engineer,
        test_agent=mock_tester,
    )
    request = ScriptRequest(
        task_description="计算均线",
        input_data="收盘价列表",
        output_format="float列表",
    )
    script, report = team.run(request)

    assert isinstance(script, GeneratedScript)
    assert isinstance(report, TestReport)
    assert report.passed is True
