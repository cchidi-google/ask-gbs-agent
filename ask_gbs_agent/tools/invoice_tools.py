"""Cross-System Coupa & Oracle Invoice/Payment Diagnostic Tools (Rubric Category 1).

Implements `lookup_coupa_oracle_invoice_record` and `request_missing_invoice_identifier_form`
with exhaustive Google-style docstrings, strict Pydantic v2 validation, self-evaluation
security guardrails (`RULE-06`), and guided error recovery (`GuidedToolErrorResponse`).
"""

from __future__ import annotations

from typing import Any, Optional

from google.adk.tools import ToolContext
from pydantic import ValidationError

from ask_gbs_agent.memory.persistent_store import get_memory_service
from ask_gbs_agent.observability.tracing import start_agent_span
from ask_gbs_agent.plugins.a2ui_canvas_plugin import (
    build_invoice_payment_status_card,
    build_missing_identifier_lookup_card,
    build_multi_invoice_reconciliation_canvas,
    queue_a2ui_surface,
)
from ask_gbs_agent.plugins.policy_plugin import SelfEvaluationGuardrail
from ask_gbs_agent.schemas import (
    GuidedToolErrorResponse,
    InvoiceDiagnosticOutput,
    InvoiceLookupInput,
    MissingIdentifierFormInput,
)
from ask_gbs_agent.tools.golden_catalog import find_golden_record


