"""Tests all 30 Golden Dataset scenarios, Exemptions Registry, and 2-Step HITL ServiceNow workflow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ask_gbs_agent.callbacks import before_tool_callback, parse_a2ui_user_action_event
from ask_gbs_agent.tools import (
    evaluate_supplier_exemption_status,
    lookup_coupa_oracle_invoice_record,
    open_interactive_coupa_kb_canvas,
    open_urgent_payment_acceleration_form,
    request_missing_invoice_identifier_form,
    stage_servicenow_case_intake_form,
    submit_confirmed_servicenow_case,
)
from ask_gbs_agent.tools.golden_catalog import GOLDEN_RECORDS


def make_ctx(state: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(
        state=dict(state or {}),
        agent_name="test_ask_gbs_agent",
        invocation_id="test-session-golden",
    )


@pytest.mark.parametrize(
    "record",
    GOLDEN_RECORDS,
    ids=[r["scenario_id"] for r in GOLDEN_RECORDS],
)
def test_all_thirty_golden_dataset_scenarios_resolve(record: dict[str, Any]) -> None:
    """Verifies all 17 Invoice, 5 Payment, and 8 Teaser scenarios resolve accurately."""
    ctx = make_ctx()
    res = lookup_coupa_oracle_invoice_record(
        identifier=record["invoice_number"],
        tool_context=ctx,
    )
    assert res["scenario_id"] == record["scenario_id"]
    assert res["kb_reference"] == record["kb_reference"]
    assert len(ctx.state["pending_a2ui_parts"]) == 1

    if record["scenario_id"] == "PAY-03":
        assert res["a2ui_surface_id"] == "gbs-biodata-reconciliation-canvas"
        assert res["target_servicenow_queue"] == "GBS-Senior-AP-Escalations"
    elif record["scenario_id"] == "PAY-05":
        assert res["status"] == "SECURITY_HOLD"
        assert res["confidence_score"] == 62
        assert res["masked_bank_account"] == "[REDACTED — SECURITY HOLD]"
        assert ctx.state.get("security_hold_active") is True
    elif record["scenario_id"] == "PAY-01":
        assert res["coupa_submission_date"] == "2025-12-15"
        assert res["calculated_net_due_date"] == "2026-01-14"
        assert res["eft_reference"] == "1664447"


def test_external_domain_mismatch_triggers_security_hold_dynamically() -> None:
    """Verifies RULE-06 dynamic domain mismatch even on otherwise clean supplier records."""
    ctx = make_ctx()
    res = lookup_coupa_oracle_invoice_record(
        identifier="INV1750822",
        inquirer_email="suspicious.actor@unverified-acquirer.example.org",
        tool_context=ctx,
    )
    assert res["status"] == "SECURITY_HOLD"
    assert res["confidence_score"] == 62
    assert res["masked_bank_account"] == "[REDACTED — SECURITY HOLD]"
    assert res["target_servicenow_queue"] == "GBS-Vendor-Management-Security"


def test_supplier_exemptions_registry_exempt_vs_non_exempt() -> None:
    exempt_res = evaluate_supplier_exemption_status(
        supplier_name="Pacific Grid Energy Corp",
        invoice_number="9933297861012112025",
    )
    assert exempt_res["exemption_status"] == "EXEMPT"
    assert "ap-ebilling-can@enterprise-gbs.example.com" in exempt_res["submission_channel"]

    non_exempt_res = evaluate_supplier_exemption_status(
        supplier_name="NovaTech Leasing Services",
        invoice_number="4810238",
    )
    assert non_exempt_res["exemption_status"] == "NON-EXEMPT"
    assert "Coupa Supplier Portal" in non_exempt_res["submission_channel"]


def test_missing_identifier_clarification_card_and_urgent_payment_form() -> None:
    ctx = make_ctx()
    clarify = request_missing_invoice_identifier_form(
        user_query="Hi, I need help with an invoice that hasn't been paid yet.",
        inquiry_type="PAYMENT_INQUIRY",
        tool_context=ctx,
    )
    assert clarify["status"] == "CLARIFICATION_FORM_STAGED"
    assert clarify["a2ui_surface_id"] == "gbs-missing-identifier-card"

    urgent = open_urgent_payment_acceleration_form(
        invoice_number="INV00026056",
        geography="EMEA",
        tool_context=ctx,
    )
    assert urgent["status"] == "URGENT_PAYMENT_FORM_STAGED"
    assert urgent["target_servicenow_queue"] == "GBS-EMEA-AP-UrgentPayments"


def test_two_step_servicenow_hitl_gate_blocks_until_user_confirms() -> None:
    """Verifies Surface A staging, hard HITL block before confirmation, and Surface B receipt."""
    ctx = make_ctx()

    # Out-of-scope query returns GuidedToolErrorResponse pointing to stage_servicenow_case_intake_form
    unknown = lookup_coupa_oracle_invoice_record(
        identifier="CUSTOM-TAX-AUDIT-2026",
        tool_context=ctx,
    )
    assert unknown["status"] == "RECOVERABLE_ERROR"
    assert unknown["suggested_next_tool"] == "stage_servicenow_case_intake_form"

    # Step 1: Stage Surface A
    staged = stage_servicenow_case_intake_form(
        description="Approved Invoice 2158 ($22,772.00) billed for wrong amount; hold requested.",
        service_area="INVOICE_SUPPORT",
        reference_number="2158",
        priority="P2",
        tool_context=ctx,
    )
    assert staged["status"] == "SERVICENOW_INTAKE_FORM_STAGED"
    assert staged["a2ui_surface_id"] == "gbs-servicenow-intake-form"
    assert ctx.state["hitl_ticket_staged"] is True

    # Attempt premature Step 2 through `before_tool_callback` -> MUST BLOCK
    dummy_tool = SimpleNamespace(name="submit_confirmed_servicenow_case")
    gate_block = before_tool_callback(
        tool=dummy_tool,  # type: ignore[arg-type]
        args={"description": "Premature attempt", "reference_number": "2158"},
        tool_context=ctx,
    )
    assert gate_block is not None
    assert gate_block["status"] == "RECOVERABLE_ERROR"
    assert gate_block["error_code"] == "HITL_CONFIRMATION_REQUIRED"

    # Direct tool call without confirmation -> ALSO BLOCKS
    direct_block = submit_confirmed_servicenow_case(
        description="Approved Invoice 2158 ($22,772.00) billed for wrong amount; hold requested.",
        reference_number="2158",
        tool_context=ctx,
    )
    assert direct_block["error_code"] == "HITL_CONFIRMATION_REQUIRED"

    # Simulate user clicking `[Submit ServiceNow Case]` on Surface A in Gemini Enterprise
    clicked = parse_a2ui_user_action_event(
        '{"event": {"name": "confirm_create_servicenow_case", "context": {"referenceNumber": "2158"}}}',
        ctx.state,
    )
    assert clicked is True
    assert ctx.state["hitl_user_confirmed"] is True

    # Step 2 now passes HITL gate and emits Surface B (`CS9940120`)
    gate_pass = before_tool_callback(
        tool=dummy_tool,  # type: ignore[arg-type]
        args={"description": "Confirmed", "reference_number": "2158"},
        tool_context=ctx,
    )
    assert gate_pass is None

    receipt = submit_confirmed_servicenow_case(
        description="Approved Invoice 2158 ($22,772.00) billed for wrong amount; hold requested.",
        service_area="INVOICE_SUPPORT",
        reference_number="2158",
        priority="P2",
        tool_context=ctx,
    )
    assert receipt["status"] == "CREATED_ILLUSTRATIVE"
    assert receipt["case_number"] == "CS9940120"
    assert receipt["assignment_group"] == "GBS-Global-AP-InvoiceProcessing"
    assert receipt["a2ui_surface_id"] == "gbs-servicenow-receipt-CS9940120"


def test_interactive_kb_canvas_tool() -> None:
    ctx = make_ctx()
    res = open_interactive_coupa_kb_canvas(
        kb_article_id="KB0015760",
        topic_focus="Coding Non-PO Invoice 132.001-03",
        tool_context=ctx,
    )
    assert res["status"] == "KB_CANVAS_OPENED"
    assert res["a2ui_surface_id"] == "gbs-kb-canvas-KB0015760"
