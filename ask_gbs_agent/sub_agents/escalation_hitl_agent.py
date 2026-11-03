"""Sub-Agent 3: Escalation, Security & HITL ServiceNow Specialist (`gemini-2.5-pro` + `SequentialAgent`).

Combines an `LlmAgent` powered by `gemini-2.5-pro` with a structured ADK
`SequentialAgent` pipeline (`reconciliation_to_escalation_pipeline`) that
reconciles multi-invoice legal hold statements (`PAY-03`) in Step 1 and stages
the mandatory `P1` ServiceNow escalation form (`Surface A`) in Step 2.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent

from ask_gbs_agent.callbacks import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)
from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.prompts import ESCALATION_HITL_SUBAGENT_PROMPT
from ask_gbs_agent.tools import (
    lookup_coupa_oracle_invoice_record,
    open_urgent_payment_acceleration_form,
    stage_servicenow_case_intake_form,
    submit_confirmed_servicenow_case,
)


def build_reconciliation_pipeline() -> SequentialAgent:
    """Builds the 2-stage ADK `SequentialAgent` for multi-invoice legal hold escalations."""
    settings = get_settings()

    reconcile_step = LlmAgent(
        name="statement_reconciliation_step_agent",
        model=settings.gemini_pro_model,
        description="Step 1: Reconciles multi-invoice supplier statements in the Side-Panel Canvas.",
        instruction=(
            "Step 1 of Sequential Escalation Pipeline: Call `lookup_coupa_oracle_invoice_record` "
            "to reconcile all listed statement invoices and queue the Side-Panel Canvas RichTable. "
            "Store a concise summary of paid vs blocked invoices."
        ),
        tools=[lookup_coupa_oracle_invoice_record],
        output_key="statement_reconciliation_summary",
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )

    stage_ticket_step = LlmAgent(
        name="servicenow_staging_step_agent",
        model=settings.gemini_pro_model,
        description="Step 2: Stages the pre-populated P1/P2 ServiceNow Case Intake Form (Surface A).",
        instruction=(
            "Step 2 of Sequential Escalation Pipeline: Using the reconciliation results, call "
            "`stage_servicenow_case_intake_form` (`priority='P1'` for legal/account-freeze notices "
            "or `priority='P2'` for security/approved-invoice holds) and explain the next steps."
        ),
        tools=[stage_servicenow_case_intake_form],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )

    return SequentialAgent(
        name="reconciliation_to_escalation_pipeline",
        description=(
            "Deterministic 2-step SequentialAgent pipeline that reconciles multi-invoice "
            "legal hold notices in the Side-Panel Canvas and stages a P1 ServiceNow case."
        ),
        sub_agents=[reconcile_step, stage_ticket_step],
    )


reconciliation_to_escalation_pipeline = build_reconciliation_pipeline()


def build_escalation_hitl_subagent(
    pipeline: SequentialAgent | None = None,
) -> LlmAgent:
    """Constructs the `gemini-2.5-pro` Escalation, Security & HITL ServiceNow specialist."""
    settings = get_settings()
    attached_pipeline = pipeline or build_reconciliation_pipeline()
    return LlmAgent(
        name="escalation_hitl_specialist_agent",
        model=settings.gemini_pro_model,
        description=(
            "High-reasoning specialist (`gemini-2.5-pro`) for multi-invoice legal reminders "
            "(PAY-03), external email domain mismatch security holds (PAY-05), approved "
            "wrong-amount Oracle holds (INV-11), out-of-scope custom inquiries, and the "
            "2-step HITL ServiceNow case creation workflow (Surface A & Surface B)."
        ),
        instruction=ESCALATION_HITL_SUBAGENT_PROMPT,
        tools=[
            lookup_coupa_oracle_invoice_record,
            stage_servicenow_case_intake_form,
            submit_confirmed_servicenow_case,
            open_urgent_payment_acceleration_form,
        ],
        sub_agents=[attached_pipeline],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )


escalation_hitl_specialist_agent = build_escalation_hitl_subagent(
    pipeline=reconciliation_to_escalation_pipeline
)