def lookup_coupa_oracle_invoice_record(
    identifier: str,
    supplier_name: Optional[str] = None,
    po_number: Optional[str] = None,
    inquirer_email: Optional[str] = None,
    inquiry_context: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Reconciles an invoice, payment batch, PO, or supplier across Coupa and Oracle Financials.

    Summary:
        Performs a read-only cross-system diagnostic across Coupa (approval routing,
        3-way match receipts, `VertexCallOut` tax logs), Oracle Financials (voucher IDs,
        Net 30 submission date math per `KB0015901`, EFT payment references), the
        Supplier Email Exemptions Registry (`KB0015802`), and Phase 1 Service Tiles.
        Automatically queues the corresponding Gemini Enterprise A2UI v0.9 visual surface
        (`Surface D` inline status tracker card or `Surface E` Side-Panel `Canvas`
        multi-invoice `RichTable`).

    Business Rules:
        - `RULE-01`: Strictly read-only ERP posture; never mutates Coupa or Oracle records.
        - `RULE-02` (`KB0015901`): Net 30 due dates are calculated from the Coupa
          Submission Date, NOT the supplier's PDF document date.
        - `RULE-04` (`KB0015835`): Approved invoices with wrong amounts (`INV-11` / `2158`)
          cannot be rejected in Coupa and require `stage_servicenow_case_intake_form`.
        - `RULE-06` (`KB0015950`): External email domain mismatches (`PAY-05` / `2458874037`)
          set `confidence_score = 62 (< 80)`, redact bank digits, and require security HITL.

    Args:
        identifier: Invoice number, Coupa ID, Oracle voucher/EFT reference, PO number,
            supplier name, or scenario reference (e.g., `'INV00026056'`, `'2158'`, `'23469'`).
        supplier_name: Optional supplier or vendor name provided by the user.
        po_number: Optional Purchase Order number (e.g., `'PO #1763463'`).
        inquirer_email: Optional email address of the requester or external supplier contact
            used to verify domain alignment under `RULE-06`.
        inquiry_context: Optional natural-language summary of the user's question.
        tool_context: ADK `ToolContext` injected automatically at runtime for session state.

    Returns:
        dict[str, Any]: Serialized `InvoiceDiagnosticOutput` when a record is resolved, or
        a `GuidedToolErrorResponse` (`status="RECOVERABLE_ERROR"`) instructing the LLM
        how to recover (either via `request_missing_invoice_identifier_form` or
        `stage_servicenow_case_intake_form` for out-of-scope custom inquiries).

    Example:
        >>> res = lookup_coupa_oracle_invoice_record(identifier="INV00026056")
        >>> res["calculated_net_due_date"]
        '2026-01-14'
    """
    with start_agent_span(
        "gbs.tool_execution",
        {"tool.name": "lookup_coupa_oracle_invoice_record", "identifier": identifier},
    ):
        try:
            validated_in = InvoiceLookupInput(
                identifier=identifier,
                supplier_name=supplier_name,
                po_number=po_number,
                inquirer_email=inquirer_email,
                inquiry_context=inquiry_context,
            )
        except ValidationError as exc:
            err = GuidedToolErrorResponse(
                error_code="INVALID_OR_MISSING_IDENTIFIER",
                failed_tool="lookup_coupa_oracle_invoice_record",
                error_detail=str(exc),
                llm_recovery_instruction=(
                    "The user did not provide a valid invoice, PO, or supplier identifier. "
                    "Call `request_missing_invoice_identifier_form` to render the A2UI Quick-Lookup "
                    "card and ask the user for their Invoice Number or PO Number."
                ),
                suggested_next_tool="request_missing_invoice_identifier_form",
            )
            return err.model_dump()

        matched = find_golden_record(
            identifier=validated_in.identifier,
            supplier_name=validated_in.supplier_name,
            po_number=validated_in.po_number,
        )

        if matched is None:
            # Hybrid FTS5 + Cosine Vector fallback against PersistentGbsMemoryService
            rag_hits = get_memory_service().search_knowledge_base(
                query=f"{validated_in.identifier} {validated_in.supplier_name or ''} {validated_in.inquiry_context or ''}".strip(),
                top_k=3,
            )
            err = GuidedToolErrorResponse(
                error_code="RECORD_NOT_FOUND_IN_ERP_OR_KB",
                failed_tool="lookup_coupa_oracle_invoice_record",
                error_detail=(
                    f"Identifier '{validated_in.identifier}' was not found in Coupa, Oracle "
                    "Financials, or the Golden Dataset."
                ),
                llm_recovery_instruction=(
                    "This inquiry is outside deterministic self-service records and requires "
                    "human GBS analyst investigation. Immediately call "
                    "`stage_servicenow_case_intake_form` to present the A2UI ServiceNow Case "
                    "Intake Form (Surface A) pre-populated with the user's reference and question."
                ),
                suggested_next_tool="stage_servicenow_case_intake_form",
                context_metadata={
                    "queried_identifier": validated_in.identifier,
                    "closest_kb_snippets": [h["section_title"] for h in rag_hits[:2]],
                },
            )
            return err.model_dump()

        evaluated = SelfEvaluationGuardrail.evaluate_record_lookup(
            record=matched,
            inquirer_email=validated_in.inquirer_email,
        )

        state = tool_context.state if tool_context is not None else None
        if evaluated.get("security_hold_triggered") and state is not None:
            state["security_hold_active"] = True

        if evaluated["scenario_id"] == "PAY-03":
            surface_pkg = build_multi_invoice_reconciliation_canvas()
        else:
            surface_pkg = build_invoice_payment_status_card(evaluated)

        queue_a2ui_surface(state, surface_pkg)

        if evaluated.get("security_hold_triggered"):
            status_val = "SECURITY_HOLD"
        elif evaluated.get("requires_hitl_ticket"):
            status_val = "ESCALATION_REQUIRED"
        else:
            status_val = "RESOLVED"

        output = InvoiceDiagnosticOutput(
            status=status_val,
            scenario_id=evaluated["scenario_id"],
            category=evaluated["category"],
            invoice_number=evaluated["invoice_number"],
            coupa_id=evaluated["coupa_id"],
            oracle_voucher_id=evaluated["oracle_voucher_id"],
            supplier_name=evaluated["supplier_name"],
            backing_po=evaluated["backing_po"],
            billed_amount=evaluated["billed_amount"],
            invoice_pdf_date=evaluated["invoice_pdf_date"],
            coupa_submission_date=evaluated["coupa_submission_date"],
            calculated_net_due_date=evaluated["calculated_net_due_date"],
            coupa_status=evaluated["coupa_status"],
            oracle_payment_status=evaluated["oracle_payment_status"],
            eft_reference=evaluated.get("eft_reference"),
            masked_bank_account=evaluated["masked_bank_account"],
            confidence_score=int(evaluated["confidence_score"]),
            security_hold_triggered=bool(evaluated["security_hold_triggered"]),
            requires_hitl_ticket=bool(evaluated["requires_hitl_ticket"]),
            target_servicenow_queue=evaluated["target_servicenow_queue"],
            kb_reference=evaluated["kb_reference"],
            diagnostic_summary=evaluated["diagnostic_summary"],
            recommended_next_steps=list(evaluated.get("recommended_next_steps", [])),
            a2ui_surface_id=surface_pkg["surface_id"],
        )
        return output.model_dump()


def request_missing_invoice_identifier_form(
    user_query: str,
    inquiry_type: str = "INVOICE_STATUS",
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Stages the inline A2UI Quick-Lookup Clarification Card (`Surface C`) when identifiers are missing.

    Summary:
        Invoked when a user asks a general invoice, payment, or PO status question
        (e.g., *"I need help with an invoice that hasn't been paid yet"*) without
        providing an Invoice Number, Coupa ID, PO Number, or Supplier Name.

    Business Rules:
        - Prevents premature ServiceNow ticket dumps by capturing missing slots
          conversationally and via an interactive A2UI `MaterialCard` (`Surface C`).

    Args:
        user_query: The user's original natural-language helpdesk message.
        inquiry_type: One of `'INVOICE_STATUS'`, `'PAYMENT_INQUIRY'`, `'PO_SUPPORT'`,
            or `'GENERAL'`. Defaults to `'INVOICE_STATUS'`.
        tool_context: ADK `ToolContext` injected automatically at runtime.

    Returns:
        dict[str, Any]: Confirmation payload including `a2ui_surface_id="gbs-missing-identifier-card"`
        or a `GuidedToolErrorResponse` if arguments fail schema validation.

    Example:
        >>> res = request_missing_invoice_identifier_form("I need help with an unpaid invoice")
        >>> res["a2ui_surface_id"]
        'gbs-missing-identifier-card'
    """
    with start_agent_span(
        "gbs.tool_execution",
        {"tool.name": "request_missing_invoice_identifier_form", "inquiry_type": inquiry_type},
    ):
        try:
            normalized_type = inquiry_type.upper().strip()
            if normalized_type not in {
                "INVOICE_STATUS",
                "PAYMENT_INQUIRY",
                "PO_SUPPORT",
                "GENERAL",
            }:
                normalized_type = "INVOICE_STATUS"
            validated = MissingIdentifierFormInput(
                user_query=user_query,
                inquiry_type=normalized_type,  # type: ignore[arg-type]
            )
        except ValidationError as exc:
            return GuidedToolErrorResponse(
                error_code="INVALID_CLARIFICATION_FORM_INPUT",
                failed_tool="request_missing_invoice_identifier_form",
                error_detail=str(exc),
                llm_recovery_instruction=(
                    "Pass the user's non-empty question string as `user_query` and ask the user "
                    "for their Invoice Number, PO Number, or Supplier Name."
                ),
                suggested_next_tool=None,
            ).model_dump()

        surface_pkg = build_missing_identifier_lookup_card(
            inquiry_type=validated.inquiry_type,
        )
        state = tool_context.state if tool_context is not None else None
        queue_a2ui_surface(state, surface_pkg)

        return {
            "status": "CLARIFICATION_FORM_STAGED",
            "inquiry_type": validated.inquiry_type,
            "a2ui_surface_id": surface_pkg["surface_id"],
            "guidance_for_agent": (
                "Politely ask the user to enter or reply with their Invoice Number, PO Number, "
                "or Supplier Name using the Quick-Lookup Card rendered inline."
            ),
        }
