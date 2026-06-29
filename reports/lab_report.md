# Day 08 Lab Report — LangGraph Agentic Orchestration

## 1. Team / student

- **Name**: Student & Antigravity AI Pair Programming Team
- **Repo/commit**: Day 08 LangGraph Agent Lab (Production-style Orchestration)
- **Date**: 2026-06-29
- **Overall Success Rate**: 100.00% (7 scenarios tested)

## 2. Architecture

The workflow is structured as a robust **LangGraph StateGraph** designed for handling support-ticket operations. Key architectural components include:
- **Intake & Classification**: Raw user queries enter via `intake` and are routed by `classify` using structured LLM output (`with_structured_output`) into 5 distinct priority routes (`risky` > `tool` > `missing_info` > `error` > `simple`).
- **Conditional Routing**: 4 dedicated routing gates (`route_after_classify`, `route_after_evaluate`, `route_after_retry`, `route_after_approval`) dynamically direct the agent flow based on state evaluation.
- **Retry Loop Gate & LLM-as-a-Judge**: The `evaluate` node acts as an intelligent quality gate utilizing structured LLM output (`EvaluationJudge`) to evaluate tool lookup completeness and factual accuracy before allowing the workflow to proceed or triggering a retry up to `max_attempts`.
- **Human-In-The-Loop (HITL)**: High-risk operations (refunds, account deletions) pass through `risky_action` and pause at `approval` for human verification.
- **Unified Termination**: All paths converge at `finalize` to emit comprehensive audit logs before reaching `END`.

## 3. State schema

The workflow manages state via `AgentState` (TypedDict) utilizing lean serializable data structures and explicit reducer annotations:

| Field | Reducer | Why |
|---|---|---|
| `messages` | append (`add`) | Retains complete audit history of conversation and prompts |
| `tool_results` | append (`add`) | Records outputs from tool lookups across multiple retry attempts |
| `errors` | append (`add`) | Logs transient failure messages and stack traces during retries |
| `events` | append (`add`) | Normalized `LabEvent` tracking for latency, node visits, and grading metrics |
| `route` | overwrite | Maintains the active execution path decided by classification |
| `risk_level` | overwrite | Identifies whether the current transaction requires elevated scrutiny |
| `attempt` | overwrite | Tracks the current retry counter to prevent unbounded loops |
| `evaluation_result`| overwrite | Drives conditional routing between success answer and retry fallback |
| `approval` | overwrite | Captures reviewer decision (`approved`, `reviewer`, `comment`) |

## 4. Scenario results

Summary Metrics:
- **Total Scenarios**: 7
- **Success Rate**: 100.00%
- **Average Nodes Visited**: 6.4
- **Total Retries Executed**: 3
- **Total HITL Interrupts**: 2

Per-Scenario Execution Table:

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | ✅ Yes | 0 | 0 |
| S02_tool | tool | tool | ✅ Yes | 0 | 0 |
| S03_missing | missing_info | missing_info | ✅ Yes | 0 | 0 |
| S04_risky | risky | risky | ✅ Yes | 0 | 1 |
| S05_error | error | error | ✅ Yes | 2 | 0 |
| S06_delete | risky | risky | ✅ Yes | 0 | 1 |
| S07_dead_letter | error | error | ✅ Yes | 1 | 0 |

## 5. Failure analysis

We analyzed and mitigated several critical failure modes:
1. **Transient Tool Failure & Unbounded Retries**: When calling external lookup services (`S05_error`), network timeouts can occur. Without bounded checks, the agent could loop infinitely producing high API costs. We mitigated this by tracking `attempt` against `max_attempts` in `route_after_retry`. Once exhausted (`S07_dead_letter`), the ticket is gracefully moved to `dead_letter`.
2. **Unauthorized Risky Actions**: Queries requesting refunds or account deletions (`S04_risky`, `S06_delete`) carry high business risk if hallucinated or executed autonomously. We enforced a strict priority rule in LLM classification and inserted a mandatory HITL `approval` node gate. If rejected, the system routes to `clarify` instead of executing the tool.

## 6. Persistence / recovery evidence

The workflow integrates LangGraph checkpointers (`MemorySaver` and `SqliteSaver`). By isolating execution state per `thread_id` (`thread-<scenario_id>`), the system guarantees thread safety across concurrent user sessions. Checkpointing preserves full checkpoint history after every graph step, enabling crash-resume capabilities and state inspection at any intermediate node.

## 7. Extension work

We completed the following bonus extensions:
- **SQLite Checkpointer Integration**: Extended `persistence.py` to support `SqliteSaver` backed by SQLite WAL (Write-Ahead Logging) mode (`PRAGMA journal_mode=WAL;`), providing production-ready disk persistence that survives process restarts.
- **LLM-as-a-Judge QA Evaluation**: Upgraded `evaluate_node` from static string heuristic checks to an advanced AI QA Judge pattern (`EvaluationJudge`) that evaluates tool execution accuracy against user queries with structured reasoning logs.
- **Robust Offline Fallback**: Designed multi-layered fallback handling in LLM nodes so automated grading and CI pipelines run seamlessly even when external LLM endpoints experience outages.

## 8. Improvement plan

If given additional time to productionize this workflow, we would prioritize:
1. **PostgreSQL Checkpointer & Async Fan-out**: Deploying `AsyncPostgresSaver` for distributed multi-instance scaling and utilizing LangGraph's `Send()` API to execute parallel tool lookups concurrently.
2. **Real-time Webhook Dashboard**: Integrating automated Slack/Microsoft Teams webhook alerts when tickets hit `dead_letter` or require high-priority HITL approval.
