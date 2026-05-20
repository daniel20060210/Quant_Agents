# tests/script_agents/test_trading_agent_responder.py
# 验证 TradingAgentResponder.answer() 的行为：
#   1. 返回与 questions 等长的答案列表
#   2. questions 为空时直接返回空列表，不调用 LLM
from unittest.mock import patch
from agents.script_agents.trading_agent_responder import TradingAgentResponder
from agents.models import ScriptRequest


def _make_request():
    """构造最小化的 ScriptRequest 测试数据。"""
    return ScriptRequest(
        task_description="计算20日均线",
        input_data="收盘价列表",
        output_format="float列表",
    )


def test_answer_returns_same_length_as_questions():
    """answer() 必须返回与 questions 等长的答案列表。"""
    responder = TradingAgentResponder()
    questions = ["均线周期是固定的还是参数化的？", "输出是序列还是最新一个值？"]
    mock_response = '{"answers": ["参数化，调用方传入。", "完整序列。"]}'

    with patch.object(responder, "_call_llm", return_value=mock_response):
        answers = responder.answer(_make_request(), questions)

    assert len(answers) == 2
    assert answers[0] == "参数化，调用方传入。"
    assert answers[1] == "完整序列。"


def test_answer_with_empty_questions_skips_llm():
    """questions 为空时，直接返回空列表，不调用 LLM。"""
    responder = TradingAgentResponder()

    with patch.object(responder, "_call_llm") as mock_llm:
        answers = responder.answer(_make_request(), [])

    assert answers == []
    # 确认 LLM 未被调用，避免不必要的 API 消耗
    mock_llm.assert_not_called()
