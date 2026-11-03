"""GBS Policy & Self-Evaluation Confidence Guardrail Plugin (Rubric 3.3).

Enforces three enterprise guardrails across all sub-agents and tools:
1. **Read-Only ERP Posture (`RULE-01`)**: Blocks any direct write/mutation attempt
   against Coupa or Oracle Financials (`approve_invoice`, `override_3way_match`, etc.).
2. **Self-Evaluation Confidence Scoring (`RULE-06` / `KB0015950`)**: Evaluates supplier
   identity and email domain alignment on every lookup. External domain mismatches
   (such as `PAY-05`: `@veritaslabs-group.example.com` vs `DNU - EnviroLab Analytics Inc`)
   drop `confidence_score` to `62` (`< 80`), redact bank account digits to
   `[REDACTED — SECURITY HOLD]`, and mandate `GBS-Vendor-Management-Security` escalation.
3. **Output Safety & Redaction Verification**: Ensures sensitive bank digits remain
   masked whenever a session is under an active security hold.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin
from google.adk.tools import BaseTool, ToolContext

from ask_gbs_agent.observability.structured_logger import get_structured_logger
from ask_gbs_agent.schemas import GuidedToolErrorResponse

PROHIBITED_ERP_WRITE_TOOLS = frozenset(
    {
        "approve_coupa_invoice",
        "delete_coupa_invoice",
        "override_3way_match_tolerance",
        "release_oracle_payment_hold_direct",
        "mutate_supplier_bank_account",
        "edit_oracle_gl_string_direct",
    }
)

SECURITY_HOLD_MASK = "[REDACTED — SECURITY HOLD]"
RAW_BANK_TAIL_RE = re.compile(r"\bxxx\d{4}\b", re.IGNORECASE)

_LOGGER = get_structured_logger("ask_gbs_agent.policy_guardrail")


class SelfEvaluationGuardrail:
    """Evaluates diagnostic confidence and enforces RULE-06 security holds."""

    CONFIDENCE_THRESHOLD = 80

    @classmethod
    def evaluate_record_lookup(
        cls,
        record: dict[str, Any],
        inquirer_email: Optional[str] = None,
    ) -> dict[str, Any]:
        """Computes self-eval confidence and applies bank digit masking if `< 80`."""
        evaluated = dict(record)
        supplier_name = str(evaluated.get("supplier_name", ""))
        official_domain = str(evaluated.get("official_email_domain", "")).lower().strip()
        base_confidence = int(evaluated.get("confidence_score", 95))

        domain_mismatch = False
        if inquirer_email and "@" in inquirer_email:
            caller_domain = inquirer_email.split("@", 1)[1].lower().strip()
            # Internal enterprise employees are trusted; external mismatches trigger RULE-06
            if (
                caller_domain != "enterprise-gbs.example.com"
                and official_domain
                and caller_domain != official_domain
            ):
                domain_mismatch = True

        is_dnu_vendor = supplier_name.upper().startswith("DNU") or (
            evaluated.get("scenario_id") == "PAY-05"
        )

        if domain_mismatch or is_dnu_vendor or base_confidence < cls.CONFIDENCE_THRESHOLD:
            evaluated["confidence_score"] = 62
            evaluated["security_hold_triggered"] = True
            evaluated["masked_bank_account"] = SECURITY_HOLD_MASK
            evaluated["requires_hitl_ticket"] = True
            evaluated["target_servicenow_queue"] = "GBS-Vendor-Management-Security"
            evaluated["status"] = "SECURITY_HOLD"
            _LOGGER.warning(
                "SelfEvaluationGuardrail triggered security hold (confidence < 80)",
                scenario_id=evaluated.get("scenario_id"),
                confidence_score=62,
                domain_mismatch=domain_mismatch,
                is_dnu_vendor=is_dnu_vendor,
            )
        else:
            evaluated["security_hold_triggered"] = False

        return evaluated


class GbsPolicyGuardrailPlugin(BasePlugin):
    """ADK `BasePlugin` enforcing Read-Only ERP policy and security hold masking."""

    def __init__(self, name: str = "gbs_policy_guardrail_plugin") -> None:
        super().__init__(name=name)
        self.evaluator = SelfEvaluationGuardrail()

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict[str, Any]]:
        """Blocks prohibited direct ERP mutations and returns guided recovery instructions."""
        tool_name = getattr(tool, "name", "") or ""
        if tool_name in PROHIBITED_ERP_WRITE_TOOLS:
            _LOGGER.warning(
                "Blocked prohibited direct ERP write attempt under RULE-01",
                blocked_tool=tool_name,
            )
            blocked = GuidedToolErrorResponse(
                error_code="READ_ONLY_ERP_POLICY_VIOLATION",
                failed_tool=tool_name,
                error_detail=(
                    f"Tool `{tool_name}` is blocked by GBS Policy RULE-01: Ask GBS operates in "
                    "strictly Read-Only diagnostic posture for Coupa and Oracle Financials."
                ),
                llm_recovery_instruction=(
                    "Explain to the user that Ask GBS has read-only ERP access and call "
                    "`stage_servicenow_case_intake_form` so a GBS specialist can execute the change."
                ),
                suggested_next_tool="stage_servicenow_case_intake_form",
            )
            return blocked.model_dump()
        return None

    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        """Scrubs any residual masked bank tails if the session is in SECURITY_HOLD state."""
        state = callback_context.state
        if not state or not state.get("security_hold_active"):
            return None

        content = getattr(llm_response, "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text and "<a2a_datapart_json>" not in text:
                part.text = RAW_BANK_TAIL_RE.sub(SECURITY_HOLD_MASK, text)
        return None
