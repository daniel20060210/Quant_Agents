# agents/script_agents/__init__.py
# script_agents 子包：存放所有脚本生成相关的 Agent。
# 包含需求分析、代码编写、测试验证、以及交易Agent回答者四个角色。
from .requirement_agent import RequirementAgent
from .engineer_agent import EngineerAgent
from .test_agent import TestAgent
from .trading_agent_responder import TradingAgentResponder
