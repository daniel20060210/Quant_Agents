from typing import TypedDict, Optional
from agents.models import ScriptRequest, ScriptSpec, GeneratedScript, TestReport


class OuterState(TypedDict):
    request: ScriptRequest
    spec: Optional[ScriptSpec]
    script: Optional[GeneratedScript]
    report: Optional[TestReport]
    requirement_retries: int


class InnerState(TypedDict):
    spec: ScriptSpec
    script: Optional[GeneratedScript]
    report: Optional[TestReport]
    engineer_retries: int
    last_errors: list[str]
