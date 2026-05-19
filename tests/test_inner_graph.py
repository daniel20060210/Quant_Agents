from unittest.mock import MagicMock
from agents.graphs.inner_graph import build_inner_graph
from agents.graphs.states import InnerState
from agents.models import ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_spec(feedback=""):
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线" + feedback,
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def _make_script():
    return GeneratedScript(file_path="scripts/generated/20260519/calc_ma.py", code="def calc_ma(): pass")


def test_inner_graph_passes_on_first_try():
    """测试Agent第一次就通过时，图直接结束"""
    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.return_value = TestReport(passed=True)

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_engineer.write_script.call_count == 1
    assert mock_tester.test.call_count == 1


def test_inner_graph_retries_engineer_on_failure():
    """测试Agent失败时，工程师最多重试2次"""
    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.side_effect = [
        TestReport(passed=False, errors=["错误A"]),
        TestReport(passed=False, errors=["错误B"]),
        TestReport(passed=True),
    ]

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_engineer.write_script.call_count == 3


def test_inner_graph_exhausts_retries():
    """工程师重试2次后仍失败，图结束并返回失败报告"""
    mock_engineer = MagicMock()
    mock_engineer.write_script.return_value = _make_script()

    mock_tester = MagicMock()
    mock_tester.test.return_value = TestReport(passed=False, errors=["持续错误"])

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    result = graph.invoke(init)

    assert result["report"].passed is False
    assert mock_engineer.write_script.call_count == 3  # 初次 + 2次重试


def test_inner_graph_injects_errors_into_spec():
    """重试时，上次错误应注入到 spec.logic_description"""
    injected_specs = []

    def capture_spec(spec):
        injected_specs.append(spec.logic_description)
        return _make_script()

    mock_engineer = MagicMock()
    mock_engineer.write_script.side_effect = capture_spec

    mock_tester = MagicMock()
    mock_tester.test.side_effect = [
        TestReport(passed=False, errors=["错误X"]),
        TestReport(passed=True),
    ]

    graph = build_inner_graph(engineer_agent=mock_engineer, test_agent=mock_tester)
    init: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    graph.invoke(init)

    assert "错误X" in injected_specs[1]
