# 验证 OuterState 和 InnerState TypedDict 的字段定义是否正确
from agents.graphs.states import OuterState, InnerState
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport, Param, TestCase


def _make_request():
    """构造最小化的 ScriptRequest 测试数据。"""
    return ScriptRequest(
        task_description="计算均线",
        input_data="收盘价列表",
        output_format="float列表",
    )


def _make_spec():
    """构造最小化的 ScriptSpec 测试数据。"""
    return ScriptSpec(
        function_name="calc_ma",
        parameters=[Param(name="prices", type="list[float]", description="收盘价")],
        logic_description="计算N日均线",
        expected_output="list[float]",
        test_cases=[TestCase(input="[1,2,3]", expected_output="[2.0]")],
    )


def test_outer_state_defaults():
    # 确认外层状态初始值：spec 为 None，重试计数为 0
    state: OuterState = {
        "request": _make_request(),
        "spec": None,
        "script": None,
        "report": None,
        "requirement_retries": 0,
    }
    assert state["requirement_retries"] == 0
    assert state["spec"] is None


def test_inner_state_defaults():
    # 确认内层状态初始值：重试计数为 0，错误列表为空
    state: InnerState = {
        "spec": _make_spec(),
        "script": None,
        "report": None,
        "engineer_retries": 0,
        "last_errors": [],
    }
    assert state["engineer_retries"] == 0
    assert state["last_errors"] == []
