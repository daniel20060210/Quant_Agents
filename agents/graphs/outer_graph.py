from langgraph.graph import StateGraph, END
from agents.graphs.states import OuterState, InnerState
from agents.requirement_agent import RequirementAgent

REQUIREMENT_RETRIES_LIMIT = 1


def build_outer_graph(
    requirement_agent: RequirementAgent | None = None,
    inner_graph=None,
):
    req_agent = requirement_agent or RequirementAgent()
    inner = inner_graph or _default_inner()

    def requirement_node(state: OuterState) -> OuterState:
        spec = req_agent.analyze(state["request"])
        return {**state, "spec": spec}

    def inner_subgraph_node(state: OuterState) -> OuterState:
        inner_init: InnerState = {
            "spec": state["spec"],
            "script": None,
            "report": None,
            "engineer_retries": 0,
            "last_errors": [],
        }
        result = inner.invoke(inner_init)
        return {
            **state,
            "script": result["script"],
            "report": result["report"],
        }

    def route_after_inner(state: OuterState) -> str:
        if state["report"].passed:
            return "end"
        if state["requirement_retries"] < REQUIREMENT_RETRIES_LIMIT:
            return "retry_requirement"
        return "end"

    def increment_requirement_retries(state: OuterState) -> OuterState:
        return {**state, "requirement_retries": state["requirement_retries"] + 1}

    builder = StateGraph(OuterState)
    builder.add_node("requirement_node", requirement_node)
    builder.add_node("inner_subgraph", inner_subgraph_node)
    builder.add_node("increment_requirement_retries", increment_requirement_retries)

    builder.set_entry_point("requirement_node")
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
