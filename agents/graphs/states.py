from typing import TypedDict, Optional
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport


class OuterState(TypedDict):
    """外层图（ScriptTeamGraph）的共享状态。"""
    request: ScriptRequest          # 原始任务，贯穿整个流程不变
    spec: Optional[ScriptSpec]      # 需求分析节点输出，内层失败重跑时会被覆盖
    script: Optional[GeneratedScript]  # 内层子图最终生成的脚本
    report: Optional[TestReport]    # 内层子图最终的测试报告
    requirement_retries: int        # 已重跑需求分析的次数，上限 REQUIREMENT_RETRIES_LIMIT=1


class InnerState(TypedDict):
    """内层子图（EngineerTestGraph）的共享状态。每次进入内层时从 0 重置。"""
    spec: ScriptSpec                # 来自外层，重试时 logic_description 会追加错误反馈
    script: Optional[GeneratedScript]
    report: Optional[TestReport]
    engineer_retries: int           # 已重试工程师节点的次数，上限 ENGINEER_RETRIES_LIMIT=2
    last_errors: list[str]          # 上次测试失败的 errors，注入下一轮工程师节点
