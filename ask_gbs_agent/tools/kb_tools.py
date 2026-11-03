"""Interactive Coupa Knowledge Base Canvas & Supplier Exemptions Tools (Rubric Category 1).

Implements `open_interactive_coupa_kb_canvas` (`KB0015760`–`KB0016050`) and
`evaluate_supplier_exemption_status` (`KB0015802`).
"""

from __future__ import annotations

from typing import Any, Optional

from google.adk.tools import ToolContext
from pydantic import ValidationError

from ask_gbs_agent.memory.persistent_store import get_memory_service
from ask_gbs_agent.observability.tracing import start_agent_span
from ask_gbs_agent.plugins.a2ui_canvas_plugin import (
    KB_ARTICLES_CATALOG,
    build_interactive_kb_canvas,
    queue_a2ui_surface,
)
from ask_gbs_agent.schemas import (
    GuidedToolErrorResponse,
    KbCanvasInput,
    SupplierExemptionInput,
)
from ask_gbs_agent.tools.golden_catalog import SUPPLIER_EXEMPTIONS_REGISTRY, normalize_key


def open_interactive_coupa_kb_canvas(
    kb_article_id: str = "KB0015760",
    topic_focus: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Opens an interactive step-by-step Coupa / Procurement KB guide in the Side-Panel Canvas.

    Summary:
        Retrieves curated ServiceNow Knowledge Base guidance (`KB0015760`–`KB0016050`)
        from the hybrid RAG memory service and queues an A2UI v0.9 `Canvas` (`Surface E`)
        featuring collapsible `MaterialExpansionPanel` accordions in Gemini Enterprise.

    Business Rules:
        - Keeps lengthy Coupa navigation checklists out of the chat stream by rendering
          structured accordions in the right-hand Side-Panel `Canvas`.
        - Enforces `<= 62` character titles on all `MaterialExpansionPanel` components.

    Args:
        kb_article_id: ServiceNow KB identifier matching `^KB\\d{7}$` (e.g., `'KB0015760'`
            for Non-PO coding, `'KB0015802'` for Supplier Exemptions, `'KB0015810'` for
            PO vs Non-PO routing, `'KB0015822'` for Holds/VertexCallOut, `'KB0015835'`
            for Disputed/Wrong-Amount invoices, `'KB0015849'` for 3-Way Match Receipts,
            `'KB0015860'` for Delegation/Notifications/Views, `'KB0015901'` for Net 30 math).
        topic_focus: Optional user-specific focus question to highlight on the Canvas.
        tool_context: ADK `ToolContext` injected automatically at runtime.

    Returns:
        dict[str, Any]: Structured KB article steps, hybrid RAG excerpts, and the queued
        `a2ui_surface_id`, or `GuidedToolErrorResponse` if `kb_article_id` is malformed.

    Example:
        >>> res = open_interactive_coupa_kb_canvas(kb_article_id="KB0015760")
        >>> res["kb_article_id"]
        'KB0015760'
    """
    with start_agent_span(
        "gbs.tool_execution",
        {"tool.name": "open_interactive_coupa_kb_canvas", "kb_article_id": kb_article_id},
    ):
        try:
            validated = KbCanvasInput(
                kb_article_id=kb_article_id.upper().strip(),
                topic_focus=topic_focus,
            )
        except ValidationError as exc:
            return GuidedToolErrorResponse(
                error_code="INVALID_KB_ARTICLE_ID",
                failed_tool="open_interactive_coupa_kb_canvas",
                error_detail=str(exc),
                llm_recovery_instruction=(
                    "Provide a valid 7-digit KB ID formatted as 'KB0015760'..'KB0016050', or "
                    "call `stage_servicenow_case_intake_form` if the user's topic is not covered "
                    "by the standard Coupa Knowledge Base."
                ),
                suggested_next_tool="stage_servicenow_case_intake_form",
            ).model_dump()

        rag_chunks = get_memory_service().search_knowledge_base(
            query=f"{validated.kb_article_id} {validated.topic_focus or ''}".strip(),
            top_k=2,
        )
        surface_pkg = build_interactive_kb_canvas(
            kb_article_id=validated.kb_article_id,
            topic_focus=validated.topic_focus,
        )
        state = tool_context.state if tool_context is not None else None
        queue_a2ui_surface(state, surface_pkg)

        kb_entry = KB_ARTICLES_CATALOG.get(validated.kb_article_id, {})
        return {
            "status": "KB_CANVAS_OPENED",
            "kb_article_id": validated.kb_article_id,
            "title": kb_entry.get(
                "title",
                f"{validated.kb_article_id} — Enterprise GBS Knowledge Guide",
            ),
            "summary": kb_entry.get(
                "summary",
                "Step-by-step Coupa & Procurement workflow opened in the Side-Panel Canvas.",
            ),
            "steps": [
                {"heading": h, "instruction": b}
                for h, b in kb_entry.get("steps", [])
            ],
            "rag_supporting_sections": [c["section_title"] for c in rag_chunks],
            "a2ui_surface_id": surface_pkg["surface_id"],
        }


def evaluate_supplier_exemption_status(
    supplier_name: str,
    invoice_number: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Evaluates whether a supplier qualifies for PDF email e-billing (`KB0015802`).

    Summary:
        Checks the Supplier Email Exemptions Registry (`RULE-05` / `KB0015802`) when an
        invoice is missing from Coupa to determine if the vendor is an `EXEMPT`
        regulated utility/municipal entity (permitted to email regional AP mailboxes)
        or a `NON-EXEMPT` commercial vendor (required to submit via Coupa Supplier Portal).

    Business Rules:
        - `EXEMPT` vendors (`PACIFIC GRID ENERGY CORP`, `AQUAFLOW UTILITIES LTD`,
          `METRO MUNICIPAL WATER AUTHORITY`) submit PDFs to regional `ap-ebilling-*` mailboxes.
        - `NON-EXEMPT` vendors (`NOVATECH LEASING SERVICES`, `TITAN EARTHWORKS LLC`,
          `CRESTLINE BUILDERS INC`, and all unlisted commercial vendors) must use CSP.

    Args:
        supplier_name: Legal or trading name of the supplier to evaluate.
        invoice_number: Optional missing invoice number being investigated.
        tool_context: ADK `ToolContext` injected automatically at runtime.

    Returns:
        dict[str, Any]: Exemption status (`EXEMPT` or `NON-EXEMPT`), permitted submission
        channel, and KB reference `KB0015802`.

    Example:
        >>> res = evaluate_supplier_exemption_status("Pacific Grid Energy Corp")
        >>> res["exemption_status"]
        'EXEMPT'
    """
    with start_agent_span(
        "gbs.tool_execution",
        {"tool.name": "evaluate_supplier_exemption_status", "supplier_name": supplier_name},
    ):
        try:
            validated = SupplierExemptionInput(
                supplier_name=supplier_name,
                invoice_number=invoice_number,
            )
        except ValidationError as exc:
            return GuidedToolErrorResponse(
                error_code="INVALID_SUPPLIER_NAME",
                failed_tool="evaluate_supplier_exemption_status",
                error_detail=str(exc),
                llm_recovery_instruction=(
                    "Provide a non-empty `supplier_name`, or call "
                    "`request_missing_invoice_identifier_form` to ask the user for the vendor name."
                ),
                suggested_next_tool="request_missing_invoice_identifier_form",
            ).model_dump()

        norm = normalize_key(validated.supplier_name)
        entry = SUPPLIER_EXEMPTIONS_REGISTRY.get(norm)
        if entry is None:
            for key, candidate in SUPPLIER_EXEMPTIONS_REGISTRY.items():
                if norm in key or key in norm:
                    entry = candidate
                    break

        if entry is not None:
            return {
                "status": "REGISTRY_MATCHED",
                "invoice_number": validated.invoice_number or "N/A",
                **entry,
            }

        return {
            "status": "DEFAULT_NON_EXEMPT_POLICY",
            "invoice_number": validated.invoice_number or "N/A",
            "supplier_name": validated.supplier_name,
            "exemption_status": "NON-EXEMPT",
            "submission_channel": (
                "Supplier is not on the Regulated Utility Exemptions Registry (KB0015802). "
                "Standard Enterprise Policy applies: invoices MUST be submitted digitally "
                "through the Coupa Supplier Portal (CSP); emailed PDFs are not processed."
            ),
            "kb_reference": "KB0015802",
        }
