from unittest.mock import MagicMock
from agents.graphs.outer_graph import build_outer_graph
from agents.graphs.states import OuterState
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_request():
    return ScriptRequest(
        task_description="计算均线",
        input_data="收盘价列表",
        output_format="float列表",
    )


def _make_spec():
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线",
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def _make_script():
    return GeneratedScript(file_path="scripts/generated/20260519/calc_ma.py", code="def calc_ma(): pass")


def test_outer_graph_success_first_try():
    """内层子图第一次就通过，外层直接结束"""
    mock_req = MagicMock()
    mock_req.analyze.return_value = _make_spec()

    mock_inner = MagicMock()
    mock_inner.invoke.return_value = {
        "spec": _make_spec(),
        "script": _make_script(),
        "report": TestReport(passed=True),
        "engineer_retries": 0,
        "last_errors": [],
    }

    graph = build_outer_graph(requirement_agent=mock_req, inner_graph=mock_inner)
    init: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_req.analyze.call_count == 1
    assert mock_inner.invoke.call_count == 1


def test_outer_graph_retries_requirement_on_inner_failure():
    """内层失败时，外层重跑需求分析一次"""
    mock_req = MagicMock()
    mock_req.analyze.return_value = _make_spec()

    mock_inner = MagicMock()
    mock_inner.invoke.side_effect = [
        {
            "spec": _make_spec(),
            "script": _make_script(),
            "report": TestReport(passed=False, errors=["持续错误"]),
            "engineer_retries": 2,
            "last_errors": ["持续错误"],
        },
        {
            "spec": _make_spec(),
            "script": _make_script(),
            "report": TestReport(passed=True),
            "engineer_retries": 0,
            "last_errors": [],
        },
    ]

    graph = build_outer_graph(requirement_agent=mock_req, inner_graph=mock_inner)
    init: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    result = graph.invoke(init)

    assert result["report"].passed is True
    assert mock_req.analyze.call_count == 2
    assert mock_inner.invoke.call_count == 2


def test_outer_graph_fails_after_requirement_retry_exhausted():
    """需求重跑1次后内层仍失败，外层返回失败报告"""
    mock_req = MagicMock()
    mock_req.analyze.return_value = _make_spec()

    mock_inner = MagicMock()
    mock_inner.invoke.return_value = {
        "spec": _make_spec(),
        "script": _make_script(),
        "report": TestReport(passed=False, errors=["无法修复"]),
        "engineer_retries": 2,
        "last_errors": ["无法修复"],
    }

    graph = build_outer_graph(requirement_agent=mock_req, inner_graph=mock_inner)
    init: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    result = graph.invoke(init)

    assert result["report"].passed is False
    assert mock_req.analyze.call_count == 2   # 初次 + 1次重跑
    assert mock_inner.invoke.call_count == 2
