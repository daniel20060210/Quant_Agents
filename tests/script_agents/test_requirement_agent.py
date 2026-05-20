# tests/script_agents/test_requirement_agent.py
# 验证 RequirementAgent.clarify() 的三种行为：
#   1. 需求不清晰时返回问题列表
#   2. 需求清晰时返回 None
#   3. 有历史问答时，历史内容被传入 LLM
from unittest.mock import patch
from agents.script_agents.requirement_agent import RequirementAgent
from agents.models import ScriptRequest


def _make_request():
    """构造最小化的 ScriptRequest 测试数据。"""
    return ScriptRequest(
        task_description="计算20日均线",
        input_data="收盘价列表",
        output_format="float列表",
    )


def test_clarify_returns_questions_when_unclear():
    """需求不清晰时，clarify() 返回非空问题列表。"""
    agent = RequirementAgent()
    mock_response = '{"has_questions": true, "questions": ["周期是否参数化？", "输出是序列还是单值？"]}'
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.clarify(_make_request(), [])

    assert isinstance(result, list)
    assert len(result) == 2
    assert "周期是否参数化？" in result


def test_clarify_returns_none_when_clear():
    """需求足够清晰时，clarify() 返回 None，表示可以直接生成规格书。"""
    agent = RequirementAgent()
    mock_response = '{"has_questions": false, "questions": []}'
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.clarify(_make_request(), [])

    assert result is None


def test_clarify_includes_history_in_prompt():
    """有历史问答时，clarify() 应将历史内容传入 LLM 的 user_prompt。"""
    agent = RequirementAgent()
    history = [{"questions": ["周期？"], "answers": ["参数化。"]}]
    mock_response = '{"has_questions": false, "questions": []}'

    with patch.object(agent, "_call_llm", return_value=mock_response) as mock_llm:
        agent.clarify(_make_request(), history)

    # 验证 user_prompt（第二个位置参数）包含历史问答内容
    user_prompt = mock_llm.call_args[0][1]
    assert "周期？" in user_prompt
    assert "参数化。" in user_prompt
