# ScriptAgentTeam 是脚本Agent团队的对外入口，内部由 LangGraph 多图驱动。
# 调用方只需关心 run(request) → (script, report)，无需了解图结构。
from agents.models import ScriptRequest, GeneratedScript, TestReport
from agents.requirement_agent import RequirementAgent
from agents.engineer_agent import EngineerAgent
from agents.test_agent import TestAgent
from agents.graphs.inner_graph import build_inner_graph
from agents.graphs.outer_graph import build_outer_graph
from agents.graphs.states import OuterState


class ScriptAgentTeam:
    """脚本Agent团队：LangGraph 多图嵌套实现，对外接口不变。

    重试策略：
      - 工程师节点最多重试 2 次（ENGINEER_RETRIES_LIMIT）
      - 内层全部失败后，外层重跑需求分析最多 1 次（REQUIREMENT_RETRIES_LIMIT）
    """

    def __init__(
        self,
        requirement_agent: RequirementAgent | None = None,
        engineer_agent: EngineerAgent | None = None,
        test_agent: TestAgent | None = None,
    ):
        # 先构建内层子图，再注入外层图，支持测试时传入 mock agent
        inner = build_inner_graph(
            engineer_agent=engineer_agent,
            test_agent=test_agent,
        )
        self._graph = build_outer_graph(
            requirement_agent=requirement_agent,
            inner_graph=inner,
        )

    def run(self, request: ScriptRequest) -> tuple[GeneratedScript, TestReport]:
        """执行完整流水线，返回最终生成的脚本和测试报告。"""
        init: OuterState = {
            "request": request,
            "spec": None,
            "script": None,
            "report": None,
            "requirement_retries": 0,  # 从 0 开始，外层图会在需要时递增
        }
        result = self._graph.invoke(init)
        return result["script"], result["report"]
