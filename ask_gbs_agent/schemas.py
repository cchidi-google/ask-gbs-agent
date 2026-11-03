"""Strict Pydantic v2 Input/Output Schemas & Guided Error Responses (Rubric 1.3 & 1.4).

Every tool input and output in `ask-gbs-agent` is validated through explicit
Pydantic v2 models configured with `ConfigDict(extra="forbid")` to prevent
hallucinated arguments and guarantee deterministic recovery instructions when
inputs are incomplete or out-of-scope.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ServiceAreaCode = Literal[
    "INVOICE_SUPPORT",
    "PAYMENT_SUPPORT",
    "URGENT_PAYMENT",
    "LEGAL_ESCALATION",
    "VENDOR_SECURITY",
    "GENERAL_TRIAGE",
]

PriorityCode = Literal["P1", "P2", "P3"]


class InvoiceLookupInput(BaseModel):
    """Input schema for cross-system Coupa, Oracle, Exemption, and Teaser lookups."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    identifier: str = Field(
        ...,
        min_length=2,
        max_length=128,
        description=(
            "Invoice number, Coupa ID, Oracle voucher/payment reference, PO number, "
            "supplier name, or GBS scenario/reference ID (e.g., 'INV00026056', '2158', "
            "'23469', '2458874037', 'Pacific Grid Energy Corp', 'SAV-REQ-90412')."
        ),
    )
    supplier_name: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Optional supplier/vendor name associated with the inquiry.",
    )
    po_number: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional Purchase Order number (e.g., 'PO #1763463').",
    )
    inquirer_email: Optional[str] = Field(
        default=None,
        max_length=160,
        description=(
            "Optional email address of the internal employee or external supplier contact "
            "used for external domain mismatch security validation (RULE-06)."
        ),
    )
    inquiry_context: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional natural language summary of the user's question.",
    )

    @field_validator("identifier")
    @classmethod
    def validate_non_placeholder_identifier(cls, value: str) -> str:
        lowered = value.strip().lower()
        if lowered in {"unknown", "none", "n/a", "null", "invoice", "help"}:
            raise ValueError(
                "A concrete invoice, PO, supplier, or reference identifier is required. "
                "Call `request_missing_invoice_identifier_form` if the user has not provided one."
            )
        return value


class InvoiceDiagnosticOutput(BaseModel):
    """Structured cross-system Coupa + Oracle diagnostic output schema."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["RESOLVED", "ESCALATION_REQUIRED", "SECURITY_HOLD"] = Field(
        ...,
        description="Resolution classification after cross-system Coupa/Oracle reconciliation.",
    )
    scenario_id: str = Field(
        ...,
        description="Matched sanitized GBS scenario identifier (e.g., 'PAY-01', 'INV-11').",
    )
    category: str = Field(
        ...,
        description="GBS helpdesk sub-category for the matched record.",
    )
    invoice_number: str = Field(
        ...,
        description="Primary invoice or reference identifier.",
    )
    coupa_id: str = Field(
        default="N/A",
        description="Coupa internal document ID or ingestion state.",
    )
    oracle_voucher_id: str = Field(
        default="N/A",
        description="Oracle Financials voucher ID.",
    )
    supplier_name: str = Field(
        ...,
        description="Sanitized supplier or entity name.",
    )
    backing_po: str = Field(
        default="Non-PO",
        description="Backing Purchase Order number or Non-PO indicator.",
    )
    billed_amount: str = Field(
        default="0.00 USD",
        description="Invoice billed amount and currency.",
    )
    invoice_pdf_date: str = Field(
        default="N/A",
        description="Document issue date printed on the supplier PDF.",
    )
    coupa_submission_date: str = Field(
        default="N/A",
        description="Date the compliant invoice was submitted in Coupa (drives Net 30 math).",
    )
    calculated_net_due_date: str = Field(
        default="N/A",
        description="Net due date calculated from Coupa Submission Date + Payment Terms (KB0015901).",
    )
    coupa_status: str = Field(
        ...,
        description="Current Coupa approval or hold status.",
    )
    oracle_payment_status: str = Field(
        ...,
        description="Current Oracle Financials payment status and EFT reference.",
    )
    eft_reference: Optional[str] = Field(
        default=None,
        description="Electronic Funds Transfer (EFT) payment reference if paid or scheduled.",
    )
    masked_bank_account: str = Field(
        default="N/A",
        description="Masked bank account digits (or '[REDACTED — SECURITY HOLD]' when confidence < 80).",
    )
    confidence_score: int = Field(
        default=95,
        ge=0,
        le=100,
        description="Self-evaluation confidence score (0-100); <80 triggers security redaction.",
    )
    security_hold_triggered: bool = Field(
        default=False,
        description="True when RULE-06 external domain mismatch or DNU vendor hold triggers.",
    )
    requires_hitl_ticket: bool = Field(
        default=False,
        description="True when specialist ServiceNow escalation is recommended or mandatory.",
    )
    target_servicenow_queue: str = Field(
        default="Auto-Resolved (No Ticket Needed)",
        description="Recommended regional ServiceNow assignment group.",
    )
    kb_reference: str = Field(
        default="KB0015760",
        description="Applicable ServiceNow Knowledge Base article ID.",
    )
    diagnostic_summary: str = Field(
        ...,
        description="Human-readable reconciliation summary and policy explanation.",
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="Concrete next actions for the requester, supplier, or agent.",
    )
    a2ui_surface_id: str = Field(
        ...,
        description="Identifier of the A2UI v0.9 surface queued for Gemini Enterprise rendering.",
    )


class MissingIdentifierFormInput(BaseModel):
    """Input schema for staging the Missing-Identifier Clarification Card (Surface C)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="The user's initial natural-language question lacking an invoice/PO number.",
    )
    inquiry_type: Literal[
        "INVOICE_STATUS",
        "PAYMENT_INQUIRY",
        "PO_SUPPORT",
        "GENERAL",
    ] = Field(
        default="INVOICE_STATUS",
        description="Detected helpdesk intent category to tailor the quick-lookup form.",
    )


