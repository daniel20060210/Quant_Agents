from langgraph.graph import StateGraph, END
from agents.graphs.states import InnerState
from agents.engineer_agent import EngineerAgent
from agents.test_agent import TestAgent
from agents.models import ScriptSpec

ENGINEER_RETRIES_LIMIT = 2


def build_inner_graph(
    engineer_agent: EngineerAgent | None = None,
    test_agent: TestAgent | None = None,
):
    engineer = engineer_agent or EngineerAgent()
    tester = test_agent or TestAgent()

    def engineer_node(state: InnerState) -> InnerState:
        spec = state["spec"]
        if state["last_errors"]:
            feedback = "\n\n【上一版本的问题，请修正】\n错误：\n"
            feedback += "\n".join(f"- {e}" for e in state["last_errors"])
            spec = ScriptSpec(
                function_name=spec.function_name,
                parameters=spec.parameters,
                logic_description=spec.logic_description + feedback,
                expected_output=spec.expected_output,
                test_cases=spec.test_cases,
            )
        script = engineer.write_script(spec)
        return {**state, "spec": spec, "script": script}

    def test_node(state: InnerState) -> InnerState:
        report = tester.test(state["script"], state["spec"])
        return {**state, "report": report}

    def route_after_test(state: InnerState) -> str:
        if state["report"].passed:
            return "end"
        if state["engineer_retries"] < ENGINEER_RETRIES_LIMIT:
            return "retry_engineer"
        return "exhausted"

    def increment_retries(state: InnerState) -> InnerState:
        return {
            **state,
            "engineer_retries": state["engineer_retries"] + 1,
            "last_errors": state["report"].errors,
        }

    builder = StateGraph(InnerState)
    builder.add_node("engineer_node", engineer_node)
    builder.add_node("test_node", test_node)
    builder.add_node("increment_retries", increment_retries)

    builder.set_entry_point("engineer_node")
    builder.add_edge("engineer_node", "test_node")
    builder.add_conditional_edges(
        "test_node",
        route_after_test,
        {"end": END, "retry_engineer": "increment_retries", "exhausted": END},
    )
    builder.add_edge("increment_retries", "engineer_node")

    return builder.compile()
