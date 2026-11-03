"""Lifecycle Callbacks: Compaction, A2UI Action Parser, HITL Gate & Telemetry (Rubric 2.2, 2.4, 3.4, 4.2).

Wires ADK `before_model_callback`, `after_model_callback`, `before_tool_callback`,
and `after_tool_callback` across the Coordinator and Specialist Sub-Agents.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools import BaseTool, ToolContext
from google.genai import types

from ask_gbs_agent.memory.async_worker import schedule_async_memory_consolidation
from ask_gbs_agent.memory.compaction import get_compaction_manager
from ask_gbs_agent.observability.intent_outcome_tracker import get_intent_outcome_tracker
from ask_gbs_agent.observability.structured_logger import get_structured_logger
from ask_gbs_agent.observability.tracing import start_agent_span
from ask_gbs_agent.orchestration.model_router import get_model_router
from ask_gbs_agent.schemas import GuidedToolErrorResponse

HITL_PROTECTED_TOOLS = frozenset(
    {
        "submit_confirmed_servicenow_case",
        "submit_urgent_payment_acceleration",
    }
)

EXPLICIT_CONFIRMATION_RE = re.compile(
    r"\b(confirm_create_servicenow_case|submit\s+servicenow\s+case|submit\s+urgent\s+payment\s+case|"
    r"yes,?\s*submit|confirm\s+and\s+submit|please\s+submit\s+the\s+case|approved?\s+to\s+submit)\b",
    re.IGNORECASE,
)

_LOGGER = get_structured_logger("ask_gbs_agent.callbacks")


def extract_latest_user_text(llm_request: LlmRequest) -> str:
    """Extracts the latest user message text from `LlmRequest.contents`."""
    contents = getattr(llm_request, "contents", None) or []
    for content in reversed(contents):
        if getattr(content, "role", None) == "user":
            texts = [
                getattr(p, "text", "") or ""
                for p in (getattr(content, "parts", None) or [])
                if getattr(p, "text", None)
            ]
            if texts:
                return "\n".join(texts).strip()
    return ""


A2UI_KNOWN_EVENTS = (
    "confirm_create_servicenow_case",
    "cancel_servicenow_case",
    "submit_invoice_quick_lookup",
    "open_kb_in_canvas",
    "request_urgent_early_payment",
    "request_servicenow_intake_form",
)


def _extract_json_event_context(user_text: str) -> dict[str, Any]:
    """Extracts the `context` object from an A2UI JSON button event payload if present."""
    try:
        start = user_text.find("{")
        end = user_text.rfind("}")
        if start != -1 and end > start:
            parsed = json.loads(user_text[start : end + 1])
            ctx = (
                parsed.get("context")
                or parsed.get("event", {}).get("context")
                or parsed.get("userAction", {}).get("context")
                or parsed.get("action", {}).get("context")
                or parsed.get("action", {}).get("event", {}).get("context")
                or parsed.get("data", {}).get("userAction", {}).get("context")
                or parsed.get("data", {}).get("action", {}).get("context")
                or {}
            )
            if isinstance(ctx, dict):
                return ctx
    except Exception:
        pass
    return {}


def parse_a2ui_user_action_event(user_text: str, state: Any) -> bool:
    """Detects Gemini Enterprise A2UI button events across Surfaces A–E or confirmation text."""
    if not user_text or state is None:
        return False

    ctx = _extract_json_event_context(user_text)
    for event_name in A2UI_KNOWN_EVENTS:
        if event_name in user_text:
            state["last_a2ui_button_event"] = {
                "event_name": event_name,
                "context": ctx,
            }
            break

    # Case 1: Structured JSON event payload from Gemini Enterprise Surface A submit button
    if "confirm_create_servicenow_case" in user_text:
        state["hitl_user_confirmed"] = True
        if ctx:
            state["confirmed_a2ui_form_context"] = ctx
        return True

    # Case 2: Natural language confirmation after Surface A intake card was staged
    if state.get("hitl_ticket_staged") and EXPLICIT_CONFIRMATION_RE.search(user_text):
        state["hitl_user_confirmed"] = True
        return True

    if "cancel_servicenow_case" in user_text:
        state["hitl_user_confirmed"] = False
        state["hitl_ticket_staged"] = False
        return False

    # Case 3: Secondary interactive A2UI card/canvas action buttons (Surfaces C, D, E)
    if "submit_invoice_quick_lookup" in user_text and ctx:
        state["a2ui_quick_lookup_context"] = ctx
    elif "open_kb_in_canvas" in user_text and ctx:
        state["a2ui_kb_canvas_context"] = ctx
    elif "request_urgent_early_payment" in user_text and ctx:
        state["a2ui_urgent_payment_context"] = ctx
    elif "request_servicenow_intake_form" in user_text and ctx:
        state["a2ui_intake_request_context"] = ctx

    return False


def enforce_hitl_confirmation_gate(
    tool_name: str,
    args: dict[str, Any],
    tool_context: Optional[ToolContext],
) -> Optional[dict[str, Any]]:
    """Hard Human-in-the-Loop code gate blocking unconfirmed ServiceNow ticket creation (Rubric 3.4)."""
    if tool_name not in HITL_PROTECTED_TOOLS:
        return None

    state = tool_context.state if tool_context is not None else None
    is_confirmed = bool(state is not None and state.get("hitl_user_confirmed") is True)
    if is_confirmed:
        return None

    _LOGGER.warning(
        "HITL gate blocked unconfirmed high-stakes tool invocation",
        blocked_tool=tool_name,
        args_keys=list((args or {}).keys()),
    )
    blocked = GuidedToolErrorResponse(
        error_code="HITL_CONFIRMATION_REQUIRED",
        failed_tool=tool_name,
        error_detail=(
            f"Hard HITL Gate Stop: `{tool_name}` requires explicit human confirmation "
            "(`state['hitl_user_confirmed'] == True`) before execution."
        ),
        llm_recovery_instruction=(
            "First call `stage_servicenow_case_intake_form` to display the A2UI ServiceNow "
            "Case Intake Form (`Surface A`) and wait for the user to click 'Submit ServiceNow Case'."
        ),
        suggested_next_tool="stage_servicenow_case_intake_form",
    )
    return blocked.model_dump()


def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Compacts history, parses A2UI button clicks, routes model tier, and logs INTENT."""
    state = callback_context.state
    agent_name = getattr(callback_context, "agent_name", "ask_gbs_orchestrator")

    with start_agent_span(
        "gbs.turn",
        {"agent.name": agent_name},
    ):
        compactor = get_compaction_manager()
        est_tokens = compactor.compact_llm_request(llm_request)

        latest_user_text = extract_latest_user_text(llm_request)
        confirmed = parse_a2ui_user_action_event(latest_user_text, state)

        decision = get_model_router().route_query(latest_user_text)
        exec_id = f"mdl-{uuid.uuid4().hex[:12]}"

        # Dynamically assign routed model on Coordinator turns (Flash for routine, Gemini 4 Argon for escalations)
        if agent_name == "ask_gbs_orchestrator" and hasattr(llm_request, "model"):
            llm_request.model = decision.selected_model

        if state is not None:
            state["current_model_exec_id"] = exec_id
            state["current_model_start_ts"] = time.perf_counter()
            state["routed_model"] = decision.selected_model
            state["routed_complexity_tier"] = decision.complexity_tier
            state["last_user_query"] = latest_user_text

        get_intent_outcome_tracker().log_intent(
            execution_id=exec_id,
            agent_name=agent_name,
            tool_name=f"llm_generate:{decision.selected_model}",
            sanitized_args={
                "user_query": latest_user_text[:300],
                "compacted_est_tokens": est_tokens,
                "hitl_confirmed_event": confirmed,
            },
            reason=decision.routing_reason,
            session_id=getattr(callback_context, "invocation_id", None),
        )
    return None


