"""Explicit Intent vs. Outcome Execution Telemetry Tracker (Rubric 4.2).

Records both the agent's *intended* action prior to tool/model execution
(`phase="INTENT"`) and the *actual* execution result (`phase="OUTCOME"`)
correlated by a shared `execution_id`.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from ask_gbs_agent.observability.pii_redactor import get_pii_scrubber
from ask_gbs_agent.observability.structured_logger import get_structured_logger


class IntentOutcomeTracker:
    """Captures correlated pre-execution INTENT and post-execution OUTCOME events."""

    def __init__(self, max_history: int = 500) -> None:
        self._logger = get_structured_logger("ask_gbs_agent.intent_outcome")
        self._scrubber = get_pii_scrubber()
        self._records: deque[dict[str, Any]] = deque(maxlen=max_history)

    def log_intent(
        self,
        execution_id: str,
        agent_name: str,
        tool_name: str,
        sanitized_args: dict[str, Any],
        reason: str,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Logs the agent's intended tool or model invocation before execution."""
        clean_args = self._scrubber.scrub_payload(sanitized_args)
        clean_reason = self._scrubber.scrub_text(reason)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "INTENT",
            "execution_id": execution_id,
            "session_id": session_id or "default-session",
            "agent_name": agent_name,
            "intended_tool": tool_name,
            "intended_arguments": clean_args,
            "routing_reason": clean_reason,
        }
        self._records.append(record)
        self._logger.info(
            f"Agent INTENT: {agent_name} -> {tool_name}",
            **record,
        )
        return record

    def log_outcome(
        self,
        execution_id: str,
        agent_name: str,
        tool_name: str,
        status: str,
        latency_ms: float,
        a2ui_surface_id: Optional[str] = None,
        summary: str = "",
        confidence_score: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Logs the actual post-execution outcome correlated to `execution_id`."""
        clean_summary = self._scrubber.scrub_text(summary)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "OUTCOME",
            "execution_id": execution_id,
            "session_id": session_id or "default-session",
            "agent_name": agent_name,
            "executed_tool": tool_name,
            "outcome_status": status,
            "latency_ms": round(latency_ms, 2),
            "a2ui_surface_id": a2ui_surface_id,
            "confidence_score": confidence_score,
            "outcome_summary": clean_summary,
        }
        self._records.append(record)
        self._logger.info(
            f"Agent OUTCOME: {agent_name} -> {tool_name} [{status}] ({latency_ms:.1f}ms)",
            **record,
        )
        return record

    def get_recent_records(self, execution_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Returns captured intent/outcome records (optionally filtered by `execution_id`)."""
        items = list(self._records)
        if execution_id:
            return [r for r in items if r.get("execution_id") == execution_id]
        return items

    def clear_records(self) -> None:
        """Clears the in-memory ring buffer (used in automated unit tests)."""
        self._records.clear()


@lru_cache(maxsize=1)
def get_intent_outcome_tracker() -> IntentOutcomeTracker:
    """Returns the process-wide singleton `IntentOutcomeTracker`."""
    return IntentOutcomeTracker()
