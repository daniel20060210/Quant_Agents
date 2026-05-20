# agents/graphs/outer_graph.py
# 外层图：alignment_node -> requirement_node -> inner_subgraph -> 条件路由。
# alignment_node 负责多轮需求对齐；requirement_node 使用对齐后的 aligned_request 生成规格书。
from langgraph.graph import StateGraph, END
from agents.graphs.states import OuterState, InnerState
from agents.graphs.alignment_node import build_alignment_node
from agents.script_agents.requirement_agent import RequirementAgent
from agents.script_agents.trading_agent_responder import TradingAgentResponder

# 需求分析节点最多重跑次数，超出后直接返回失败报告
REQUIREMENT_RETRIES_LIMIT = 1


def build_outer_graph(
    requirement_agent: RequirementAgent | None = None,
    responder: TradingAgentResponder | None = None,
    inner_graph=None,
):
    """
    构建外层图：alignment_node -> requirement_node -> inner_subgraph -> 条件路由。

    路由逻辑：
      - 内层通过 -> END
      - 内层失败且未超重跑上限 -> increment_requirement_retries -> requirement_node
      - 内层失败且已超上限 -> END（返回失败报告）

    Args:
        requirement_agent: 可注入 mock，用于测试
        responder: TradingAgentResponder，可注入 mock，用于测试
        inner_graph: 可注入 mock 内层图，用于测试
    """
    req_agent = requirement_agent or RequirementAgent()
    # 延迟导入避免循环依赖，测试时可注入 mock inner_graph
    inner = inner_graph or _default_inner()

    # alignment_node 是普通函数节点，通过 build_alignment_node 构建
    alignment_fn = build_alignment_node(requirement_agent=req_agent, responder=responder)

    def requirement_node(state: OuterState) -> OuterState:
        """使用对齐后的 aligned_request 生成规格书，而非原始 request。"""
        spec = req_agent.analyze(state["aligned_request"])
        return {**state, "spec": spec}

    def inner_subgraph_node(state: OuterState) -> OuterState:
        """每次进入内层子图时重置 engineer_retries 和 last_errors，确保干净起点。"""
        inner_init: InnerState = {
            "spec": state["spec"],
            "script": None,
            "report": None,
            "engineer_retries": 0,
            "last_errors": [],
        }
        result = inner.invoke(inner_init)
        return {**state, "script": result["script"], "report": result["report"]}

    def route_after_inner(state: OuterState) -> str:
        if state["report"].passed:
            return "end"
        if state["requirement_retries"] < REQUIREMENT_RETRIES_LIMIT:
            return "retry_requirement"
        return "end"

    def increment_requirement_retries(state: OuterState) -> OuterState:
        """递增需求重跑计数，下一步回到 requirement_node 重新生成规格书。"""
        return {**state, "requirement_retries": state["requirement_retries"] + 1}

    builder = StateGraph(OuterState)
    builder.add_node("alignment_node", alignment_fn)
    builder.add_node("requirement_node", requirement_node)
    builder.add_node("inner_subgraph", inner_subgraph_node)
    builder.add_node("increment_requirement_retries", increment_requirement_retries)

    # 图入口改为 alignment_node
    builder.set_entry_point("alignment_node")
    builder.add_edge("alignment_node", "requirement_node")
    builder.add_edge("requirement_node", "inner_subgraph")
    builder.add_conditional_edges(
        "inner_subgraph",
        route_after_inner,
        {"end": END, "retry_requirement": "increment_requirement_retries"},
    )
    builder.add_edge("increment_requirement_retries", "requirement_node")

    return builder.compile()


def _default_inner():
    from agents.graphs.inner_graph import build_inner_graph
    return build_inner_graph()