class UrgentPaymentFormInput(BaseModel):
    """Input schema for staging the regional Urgent Payment Acceleration form."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str = Field(
        ...,
        min_length=2,
        max_length=64,
        description="Invoice number requiring urgent out-of-cycle payment acceleration.",
    )
    supplier_name: str = Field(
        default="FieldSync Ops Ltd",
        max_length=160,
        description="Supplier name associated with the urgent payment request.",
    )
    geography: Literal["EMEA", "AMER", "APAC"] = Field(
        default="EMEA",
        description="Regional GBS treasury geography routing the request.",
    )
    operating_unit: str = Field(
        default="UK-OPS-01",
        max_length=64,
        description="Enterprise operating unit / legal entity code.",
    )
    requested_payment_date: str = Field(
        default="2026-01-05",
        max_length=32,
        description="Requested accelerated EFT release date (YYYY-MM-DD).",
    )
    business_justification: str = Field(
        default="Critical field operations continuity requirement pending Controller sign-off.",
        min_length=5,
        max_length=1000,
        description="Controller-level business impact justification per KB0015901.",
    )
    requester_email: str = Field(
        default="requester@enterprise-gbs.example.com",
        max_length=160,
        description="Contact email of the business requester.",
    )


class ServiceNowCaseIntakeInput(BaseModel):
    """Input schema for Step 1: Staging the A2UI ServiceNow Case Intake Form (Surface A)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service_area: ServiceAreaCode = Field(
        default="INVOICE_SUPPORT",
        description="Target GBS functional area mapped to the ServiceNow Assignment Group Matrix.",
    )
    reference_number: str = Field(
        default="Custom Inquiry",
        min_length=1,
        max_length=128,
        description="Invoice number, PO number, Vendor ID, or 'Custom Inquiry' for out-of-scope requests.",
    )
    priority: PriorityCode = Field(
        default="P2",
        description="Case priority: P1 (Legal/Freeze), P2 (Approved Hold/Urgent/Security), P3 (Standard).",
    )
    requester_email: str = Field(
        default="alex.rivera@enterprise-gbs.example.com",
        min_length=5,
        max_length=160,
        description="Business contact email of the requester.",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Pre-populated diagnostic summary and specialist action requested.",
    )


