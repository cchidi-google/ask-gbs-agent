"""Sub-Agent 1: Invoice & Payment Diagnostic Specialist (`gemini-2.5-flash`)."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from ask_gbs_agent.callbacks import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)
from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.prompts import DIAGNOSTIC_SUBAGENT_PROMPT
from ask_gbs_agent.tools import (
    evaluate_supplier_exemption_status,
    lookup_coupa_oracle_invoice_record,
    open_urgent_payment_acceleration_form,
    request_missing_invoice_identifier_form,
)


def build_diagnostic_subagent() -> LlmAgent:
    """Constructs the fast Coupa + Oracle single-invoice & payment diagnostic specialist."""
    settings = get_settings()
    return LlmAgent(
        name="invoice_payment_diagnostic_agent",
        model=settings.gemini_flash_model,
        description=(
            "Fast Coupa + Oracle invoice status, Net 30 due date math (KB0015901), "
            "missing-identifier Quick-Lookup card (Surface C), urgent early payment "
            "intake (PAY-01), and Supplier Email Exemptions (KB0015802) specialist."
        ),
        instruction=DIAGNOSTIC_SUBAGENT_PROMPT,
        tools=[
            lookup_coupa_oracle_invoice_record,
            request_missing_invoice_identifier_form,
            evaluate_supplier_exemption_status,
            open_urgent_payment_acceleration_form,
        ],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )


invoice_payment_diagnostic_agent = build_diagnostic_subagent()
