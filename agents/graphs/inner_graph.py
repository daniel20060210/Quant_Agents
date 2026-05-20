from langgraph.graph import StateGraph, END
from agents.graphs.states import InnerState
from agents.script_agents.engineer_agent import EngineerAgent
from agents.script_agents.test_agent import TestAgent
from agents.models import ScriptSpec

# 工程师节点最多重试次数（不含初次），超出后由外层决定是否重跑需求分析
ENGINEER_RETRIES_LIMIT = 2


def build_inner_graph(
    engineer_agent: EngineerAgent | None = None,
    test_agent: TestAgent | None = None,
):
    """
    构建内层子图：engineer_node → test_node → 条件路由。

    路由逻辑：
      - 测试通过 → END
      - 测试失败且未超重试上限 → increment_retries → engineer_node（注入错误反馈）
      - 测试失败且已超上限 → END（外层图会决定是否重跑需求分析）
    """
    engineer = engineer_agent or EngineerAgent()
    tester = test_agent or TestAgent()

    def engineer_node(state: InnerState) -> InnerState:
        spec = state["spec"]
        # 重试时将上次测试错误追加到 logic_description，引导 LLM 修正
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
        # 重试次数耗尽，通知外层升级处理
        return "exhausted"

    def increment_retries(state: InnerState) -> InnerState:
        """递增重试计数，并将本次错误存入 last_errors 供下一轮工程师节点使用。"""
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
