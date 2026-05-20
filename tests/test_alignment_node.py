# tests/test_alignment_node.py
# 验证 alignment_node 的多轮对齐循环逻辑：
#   1. 无疑问时直接输出 aligned_request，不调用 responder
#   2. 有一轮疑问，回答后无疑问，history 包含一条记录
#   3. 达到 MAX_ALIGNMENT_ROUNDS=3 后强制结束，即使仍有疑问
from unittest.mock import MagicMock
from agents.graphs.alignment_node import build_alignment_node
from agents.graphs.states import OuterState
from agents.models import ScriptRequest


def _make_request():
    return ScriptRequest(
        task_description="计算20日均线",
        input_data="收盘价列表",
        output_format="float列表",
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


def test_alignment_no_questions():
    """RequirementAgent 无疑问时，直接输出 aligned_request，history 为空，responder 不被调用。"""
    mock_req = MagicMock()
    mock_req.clarify.return_value = None  # 无疑问

    mock_responder = MagicMock()

    node_fn = build_alignment_node(requirement_agent=mock_req, responder=mock_responder)
    result = node_fn(_make_init())

    assert result["aligned_request"] is not None
    # 无疑问时 aligned_request 的 task_description 与原始相同
    assert result["aligned_request"].task_description == _make_request().task_description
    assert result["alignment_history"] == []
    mock_responder.answer.assert_not_called()


def test_alignment_one_round():
    """有一轮疑问，回答后无疑问，history 包含一条记录，Q&A 被追加到 task_description。"""
    mock_req = MagicMock()
    mock_req.clarify.side_effect = [
        ["周期是否参数化？"],  # 第一轮：有疑问
        None,                   # 第二轮：无疑问
    ]

    mock_responder = MagicMock()
    mock_responder.answer.return_value = ["参数化，调用方传入。"]

    node_fn = build_alignment_node(requirement_agent=mock_req, responder=mock_responder)
    result = node_fn(_make_init())

    assert len(result["alignment_history"]) == 1
    assert result["alignment_history"][0]["questions"] == ["周期是否参数化？"]
    assert result["alignment_history"][0]["answers"] == ["参数化，调用方传入。"]
    # Q&A 内容应被追加到 aligned_request.task_description
    assert "周期是否参数化？" in result["aligned_request"].task_description
    assert "参数化，调用方传入。" in result["aligned_request"].task_description


def test_alignment_max_rounds_enforced():
    """达到 MAX_ALIGNMENT_ROUNDS=3 后强制结束，即使 RequirementAgent 仍有疑问。"""
    mock_req = MagicMock()
    # 始终返回疑问，模拟永不满足的情况
    mock_req.clarify.return_value = ["还有疑问？"]

    mock_responder = MagicMock()
    mock_responder.answer.return_value = ["回答。"]

    node_fn = build_alignment_node(requirement_agent=mock_req, responder=mock_responder)
    result = node_fn(_make_init())

    # 最多 3 轮，不超过 MAX_ALIGNMENT_ROUNDS
    assert len(result["alignment_history"]) == 3
    assert mock_responder.answer.call_count == 3
    # 即使强制结束，aligned_request 也必须被填充
    assert result["aligned_request"] is not None
