from agents.models import ScriptRequest, GeneratedScript, TestReport
from agents.requirement_agent import RequirementAgent
from agents.engineer_agent import EngineerAgent
from agents.test_agent import TestAgent
from agents.graphs.inner_graph import build_inner_graph
from agents.graphs.outer_graph import build_outer_graph
from agents.graphs.states import OuterState


class ScriptAgentTeam:
    """脚本Agent团队：LangGraph 多图嵌套实现，对外接口不变"""

    def __init__(
        self,
        requirement_agent: RequirementAgent | None = None,
        engineer_agent: EngineerAgent | None = None,
        test_agent: TestAgent | None = None,
    ):
        inner = build_inner_graph(
            engineer_agent=engineer_agent,
            test_agent=test_agent,
        )
        self._graph = build_outer_graph(
            requirement_agent=requirement_agent,
            inner_graph=inner,
        )

    def run(self, request: ScriptRequest) -> tuple[GeneratedScript, TestReport]:
        init: OuterState = {
            "request": request,
            "spec": None,
            "script": None,
            "report": None,
            "requirement_retries": 0,
        }
        result = self._graph.invoke(init)
        return result["script"], result["report"]
