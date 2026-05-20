# agents/script_team.py
# ScriptAgentTeam 是脚本Agent团队的对外入口，内部由 LangGraph 多图驱动。
# 流程：alignment_node（多轮需求对齐）-> requirement_node -> inner_subgraph（工程师+测试）
# 调用方只需关心 run(request) -> (script, report)，无需了解图结构。
from agents.models import ScriptRequest, GeneratedScript, TestReport
from agents.script_agents.requirement_agent import RequirementAgent
from agents.script_agents.engineer_agent import EngineerAgent
from agents.script_agents.test_agent import TestAgent
from agents.script_agents.trading_agent_responder import TradingAgentResponder
from agents.graphs.inner_graph import build_inner_graph
from agents.graphs.outer_graph import build_outer_graph
from agents.graphs.states import OuterState


class ScriptAgentTeam:
    """脚本Agent团队：LangGraph 多图嵌套实现，对外接口不变。

    流程：
      1. alignment_node：RequirementAgent 与 TradingAgentResponder 多轮问答，最多 3 轮
      2. requirement_node：使用对齐后的 aligned_request 生成 ScriptSpec
      3. inner_subgraph：EngineerAgent 编写脚本，TestAgent 验证，工程师最多重试 2 次
      4. 内层失败后，外层重跑需求分析最多 1 次

    重试策略：
      - 工程师节点最多重试 2 次（ENGINEER_RETRIES_LIMIT）
      - 内层全部失败后，外层重跑需求分析最多 1 次（REQUIREMENT_RETRIES_LIMIT）
    """

    def __init__(
        self,
        requirement_agent: RequirementAgent | None = None,
        engineer_agent: EngineerAgent | None = None,
        test_agent: TestAgent | None = None,
        responder: TradingAgentResponder | None = None,
    ):
        # 先构建内层子图，再注入外层图，支持测试时传入 mock agent
        inner = build_inner_graph(
            engineer_agent=engineer_agent,
            test_agent=test_agent,
        )
        self._graph = build_outer_graph(
            requirement_agent=requirement_agent,
            responder=responder,
            inner_graph=inner,
        )

    def run(self, request: ScriptRequest) -> tuple[GeneratedScript, TestReport]:
        """执行完整流水线，返回最终生成的脚本和测试报告。"""
        init: OuterState = {
            "request": request,
            "aligned_request": None,    # 由 alignment_node 填充
            "alignment_history": [],    # 由 alignment_node 填充
            "spec": None,
            "script": None,
            "report": None,
            "requirement_retries": 0,   # 从 0 开始，外层图会在需要时递增
        }
        result = self._graph.invoke(init)
        return result["script"], result["report"]
