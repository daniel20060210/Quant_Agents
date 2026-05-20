# tests/test_outer_graph.py
# 外层图（ScriptTeamGraph）的单元测试。
# alignment_node、内层子图均通过 MagicMock 替换，专注验证外层路由逻辑。
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
    return GeneratedScript(
        file_path="scripts/generated/20260519/calc_ma.py",
        code="def calc_ma(): pass",
    )


def _make_init() -> OuterState:
    """构造外层图初始状态，所有可选字段置为 None/空。"""
    return {
        "request": _make_request(),
        "aligned_request": None,
        "alignment_history": [],
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }


def test_outer_graph_success_first_try():
    """alignment -> requirement -> inner 全部一次通过，外层直接结束。"""
    mock_req = MagicMock()
    mock_req.clarify.return_value = None  # 无疑问，跳过对齐
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
    result = graph.invoke(_make_init())

    assert result["report"].passed is True
    assert mock_req.analyze.call_count == 1
    assert mock_inner.invoke.call_count == 1


def test_outer_graph_aligned_request_passed_to_requirement():
    """requirement_node 应使用 aligned_request（含 Q&A 补充信息）而非原始 request。"""
    mock_req = MagicMock()
    mock_req.clarify.side_effect = [["周期？"], None]  # 一轮对齐后无疑问
    mock_req.analyze.return_value = _make_spec()

    mock_responder = MagicMock()
    mock_responder.answer.return_value = ["参数化。"]

    mock_inner = MagicMock()
    mock_inner.invoke.return_value = {
        "spec": _make_spec(),
        "script": _make_script(),
        "report": TestReport(passed=True),
        "engineer_retries": 0,
        "last_errors": [],
    }

    graph = build_outer_graph(
        requirement_agent=mock_req,
        responder=mock_responder,
        inner_graph=mock_inner,
    )
    result = graph.invoke(_make_init())

    # analyze 收到的应是 aligned_request，其 task_description 包含 Q&A 补充信息
    analyze_call_arg = mock_req.analyze.call_args[0][0]
    assert "周期？" in analyze_call_arg.task_description
    assert "参数化。" in analyze_call_arg.task_description


def test_outer_graph_retries_requirement_on_inner_failure():
    """内层失败时，外层重跑需求分析一次，第二次内层通过后结束。"""
    mock_req = MagicMock()
    mock_req.clarify.return_value = None
    mock_req.analyze.return_value = _make_spec()

    mock_inner = MagicMock()
    mock_inner.invoke.side_effect = [
        # 第一次：内层工程师重试耗尽，返回失败
        {
            "spec": _make_spec(),
            "script": _make_script(),
            "report": TestReport(passed=False, errors=["持续错误"]),
            "engineer_retries": 2,
            "last_errors": ["持续错误"],
        },
        # 第二次：需求重新分析后，内层通过
        {
            "spec": _make_spec(),
            "script": _make_script(),
            "report": TestReport(passed=True),
            "engineer_retries": 0,
            "last_errors": [],
        },
    ]

    graph = build_outer_graph(requirement_agent=mock_req, inner_graph=mock_inner)
    result = graph.invoke(_make_init())

    assert result["report"].passed is True
    assert mock_req.analyze.call_count == 2   # 初次 + 1次重跑
    assert mock_inner.invoke.call_count == 2


def test_outer_graph_fails_after_requirement_retry_exhausted():
    """需求重跑1次后内层仍失败，外层返回失败报告，不再继续重试。"""
    mock_req = MagicMock()
    mock_req.clarify.return_value = None
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
    result = graph.invoke(_make_init())

    assert result["report"].passed is False
    assert mock_req.analyze.call_count == 2   # 初次 + 1次重跑
    assert mock_inner.invoke.call_count == 2
