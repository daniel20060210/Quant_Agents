# agents/graphs/alignment_node.py
# alignment_node：外层图的第一个节点，负责在生成规格书前完成多轮需求对齐。
# RequirementAgent 提问 → TradingAgentResponder 回答 → 循环直到无疑问或达到上限。
from agents.graphs.states import OuterState
from agents.models import ScriptRequest
from agents.script_agents.requirement_agent import RequirementAgent
from agents.script_agents.trading_agent_responder import TradingAgentResponder

# 最多对齐轮数，防止 RequirementAgent 无限提问导致死循环
MAX_ALIGNMENT_ROUNDS = 3


def build_alignment_node(
    requirement_agent: RequirementAgent | None = None,
    responder: TradingAgentResponder | None = None,
):
    """
    构建对齐节点函数，返回可直接注册到 LangGraph 的节点函数。

    循环逻辑（最多 MAX_ALIGNMENT_ROUNDS 轮）：
      1. RequirementAgent.clarify() 判断是否有疑问
      2. 有疑问 → TradingAgentResponder.answer() 回答 → 追加到 history → 继续
      3. 无疑问或达到上限 → 将 history 拼接追加到 task_description → 写入 aligned_request

    Args:
        requirement_agent: 可注入 mock，用于测试
        responder: 可注入 mock，用于测试

    Returns:
        alignment_node 函数，签名为 (OuterState) -> OuterState
    """
    req_agent = requirement_agent or RequirementAgent()
    resp_agent = responder or TradingAgentResponder()

    def alignment_node(state: OuterState) -> OuterState:
        """执行多轮需求对齐，将对齐结果写入 aligned_request 和 alignment_history。"""
        request = state["request"]
        history: list[dict] = []

        for _ in range(MAX_ALIGNMENT_ROUNDS):
            questions = req_agent.clarify(request, history)
            if questions is None:
                # RequirementAgent 无疑问，提前结束循环
                break
            answers = resp_agent.answer(request, questions)
            history.append({"questions": questions, "answers": answers})

        # 将所有 Q&A 拼接追加到 task_description，形成增强版请求供 requirement_node 使用
        aligned_description = request.task_description
        if history:
            aligned_description += "\n\n【需求对齐补充信息】"
            for round_ in history:
                for q, a in zip(round_["questions"], round_["answers"]):
                    aligned_description += f"\nQ: {q}\nA: {a}"

        aligned_request = ScriptRequest(
            task_description=aligned_description,
            input_data=request.input_data,
            output_format=request.output_format,
        )

        return {
            **state,
            "aligned_request": aligned_request,
            "alignment_history": history,
        }

    return alignment_node
