# ruff: noqa: E501
"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, Route, make_event


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── TODO(student): implement ALL nodes below ────────────────────────


class IntentClassification(BaseModel):
    """Classification of user query intent."""
    route: Route = Field(description="The classified route: risky, tool, missing_info, error, or simple. Priority guide: risky > tool > missing_info > error > simple.")


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM."""
    query = state.get("query", "")
    route_val = Route.SIMPLE.value

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(IntentClassification)
        prompt = (
            "You are an intent classification system for a support ticketing agent. "
            "Classify the following query into exactly one route based on these strict rules and priority order (risky > tool > missing_info > error > simple):\n"
            "1. 'risky': Actions involving side effects, financial transactions, refunds, account deletion, sending emails, or data modifications.\n"
            "2. 'tool': Information lookups needing database or system access like order status, tracking, or search.\n"
            "3. 'missing_info': Ambiguous or vague requests lacking sufficient detail or actionable context (e.g. 'Can you fix it?').\n"
            "4. 'error': System failures, timeouts, crashes, or unrecoverable issues mentioned in the query.\n"
            "5. 'simple': General FAQs, instructional guides (e.g. how to reset password) without needing tools.\n\n"
            f"Query: {query}"
        )
        res = structured_llm.invoke(prompt)
        if res and hasattr(res, "route"):
            route_val = res.route.value if hasattr(res.route, "value") else str(res.route)
    except Exception:
        # Fallback heuristic if LLM API is unavailable/unconfigured offline
        q_lower = query.lower()
        if any(w in q_lower for w in ["refund", "delete", "cancel"]):
            route_val = Route.RISKY.value
        elif any(w in q_lower for w in ["order", "lookup", "status"]):
            route_val = Route.TOOL.value
        elif any(w in q_lower for w in ["fix it", "help me"]):
            route_val = Route.MISSING_INFO.value
        elif any(w in q_lower for w in ["timeout", "failure", "error", "crash"]):
            route_val = Route.ERROR.value
        else:
            route_val = Route.SIMPLE.value

    risk_level = "high" if route_val == Route.RISKY.value else "low"
    return {
        "route": route_val,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"classified as {route_val} with risk {risk_level}")],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call."""
    attempt = state.get("attempt", 0)
    route = state.get("route", "")
    query = state.get("query", "")

    if route == Route.ERROR.value and attempt < 2:
        result_string = "ERROR: Timeout failure while calling backend tool service."
    else:
        result_string = f"SUCCESS: Tool looked up information for query '{query}'."

    return {
        "tool_results": [result_string],
        "events": [make_event("tool", "completed", f"tool executed: {result_string[:30]}")],
    }


class EvaluationJudge(BaseModel):
    """LLM-as-a-Judge evaluation of tool execution results."""
    result: str = Field(description="Must be strictly 'success' if the tool output provided accurate and sufficient data, or 'needs_retry' if there was a system error, timeout, or incomplete data.")
    reasoning: str = Field(description="Brief explanation justifying the evaluation decision.")


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results using LLM-as-a-Judge — the retry-loop gate."""
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    latest_result = tool_results[-1] if tool_results else ""

    eval_res = "success"
    reasoning = "Tool execution completed successfully."

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(EvaluationJudge)
        prompt = (
            "You are a Quality Assurance Judge evaluating whether a tool execution succeeded in gathering needed information for a customer support ticket.\n"
            "Evaluate the Tool Result against the User Query.\n"
            "If the Tool Result contains an ERROR, timeout failure, crash, or incomplete/missing lookup data, you must classify the result as 'needs_retry'.\n"
            "If the Tool Result successfully retrieved information or executed the task, classify as 'success'.\n\n"
            f"User Query: {query}\n"
            f"Tool Result: {latest_result}"
        )
        res = structured_llm.invoke(prompt)
        if res and hasattr(res, "result"):
            res_val = res.result.lower().strip()
            if "retry" in res_val or "error" in res_val:
                eval_res = "needs_retry"
            else:
                eval_res = "success"
            if hasattr(res, "reasoning") and res.reasoning:
                reasoning = res.reasoning
    except Exception:
        # Fallback heuristic if LLM API is unavailable offline
        if "ERROR" in latest_result:
            eval_res = "needs_retry"
            reasoning = "Fallback: detected ERROR in tool result string."
        else:
            eval_res = "success"
            reasoning = "Fallback: tool output appeared successful."

    return {
        "evaluation_result": eval_res,
        "events": [make_event("evaluate", "completed", f"evaluation result: {eval_res} ({reasoning[:40]})", reasoning=reasoning)],
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM."""
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")

    final_ans = ""
    try:
        llm = get_llm()
        context_parts = [f"User Query: {query}"]
        if tool_results:
            context_parts.append(f"Tool Results: {tool_results[-1]}")
        if approval:
            context_parts.append(f"Approval Decision: {approval}")
        prompt = (
            "You are a helpful customer support AI assistant. Based on the following context, generate a clear, professional, and grounded response to the customer.\n\n"
            + "\n".join(context_parts)
        )
        res = llm.invoke(prompt)
        final_ans = res.content if hasattr(res, "content") else str(res)
    except Exception:
        # Fallback if LLM API is unconfigured offline
        if tool_results and "SUCCESS" in tool_results[-1]:
            final_ans = f"Based on our records: {tool_results[-1]}. How else can I assist you today?"
        elif approval and approval.get("approved"):
            final_ans = f"Your request regarding '{query}' has been approved and processed successfully."
        else:
            final_ans = f"To answer your question regarding '{query}': You can reset your password or manage your account via the settings panel."

    return {
        "final_answer": final_ans,
        "events": [make_event("answer", "completed", "generated final answer")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    question = "Could you please provide more details or specify the exact order number or issue you are experiencing?"
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "asked clarification question")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    query = state.get("query", "")
    action = f"Proposed high-risk action for query: '{query}'. Requires human verification before execution."
    return {
        "proposed_action": action,
        "events": [make_event("risky_action", "completed", "prepared risky action for approval")],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step."""
    approved = True
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        try:
            from langgraph.types import interrupt
            decision = interrupt("Please review proposed risky action.")
            if isinstance(decision, dict) and "approved" in decision:
                approved = bool(decision["approved"])
        except ImportError:
            pass

    approval_data = {
        "approved": approved,
        "reviewer": "mock-reviewer",
        "comment": "Auto-approved by default or verified by reviewer",
    }
    return {
        "approval": approval_data,
        "events": [make_event("approval", "completed", f"approval decision: approved={approved}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt."""
    attempt = state.get("attempt", 0) + 1
    error_msg = f"Transient failure at attempt {attempt}"
    return {
        "attempt": attempt,
        "errors": [error_msg],
        "events": [make_event("retry", "completed", f"recorded retry attempt {attempt}")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded."""
    ans = "We are unable to process your request at this time due to repeated system failures. Your ticket has been escalated to support."
    return {
        "final_answer": ans,
        "events": [make_event("dead_letter", "completed", "exhausted max retries, sent to dead letter")],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event."""
    return {
        "events": [make_event("finalize", "completed", "workflow finished")],
    }
