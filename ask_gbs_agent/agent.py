"""Root Coordinator Agent (`ask_gbs_orchestrator`) & ADK `App` Definition (Rubric 3.1–3.4).

Exposes `root_agent` and `app` compatible with `adk web`, `adk api_server`,
`adk eval`, Cloud Run (`main.py`), and Vertex AI Agent Engine (`deploy_agent_engine.py`).
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.apps import App

from ask_gbs_agent.callbacks import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)
from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.observability.tracing import configure_opentelemetry_tracing
from ask_gbs_agent.plugins import A2uiCanvasPlugin, GbsPolicyGuardrailPlugin
from ask_gbs_agent.prompts import AGENT_CONSTITUTION_PROMPT
from ask_gbs_agent.sub_agents import (
    build_diagnostic_subagent,
    build_escalation_hitl_subagent,
    build_kb_advisory_subagent,
)
from ask_gbs_agent.tools import (
    evaluate_supplier_exemption_status,
    lookup_coupa_oracle_invoice_record,
    open_interactive_coupa_kb_canvas,
    open_urgent_payment_acceleration_form,
    request_missing_invoice_identifier_form,
    stage_servicenow_case_intake_form,
    submit_confirmed_servicenow_case,
)

configure_opentelemetry_tracing()


def build_root_orchestrator_agent() -> LlmAgent:
    """Constructs a fresh Ask GBS Coordinator + 3 Specialist Sub-Agents hierarchy."""
    settings = get_settings()
    diag_agent = build_diagnostic_subagent()
    kb_agent = build_kb_advisory_subagent()
    esc_agent = build_escalation_hitl_subagent()

    return LlmAgent(
        name="ask_gbs_orchestrator",
        model=settings.gemini_flash_model,
        description=(
            "Ask GBS — Enterprise Finance & Procurement Helpdesk Coordinator orchestrating "
            "Coupa/Oracle invoice & payment diagnostics, interactive Side-Panel A2UI Canvas "
            "reconciliations, and 2-step Human-in-the-Loop ServiceNow case creation."
        ),
        instruction=AGENT_CONSTITUTION_PROMPT,
        tools=[
            lookup_coupa_oracle_invoice_record,
            request_missing_invoice_identifier_form,
            open_interactive_coupa_kb_canvas,
            evaluate_supplier_exemption_status,
            open_urgent_payment_acceleration_form,
            stage_servicenow_case_intake_form,
            submit_confirmed_servicenow_case,
        ],
        sub_agents=[
            diag_agent,
            kb_agent,
            esc_agent,
        ],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )


root_agent = build_root_orchestrator_agent()

app = App(
    name="ask_gbs_agent",
    root_agent=root_agent,
    plugins=[
        GbsPolicyGuardrailPlugin(),
        A2uiCanvasPlugin(),
    ],
)