def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """Logs model OUTCOME, attaches queued A2UI surfaces safely, and triggers async memory."""
    state = callback_context.state
    agent_name = getattr(callback_context, "agent_name", "ask_gbs_orchestrator")
    exec_id = (
        state.get("current_model_exec_id", f"mdl-{uuid.uuid4().hex[:8]}")
        if state is not None
        else f"mdl-{uuid.uuid4().hex[:8]}"
    )
    start_ts = (
        float(state.get("current_model_start_ts", time.perf_counter()))
        if state is not None
        else time.perf_counter()
    )
    latency_ms = max(0.1, (time.perf_counter() - start_ts) * 1000.0)
    surface_id = state.get("last_a2ui_surface_id") if state is not None else None

    # Skip intermediate partial streaming chunks; finalize only on complete turn
    if getattr(llm_response, "partial", False):
        return None

    # Blast-radius guard when attaching queued A2UI surfaces if plugin hasn't consumed them yet
    response_text_snippets: list[str] = []
    try:
        from ask_gbs_agent.plugins.a2ui_canvas_plugin import build_genai_a2ui_parts

        content = getattr(llm_response, "content", None)
        parts = list(getattr(content, "parts", None) or []) if content else []
        for p in parts:
            if getattr(p, "text", None):
                response_text_snippets.append(str(p.text))

        has_function_call = any(getattr(p, "function_call", None) is not None for p in parts)
        pending = list(state.get("pending_a2ui_parts") or []) if state is not None else []
        if pending and not has_function_call:
            existing_surfaces = {
                (getattr(p, "part_metadata", None) or {}).get("surface_id")
                for p in parts
                if getattr(p, "part_metadata", None)
            }
            for surface_pkg in pending:
                sid = surface_pkg.get("surface_id")
                if sid not in existing_surfaces:
                    parts.extend(build_genai_a2ui_parts(surface_pkg))
                    existing_surfaces.add(sid)
            if content is None:
                llm_response.content = types.Content(role="model", parts=parts)
            else:
                content.parts = parts
            if state is not None:
                state["pending_a2ui_parts"] = []
    except Exception as exc:
        _LOGGER.error(
            "after_model_callback caught A2UI attachment exception safely",
            error_type=type(exc).__name__,
        )

    merged_assistant_text = " ".join(response_text_snippets).strip()
    get_intent_outcome_tracker().log_outcome(
        execution_id=exec_id,
        agent_name=agent_name,
        tool_name=f"llm_generate:{state.get('routed_model', 'gemini-2.5-flash') if state else 'gemini-2.5-flash'}",
        status="SUCCESS",
        latency_ms=latency_ms,
        a2ui_surface_id=surface_id,
        summary=merged_assistant_text[:240] or "Tool call / delegated turn emitted.",
        session_id=getattr(callback_context, "invocation_id", None),
    )

    if merged_assistant_text:
        session_id = str(getattr(callback_context, "invocation_id", None) or "default-gbs-session")
        last_user = str(state.get("last_user_query", "")) if state is not None else ""
        turns_to_consolidate = []
        if last_user:
            turns_to_consolidate.append({"role": "user", "content": last_user})
        turns_to_consolidate.append({"role": "model", "content": merged_assistant_text})
        schedule_async_memory_consolidation(session_id=session_id, turns=turns_to_consolidate)

    return None


