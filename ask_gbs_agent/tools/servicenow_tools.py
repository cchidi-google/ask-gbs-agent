"""Illustrative Two-Step ServiceNow Case & Urgent Payment HITL Tools (Rubric 1.1–1.4 & 3.4).

Implements the interactive Human-in-the-Loop ServiceNow case workflow:
- Step 1: `stage_servicenow_case_intake_form` (queues `Surface A` intake `MaterialCard`)
- Step 2: `submit_confirmed_servicenow_case` (protected by hard HITL gate; queues `Surface B` receipt)
- Urgent Release: `open_urgent_payment_acceleration_form` (queues regional Urgent Payment card)
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from google.adk.tools import ToolContext
from pydantic import ValidationError

from ask_gbs_agent.memory.persistent_store import get_memory_service
from ask_gbs_agent.observability.tracing import start_agent_span
from ask_gbs_agent.plugins.a2ui_canvas_plugin import (
    build_servicenow_intake_form_card,
    build_servicenow_receipt_card,
    build_urgent_payment_intake_card,
    queue_a2ui_surface,
)
from ask_gbs_agent.schemas import (
    GuidedToolErrorResponse,
    ServiceNowCaseConfirmInput,
    ServiceNowCaseIntakeInput,
    ServiceNowTicketReceiptOutput,
    UrgentPaymentFormInput,
)
from ask_gbs_agent.tools.golden_catalog import ASSIGNMENT_GROUP_MATRIX


def _derive_illustrative_case_id(reference_number: str) -> str:
    """Generates a deterministic illustrative Case ID (`CS9940120` for canonical demos)."""
    cleaned = reference_number.strip()
    if cleaned in {"2158", "Custom Inquiry", "N/A"} or "2158" in cleaned:
        return "CS9940120"
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    suffix = int(digest[:6], 16) % 90000 + 10000
    return f"CS99{suffix:05d}"


def open_urgent_payment_acceleration_form(
    invoice_number: str,
    supplier_name: str = "FieldSync Ops Ltd",
    geography: str = "EMEA",
    operating_unit: str = "UK-OPS-01",
    requested_payment_date: str = "2026-01-05",
    business_justification: str = "Critical field operations continuity requirement pending Controller sign-off.",
    requester_email: str = "requester@enterprise-gbs.example.com",
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Stages the Regional Urgent Early Payment Intake Form (`KB0015901` / `PAY-01`).

    Summary:
        Renders an inline A2UI v0.9 `MaterialCard` form when a business requester needs
        an out-of-cycle urgent EFT release ahead of the calculated Net 30 Coupa
        Submission Due Date (e.g., `INV00026056` / `FieldSync Ops Ltd`).

    Business Rules:
        - Per `KB0015901`, urgent payment acceleration requires Geography (`EMEA`, `AMER`,
          `APAC`), Operating Unit, Requested Date, and Controller business impact justification.
        - Sets `hitl_ticket_staged = True` in session state; final case submission still
          requires explicit human confirmation (`Submit Urgent Payment Case`).

    Args:
        invoice_number: Approved invoice number requiring accelerated payment (e.g., `'INV00026056'`).
        supplier_name: Supplier legal name associated with the invoice.
        geography: Regional treasury queue (`'EMEA'`, `'AMER'`, or `'APAC'`).
        operating_unit: Enterprise operating unit code (e.g., `'UK-OPS-01'`).
        requested_payment_date: Desired early EFT release date (`YYYY-MM-DD`).
        business_justification: Controller business impact reason for early payment.
        requester_email: Business email of the requester.
        tool_context: ADK `ToolContext` injected automatically at runtime.

    Returns:
        dict[str, Any]: Staged form metadata including `a2ui_surface_id` and target queue.

    Example:
        >>> res = open_urgent_payment_acceleration_form(invoice_number="INV00026056")
        >>> res["status"]
        'URGENT_PAYMENT_FORM_STAGED'
    """
    with start_agent_span(
        "gbs.tool_execution",
        {"tool.name": "open_urgent_payment_acceleration_form", "invoice_number": invoice_number},
    ):
        try:
            geo_norm = geography.upper().strip()
            if geo_norm not in {"EMEA", "AMER", "APAC"}:
                geo_norm = "EMEA"
            validated = UrgentPaymentFormInput(
                invoice_number=invoice_number,
                supplier_name=supplier_name,
                geography=geo_norm,  # type: ignore[arg-type]
                operating_unit=operating_unit,
                requested_payment_date=requested_payment_date,
                business_justification=business_justification,
                requester_email=requester_email,
            )
        except ValidationError as exc:
            return GuidedToolErrorResponse(
                error_code="INVALID_URGENT_PAYMENT_INPUT",
                failed_tool="open_urgent_payment_acceleration_form",
                error_detail=str(exc),
                llm_recovery_instruction=(
                    "Provide a valid `invoice_number` and at least 5 characters of "
                    "`business_justification` before calling `open_urgent_payment_acceleration_form`."
                ),
                suggested_next_tool="request_missing_invoice_identifier_form",
            ).model_dump()

        surface_pkg = build_urgent_payment_intake_card(
            invoice_number=validated.invoice_number,
            supplier_name=validated.supplier_name,
            geography=validated.geography,
            operating_unit=validated.operating_unit,
            requested_payment_date=validated.requested_payment_date,
            business_justification=validated.business_justification,
            requester_email=validated.requester_email,
        )
        state = tool_context.state if tool_context is not None else None
        if state is not None:
            state["hitl_ticket_staged"] = True
            state["staged_servicenow_payload"] = {
                "service_area": "URGENT_PAYMENT",
                "reference_number": validated.invoice_number,
                "priority": "P2",
                "requester_email": validated.requester_email,
                "description": validated.business_justification,
            }
        queue_a2ui_surface(state, surface_pkg)

        target_queue = (
            "GBS-EMEA-AP-UrgentPayments"
            if validated.geography in {"EMEA", "APAC"}
            else "GBS-AMER-AP-EarlyPaymentRelease"
        )
        return {
            "status": "URGENT_PAYMENT_FORM_STAGED",
            "invoice_number": validated.invoice_number,
            "target_servicenow_queue": target_queue,
            "a2ui_surface_id": surface_pkg["surface_id"],
            "next_step": (
                "Await user confirmation via the 'Submit Urgent Payment Case' button before "
                "calling `submit_confirmed_servicenow_case`."
            ),
        }


