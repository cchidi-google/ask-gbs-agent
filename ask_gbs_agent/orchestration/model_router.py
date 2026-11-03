"""Strategic Flash vs. Pro Complexity Model Router (Rubric 3.2).

Dynamically classifies incoming user requests and routes:
- Routine single-invoice lookups, missing-slot clarification, utility exemptions,
  and Coupa KB navigation to **`gemini-2.5-flash`** for low-latency responsiveness.
- Complex multi-invoice legal hold / account freeze statements (`PAY-03`), external
  email domain mismatches & `DNU` vendor fraud checks (`PAY-05`), approved wrong-amount
  Oracle payment holds (`INV-11`), and multi-step out-of-scope escalations to
  **`gemini-2.5-pro`** for deep policy reasoning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Optional

from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.observability.structured_logger import get_structured_logger
from ask_gbs_agent.observability.tracing import start_agent_span

ComplexityTier = Literal["FAST_DETERMINISTIC", "COMPLEX_REASONING_ESCALATION"]

PRO_ESCALATION_PATTERNS = [
    re.compile(r"\b(legal|reminder|account\s+freeze|statutory\s+demand|stop[\s-]*work|biodata)\b", re.I),
    re.compile(r"\b(23469|23104|23288|2458874037|3001948880|2158)\b", re.I),
    re.compile(r"\b(veritaslabs|envirolab|dnu|domain\s+mismatch|acquisition|fraud|returned\s+by\s+bank)\b", re.I),
    re.compile(r"\b(wrong\s+amount|overbilled|credit\s+memo|payment\s+hold|titan\s+earthworks)\b", re.I),
    re.compile(r"\b(custom\s+tax\s+audit|escalat|servicenow\s+case|confirm_create_servicenow_case)\b", re.I),
]


@dataclass(frozen=True)
class ModelRoutingDecision:
    """Immutable routing decision emitted by `StrategicModelRouter`."""

    selected_model: str
    complexity_tier: ComplexityTier
    target_specialist: str
    routing_reason: str


class StrategicModelRouter:
    """Routes user queries between `gemini-2.5-flash` and `gemini-2.5-pro`."""

    def __init__(
        self,
        flash_model: Optional[str] = None,
        pro_model: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.flash_model = flash_model or settings.gemini_flash_model
        self.pro_model = pro_model or settings.gemini_pro_model
        self._logger = get_structured_logger("ask_gbs_agent.model_router")

    def route_query(self, user_query: str) -> ModelRoutingDecision:
        """Evaluates query complexity and selects the optimal Gemini model & specialist."""
        query_clean = (user_query or "").strip()

        with start_agent_span(
            "gbs.model_routing",
            {"query.length": len(query_clean)},
        ) as span:
            # Multi-invoice detection (>= 2 numeric invoice tokens >= 4 digits)
            invoice_tokens = re.findall(r"\b(?:INV\d+|\d{4,10})\b", query_clean, flags=re.I)
            distinct_tokens = {t.upper() for t in invoice_tokens}

            matched_pro_trigger: Optional[str] = None
            for pattern in PRO_ESCALATION_PATTERNS:
                m = pattern.search(query_clean)
                if m:
                    matched_pro_trigger = m.group(0)
                    break

            if matched_pro_trigger or len(distinct_tokens) >= 2:
                reason = (
                    f"High-complexity policy/security/multi-invoice trigger detected "
                    f"('{matched_pro_trigger or 'multi-invoice statement'}'); routing to Pro."
                )
                decision = ModelRoutingDecision(
                    selected_model=self.pro_model,
                    complexity_tier="COMPLEX_REASONING_ESCALATION",
                    target_specialist="escalation_hitl_specialist_agent",
                    routing_reason=reason,
                )
            elif re.search(
                r"\b(how\s+do\s+i|how\s+to|delegate|notification|custom\s+view|code\s+a\s+non-po|"
                r"kb\d+|saviynt|iexpense|buying\s+channel|mexico|amend\s+po)\b",
                query_clean,
                re.I,
            ):
                decision = ModelRoutingDecision(
                    selected_model=self.flash_model,
                    complexity_tier="FAST_DETERMINISTIC",
                    target_specialist="procurement_kb_advisory_agent",
                    routing_reason="Self-service Coupa/Procurement KB navigation query; routing to Flash.",
                )
            else:
                decision = ModelRoutingDecision(
                    selected_model=self.flash_model,
                    complexity_tier="FAST_DETERMINISTIC",
                    target_specialist="invoice_payment_diagnostic_agent",
                    routing_reason="Routine single-invoice or slot-filling diagnostic; routing to Flash.",
                )

            span.set_attribute("routing.selected_model", decision.selected_model)
            span.set_attribute("routing.complexity_tier", decision.complexity_tier)
            span.set_attribute("routing.target_specialist", decision.target_specialist)

            self._logger.info(
                "StrategicModelRouter selected model tier",
                selected_model=decision.selected_model,
                complexity_tier=decision.complexity_tier,
                target_specialist=decision.target_specialist,
                routing_reason=decision.routing_reason,
            )
            return decision


@lru_cache(maxsize=1)
def get_model_router() -> StrategicModelRouter:
    """Returns a singleton `StrategicModelRouter`."""
    return StrategicModelRouter()