def before_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict[str, Any]]:
    """Enforces the HITL confirmation gate and logs pre-execution tool INTENT."""
    tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "unknown_tool")
    agent_name = getattr(tool_context, "agent_name", "ask_gbs_orchestrator")
    exec_id = f"tool-{uuid.uuid4().hex[:12]}"

    state = tool_context.state if tool_context is not None else None
    if state is not None:
        timing_map = dict(state.get("_tool_timing_map") or {})
        timing_map[tool_name] = {"exec_id": exec_id, "start_ts": time.perf_counter()}
        state["_tool_timing_map"] = timing_map

    get_intent_outcome_tracker().log_intent(
        execution_id=exec_id,
        agent_name=agent_name,
        tool_name=tool_name,
        sanitized_args=dict(args or {}),
        reason=f"Executing validated GBS tool `{tool_name}`.",
        session_id=getattr(tool_context, "invocation_id", None),
    )

    blocked = enforce_hitl_confirmation_gate(tool_name=tool_name, args=args, tool_context=tool_context)
    if blocked is not None:
        get_intent_outcome_tracker().log_outcome(
            execution_id=exec_id,
            agent_name=agent_name,
            tool_name=tool_name,
            status="BLOCKED_BY_HITL_GATE",
            latency_ms=0.2,
            summary=blocked.get("error_detail", "Blocked by HITL gate"),
            session_id=getattr(tool_context, "invocation_id", None),
        )
        return blocked

    return None


def after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Logs post-execution tool OUTCOME with latency, confidence score, and A2UI surface ID."""
    tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "unknown_tool")
    agent_name = getattr(tool_context, "agent_name", "ask_gbs_orchestrator")
    state = tool_context.state if tool_context is not None else None

    exec_id = f"tool-{uuid.uuid4().hex[:8]}"
    start_ts = time.perf_counter()
    if state is not None:
        timing_map = dict(state.get("_tool_timing_map") or {})
        entry = timing_map.pop(tool_name, None)
        state["_tool_timing_map"] = timing_map
        if isinstance(entry, dict):
            exec_id = str(entry.get("exec_id", exec_id))
            start_ts = float(entry.get("start_ts", start_ts))

    latency_ms = max(0.1, (time.perf_counter() - start_ts) * 1000.0)
    resp_dict = tool_response if isinstance(tool_response, dict) else {"result": str(tool_response)}
    status = str(resp_dict.get("status", "SUCCESS"))
    surface_id = resp_dict.get("a2ui_surface_id")
    confidence = resp_dict.get("confidence_score")
    summary = str(
        resp_dict.get("diagnostic_summary")
        or resp_dict.get("error_detail")
        or resp_dict.get("title")
        or status
    )

    get_intent_outcome_tracker().log_outcome(
        execution_id=exec_id,
        agent_name=agent_name,
        tool_name=tool_name,
        status=status,
        latency_ms=latency_ms,
        a2ui_surface_id=surface_id,
        confidence_score=confidence if isinstance(confidence, int) else None,
        summary=summary[:240],
        session_id=getattr(tool_context, "invocation_id", None),
    )
    return None