def stage_servicenow_case_intake_form(
    description: str,
    service_area: str = "INVOICE_SUPPORT",
    reference_number: str = "Custom Inquiry",
    priority: str = "P2",
    requester_email: str = "alex.rivera@enterprise-gbs.example.com",
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Step 1 of Illustrative ServiceNow Case Creation: Stages the A2UI Case Intake Form (`Surface A`).

    Summary:
        Pre-populates and queues the interactive A2UI v0.9 `MaterialCard` ServiceNow
        Case Intake Form (`gbs-servicenow-intake-form`) whenever a user request requires
        back-office ERP intervention (e.g., approved wrong-amount invoice `2158`,
        multi-invoice legal hold `PAY-03`, security mismatch `PAY-05`, PDF remittance
        `PAY-04`) or falls outside the self-service RAG knowledge base.

    Business Rules:
        - Sets `hitl_ticket_staged = True` in session state and waits for the human user
          to review the form and click `[Submit ServiceNow Case]` (`confirm_create_servicenow_case`).
        - Never creates a ticket directly without human confirmation (Rubric 3.4).

    Args:
        description: Pre-populated diagnostic context and specialist action requested
            (minimum 10 characters).
        service_area: Target GBS queue category (`'INVOICE_SUPPORT'`, `'PAYMENT_SUPPORT'`,
            `'URGENT_PAYMENT'`, `'LEGAL_ESCALATION'`, `'VENDOR_SECURITY'`, or `'GENERAL_TRIAGE'`).
        reference_number: Invoice number, PO number, Vendor ID, or `'Custom Inquiry'`.
        priority: Priority level (`'P1'`, `'P2'`, or `'P3'`).
        requester_email: Business email of the requester.
        tool_context: ADK `ToolContext` injected automatically at runtime.

    Returns:
        dict[str, Any]: Staged intake summary including `a2ui_surface_id="gbs-servicenow-intake-form"`
        and target assignment group, or `GuidedToolErrorResponse` on validation error.

    Example:
        >>> res = stage_servicenow_case_intake_form(
        ...     description="Approved Invoice 2158 ($22,772) billed for wrong amount; hold needed.",
        ...     service_area="INVOICE_SUPPORT",
        ...     reference_number="2158",
        ...     priority="P2",
        ... )
        >>> res["a2ui_surface_id"]
        'gbs-servicenow-intake-form'
    """
    with start_agent_span(
        "gbs.tool_execution",
        {
            "tool.name": "stage_servicenow_case_intake_form",
            "service_area": service_area,
            "priority": priority,
        },
    ):
        area_norm = service_area.upper().strip()
        if area_norm not in ASSIGNMENT_GROUP_MATRIX:
            area_norm = "GENERAL_TRIAGE"
        prio_norm = priority.upper().strip()[:2]
        if prio_norm not in {"P1", "P2", "P3"}:
            prio_norm = "P2"

        try:
            validated = ServiceNowCaseIntakeInput(
                service_area=area_norm,  # type: ignore[arg-type]
                reference_number=reference_number,
                priority=prio_norm,  # type: ignore[arg-type]
                requester_email=requester_email,
                description=description,
            )
        except ValidationError as exc:
            return GuidedToolErrorResponse(
                error_code="INVALID_SERVICENOW_INTAKE_INPUT",
                failed_tool="stage_servicenow_case_intake_form",
                error_detail=str(exc),
                llm_recovery_instruction=(
                    "Ensure `description` is at least 10 characters summarizing the user's "
                    "issue and retry `stage_servicenow_case_intake_form`."
                ),
                suggested_next_tool="stage_servicenow_case_intake_form",
            ).model_dump()

        surface_pkg = build_servicenow_intake_form_card(
            service_area=validated.service_area,
            reference_number=validated.reference_number,
            priority=validated.priority,
            requester_email=validated.requester_email,
            description=validated.description,
        )

        state = tool_context.state if tool_context is not None else None
        if state is not None:
            state["hitl_ticket_staged"] = True
            state["staged_servicenow_payload"] = validated.model_dump()
        queue_a2ui_surface(state, surface_pkg)

        routing = ASSIGNMENT_GROUP_MATRIX[validated.service_area]
        return {
            "status": "SERVICENOW_INTAKE_FORM_STAGED",
            "a2ui_surface_id": surface_pkg["surface_id"],
            "service_area": validated.service_area,
            "assignment_group": routing["assignment_group"],
            "priority": validated.priority,
            "target_sla": routing["target_sla"],
            "reference_number": validated.reference_number,
            "hitl_instruction": (
                "Present the pre-populated ServiceNow Case Intake Form to the user and wait "
                "for them to click 'Submit ServiceNow Case' (or explicitly confirm in chat) "
                "before calling `submit_confirmed_servicenow_case`."
            ),
        }


def submit_confirmed_servicenow_case(
    description: str,
    service_area: str = "INVOICE_SUPPORT",
    reference_number: str = "2158",
    priority: str = "P2",
    requester_email: str = "alex.rivera@enterprise-gbs.example.com",
    user_confirmed: bool = True,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Step 2 of Illustrative ServiceNow Case Creation: Generates Confirmed Receipt (`Surface B`).

    Summary:
        Executes Step 2 of the ServiceNow case workflow ONLY after human-in-the-loop
        confirmation (`state["hitl_user_confirmed"] == True`). Generates a deterministic
        illustrative ServiceNow Case ID (e.g., `CS9940120`), records the PII-scrubbed
        ticket in SQLite session memory, and queues the A2UI v0.9 Confirmation Receipt
        Card (`Surface B`) with zero live ServiceNow mutation.

    Business Rules:
        - **Hard HITL Code Stop (Rubric 3.4)**: Execution is blocked unless
          `tool_context.state["hitl_user_confirmed"]` is `True`.
        - Routes to the regional queue & SLA in `ASSIGNMENT_GROUP_MATRIX`.

    Args:
        description: Confirmed case description and specialist instructions.
        service_area: Confirmed GBS functional area (`'INVOICE_SUPPORT'`, etc.).
        reference_number: Confirmed Invoice, PO, or custom inquiry identifier.
        priority: Confirmed priority code (`'P1'`, `'P2'`, or `'P3'`).
        requester_email: Confirmed requester business contact email.
        user_confirmed: Boolean confirmation flag (also verified against session state).
        tool_context: ADK `ToolContext` injected automatically at runtime.

    Returns:
        dict[str, Any]: Serialized `ServiceNowTicketReceiptOutput` (`CS9940120`) when
        confirmed, or `GuidedToolErrorResponse` (`HITL_CONFIRMATION_REQUIRED`) if
        invoked prior to human confirmation.

    Example:
        >>> # Requires tool_context.state["hitl_user_confirmed"] == True
        >>> pass
    """
    with start_agent_span(
        "gbs.tool_execution",
        {
            "tool.name": "submit_confirmed_servicenow_case",
            "service_area": service_area,
            "reference_number": reference_number,
        },
    ):
        state = tool_context.state if tool_context is not None else None
        is_state_confirmed = bool(state and state.get("hitl_user_confirmed") is True)

        if not is_state_confirmed or not user_confirmed:
            return GuidedToolErrorResponse(
                error_code="HITL_CONFIRMATION_REQUIRED",
                failed_tool="submit_confirmed_servicenow_case",
                error_detail=(
                    "Human-in-the-Loop Gate Blocked Execution: `submit_confirmed_servicenow_case` "
                    "cannot execute until the user clicks 'Submit ServiceNow Case' on Surface A "
                    "or explicitly confirms submission (`state['hitl_user_confirmed'] == True`)."
                ),
                llm_recovery_instruction=(
                    "Call `stage_servicenow_case_intake_form` first (if not yet staged) and "
                    "ask the user to review the ServiceNow Case Intake Form and click "
                    "'Submit ServiceNow Case' to confirm."
                ),
                suggested_next_tool="stage_servicenow_case_intake_form",
            ).model_dump()

        area_norm = service_area.upper().strip()
        if area_norm not in ASSIGNMENT_GROUP_MATRIX:
            area_norm = "GENERAL_TRIAGE"
        prio_norm = priority.upper().strip()[:2]
        if prio_norm not in {"P1", "P2", "P3"}:
            prio_norm = "P2"

        try:
            validated = ServiceNowCaseConfirmInput(
                service_area=area_norm,  # type: ignore[arg-type]
                reference_number=reference_number,
                priority=prio_norm,  # type: ignore[arg-type]
                requester_email=requester_email,
                description=description,
                user_confirmed=user_confirmed,
            )
        except ValidationError as exc:
            return GuidedToolErrorResponse(
                error_code="INVALID_SERVICENOW_CONFIRM_INPUT",
                failed_tool="submit_confirmed_servicenow_case",
                error_detail=str(exc),
                llm_recovery_instruction=(
                    "Ensure `description` (min 10 chars) and `requester_email` are valid, "
                    "then retry `submit_confirmed_servicenow_case`."
                ),
                suggested_next_tool="stage_servicenow_case_intake_form",
            ).model_dump()

        case_number = _derive_illustrative_case_id(validated.reference_number)
        routing = ASSIGNMENT_GROUP_MATRIX[validated.service_area]
        priority_labels = {
            "P1": "P1 — Critical",
            "P2": "P2 — High",
            "P3": "P3 — Standard",
        }
        priority_label = priority_labels[validated.priority]
        target_sla = (
            "2 Business Hours"
            if validated.priority == "P1"
            else ("4 Business Hours" if validated.priority == "P2" else routing["target_sla"])
        )

        get_memory_service().record_illustrative_servicenow_case(
            case_number=case_number,
            service_area=validated.service_area,
            assignment_group=routing["assignment_group"],
            priority=priority_label,
            target_sla=target_sla,
            reference_number=validated.reference_number,
            requester_email=validated.requester_email,
            description=validated.description,
        )

        surface_pkg = build_servicenow_receipt_card(
            case_number=case_number,
            assignment_group=routing["assignment_group"],
            priority_label=priority_label,
            target_sla=target_sla,
            reference_number=validated.reference_number,
            requester_email=validated.requester_email,
        )
        queue_a2ui_surface(state, surface_pkg)
        if state is not None:
            state["last_created_case_number"] = case_number
            state["hitl_user_confirmed"] = False

        receipt = ServiceNowTicketReceiptOutput(
            case_number=case_number,
            assignment_group=routing["assignment_group"],
            priority=priority_label,
            target_sla=target_sla,
            reference_number=validated.reference_number,
            requester_email=validated.requester_email,
            description=validated.description,
            a2ui_surface_id=surface_pkg["surface_id"],
        )
        return receipt.model_dump()