class ServiceNowCaseConfirmInput(BaseModel):
    """Input schema for Step 2: Submitting a user-confirmed ServiceNow Support Case (Surface B)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service_area: ServiceAreaCode = Field(
        default="INVOICE_SUPPORT",
        description="Confirmed GBS functional area.",
    )
    reference_number: str = Field(
        default="Custom Inquiry",
        min_length=1,
        max_length=128,
        description="Confirmed Invoice, PO, or custom inquiry reference.",
    )
    priority: PriorityCode = Field(
        default="P2",
        description="Confirmed ServiceNow priority level (P1, P2, or P3).",
    )
    requester_email: str = Field(
        default="alex.rivera@enterprise-gbs.example.com",
        min_length=5,
        max_length=160,
        description="Confirmed requester business email.",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Confirmed case description and specialist action details.",
    )
    user_confirmed: bool = Field(
        default=True,
        description="Explicit indicator that the human user confirmed case creation.",
    )


class ServiceNowTicketReceiptOutput(BaseModel):
    """Output schema for the illustrative ServiceNow Case Confirmation Receipt (Surface B)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["CREATED_ILLUSTRATIVE"] = Field(
        default="CREATED_ILLUSTRATIVE",
        description="Confirmation that the illustrative demo ServiceNow ticket was staged.",
    )
    case_number: str = Field(
        ...,
        pattern=r"^CS\d{7}$",
        description="Generated illustrative ServiceNow Case ID (e.g., 'CS9940120').",
    )
    assignment_group: str = Field(
        ...,
        description="Regional ServiceNow Assignment Group queue.",
    )
    priority: str = Field(
        ...,
        description="Formatted priority label (e.g., 'P2 — High').",
    )
    target_sla: str = Field(
        ...,
        description="Target SLA response window (e.g., '4 Business Hours').",
    )
    reference_number: str = Field(
        ...,
        description="Associated invoice, PO, or inquiry reference.",
    )
    requester_email: str = Field(
        ...,
        description="Submitted requester email.",
    )
    description: str = Field(
        ...,
        description="Full transferred diagnostic context.",
    )
    demo_mode_notice: str = Field(
        default=(
            "Illustrative Demo Workflow: Case confirmation generated with full context transfer. "
            "No live backend ServiceNow mutation was executed."
        ),
        description="Explicit transparency notice confirming read-only demo safety.",
    )
    a2ui_surface_id: str = Field(
        ...,
        description="Surface ID of the rendered receipt card (e.g., 'gbs-servicenow-receipt-CS9940120').",
    )


class KbCanvasInput(BaseModel):
    """Input schema for opening interactive Coupa/Procurement KB guides in the Side-Panel Canvas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kb_article_id: str = Field(
        default="KB0015760",
        pattern=r"^KB\d{7}$",
        description=(
            "ServiceNow Knowledge Base article ID (e.g., 'KB0015760', 'KB0015802', 'KB0015810', "
            "'KB0015822', 'KB0015835', 'KB0015849', 'KB0015860', 'KB0015901', 'KB0016010'..'KB0016050')."
        ),
    )
    topic_focus: Optional[str] = Field(
        default=None,
        max_length=240,
        description="Optional specific user workflow question to highlight in the Canvas guide.",
    )


class SupplierExemptionInput(BaseModel):
    """Input schema for checking the Supplier Email Exemptions Registry (`KB0015802`)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    supplier_name: str = Field(
        ...,
        min_length=2,
        max_length=160,
        description="Supplier legal or trading name to verify against the Exemptions Registry.",
    )
    invoice_number: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional invoice number not found in Coupa.",
    )


class GuidedToolErrorResponse(BaseModel):
    """Guided error response returned to the LLM instead of raising unhandled exceptions (Rubric 1.4)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["RECOVERABLE_ERROR"] = Field(
        default="RECOVERABLE_ERROR",
        description="Signals to the LLM that the error is recoverable via guided follow-up.",
    )
    error_code: str = Field(
        ...,
        description="Machine-readable error classification (e.g., 'RECORD_NOT_FOUND', 'HITL_CONFIRMATION_REQUIRED').",
    )
    failed_tool: str = Field(
        ...,
        description="Name of the tool that encountered the validation or lookup condition.",
    )
    error_detail: str = Field(
        ...,
        description="Clear diagnostic explanation of what failed or was missing.",
    )
    llm_recovery_instruction: str = Field(
        ...,
        description="Explicit step-by-step instruction telling the LLM how to recover gracefully.",
    )
    suggested_next_tool: Optional[str] = Field(
        default="stage_servicenow_case_intake_form",
        description="Recommended tool for the LLM to invoke next.",
    )
    context_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional sanitized context to help the LLM populate the recovery tool.",
    )
