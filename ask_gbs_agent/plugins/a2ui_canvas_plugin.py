"""Gemini Enterprise A2UI v0.9 Canvas & Inline MaterialCard Plugin.

Implements all 5 A2UI v0.9 surfaces (Surfaces A–E) plus the Urgent Payment
Acceleration Card using the official Gemini Enterprise composite catalog:
`https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json`

Every generated payload strictly conforms to Gemini Enterprise A2UI v0.9 rules:
1. Envelope messages carry `"version": "v0.9"`.
2. `createSurface.catalogId` matches `GE_COMPOSITE_CATALOG_ID`.
3. `surfaceId` is consistent across `createSurface`, `updateComponents`, and `updateDataModel`.
4. `updateComponents.components` has a unique `"id": "root"` (`MaterialCard` or `Canvas`).
5. `Canvas` and `MaterialCard` roots specify `"children": ["<child_id>", ...]` (`ChildList`).
6. Every referenced `children` component ID resolves to a valid component with zero cycles,
   and every component property matches the strict official Zod catalog schema with zero
   unrecognized keys (`MaterialIcon.icon`, `MaterialExpansionPanel.children`, etc.).
7. `MaterialTable` specifies `columns` (`header`, `field`) and string-typed `rows`, paired with
   `VegaChart` bound via `updateDataModel` (`DynamicValue` `DataBinding`).
8. `MaterialExpansionPanel` titles are strictly `<= 62` characters.
9. `MaterialButton` actions follow `{"event": {"name": "...", "context": {...}}}`.
10. Packaged wire payloads wrap JSON inside `<a2a_datapart_json>...</a2a_datapart_json>` with
    `mimeType = "application/json+a2ui"` and `readable_text` fallback metadata.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin
from google.genai import types

from ask_gbs_agent.observability.structured_logger import get_structured_logger
from ask_gbs_agent.observability.tracing import start_agent_span

A2UI_VERSION = "v0.9"
GE_COMPOSITE_CATALOG_ID = (
    "https://www.gstatic.com/vertexaisearch/a2ui/v0_9/"
    "gemini_enterprise_composite_catalog.json"
)
A2UI_MIME_TYPE = "application/json+a2ui"
MAX_EXPANSION_TITLE_LEN = 62

_LOGGER = get_structured_logger("ask_gbs_agent.a2ui_plugin")


def _safe_surface_slug(raw: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", raw.strip()).strip("-")
    return slug[:48] or "default"


def _clamp_title(title: str, max_len: int = MAX_EXPANSION_TITLE_LEN) -> str:
    cleaned = " ".join(title.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def package_a2ui_datapart(
    a2ui_messages: list[dict[str, Any]],
    surface_id: str,
    readable_text: str,
) -> dict[str, Any]:
    """Packages an A2UI v0.9 message array into the `<a2a_datapart_json>` wire envelope."""
    with start_agent_span(
        "gbs.a2ui_canvas_build",
        {"surface_id": surface_id, "message_count": len(a2ui_messages)},
    ):
        envelope = {
            "kind": "data",
            "mimeType": A2UI_MIME_TYPE,
            "data": a2ui_messages,
            "metadata": {
                "mimeType": A2UI_MIME_TYPE,
                "surface_id": surface_id,
                "readable_text": readable_text,
            },
        }
        wire_tag = f"<a2a_datapart_json>{json.dumps(envelope, ensure_ascii=False)}</a2a_datapart_json>"
        return {
            "surface_id": surface_id,
            "mime_type": A2UI_MIME_TYPE,
            "readable_text": readable_text,
            "messages": a2ui_messages,
            "envelope": envelope,
            "wire_tag": wire_tag,
        }


def build_genai_a2ui_parts(packaged_surface: dict[str, Any]) -> list[types.Part]:
    """Converts a packaged A2UI surface into ADK `inline_data` A2A `DataPart` blobs.

    ADK's `convert_genai_part_to_a2a_part` translates `Part(inline_data=Blob(
    mime_type='text/plain', data=b'<a2a_datapart_json>...</a2a_datapart_json>'),
    part_metadata={'mimeType': 'application/json+a2ui', ...})` into structured A2A
    `DataPart` protocol messages rather than plain chat `TextPart` strings.
    """
    messages = packaged_surface.get("messages") or []
    surface_id = str(packaged_surface.get("surface_id") or "gbs-surface")
    readable_text = str(packaged_surface.get("readable_text") or "Interactive GBS A2UI Surface")
    meta = {
        "mimeType": A2UI_MIME_TYPE,
        "surface_id": surface_id,
        "readable_text": readable_text,
    }

    is_a2a_v1 = True
    try:
        from google.adk.a2a import _compat as adk_a2a_compat

        is_a2a_v1 = bool(getattr(adk_a2a_compat, "IS_A2A_V1", True))
    except Exception:
        pass

    out_parts: list[types.Part] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        payload_obj = msg if is_a2a_v1 else {"kind": "data", "data": msg, "metadata": meta}
        raw_bytes = (
            b"<a2a_datapart_json>"
            + json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
            + b"</a2a_datapart_json>"
        )
        out_parts.append(
            types.Part(
                inline_data=types.Blob(
                    data=raw_bytes,
                    mime_type="text/plain",
                ),
                part_metadata=dict(meta),
            )
        )
    return out_parts


def queue_a2ui_surface(
    state: Optional[dict[str, Any]],
    packaged_surface: dict[str, Any],
) -> None:
    """Queues a packaged A2UI surface on ADK session/tool state for model attachment."""
    if state is None:
        return
    pending = list(state.get("pending_a2ui_parts") or [])
    # Avoid duplicate surface IDs within the same turn
    pending = [p for p in pending if p.get("surface_id") != packaged_surface.get("surface_id")]
    pending.append(packaged_surface)
    state["pending_a2ui_parts"] = pending
    state["last_a2ui_surface_id"] = packaged_surface.get("surface_id")


def build_servicenow_intake_form_card(
    service_area: str = "INVOICE_SUPPORT",
    reference_number: str = "2158",
    priority: str = "P2",
    requester_email: str = "alex.rivera@enterprise-gbs.example.com",
    description: str = (
        "Approved Invoice 2158 ($22,772.00 USD, Titan Earthworks LLC, PO #1763463) "
        "billed for incorrect amount. Requesting immediate Oracle payment hold and Credit Memo."
    ),
) -> dict[str, Any]:
    """Builds Surface A: Inline `MaterialCard` ServiceNow Case Intake Form (Step 1 HITL)."""
    surface_id = "gbs-servicenow-intake-form"
    messages: list[dict[str, Any]] = [
        {
            "version": A2UI_VERSION,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_COMPOSITE_CATALOG_ID,
                "sendDataModel": True,
            },
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "root",
                        "component": "MaterialCard",
                        "appearance": "outlined",
                        "children": ["sn-form-col"],
                    },
                    {
                        "id": "sn-form-col",
                        "component": "MaterialColumn",
                        "style": {"gap": "12px", "padding": "16px"},
                        "children": [
                            "sn-header-row",
                            "sn-subtitle",
                            "sn-div-1",
                            "sn-select-category",
                            "sn-input-ref",
                            "sn-select-priority",
                            "sn-input-email",
                            "sn-input-description",
                            "sn-btn-row",
                        ],
                    },
                    {
                        "id": "sn-header-row",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px"},
                        "children": ["sn-icon", "sn-title"],
                    },
                    {
                        "id": "sn-icon",
                        "component": "MaterialIcon",
                        "icon": "support_agent",
                        "color": "primary",
                    },
                    {
                        "id": "sn-title",
                        "component": "MaterialText",
                        "text": "Create ServiceNow Support Case — Human Specialist Handoff",
                        "usageHint": "h4",
                    },
                    {
                        "id": "sn-subtitle",
                        "component": "MaterialText",
                        "text": (
                            "This request requires GBS specialist intervention. Review or edit "
                            "the fields below and click Submit ServiceNow Case."
                        ),
                        "usageHint": "body2",
                    },
                    {
                        "id": "sn-div-1",
                        "component": "MaterialDivider",
                    },
                    {
                        "id": "sn-select-category",
                        "component": "MaterialSelect",
                        "label": "GBS Service Area",
                        "value": {"path": "/snTicket/serviceArea"},
                        "options": [
                            {
                                "label": "Supplier Invoice Support (GBS-Global-AP-InvoiceProcessing)",
                                "value": "INVOICE_SUPPORT",
                            },
                            {
                                "label": "Supplier Payment & Remittance (GBS-Regional-Payments-Remittance)",
                                "value": "PAYMENT_SUPPORT",
                            },
                            {
                                "label": "Urgent / Early Payment Release (GBS-EMEA-AP-UrgentPayments)",
                                "value": "URGENT_PAYMENT",
                            },
                            {
                                "label": "Senior AP Legal / Hold Escalation (GBS-Senior-AP-Escalations)",
                                "value": "LEGAL_ESCALATION",
                            },
                            {
                                "label": "Vendor Management & Security (GBS-Vendor-Management-Security)",
                                "value": "VENDOR_SECURITY",
                            },
                            {
                                "label": "General Finance & Procurement Triage (GBS-General-Helpdesk-Triage)",
                                "value": "GENERAL_TRIAGE",
                            },
                        ],
                    },
                    {
                        "id": "sn-input-ref",
                        "component": "MaterialInput",
                        "label": "Invoice, PO, or Supplier Reference Number",
                        "placeholder": "e.g., 2158, INV00026056, or Custom Inquiry",
                        "value": {"path": "/snTicket/referenceNumber"},
                    },
                    {
                        "id": "sn-select-priority",
                        "component": "MaterialSelect",
                        "label": "Urgency / Priority Level",
                        "value": {"path": "/snTicket/priority"},
                        "options": [
                            {
                                "label": "P1 — Critical (Supplier Account Freeze / Legal Demand)",
                                "value": "P1",
                            },
                            {
                                "label": "P2 — High (Approved Invoice Hold / Urgent Payment)",
                                "value": "P2",
                            },
                            {
                                "label": "P3 — Standard (General Inquiry / Remittance Advice)",
                                "value": "P3",
                            },
                        ],
                    },
                    {
                        "id": "sn-input-email",
                        "component": "MaterialInput",
                        "label": "Requester Contact Email",
                        "type": "email",
                        "placeholder": "e.g., alex.rivera@enterprise-gbs.example.com",
                        "value": {"path": "/snTicket/requesterEmail"},
                    },
                    {
                        "id": "sn-input-description",
                        "component": "MaterialInput",
                        "label": "Case Description & Action Requested",
                        "placeholder": "Describe the issue and required specialist action...",
                        "value": {"path": "/snTicket/description"},
                    },
                    {
                        "id": "sn-btn-row",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px", "flexWrap": "wrap"},
                        "children": ["btn-submit-sn", "btn-cancel-sn"],
                    },
                    {
                        "id": "btn-submit-sn",
                        "component": "MaterialButton",
                        "label": "Submit ServiceNow Case",
                        "variant": "raised",
                        "color": "primary",
                        "leadingIcon": "task_alt",
                        "action": {
                            "event": {
                                "name": "confirm_create_servicenow_case",
                                "context": {
                                    "serviceArea": {"path": "/snTicket/serviceArea"},
                                    "referenceNumber": {"path": "/snTicket/referenceNumber"},
                                    "priority": {"path": "/snTicket/priority"},
                                    "requesterEmail": {"path": "/snTicket/requesterEmail"},
                                    "description": {"path": "/snTicket/description"},
                                },
                            }
                        },
                    },
                    {
                        "id": "btn-cancel-sn",
                        "component": "MaterialButton",
                        "label": "Cancel",
                        "variant": "basic",
                        "action": {
                            "event": {
                                "name": "cancel_servicenow_case",
                                "context": {"status": "cancelled"},
                            }
                        },
                    },
                ],
            },
        },
        {
            "version": A2UI_VERSION,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/snTicket",
                "value": {
                    "serviceArea": service_area,
                    "referenceNumber": reference_number,
                    "priority": priority,
                    "requesterEmail": requester_email,
                    "description": description,
                },
            },
        },
    ]
    readable = (
        f"ServiceNow Case Intake Form ({service_area}, Ref: {reference_number}, Priority: {priority})"
    )
    return package_a2ui_datapart(messages, surface_id=surface_id, readable_text=readable)


def build_servicenow_receipt_card(
    case_number: str = "CS9940120",
    assignment_group: str = "GBS-Global-AP-InvoiceProcessing",
    priority_label: str = "P2 — High",
    target_sla: str = "4 Business Hours",
    reference_number: str = "2158",
    requester_email: str = "alex.rivera@enterprise-gbs.example.com",
) -> dict[str, Any]:
    """Builds Surface B: Inline `MaterialCard` ServiceNow Case Confirmation Receipt (Step 2)."""
    surface_id = f"gbs-servicenow-receipt-{_safe_surface_slug(case_number)}"
    details_md = (
        f"• **Case Number**: `{case_number}`\n"
        f"• **Status**: `New — Assigned`\n"
        f"• **Assignment Group**: `{assignment_group}`\n"
        f"• **Priority & Target SLA**: `{priority_label}` ({target_sla})\n"
        f"• **Reference Number**: `{reference_number}`\n"
        f"• **Submitted By**: `{requester_email}`"
    )
    messages: list[dict[str, Any]] = [
        {
            "version": A2UI_VERSION,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_COMPOSITE_CATALOG_ID,
            },
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "root",
                        "component": "MaterialCard",
                        "appearance": "outlined",
                        "children": ["receipt-col"],
                    },
                    {
                        "id": "receipt-col",
                        "component": "MaterialColumn",
                        "style": {"gap": "12px", "padding": "16px"},
                        "children": [
                            "receipt-header",
                            "receipt-div",
                            "receipt-details",
                            "receipt-note",
                        ],
                    },
                    {
                        "id": "receipt-header",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px"},
                        "children": ["receipt-icon", "receipt-title"],
                    },
                    {
                        "id": "receipt-icon",
                        "component": "MaterialIcon",
                        "icon": "check_circle",
                        "color": "primary",
                    },
                    {
                        "id": "receipt-title",
                        "component": "MaterialText",
                        "text": f"ServiceNow Case Created — {case_number}",
                        "usageHint": "h4",
                    },
                    {
                        "id": "receipt-div",
                        "component": "MaterialDivider",
                    },
                    {
                        "id": "receipt-details",
                        "component": "MaterialText",
                        "text": details_md,
                        "usageHint": "body1",
                    },
                    {
                        "id": "receipt-note",
                        "component": "MaterialText",
                        "text": (
                            "Illustrative Demo Workflow: Case confirmation generated with full "
                            "context transfer. No live backend ServiceNow mutation was executed."
                        ),
                        "usageHint": "caption",
                    },
                ],
            },
        },
    ]
    readable = f"ServiceNow Case Confirmation Receipt {case_number} ({assignment_group})"
    return package_a2ui_datapart(messages, surface_id=surface_id, readable_text=readable)


def build_missing_identifier_lookup_card(
    inquiry_type: str = "INVOICE_STATUS",
    prompt_note: str = "Provide your Invoice Number, PO Number, or Supplier Name to run an instant Coupa + Oracle diagnostic.",
) -> dict[str, Any]:
    """Builds Surface C: Inline `MaterialCard` Quick-Lookup Form when identifier is omitted."""
    surface_id = "gbs-missing-identifier-card"
    messages: list[dict[str, Any]] = [
        {
            "version": A2UI_VERSION,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_COMPOSITE_CATALOG_ID,
                "sendDataModel": True,
            },
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "root",
                        "component": "MaterialCard",
                        "appearance": "outlined",
                        "children": ["lookup-col"],
                    },
                    {
                        "id": "lookup-col",
                        "component": "MaterialColumn",
                        "style": {"gap": "12px", "padding": "16px"},
                        "children": [
                            "lookup-header",
                            "lookup-subtitle",
                            "lookup-div",
                            "lookup-input-id",
                            "lookup-input-supplier",
                            "lookup-select-type",
                            "lookup-btn-row",
                        ],
                    },
                    {
                        "id": "lookup-header",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px"},
                        "children": ["lookup-icon", "lookup-title"],
                    },
                    {
                        "id": "lookup-icon",
                        "component": "MaterialIcon",
                        "icon": "manage_search",
                        "color": "primary",
                    },
                    {
                        "id": "lookup-title",
                        "component": "MaterialText",
                        "text": "Ask GBS Quick-Lookup — Invoice & Payment Diagnostic",
                        "usageHint": "h4",
                    },
                    {
                        "id": "lookup-subtitle",
                        "component": "MaterialText",
                        "text": prompt_note,
                        "usageHint": "body2",
                    },
                    {
                        "id": "lookup-div",
                        "component": "MaterialDivider",
                    },
                    {
                        "id": "lookup-input-id",
                        "component": "MaterialInput",
                        "label": "Invoice Number, Coupa ID, or PO Number",
                        "placeholder": "e.g., INV00026056, 2158, 23469, or PO #1763463",
                        "value": {"path": "/quickLookup/identifier"},
                    },
                    {
                        "id": "lookup-input-supplier",
                        "component": "MaterialInput",
                        "label": "Supplier Name (Optional)",
                        "placeholder": "e.g., FieldSync Ops Ltd or Pacific Grid Energy Corp",
                        "value": {"path": "/quickLookup/supplierName"},
                    },
                    {
                        "id": "lookup-select-type",
                        "component": "MaterialSelect",
                        "label": "Helpdesk Topic",
                        "value": {"path": "/quickLookup/inquiryType"},
                        "options": [
                            {"label": "Invoice Approval / Hold Status", "value": "INVOICE_STATUS"},
                            {"label": "Payment Due Date / EFT Remittance", "value": "PAYMENT_INQUIRY"},
                            {"label": "Purchase Order / Goods Receipt", "value": "PO_SUPPORT"},
                            {"label": "General Finance / Procurement Inquiry", "value": "GENERAL"},
                        ],
                    },
                    {
                        "id": "lookup-btn-row",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px", "flexWrap": "wrap"},
                        "children": ["btn-run-lookup", "btn-open-sn-fallback"],
                    },
                    {
                        "id": "btn-run-lookup",
                        "component": "MaterialButton",
                        "label": "Check Coupa & Oracle Status",
                        "variant": "raised",
                        "color": "primary",
                        "leadingIcon": "search",
                        "action": {
                            "event": {
                                "name": "submit_invoice_quick_lookup",
                                "context": {
                                    "identifier": {"path": "/quickLookup/identifier"},
                                    "supplierName": {"path": "/quickLookup/supplierName"},
                                    "inquiryType": {"path": "/quickLookup/inquiryType"},
                                },
                            }
                        },
                    },
                    {
                        "id": "btn-open-sn-fallback",
                        "component": "MaterialButton",
                        "label": "No Invoice # — Open Support Case",
                        "variant": "basic",
                        "action": {
                            "event": {
                                "name": "request_servicenow_intake_form",
                                "context": {"reason": "no_identifier_available"},
                            }
                        },
                    },
                ],
            },
        },
        {
            "version": A2UI_VERSION,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/quickLookup",
                "value": {
                    "identifier": "",
                    "supplierName": "",
                    "inquiryType": inquiry_type,
                },
            },
        },
    ]
    readable = "Ask GBS Quick-Lookup Card (awaiting Invoice, PO, or Supplier identifier)"
    return package_a2ui_datapart(messages, surface_id=surface_id, readable_text=readable)


def build_invoice_payment_status_card(
    record: dict[str, Any],
) -> dict[str, Any]:
    """Builds Surface D: Inline `MaterialCard` Coupa + Oracle Diagnostic Tracker Card."""
    inv_num = str(record.get("invoice_number", "UNKNOWN"))
    surface_id = f"gbs-invoice-status-{_safe_surface_slug(inv_num)}"
    supplier = str(record.get("supplier_name", "Enterprise Supplier"))
    coupa_status = str(record.get("coupa_status", "N/A"))
    oracle_status = str(record.get("oracle_payment_status", "N/A"))
    pdf_date = str(record.get("invoice_pdf_date", "N/A"))
    sub_date = str(record.get("coupa_submission_date", "N/A"))
    due_date = str(record.get("calculated_net_due_date", "N/A"))
    amount = str(record.get("billed_amount", "0.00 USD"))
    eft_ref = str(record.get("eft_reference") or "Pending / N/A")
    bank_masked = str(record.get("masked_bank_account", "N/A"))
    kb_ref = str(record.get("kb_reference", "KB0015901"))
    confidence = int(record.get("confidence_score", 95))
    summary = str(record.get("diagnostic_summary", ""))

    metrics_md = (
        f"• **Supplier**: `{supplier}` | **Billed Amount**: `{amount}`\n"
        f"• **Coupa Status**: `{coupa_status}` (Coupa ID: `{record.get('coupa_id', 'N/A')}`)\n"
        f"• **Oracle Status**: `{oracle_status}` (Voucher: `{record.get('oracle_voucher_id', 'N/A')}` | EFT: `{eft_ref}`)\n"
        f"• **Net 30 Terms Math (`KB0015901`)**: PDF Date `{pdf_date}` → Coupa Submitted `{sub_date}` → **Net Due `{due_date}`**\n"
        f"• **Remit-To Bank**: `{bank_masked}` | **Diagnostic Confidence**: `{confidence}%`"
    )

    messages: list[dict[str, Any]] = [
        {
            "version": A2UI_VERSION,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_COMPOSITE_CATALOG_ID,
            },
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "root",
                        "component": "MaterialCard",
                        "appearance": "outlined",
                        "children": ["status-col"],
                    },
                    {
                        "id": "status-col",
                        "component": "MaterialColumn",
                        "style": {"gap": "12px", "padding": "16px"},
                        "children": [
                            "status-header",
                            "status-div",
                            "status-metrics",
                            "status-summary",
                            "status-actions",
                        ],
                    },
                    {
                        "id": "status-header",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px"},
                        "children": ["status-icon", "status-title"],
                    },
                    {
                        "id": "status-icon",
                        "component": "MaterialIcon",
                        "icon": "receipt_long",
                        "color": "primary",
                    },
                    {
                        "id": "status-title",
                        "component": "MaterialText",
                        "text": f"Cross-System Coupa & Oracle Tracker — {inv_num}",
                        "usageHint": "h4",
                    },
                    {
                        "id": "status-div",
                        "component": "MaterialDivider",
                    },
                    {
                        "id": "status-metrics",
                        "component": "MaterialText",
                        "text": metrics_md,
                        "usageHint": "body1",
                    },
                    {
                        "id": "status-summary",
                        "component": "MaterialText",
                        "text": summary,
                        "usageHint": "body2",
                    },
                    {
                        "id": "status-actions",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px", "flexWrap": "wrap"},
                        "children": [
                            "btn-open-kb-canvas",
                            "btn-urgent-pay",
                            "btn-escalate-sn",
                        ],
                    },
                    {
                        "id": "btn-open-kb-canvas",
                        "component": "MaterialButton",
                        "label": f"Open {kb_ref} in Canvas",
                        "variant": "stroked",
                        "leadingIcon": "menu_book",
                        "action": {
                            "event": {
                                "name": "open_kb_in_canvas",
                                "context": {
                                    "kbArticleId": kb_ref,
                                    "invoiceNumber": inv_num,
                                },
                            }
                        },
                    },
                    {
                        "id": "btn-urgent-pay",
                        "component": "MaterialButton",
                        "label": "Request Urgent Payment",
                        "variant": "basic",
                        "action": {
                            "event": {
                                "name": "request_urgent_early_payment",
                                "context": {
                                    "invoiceNumber": inv_num,
                                    "supplierName": supplier,
                                },
                            }
                        },
                    },
                    {
                        "id": "btn-escalate-sn",
                        "component": "MaterialButton",
                        "label": "Create ServiceNow Case",
                        "variant": "raised",
                        "color": "primary",
                        "action": {
                            "event": {
                                "name": "request_servicenow_intake_form",
                                "context": {
                                    "referenceNumber": inv_num,
                                    "supplierName": supplier,
                                },
                            }
                        },
                    },
                ],
            },
        },
    ]
    readable = f"Coupa/Oracle Status Card for {inv_num} ({supplier}: {coupa_status} / {oracle_status})"
    return package_a2ui_datapart(messages, surface_id=surface_id, readable_text=readable)


def build_urgent_payment_intake_card(
    invoice_number: str = "INV00026056",
    supplier_name: str = "FieldSync Ops Ltd",
    geography: str = "EMEA",
    operating_unit: str = "UK-OPS-01",
    requested_payment_date: str = "2026-01-05",
    business_justification: str = "Critical field operations continuity requirement.",
    requester_email: str = "requester@enterprise-gbs.example.com",
) -> dict[str, Any]:
    """Builds the Regional Urgent Payment Acceleration Intake Card (`KB0015901`)."""
    surface_id = f"gbs-urgent-payment-{_safe_surface_slug(invoice_number)}"
    target_queue = (
        "GBS-EMEA-AP-UrgentPayments"
        if geography == "EMEA"
        else "GBS-AMER-AP-EarlyPaymentRelease"
    )
    messages: list[dict[str, Any]] = [
        {
            "version": A2UI_VERSION,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_COMPOSITE_CATALOG_ID,
                "sendDataModel": True,
            },
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "root",
                        "component": "MaterialCard",
                        "appearance": "outlined",
                        "children": ["urgent-col"],
                    },
                    {
                        "id": "urgent-col",
                        "component": "MaterialColumn",
                        "style": {"gap": "12px", "padding": "16px"},
                        "children": [
                            "urgent-header",
                            "urgent-note",
                            "urgent-div",
                            "urgent-select-geo",
                            "urgent-input-ou",
                            "urgent-input-date",
                            "urgent-input-just",
                            "urgent-btn-row",
                        ],
                    },
                    {
                        "id": "urgent-header",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px"},
                        "children": ["urgent-icon", "urgent-title"],
                    },
                    {
                        "id": "urgent-icon",
                        "component": "MaterialIcon",
                        "icon": "bolt",
                        "color": "primary",
                    },
                    {
                        "id": "urgent-title",
                        "component": "MaterialText",
                        "text": f"Urgent Early Payment Intake — {invoice_number}",
                        "usageHint": "h4",
                    },
                    {
                        "id": "urgent-note",
                        "component": "MaterialText",
                        "text": (
                            f"Supplier: {supplier_name} | Target Treasury Queue: {target_queue}. "
                            "Out-of-cycle EFT releases require Controller business impact justification (KB0015901)."
                        ),
                        "usageHint": "body2",
                    },
                    {
                        "id": "urgent-div",
                        "component": "MaterialDivider",
                    },
                    {
                        "id": "urgent-select-geo",
                        "component": "MaterialSelect",
                        "label": "Treasury Geography",
                        "value": {"path": "/urgentPay/geography"},
                        "options": [
                            {"label": "EMEA (GBS-EMEA-AP-UrgentPayments)", "value": "EMEA"},
                            {"label": "AMER (GBS-AMER-AP-EarlyPaymentRelease)", "value": "AMER"},
                            {"label": "APAC (GBS-EMEA-AP-UrgentPayments)", "value": "APAC"},
                        ],
                    },
                    {
                        "id": "urgent-input-ou",
                        "component": "MaterialInput",
                        "label": "Operating Unit / Legal Entity",
                        "value": {"path": "/urgentPay/operatingUnit"},
                    },
                    {
                        "id": "urgent-input-date",
                        "component": "MaterialInput",
                        "label": "Requested Early Payment Date (YYYY-MM-DD)",
                        "type": "date",
                        "value": {"path": "/urgentPay/requestedDate"},
                    },
                    {
                        "id": "urgent-input-just",
                        "component": "MaterialInput",
                        "label": "Controller Business Impact Justification",
                        "value": {"path": "/urgentPay/justification"},
                    },
                    {
                        "id": "urgent-btn-row",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px", "flexWrap": "wrap"},
                        "children": ["btn-submit-urgent"],
                    },
                    {
                        "id": "btn-submit-urgent",
                        "component": "MaterialButton",
                        "label": "Submit Urgent Payment Case",
                        "variant": "raised",
                        "color": "primary",
                        "leadingIcon": "send",
                        "action": {
                            "event": {
                                "name": "confirm_create_servicenow_case",
                                "context": {
                                    "serviceArea": "URGENT_PAYMENT",
                                    "referenceNumber": invoice_number,
                                    "priority": "P2",
                                    "requesterEmail": requester_email,
                                    "description": {"path": "/urgentPay/justification"},
                                },
                            }
                        },
                    },
                ],
            },
        },
        {
            "version": A2UI_VERSION,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/urgentPay",
                "value": {
                    "geography": geography,
                    "operatingUnit": operating_unit,
                    "requestedDate": requested_payment_date,
                    "justification": business_justification,
                },
            },
        },
    ]
    readable = f"Urgent Payment Acceleration Form for {invoice_number} ({target_queue})"
    return package_a2ui_datapart(messages, surface_id=surface_id, readable_text=readable)


def build_multi_invoice_reconciliation_canvas() -> dict[str, Any]:
    """Builds Surface E (Reconciliation): Side-Panel `Canvas` with `MaterialTable` & `VegaChart` (`PAY-03`)."""
    surface_id = "gbs-biodata-reconciliation-canvas"
    table_columns = [
        {"header": "Invoice #", "field": "invoice_number"},
        {"header": "Coupa ID", "field": "coupa_id"},
        {"header": "Backing PO", "field": "po_number"},
        {"header": "Amount (GBP)", "field": "amount_gbp"},
        {"header": "Coupa Status", "field": "coupa_status"},
        {"header": "Oracle Payment / Blocker", "field": "oracle_status"},
    ]
    table_rows = [
        {
            "invoice_number": "23469",
            "coupa_id": "709187",
            "po_number": "PO #UK1734685",
            "amount_gbp": "2,196.85",
            "coupa_status": "Approved",
            "oracle_status": "PAID 2026-01-16 (EFT 1667857)",
        },
        {
            "invoice_number": "23104",
            "coupa_id": "711204",
            "po_number": "PO #UK1734685",
            "amount_gbp": "940.00",
            "coupa_status": "Pending Approval",
            "oracle_status": "Unpaid — Awaiting PM Approval",
        },
        {
            "invoice_number": "23288",
            "coupa_id": "715890",
            "po_number": "PO #UK1754578",
            "amount_gbp": "1,450.00",
            "coupa_status": "Pending Receipt",
            "oracle_status": "Blocked — Missing 3-Way Goods Receipt",
        },
    ]

    vega_spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "BioData Registry Online Statement Spend by Payment State (GBP)",
        "data": {
            "values": [
                {"invoice": "23469 (Paid)", "amount_gbp": 2196.85, "state": "Paid via EFT"},
                {"invoice": "23104 (Pending Approval)", "amount_gbp": 940.00, "state": "Pending PM Approval"},
                {"invoice": "23288 (Pending Receipt)", "amount_gbp": 1450.00, "state": "3-Way Match Hold"},
            ]
        },
        "mark": "bar",
        "encoding": {
            "x": {"field": "invoice", "type": "nominal", "title": "Statement Invoice"},
            "y": {"field": "amount_gbp", "type": "quantitative", "title": "Amount (GBP)"},
            "color": {"field": "state", "type": "nominal", "title": "Reconciliation State"},
        },
    }

    messages: list[dict[str, Any]] = [
        {
            "version": A2UI_VERSION,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_COMPOSITE_CATALOG_ID,
            },
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "root",
                        "component": "Canvas",
                        "autoOpen": True,
                        "cardTitle": "BioData Registry Online — Statement Reconciliation",
                        "cardDescription": "3-invoice Coupa + Oracle audit (4,586.85 GBP) with P1 Legal Escalation",
                        "cardIcon": "table_chart",
                        "children": ["canvas-main-col"],
                    },
                    {
                        "id": "canvas-main-col",
                        "component": "MaterialColumn",
                        "style": {"gap": "14px", "padding": "16px"},
                        "children": [
                            "canvas-title",
                            "canvas-subtitle",
                            "canvas-div-top",
                            "canvas-table",
                            "canvas-chart",
                            "canvas-acc-1",
                            "canvas-acc-2",
                            "canvas-action-row",
                        ],
                    },
                    {
                        "id": "canvas-title",
                        "component": "MaterialText",
                        "text": "BioData Registry Online — Legal Hold Statement Reconciliation",
                        "usageHint": "h3",
                    },
                    {
                        "id": "canvas-subtitle",
                        "component": "MaterialText",
                        "text": (
                            "Total Statement: 4,586.85 GBP across 3 invoices | Paid: 2,196.85 GBP | "
                            "Blocked in Coupa: 2,390.00 GBP | Mandatory P1 Escalation Policy (RULE-06)"
                        ),
                        "usageHint": "body2",
                    },
                    {
                        "id": "canvas-div-top",
                        "component": "MaterialDivider",
                    },
                    {
                        "id": "canvas-table",
                        "component": "MaterialTable",
                        "caption": "BioData Registry Online Statement Invoices (Coupa + Oracle)",
                        "columns": table_columns,
                        "rows": table_rows,
                    },
                    {
                        "id": "canvas-chart",
                        "component": "VegaChart",
                        "spec": {"path": "/reconciliation/vegaSpec"},
                        "height": 260,
                    },
                    {
                        "id": "canvas-acc-1",
                        "component": "MaterialExpansionPanel",
                        "title": _clamp_title("1. Immediate Remittance Proof for Invoice 23469"),
                        "expanded": True,
                        "children": ["canvas-acc-1-body"],
                    },
                    {
                        "id": "canvas-acc-1-body",
                        "component": "MaterialText",
                        "text": (
                            "Share Oracle EFT Reference 1667857 (2,196.85 GBP paid 2026-01-16 to "
                            "HSBC UK xxx8810) with BioData Registry Online collections immediately."
                        ),
                        "usageHint": "body2",
                    },
                    {
                        "id": "canvas-acc-2",
                        "component": "MaterialExpansionPanel",
                        "title": _clamp_title("2. Unblocking Invoices 23104 & 23288 + P1 Escalation"),
                        "expanded": True,
                        "children": ["canvas-acc-2-body"],
                    },
                    {
                        "id": "canvas-acc-2-body",
                        "component": "MaterialText",
                        "text": (
                            "• Invoice 23104 (940.00 GBP): Approve in Coupa on PO #UK1734685.\n"
                            "• Invoice 23288 (1,450.00 GBP): Enter Goods Receipt (Truck Icon, KB0015849) on PO #UK1754578.\n"
                            "• Escalate P1 Case to GBS-Senior-AP-Escalations (2-Hour SLA) to prevent account freeze."
                        ),
                        "usageHint": "body2",
                    },
                    {
                        "id": "canvas-action-row",
                        "component": "MaterialRow",
                        "align": "center",
                        "style": {"gap": "8px", "flexWrap": "wrap"},
                        "children": ["btn-canvas-p1-case"],
                    },
                    {
                        "id": "btn-canvas-p1-case",
                        "component": "MaterialButton",
                        "label": "Confirm P1 Senior AP Escalation Case",
                        "variant": "raised",
                        "color": "warn",
                        "leadingIcon": "gavel",
                        "action": {
                            "event": {
                                "name": "confirm_create_servicenow_case",
                                "context": {
                                    "serviceArea": "LEGAL_ESCALATION",
                                    "referenceNumber": "23469, 23104, 23288",
                                    "priority": "P1",
                                    "requesterEmail": "requester@enterprise-gbs.example.com",
                                    "description": (
                                        "Second Payment Reminder Notice threatening account freeze from "
                                        "BioData Registry Online (23469 Paid EFT 1667857; 23104 Pending Approval; "
                                        "23288 Pending Receipt)."
                                    ),
                                },
                            }
                        },
                    },
                ],
            },
        },
        {
            "version": A2UI_VERSION,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/reconciliation",
                "value": {
                    "vegaSpec": vega_spec,
                },
            },
        },
    ]
    readable = (
        "Side-Panel Canvas: BioData Registry Online Multi-Invoice Reconciliation "
        "(23469 Paid, 23104 Pending Approval, 23288 Pending Receipt)"
    )
    return package_a2ui_datapart(messages, surface_id=surface_id, readable_text=readable)


KB_ARTICLES_CATALOG: dict[str, dict[str, Any]] = {
    "KB0015760": {
        "title": "KB0015760 — Finding, Viewing & Coding Non-PO Invoices",
        "summary": "Step-by-step Coupa workflow to locate actionable invoices and code Non-PO project/GL strings.",
        "steps": [
            (
                "Step 1: Open Actionable Invoices View in Coupa",
                "Navigate to Activity > Invoices and set the View filter dropdown to 'Requiring My Action' (coding) or 'Requiring My Approval'.",
            ),
            (
                "Step 2: Select Commodity & Open Billing String",
                "Click the Invoice Number or Edit Pencil icon, select the Commodity on each line, and click the Billing Magnifying Glass.",
            ),
            (
                "Step 3: Enter Project / Task / Expenditure & Submit",
                "Populate Project Number, Task Number, and Expenditure Type (or GL Cost Center), then click Save and Submit.",
            ),
        ],
    },
    "KB0015802": {
        "title": "KB0015802 — Supplier Email Exemptions & CSP Mandate",
        "summary": "Determines whether a supplier must use the Coupa Supplier Portal (CSP) or qualifies for utility PDF e-billing.",
        "steps": [
            (
                "Rule 1: Standard Commercial Suppliers (Non-Exempt)",
                "All commercial suppliers must submit digital invoices via the Coupa Supplier Portal (CSP). Emailed PDFs are rejected.",
            ),
            (
                "Rule 2: Regulated Utilities & Municipal Entities (Exempt)",
                "Verified utilities in the Exemptions Registry may email PDFs to ap-ebilling-can / ap-ebilling-uk / ap-ebilling-us.",
            ),
        ],
    },
    "KB0015810": {
        "title": "KB0015810 — Reassigning Approvers (PO vs Non-PO)",
        "summary": "Explains why Non-PO invoices can be reassigned directly while PO-backed invoices inherit PO hierarchy.",
        "steps": [
            (
                "Path A: Non-PO Invoice Reassignment",
                "Open Activity > Invoices > Edit Pencil and update the Requester or Project Manager field directly in Coupa.",
            ),
            (
                "Path B: PO-Backed Invoice Reassignment",
                "Submit a PO Change Request on the underlying Purchase Order so future invoices route to the new owner.",
            ),
        ],
    },
    "KB0015822": {
        "title": "KB0015822 — Coupa Holds & VertexCallOut Tax Variances",
        "summary": "Distinguishes requester On Hold, AP/Booking Hold, and automated VertexCallOut tax engine holds.",
        "steps": [
            (
                "1. VertexCallOut Rejected / Tax Variance",
                "Owned automatically by GBS-EMEA-AP-TaxValidation. Zero action is required from the business requester.",
            ),
            (
                "2. AP Hold / Booking Hold Resolution",
                "Placed by Accounts Payable for banking or compliance review; submit a ServiceNow case to GBS-Global-AP-InvoiceProcessing.",
            ),
        ],
    },
    "KB0015835": {
        "title": "KB0015835 — Disputed, Pre-PO & Wrong-Amount Approved Invoices",
        "summary": "Remediation rules for pre-PO uploads, PO price tolerances, and already-approved wrong-amount invoices.",
        "steps": [
            (
                "1. Approved Invoice Billed for Wrong Amount",
                "Cannot be rejected in Coupa once Approved. Immediately submit a P2 ServiceNow case for an Oracle Payment Hold + Credit Memo.",
            ),
            (
                "2. Pre-PO Upload & Tolerance Variances",
                "Pre-PO disputed invoices require fresh CSP upload against the approved PO; tolerance variances need a PO Change Request or credit.",
            ),
        ],
    },
    "KB0015849": {
        "title": "KB0015849 — 3-Way Match & Goods Receipting in Coupa",
        "summary": "How to clear Pending Receipt holds by entering a Goods Receipt (Truck Icon) in Coupa.",
        "steps": [
            (
                "Step 1: Verify Delivery Condition",
                "Confirm physical goods or milestone deliverables were received in satisfactory condition before receipting.",
            ),
            (
                "Step 2: Submit Goods Receipt via Truck Icon",
                "Go to Activity > Requisitions, click the Truck Icon ('Manage Receipts') on the PO line, enter quantity/amount, and Submit.",
            ),
        ],
    },
    "KB0015860": {
        "title": "KB0015860 — Approval Delegation, Notifications & Custom Views",
        "summary": "Self-service Coupa profile settings for vacation delegation, alert preferences, and Excel exports.",
        "steps": [
            (
                "1. Approval vs Receiving Delegation",
                "Configure invoice approval delegates in Settings > Approvals > Create Delegate, and goods receipts in Settings > Receiving.",
            ),
            (
                "2. Notification Alerts & Custom Excel Views",
                "Never disable mandatory Approval/Action Required emails. Use Activity > Invoices > View > Create View > Export to Excel.",
            ),
        ],
    },
    "KB0015901": {
        "title": "KB0015901 — Net 30 Submission Date Math & Urgent Payments",
        "summary": "Enterprise AP payment term calculation rule and Controller-approved urgent payment intake policy.",
        "steps": [
            (
                "1. Net Due Date = Coupa Submission Date + Terms",
                "Payment terms start on the Coupa Submission Date (when a compliant invoice enters Coupa), NOT the supplier PDF date.",
            ),
            (
                "2. Out-of-Cycle Urgent Payment Acceleration",
                "Requires Geography, Operating Unit, Requested Date, and Controller business impact justification.",
            ),
        ],
    },
}


def build_interactive_kb_canvas(
    kb_article_id: str = "KB0015760",
    topic_focus: Optional[str] = None,
) -> dict[str, Any]:
    """Builds Surface E (KB Guide): Side-Panel `Canvas` with `MaterialExpansionPanel` steps."""
    kb_meta = KB_ARTICLES_CATALOG.get(
        kb_article_id,
        {
            "title": f"{kb_article_id} — Enterprise GBS Procurement & Coupa Guide",
            "summary": "Interactive step-by-step Coupa, Procurement, SIM, and Employee Expense self-service guide.",
            "steps": [
                (
                    "Step 1: Review Policy & Self-Service Navigation",
                    "Follow the guided Coupa / Saviynt / Oracle iExpense workflow steps for your region and document type.",
                ),
                (
                    "Step 2: Specialist Escalation When Blocked",
                    "If system permissions or ERP locks prevent completion, submit a ServiceNow case with your reference ID.",
                ),
            ],
        },
    )
    surface_id = f"gbs-kb-canvas-{_safe_surface_slug(kb_article_id)}"

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Canvas",
            "autoOpen": True,
            "cardTitle": kb_meta["title"],
            "cardDescription": kb_meta["summary"],
            "cardIcon": "menu_book",
            "children": ["canvas-main-col"],
        },
        {
            "id": "canvas-title",
            "component": "MaterialText",
            "text": kb_meta["title"],
            "usageHint": "h3",
        },
        {
            "id": "canvas-summary",
            "component": "MaterialText",
            "text": (
                f"{kb_meta['summary']}"
                + (f" | Highlighted Topic: {topic_focus}" if topic_focus else "")
            ),
            "usageHint": "body1",
        },
        {
            "id": "canvas-div",
            "component": "MaterialDivider",
        },
    ]

    panel_ids: list[str] = []
    for idx, (step_title, step_body) in enumerate(kb_meta["steps"], start=1):
        pid = f"kb-panel-{idx}"
        bid = f"kb-panel-body-{idx}"
        panel_ids.append(pid)
        components.append(
            {
                "id": pid,
                "component": "MaterialExpansionPanel",
                "title": _clamp_title(step_title),
                "expanded": idx == 1,
                "children": [bid],
            }
        )
        components.append(
            {
                "id": bid,
                "component": "MaterialText",
                "text": step_body,
                "usageHint": "body2",
            }
        )

    components.extend(
        [
            {
                "id": "kb-btn-row",
                "component": "MaterialRow",
                "align": "center",
                "style": {"gap": "8px", "flexWrap": "wrap"},
                "children": ["btn-kb-need-help"],
            },
            {
                "id": "btn-kb-need-help",
                "component": "MaterialButton",
                "label": "Still Blocked? Open ServiceNow Case",
                "variant": "stroked",
                "leadingIcon": "support_agent",
                "action": {
                    "event": {
                        "name": "request_servicenow_intake_form",
                        "context": {"kbArticleId": kb_article_id},
                    }
                },
            },
        ]
    )

    main_col = {
        "id": "canvas-main-col",
        "component": "MaterialColumn",
        "style": {"gap": "14px", "padding": "16px"},
        "children": ["canvas-title", "canvas-summary", "canvas-div", *panel_ids, "kb-btn-row"],
    }
    components.insert(1, main_col)

    messages: list[dict[str, Any]] = [
        {
            "version": A2UI_VERSION,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_COMPOSITE_CATALOG_ID,
            },
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": components,
            },
        },
    ]
    readable = f"Side-Panel Canvas Guide: {kb_meta['title']}"
    return package_a2ui_datapart(messages, surface_id=surface_id, readable_text=readable)


class A2uiCanvasPlugin(BasePlugin):
    """ADK `BasePlugin` injecting queued A2UI v0.9 `<a2a_datapart_json>` surfaces into responses."""

    def __init__(self, name: str = "a2ui_canvas_plugin") -> None:
        super().__init__(name=name)

    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        """Attaches queued A2UI v0.9 surfaces to the final assistant turn safely."""
        try:
            # Wait for the final non-partial aggregated turn during streaming
            if getattr(llm_response, "partial", False):
                return None

            state = callback_context.state
            pending = state.get("pending_a2ui_parts") if state is not None else None
            if not pending:
                return None

            content = getattr(llm_response, "content", None)
            parts = list(getattr(content, "parts", None) or []) if content else []

            # Do not attach A2UI parts onto intermediate tool-call turns; wait for text response
            has_function_call = any(getattr(p, "function_call", None) is not None for p in parts)
            if has_function_call:
                return None

            existing_surfaces = {
                (getattr(p, "part_metadata", None) or {}).get("surface_id")
                for p in parts
                if getattr(p, "part_metadata", None)
            }
            for surface_pkg in pending:
                sid = surface_pkg.get("surface_id")
                if sid not in existing_surfaces:
                    parts.extend(build_genai_a2ui_parts(surface_pkg))
                    existing_surfaces.add(sid)

            if content is None:
                llm_response.content = types.Content(role="model", parts=parts)
            else:
                content.parts = parts

            state["pending_a2ui_parts"] = []
            _LOGGER.info(
                "A2uiCanvasPlugin attached A2UI v0.9 surface(s) to model response",
                attached_count=len(pending),
                surface_ids=[p.get("surface_id") for p in pending],
            )
        except Exception as exc:
            _LOGGER.error(
                "A2uiCanvasPlugin blast-radius guard caught serialization error",
                error_type=type(exc).__name__,
            )
        return None
