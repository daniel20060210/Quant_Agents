# 包结构重组 + 需求对齐节点 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 将三个 Agent 迁移到 agents/script_agents/ 子包，并在外层图中插入 alignment_node，实现 RequirementAgent 与交易Agent之间的多轮需求对齐。

**Architecture:** 新增 agents/script_agents/ 子包存放所有脚本Agent；外层图入口改为 alignment_node，该节点内部循环调用 RequirementAgent.clarify() 和 TradingAgentResponder.answer()，最多 3 轮，输出增强版 aligned_request 后交给 requirement_node 生成规格书；ScriptAgentTeam.run() 对外接口不变。

**Tech Stack:** Python 3.11+, langgraph, openai（DeepSeek 兼容）

---
