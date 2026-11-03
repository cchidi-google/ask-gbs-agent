"""Complete Sanitized Golden Dataset Catalog (`INV-01`..`INV-17`, `PAY-01`..`PAY-05`, `ACC-01`..`CSP-01`).

Mirrors `ask_gbs_agent/data/gbs_source_of_truth_data.md` with 100% synthetic dummy
identifiers for deterministic cross-system Coupa + Oracle diagnostics.
"""

from __future__ import annotations

import re
from typing import Any, Optional


def normalize_key(value: str) -> str:
    """Normalizes invoice numbers, PO numbers, and vendor names for resilient lookup."""
    cleaned = value.strip().upper()
    cleaned = re.sub(r"^PO\s*#?\s*", "", cleaned)
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    return cleaned


GOLDEN_RECORDS: list[dict[str, Any]] = [
    # --- TAB 1: SUPPLIER INVOICE SUPPORT (INV-01 .. INV-17) ---
    {
        "scenario_id": "INV-01",
        "category": "Invoice Pending Approval",
        "invoice_number": "INV11188136",
        "aliases": ["INV11188136", "684575", "CS0844658", "PRJ-88401.01"],
        "coupa_id": "684575",
        "oracle_voucher_id": "N/A (Not Exported)",
        "supplier_name": "AquaFlow Utilities Ltd",
        "official_email_domain": "aquaflow-util.example.uk",
        "backing_po": "Non-PO",
        "billed_amount": "1304.51 GBP",
        "invoice_pdf_date": "2025-11-28",
        "coupa_submission_date": "2025-12-04",
        "calculated_net_due_date": "2026-01-03",
        "coupa_status": "Pending Approval",
        "oracle_payment_status": "Awaiting Coupa Approval",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015760",
        "diagnostic_summary": (
            "Invoice INV11188136 (1,304.51 GBP, AquaFlow Utilities Ltd) is currently Pending Approval "
            "in Coupa awaiting Project Manager cost coding and approval by Marcus Vance "
            "(marcus.vance@enterprise-gbs.example.com). It will export to Oracle once approved."
        ),
        "recommended_next_steps": [
            "Contact PM Marcus Vance to complete project cost coding (PRJ-88401.01) and approve in Coupa.",
            "Net 30 due date is 2026-01-03 based on the 2025-12-04 Coupa submission date (KB0015901).",
        ],
    },
    {
        "scenario_id": "INV-02",
        "category": "Invoice Approved Awaiting Payment",
        "invoice_number": "4106076",
        "aliases": ["4106076", "822705", "23801140", "AU1729901", "Outback SatCom Pty Ltd"],
        "coupa_id": "822705",
        "oracle_voucher_id": "23801140",
        "supplier_name": "Outback SatCom Pty Ltd",
        "official_email_domain": "outbacksatcom.example.au",
        "backing_po": "PO #AU1729901",
        "billed_amount": "1087.40 AUD",
        "invoice_pdf_date": "2025-11-18",
        "coupa_submission_date": "2025-12-15",
        "calculated_net_due_date": "2026-01-14",
        "coupa_status": "Approved",
        "oracle_payment_status": "Scheduled for ANZ EFT Run (2026-01-14)",
        "eft_reference": "Scheduled-ANZ-20260114",
        "masked_bank_account": "ANZ Commercial xxx9104",
        "confidence_score": 98,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015901",
        "diagnostic_summary": (
            "Invoice 4106076 (1,087.40 AUD, Outback SatCom Pty Ltd) is Approved in Coupa and validated "
            "in Oracle (Voucher 23801140) with zero holds. Scheduled for the ANZ regional EFT run on or "
            "before 2026-01-14 (Coupa submission 2025-12-15 + Net 30)."
        ),
        "recommended_next_steps": [
            "No action required; payment will release automatically in the 2026-01-14 ANZ EFT cycle.",
        ],
    },
    {
        "scenario_id": "INV-03",
        "category": "Approval Routing Support (Wrong PA/PM)",
        "invoice_number": "IVC000000056640",
        "aliases": ["IVC000000056640", "781775", "Apex Talent Solutions", "CS0887204"],
        "coupa_id": "781775",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Apex Talent Solutions",
        "official_email_domain": "apextalent.example.com",
        "backing_po": "Non-PO",
        "billed_amount": "1118.64 USD",
        "invoice_pdf_date": "2025-12-01",
        "coupa_submission_date": "2025-12-05",
        "calculated_net_due_date": "2026-01-04",
        "coupa_status": "Pending Action",
        "oracle_payment_status": "Awaiting Coding/Routing",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 96,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "GBS-Global-AP-InvoiceProcessing",
        "kb_reference": "KB0015810",
        "diagnostic_summary": (
            "Invoice IVC000000056640 ($1,118.64 USD, Apex Talent Solutions) is a Non-PO invoice "
            "currently assigned to David Kestrel. Per KB0015810 (RULE-03), Non-PO invoices can be "
            "reassigned directly in Coupa (Activity > Invoices > Edit Pencil) to Elena Rostova."
        ),
        "recommended_next_steps": [
            "Edit the Requester/PM field directly on Non-PO invoice IVC000000056640 in Coupa to Elena Rostova.",
            "If the invoice header is locked, open a ServiceNow case to GBS-Global-AP-InvoiceProcessing.",
        ],
    },
    {
        "scenario_id": "INV-04",
        "category": "Non-PO Invoice Coding Guidance",
        "invoice_number": "132.001-03",
        "aliases": ["132.001-03", "13200103", "799104", "Strata Civil Engineering", "PRJ-60739809.03"],
        "coupa_id": "799104",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Strata Civil Engineering",
        "official_email_domain": "stratacivil.example.com",
        "backing_po": "Non-PO",
        "billed_amount": "23480.00 USD",
        "invoice_pdf_date": "2025-12-10",
        "coupa_submission_date": "2025-12-12",
        "calculated_net_due_date": "2026-01-11",
        "coupa_status": "Pending Action (Uncoded)",
        "oracle_payment_status": "Awaiting Coding",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015760",
        "diagnostic_summary": (
            "Non-PO Invoice 132.001-03 ($23,480.00 USD, Strata Civil Engineering) requires project cost "
            "coding by Hannah Abbott per KB0015760: Activity > Invoices > Requiring My Action > Edit Pencil > "
            "Select Commodity > Click Billing Magnifying Glass > Enter Project PRJ-60739809.03, Task & "
            "Expenditure Type > Submit."
        ),
        "recommended_next_steps": [
            "Open Coupa > Activity > Invoices > Requiring My Action and click the Edit Pencil on 132.001-03.",
            "Assign Commodity and enter Project PRJ-60739809.03 via the Billing Magnifying Glass.",
        ],
    },
    {
        "scenario_id": "INV-05",
        "category": "Invoice Rejected — Vertex Tax Validation",
        "invoice_number": "107666",
        "aliases": ["107666", "728024", "23594537", "RheinClean Facility GmbH", "DE1704112"],
        "coupa_id": "728024",
        "oracle_voucher_id": "23594537",
        "supplier_name": "RheinClean Facility GmbH",
        "official_email_domain": "rheinclean.example.de",
        "backing_po": "PO #DE1704112",
        "billed_amount": "58.17 EUR",
        "invoice_pdf_date": "2025-12-02",
        "coupa_submission_date": "2025-12-03",
        "calculated_net_due_date": "2026-01-02",
        "coupa_status": "Rejected (VertexCallOut)",
        "oracle_payment_status": "Tax Variance Hold",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 98,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "GBS-EMEA-AP-TaxValidation",
        "kb_reference": "KB0015822",
        "diagnostic_summary": (
            "Invoice 107666 (58.17 EUR, RheinClean Facility GmbH, PO #DE1704112) triggered an automated "
            "VertexCallOut EU VAT variance check (KB0015822). Remediation is owned automatically by the "
            "Global AP / Tax Team (GBS-EMEA-AP-TaxValidation); no action is required from the business requester."
        ),
        "recommended_next_steps": [
            "No action required from the business requester; Global AP / Tax Team owns VertexCallOut resolution.",
        ],
    },
    {
        "scenario_id": "INV-06",
        "category": "Invoice Not Found — Exempt Utility Supplier",
        "invoice_number": "9933297861012112025",
        "aliases": ["9933297861012112025", "Pacific Grid Energy Corp", "SUP-60119"],
        "coupa_id": "NOT_IN_COUPA",
        "oracle_voucher_id": "NOT_IN_ORACLE",
        "supplier_name": "Pacific Grid Energy Corp",
        "official_email_domain": "pacificgrid.example.ca",
        "backing_po": "Non-PO (Utility)",
        "billed_amount": "1052.72 CAD",
        "invoice_pdf_date": "2025-12-11",
        "coupa_submission_date": "Not Submitted",
        "calculated_net_due_date": "NET 30 upon receipt",
        "coupa_status": "Not Found in Coupa",
        "oracle_payment_status": "Not Found",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015802",
        "diagnostic_summary": (
            "Invoice 9933297861012112025 (1,052.72 CAD) is not yet in Coupa. Supplier Exemptions Registry "
            "Check (KB0015802): PACIFIC GRID ENERGY CORP (SUP-60119) is an EXEMPT Regulated Utility. "
            "Forward the PDF invoice directly to ap-ebilling-can@enterprise-gbs.example.com referencing "
            "Cost Center CC-2109-VAN."
        ),
        "recommended_next_steps": [
            "Email the PDF utility bill to ap-ebilling-can@enterprise-gbs.example.com with Cost Center CC-2109-VAN.",
        ],
    },
    {
        "scenario_id": "INV-07",
        "category": "Invoice Not Found — Non-Exempt Supplier",
        "invoice_number": "4810238",
        "aliases": ["4810238", "4810237", "4810236", "4810235", "NovaTech Leasing Services", "US1698410"],
        "coupa_id": "NOT_IN_COUPA",
        "oracle_voucher_id": "NOT_IN_ORACLE",
        "supplier_name": "NovaTech Leasing Services",
        "official_email_domain": "novatechlease.example.com",
        "backing_po": "PO #US1698410",
        "billed_amount": "4420.00 USD",
        "invoice_pdf_date": "2025-11-25",
        "coupa_submission_date": "Not Submitted",
        "calculated_net_due_date": "NET 30 upon CSP upload",
        "coupa_status": "Not Found in Coupa",
        "oracle_payment_status": "Not Found",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 98,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015802",
        "diagnostic_summary": (
            "Invoices 4810238, 4810237, 4810236, and 4810235 ($4,420.00 USD batch) are not in Coupa. "
            "Exemptions Registry Check (KB0015802): NOVATECH LEASING SERVICES (SUP-70441) is NON-EXEMPT. "
            "Emailed PDFs are automatically rejected; the supplier must submit directly via the Coupa "
            "Supplier Portal (CSP) against PO #US1698410."
        ),
        "recommended_next_steps": [
            "Instruct NovaTech Leasing Services to upload the invoices via the Coupa Supplier Portal (CSP) referencing PO #US1698410.",
        ],
    },
    {
        "scenario_id": "INV-08",
        "category": "Invoice Void / Cancel or Hold Status",
        "invoice_number": "75862",
        "aliases": ["75862", "REV75862", "HOLD-822238", "741902", "23601988", "Metro Survey Associates"],
        "coupa_id": "741902",
        "oracle_voucher_id": "23601988",
        "supplier_name": "Metro Survey Associates",
        "official_email_domain": "metrosurvey.example.com",
        "backing_po": "Non-PO",
        "billed_amount": "1775.00 USD",
        "invoice_pdf_date": "2025-11-19",
        "coupa_submission_date": "2025-11-20",
        "calculated_net_due_date": "N/A (Voided)",
        "coupa_status": "Voided (Offset by Credit Memo REV75862)",
        "oracle_payment_status": "Cancelled / Zero Balance",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 96,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "GBS-Global-AP-InvoiceProcessing",
        "kb_reference": "KB0015822",
        "diagnostic_summary": (
            "Invoice 75862 ($1,775.00 USD, Metro Survey Associates) is already offset by Credit Memo "
            "REV75862 (-$1,775.00 USD) and marked Voided with zero balance. Note: if inquiring about "
            "HOLD-822238 (on AP Hold / Booking Hold per KB0015822), submit a ServiceNow case to AP."
        ),
        "recommended_next_steps": [
            "No further action needed for Voided invoice 75862.",
            "For invoices on AP Hold / Booking Hold (e.g., HOLD-822238), stage a ServiceNow case to GBS-Global-AP-InvoiceProcessing.",
        ],
    },
    {
        "scenario_id": "INV-09",
        "category": "Delegate Invoice Approval Responsibilities",
        "invoice_number": "DELEGATION-HOWTO",
        "aliases": ["INV-09", "DELEGATION", "CREATE DELEGATE", "CS0855537"],
        "coupa_id": "N/A",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Internal Coupa Settings Guide",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "General How-To",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Self-Service Configuration",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 99,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015860",
        "diagnostic_summary": (
            "Per KB0015860, Approval Delegation and Goods Receiving Delegation are configured separately "
            "in Coupa: Click Username (top right) > Settings > Approvals > Create Delegate > Select "
            "Delegate User, Start Date, End Date & Reason > Save (use Settings > Receiving for receipts)."
        ),
        "recommended_next_steps": [
            "Configure invoice approval delegation under Settings > Approvals > Create Delegate.",
            "Configure goods receipt delegation separately under Settings > Receiving.",
        ],
    },
    {
        "scenario_id": "INV-10",
        "category": "Invoice Disputed — Uploaded Before PO Approved",
        "invoice_number": "63187",
        "aliases": ["63187", "710932", "ES1750688", "HydroGeo Software LLC", "CS0843759"],
        "coupa_id": "710932",
        "oracle_voucher_id": "N/A",
        "supplier_name": "HydroGeo Software LLC",
        "official_email_domain": "hydrogeosoft.example.com",
        "backing_po": "PO #ES1750688 (Unlinked)",
        "billed_amount": "805.50 USD",
        "invoice_pdf_date": "2025-12-01",
        "coupa_submission_date": "2025-12-01",
        "calculated_net_due_date": "Blocked (Disputed)",
        "coupa_status": "Disputed (Pre-PO Upload)",
        "oracle_payment_status": "Blocked",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015835",
        "diagnostic_summary": (
            "Invoice 63187 ($805.50 USD, HydroGeo Software LLC) was uploaded on 2025-12-01 before "
            "PO #ES1750688 was approved on 2025-12-06. Per KB0015835, approved POs cannot be retro-linked "
            "to disputed Non-PO invoices; the supplier must submit a fresh invoice against PO #ES1750688 in CSP."
        ),
        "recommended_next_steps": [
            "Ask HydroGeo Software LLC to submit a new invoice directly against PO #ES1750688 in the Coupa Supplier Portal (CSP).",
        ],
    },
    {
        "scenario_id": "INV-11",
        "category": "Incorrect Invoice Amount or Details (Approved Invoice)",
        "invoice_number": "2158",
        "aliases": ["2158", "758874", "23664170", "1763463", "Titan Earthworks LLC", "CS0880857"],
        "coupa_id": "758874",
        "oracle_voucher_id": "23664170",
        "supplier_name": "Titan Earthworks LLC",
        "official_email_domain": "titanearthworks.example.com",
        "backing_po": "PO #1763463",
        "billed_amount": "22772.00 USD",
        "invoice_pdf_date": "2025-12-08",
        "coupa_submission_date": "2025-12-09",
        "calculated_net_due_date": "2026-01-08",
        "coupa_status": "Approved",
        "oracle_payment_status": "Exported to Oracle (Unpaid)",
        "eft_reference": None,
        "masked_bank_account": "US Commercial Bank xxx5512",
        "confidence_score": 96,
        "requires_hitl_ticket": True,
        "target_servicenow_queue": "GBS-Global-AP-InvoiceProcessing",
        "kb_reference": "KB0015835",
        "diagnostic_summary": (
            "CRITICAL RULE-04 (KB0015835): Invoice 2158 ($22,772.00 USD, Titan Earthworks LLC, PO #1763463) "
            "is already Approved in Coupa and exported to Oracle (Voucher 23664170). It CANNOT be rejected "
            "or edited in Coupa. Immediate P2 ServiceNow escalation to GBS-Global-AP-InvoiceProcessing is "
            "required to place an Oracle Payment Hold and coordinate a supplier Credit Memo + replacement invoice."
        ),
        "recommended_next_steps": [
            "Stage and submit a P2 ServiceNow Case to GBS-Global-AP-InvoiceProcessing for an immediate Oracle Payment Hold on Voucher 23664170.",
            "Instruct Titan Earthworks LLC to submit a Credit Memo plus a corrected invoice via CSP.",
        ],
    },
    {
        "scenario_id": "INV-12",
        "category": "Invoice Exceeds PO or Charge Tolerance",
        "invoice_number": "00218",
        "aliases": ["00218", "00221", "762190", "762194", "1637772", "Crestline Builders Inc"],
        "coupa_id": "762190 / 762194",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Crestline Builders Inc",
        "official_email_domain": "crestlinebuilders.example.com",
        "backing_po": "PO #1637772",
        "billed_amount": "12981.20 USD (00218) / 14126.60 USD (00221)",
        "invoice_pdf_date": "2025-12-05",
        "coupa_submission_date": "2025-12-06",
        "calculated_net_due_date": "2026-01-05 (Blocked)",
        "coupa_status": "Disputed (Price/Tolerance Variance)",
        "oracle_payment_status": "Blocked",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 96,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015835",
        "diagnostic_summary": (
            "Invoices 00218 ($12,981.20 USD) and 00221 ($14,126.60 USD) from Crestline Builders Inc "
            "exceed remaining line tolerance on PO #1637772 (KB0015835). Either: (1) if extra charges are "
            "valid, the PM submits a PO Change Request in Coupa to increase PO #1637772; or (2) if overbilled, "
            "the supplier issues corrected invoices matching PO #1637772."
        ),
        "recommended_next_steps": [
            "Option 1 (Valid Scope Increase): Submit a PO Change Request on PO #1637772 in Coupa.",
            "Option 2 (Supplier Overbilling): Have Crestline Builders Inc submit revised invoices in CSP.",
        ],
    },
    {
        "scenario_id": "INV-13",
        "category": "Other Invoice Status (Draft, New, Voided, Abandoned)",
        "invoice_number": "20330426",
        "aliases": ["20330426", "675724", "1704816", "Boreal Engineering Group", "CS0844420"],
        "coupa_id": "675724",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Boreal Engineering Group",
        "official_email_domain": "borealeng.example.ca",
        "backing_po": "PO #1704816",
        "billed_amount": "184079.57 CAD",
        "invoice_pdf_date": "2025-11-29",
        "coupa_submission_date": "2025-11-30",
        "calculated_net_due_date": "Pending Workflow Entry",
        "coupa_status": "Draft",
        "oracle_payment_status": "Not Exported",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 95,
        "requires_hitl_ticket": True,
        "target_servicenow_queue": "GBS-Global-AP-InvoiceProcessing",
        "kb_reference": "KB0015760",
        "diagnostic_summary": (
            "Invoice 20330426 (184,079.57 CAD, Boreal Engineering Group, PO #1704816) is stuck in Draft "
            "status during OCR/ingestion validation and has not entered the approval workflow. Business "
            "requesters cannot approve Draft invoices; escalate via ServiceNow to the Invoice Processing Team."
        ),
        "recommended_next_steps": [
            "Submit a ServiceNow case to GBS-Global-AP-InvoiceProcessing to release Coupa Draft ID 675724 into workflow.",
        ],
    },
    {
        "scenario_id": "INV-14",
        "category": "Invoice Pending Receipt (3-Way Match)",
        "invoice_number": "650782",
        "aliases": ["650782", "650792", "652782", "714501", "714509", "UK1761078", "UK1725036", "EnviroPack Supplies Ltd"],
        "coupa_id": "714501 / 714509",
        "oracle_voucher_id": "N/A",
        "supplier_name": "EnviroPack Supplies Ltd",
        "official_email_domain": "enviropack.example.uk",
        "backing_po": "PO #UK1761078 (650782) & PO #UK1725036 (650792)",
        "billed_amount": "81.60 GBP (650782), 153.60 GBP (650792), 330.00 GBP (652782)",
        "invoice_pdf_date": "2025-12-03",
        "coupa_submission_date": "2025-12-04",
        "calculated_net_due_date": "2026-01-03 (Pending Receipt)",
        "coupa_status": "Pending Receipt (650782, 650792); Disputed (652782)",
        "oracle_payment_status": "Blocked by 3-Way Match",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015849",
        "diagnostic_summary": (
            "Invoices 650782 (81.60 GBP) and 650792 (153.60 GBP) from EnviroPack Supplies Ltd are blocked "
            "by a 3-Way Match Hold (Pending Receipt) per KB0015849, while 652782 (330.00 GBP) is Disputed. "
            "Clarify whether the goods were delivered in good condition: if delivered, submit a Goods Receipt "
            "in Coupa via Activity > Requisitions > Truck Icon."
        ),
        "recommended_next_steps": [
            "Confirm if goods were delivered in good condition.",
            "If delivered: Go to Coupa > Activity > Requisitions > Click the Truck Icon (Manage Receipts) to post the Goods Receipt.",
            "If faulty or undelivered: Keep on hold or dispute in Coupa.",
        ],
    },
    {
        "scenario_id": "INV-15",
        "category": "Coupa Navigation — Find and View Invoices",
        "invoice_number": "COUPA-NAV-822590",
        "aliases": ["INV-15", "822590", "FIND INVOICES", "CS0859102"],
        "coupa_id": "822590",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Internal Coupa Navigation Guide",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "General How-To",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Self-Service Navigation",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 99,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015760",
        "diagnostic_summary": (
            "Three ways to locate actionable invoices in Coupa (KB0015760): (1) Activity > Invoices > View "
            "Dropdown ('Requiring My Action' for coding vs 'Requiring My Approval'), (2) Coupa Home 'To Do' "
            "widget, or (3) Coupa Mobile App."
        ),
        "recommended_next_steps": [
            "Use Activity > Invoices > View Dropdown: Requiring My Action or Requiring My Approval.",
        ],
    },
    {
        "scenario_id": "INV-16",
        "category": "Coupa Notification Preferences",
        "invoice_number": "COUPA-NOTIFICATIONS",
        "aliases": ["INV-16", "NOTIFICATION PREFERENCES", "CS0860115"],
        "coupa_id": "N/A",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Internal Coupa Settings Guide",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "General How-To",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Self-Service Configuration",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 99,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015860",
        "diagnostic_summary": (
            "Navigate to Click Username > Settings > Notifications (KB0015860) to toggle Email, Online, and "
            "Mobile alerts per module. Warning: Never disable mandatory 'Approval Required' or 'Action Required' alerts."
        ),
        "recommended_next_steps": [
            "Open Settings > Notifications and retain Email alerts for Approval Required and Action Required.",
        ],
    },
    {
        "scenario_id": "INV-17",
        "category": "Create a Report or Customise an Invoice View",
        "invoice_number": "COUPA-CUSTOM-VIEW",
        "aliases": ["INV-17", "CUSTOM VIEW", "EXPORT TO EXCEL", "CS0861440"],
        "coupa_id": "N/A",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Internal Coupa Reporting Guide",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "General How-To",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Self-Service Reporting",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 99,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015860",
        "diagnostic_summary": (
            "To create a custom Coupa invoice report (KB0015860): Activity > Invoices > View dropdown > "
            "Create View > Name View > Add Filter Conditions > Drag & Drop Columns > Save > Click Export to Excel."
        ),
        "recommended_next_steps": [
            "Use Activity > Invoices > View dropdown > Create View and click Export to Excel.",
        ],
    },
    # --- TAB 2: SUPPLIER PAYMENT SUPPORT (PAY-01 .. PAY-05) ---
    {
        "scenario_id": "PAY-01",
        "category": "Urgent Payment Request vs. Due Date Calculation",
        "invoice_number": "INV00026056",
        "aliases": ["INV00026056", "676655", "23398104", "1664447", "UK1749479", "FieldSync Ops Ltd", "CS0845067"],
        "coupa_id": "676655",
        "oracle_voucher_id": "23398104",
        "supplier_name": "FieldSync Ops Ltd",
        "official_email_domain": "fieldsync-ops.example.uk",
        "backing_po": "PO #UK1749479",
        "billed_amount": "3831.60 GBP",
        "invoice_pdf_date": "2025-11-30",
        "coupa_submission_date": "2025-12-15",
        "calculated_net_due_date": "2026-01-14",
        "coupa_status": "Approved",
        "oracle_payment_status": "Scheduled / Paid 2026-01-14 (EFT Ref: 1664447)",
        "eft_reference": "1664447",
        "masked_bank_account": "Barclays UK xxx4419",
        "confidence_score": 96,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "GBS-EMEA-AP-UrgentPayments",
        "kb_reference": "KB0015901",
        "diagnostic_summary": (
            "Submission Date Rule (KB0015901): Although the supplier PDF is dated 2025-11-30, Invoice "
            "INV00026056 (3,831.60 GBP, FieldSync Ops Ltd, Coupa 676655 / Oracle 23398104) was submitted "
            "into Coupa on 2025-12-15, making the true Net 30 Due Date 2026-01-14 (EFT Ref: 1664447). "
            "Confirm if 2026-01-14 resolves your inquiry or request an out-of-cycle Urgent Payment Acceleration."
        ),
        "recommended_next_steps": [
            "Confirm if the 2026-01-14 EFT payment schedule (EFT 1664447) satisfies the supplier.",
            "If out-of-cycle early release is required, submit the Urgent Payment Acceleration form (GBS-EMEA-AP-UrgentPayments).",
        ],
    },
    {
        "scenario_id": "PAY-02",
        "category": "Invoice Payment Inquiry (Umbrella Diagnostic & PWP)",
        "invoice_number": "INV1750822",
        "aliases": ["INV1750822", "634711", "23104552", "5000057420", "1737540", "CloudCore Systems LLC", "CS0845052"],
        "coupa_id": "634711",
        "oracle_voucher_id": "23104552",
        "supplier_name": "CloudCore Systems LLC",
        "official_email_domain": "cloudcoresys.example.com",
        "backing_po": "PO #1737540",
        "billed_amount": "130199.07 USD",
        "invoice_pdf_date": "2025-11-28",
        "coupa_submission_date": "2025-12-03",
        "calculated_net_due_date": "2026-01-02",
        "coupa_status": "Approved",
        "oracle_payment_status": "PAID on 2026-01-02 via Electronic Payment (EFT Ref: 5000057420)",
        "eft_reference": "5000057420",
        "masked_bank_account": "First National Commercial Bank xxx0724",
        "confidence_score": 98,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0015901",
        "diagnostic_summary": (
            "Invoice INV1750822 ($130,199.07 USD, CloudCore Systems LLC, PO #1737540) was PAID in full on "
            "2026-01-02 via Electronic Payment EFT Reference 5000057420 to First National Commercial Bank "
            "account ending in xxx0724. (Note: Pay-When-Paid [PWP] terms release upon client funds receipt where applicable.)"
        ),
        "recommended_next_steps": [
            "Share EFT Reference 5000057420 (paid 2026-01-02) with CloudCore Systems LLC.",
        ],
    },
    {
        "scenario_id": "PAY-03",
        "category": "Supplier Legal Reminder / Account Hold Notice",
        "invoice_number": "23469",
        "aliases": [
            "23469",
            "23104",
            "23288",
            "709187",
            "711204",
            "715890",
            "23490112",
            "1667857",
            "UK1734685",
            "UK1754578",
            "BioData Registry Online",
            "CS0844829",
        ],
        "coupa_id": "709187 (23469), 711204 (23104), 715890 (23288)",
        "oracle_voucher_id": "23490112 (23469)",
        "supplier_name": "BioData Registry Online",
        "official_email_domain": "biodata-registry.example.uk",
        "backing_po": "PO #UK1734685 (23469, 23104) & PO #UK1754578 (23288)",
        "billed_amount": "4586.85 GBP Total (23469: 2196.85 GBP; 23104: 940.00 GBP; 23288: 1450.00 GBP)",
        "invoice_pdf_date": "2025-12-01",
        "coupa_submission_date": "2025-12-17",
        "calculated_net_due_date": "2026-01-16",
        "coupa_status": "23469: Approved | 23104: Pending Approval | 23288: Pending Receipt",
        "oracle_payment_status": "23469: PAID 2026-01-16 (EFT 1667857) | 23104 & 23288: Unpaid / Blocked",
        "eft_reference": "1667857",
        "masked_bank_account": "HSBC UK xxx8810",
        "confidence_score": 90,
        "requires_hitl_ticket": True,
        "target_servicenow_queue": "GBS-Senior-AP-Escalations",
        "kb_reference": "KB0015849",
        "diagnostic_summary": (
            "MANDATORY P1 HITL ESCALATION (RULE-06): BioData Registry Online issued a Second Payment "
            "Reminder Notice threatening an account freeze across 3 invoices: (1) 23469 (2,196.85 GBP) is "
            "PAID on 2026-01-16 via EFT 1667857; (2) 23104 (940.00 GBP) is Pending PM Approval in Coupa; "
            "(3) 23288 (1,450.00 GBP) is blocked on Pending Receipt (3-Way Match). Full reconciliation "
            "opened in the Side-Panel Canvas; stage a P1 ServiceNow escalation to GBS-Senior-AP-Escalations."
        ),
        "recommended_next_steps": [
            "Review the 3-invoice RichTable reconciliation in the Gemini Enterprise Side-Panel Canvas.",
            "Provide EFT 1667857 proof of payment for 23469, approve 23104, receipt 23288, and submit a P1 ServiceNow Case to GBS-Senior-AP-Escalations.",
        ],
    },
    {
        "scenario_id": "PAY-04",
        "category": "Remittance Advice / Proof of Payment Request",
        "invoice_number": "FLEX-88912",
        "aliases": ["FLEX-88912", "661098", "23289001", "1661092", "UK1710229", "FleetRent Commercial UK", "CS0845139"],
        "coupa_id": "661098",
        "oracle_voucher_id": "23289001",
        "supplier_name": "FleetRent Commercial UK",
        "official_email_domain": "fleetrent-uk.example.com",
        "backing_po": "PO #UK1710229",
        "billed_amount": "6215.85 GBP",
        "invoice_pdf_date": "2025-11-24",
        "coupa_submission_date": "2025-11-28",
        "calculated_net_due_date": "2025-12-28",
        "coupa_status": "Approved",
        "oracle_payment_status": "PAID on 2025-12-29 (EFT Ref: 1661092)",
        "eft_reference": "1661092",
        "masked_bank_account": "Lloyds Commercial xxx3309",
        "confidence_score": 94,
        "requires_hitl_ticket": True,
        "target_servicenow_queue": "GBS-Regional-Payments-Remittance",
        "kb_reference": "KB0015901",
        "diagnostic_summary": (
            "Oracle confirms Invoice FLEX-88912 (6,215.85 GBP, FleetRent Commercial UK) was PAID on "
            "2025-12-29 under EFT Reference 1661092. Because Ask GBS cannot export or email official PDF "
            "remittance advices from Oracle (RULE-01), submit a P3 ServiceNow case to GBS-Regional-Payments-Remittance."
        ),
        "recommended_next_steps": [
            "Stage and confirm a P3 ServiceNow Case to GBS-Regional-Payments-Remittance to dispatch the official PDF remittance advice.",
        ],
    },
    {
        "scenario_id": "PAY-05",
        "category": "Payment Rejected / Returned & External Domain Mismatch Guardrail",
        "invoice_number": "2458874037",
        "aliases": [
            "2458874037",
            "3001948880",
            "311717",
            "22904118",
            "1609441",
            "EnviroLab Analytics Inc",
            "DNU - EnviroLab Analytics Inc",
            "veritaslabs-group.example.com",
            "CS0844545",
        ],
        "coupa_id": "311717",
        "oracle_voucher_id": "22904118",
        "supplier_name": "DNU - EnviroLab Analytics Inc",
        "official_email_domain": "envirolab-inc.example.com",
        "backing_po": "PO #1609441",
        "billed_amount": "2136.00 USD",
        "invoice_pdf_date": "2025-10-15",
        "coupa_submission_date": "2025-10-18",
        "calculated_net_due_date": "2025-11-17",
        "coupa_status": "Approved (Vendor Marked DNU)",
        "oracle_payment_status": "Payment 3001948880 Returned / Rejected by Receiving Bank",
        "eft_reference": "3001948880 (Returned)",
        "masked_bank_account": "[REDACTED — SECURITY HOLD]",
        "confidence_score": 62,
        "requires_hitl_ticket": True,
        "target_servicenow_queue": "GBS-Vendor-Management-Security",
        "kb_reference": "KB0015950",
        "diagnostic_summary": (
            "SECURITY GUARDRAIL TRIGGERED (Confidence = 62 < 80, RULE-06 / KB0015950): Payment 3001948880 "
            "for Invoice 2458874037 ($2,136.00 USD) was returned by the receiving bank, vendor 'DNU - "
            "EnviroLab Analytics Inc' is flagged Do Not Use, and external inquirer domain "
            "(@veritaslabs-group.example.com) does not match the supplier record on file. Bank account "
            "digits are redacted; mandatory P2 security escalation to GBS-Vendor-Management-Security required."
        ),
        "recommended_next_steps": [
            "Do NOT disclose any banking or routing digits to the unverified external domain.",
            "Stage a mandatory P2 Security Escalation Case to GBS-Vendor-Management-Security for positive vendor verification.",
        ],
    },
    # --- SECTION 5: EXPANSION SERVICE TILES (ACC-01 .. CSP-01) ---
    {
        "scenario_id": "ACC-01",
        "category": "Coupa Access Request",
        "invoice_number": "SAV-REQ-90412",
        "aliases": ["ACC-01", "SAV-REQ-90412", "SAVIYNT", "BUYER ROLE", "COUPA ACCESS"],
        "coupa_id": "SAV-REQ-90412",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Saviynt Identity Governance (Internal)",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "Access Governance",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Request via Saviynt (KB0016010)",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 98,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "GBS-Coupa-Admin-IT",
        "kb_reference": "KB0016010",
        "diagnostic_summary": (
            "Per KB0016010, new or expanded Coupa Buyer/Approver permissions (Ref SAV-REQ-90412) must be "
            "requested through Saviynt Identity Governance with line-manager approval. If post-approval "
            "role sync fails, escalate to GBS-Coupa-Admin-IT."
        ),
        "recommended_next_steps": [
            "Submit role request in Saviynt Identity Governance (KB0016010).",
            "Open a ServiceNow case if approved Saviynt roles do not sync within 4 hours.",
        ],
    },
    {
        "scenario_id": "PROC-01",
        "category": "Procurement — PO Amendments",
        "invoice_number": "PO #12345",
        "aliases": ["PROC-01", "12345", "US1780112", "AE1790441", "PO AMENDMENT"],
        "coupa_id": "PO-AMEND",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Regional Procurement Routing (KB0016020)",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "PO #12345 / #US1780112 / #AE1790441",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Regional Amendment Matrix (KB0016020)",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0016020",
        "diagnostic_summary": (
            "Regional PO Amendment Routing (KB0016020): (1) Standard Open Goods/Services PO (#12345) -> "
            "Initiate Coupa Change Order; (2) US/CAN Subcontractor PO (#US1780112) -> Submit Subcontractor "
            "Admin Form; (3) MEA/LATAM PO (#AE1790441) -> Submit Regional Procurement Intake Form."
        ),
        "recommended_next_steps": [
            "Select the amendment channel matching your PO type and region per KB0016020.",
        ],
    },
    {
        "scenario_id": "PROC-02",
        "category": "Procurement — Requisition Buying Channels & Mexico Rule",
        "invoice_number": "REQ-BUY-2026",
        "aliases": ["PROC-02", "REQ-BUY-2026", "MEXICO PO", "BUYING CHANNELS"],
        "coupa_id": "REQ-BUY-2026",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Global Buying Channel Matrix (KB0016025)",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "Requisition Triage",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Buying Channel Matrix (KB0016025)",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 98,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0016025",
        "diagnostic_summary": (
            "Buying Channel Matrix (KB0016025): Punchout/Hosted Catalog -> Standard Coupa Cart; US/CAN "
            "Non-Catalog -> Free-Form Requisition; US/CAN Subconsultant -> Subcontractor Admin Form; "
            "Europe/APAC -> Request a PO. Mexico Exception: ALL Mexico POs are quantity-based and require "
            "a manual Goods Receipt in Coupa even for professional services."
        ),
        "recommended_next_steps": [
            "For Mexico POs, ensure a manual Goods Receipt is entered in Coupa to release 3-way match.",
        ],
    },
    {
        "scenario_id": "SUP-01",
        "category": "Supplier Management (Coupa SIM) — New Supplier Onboarding",
        "invoice_number": "SIM-NEW-4401",
        "aliases": ["SUP-01", "SIM-NEW-4401", "Nordic Marine Survey AS"],
        "coupa_id": "SIM-NEW-4401",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Nordic Marine Survey AS",
        "official_email_domain": "nordicmarine.example.no",
        "backing_po": "Coupa SIM",
        "billed_amount": "0.00 NOK",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "SIM Onboarding Triage (KB0016030)",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 96,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "GBS-Vendor-Management-Security",
        "kb_reference": "KB0016030",
        "diagnostic_summary": (
            "Per KB0016030, standard Coupa-enabled suppliers (e.g., Nordic Marine Survey AS, SIM-NEW-4401) "
            "are onboarded via 'New Supplier Request' in Coupa SIM. One-time legal/expert witnesses or "
            "non-Coupa entities require a ServiceNow case to Vendor Management."
        ),
        "recommended_next_steps": [
            "Initiate a New Supplier Request in Coupa SIM for Nordic Marine Survey AS, or stage a ServiceNow case for one-time legal/expert exceptions.",
        ],
    },
    {
        "scenario_id": "SUP-02",
        "category": "Supplier Management (Coupa SIM) — Multi-Workstream Status",
        "invoice_number": "SIM-REQ-88410",
        "aliases": ["SUP-02", "SIM-REQ-88410", "GeoSyntec Environmental Inc"],
        "coupa_id": "SIM-REQ-88410",
        "oracle_voucher_id": "N/A",
        "supplier_name": "GeoSyntec Environmental Inc",
        "official_email_domain": "geosyntec-env.example.com",
        "backing_po": "Coupa SIM",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "N/A",
        "coupa_status": "Stage 3 of 3 In Progress (Pending TPRM Cyber Questionnaire)",
        "oracle_payment_status": "Vendor Inactive Until All 3 Stages Complete",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 98,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0016030",
        "diagnostic_summary": (
            "GeoSyntec Environmental Inc (SIM-REQ-88410) Onboarding Status (KB0016030): (1) Internal SIM "
            "Request: Complete; (2) Supplier Profile & Tax/Banking Form: Complete; (3) Third-Party Risk "
            "Management (TPRM) Security Review: In Progress — Pending Cyber Questionnaire. Vendor activates "
            "once Stage 3 completes."
        ),
        "recommended_next_steps": [
            "Follow up with GeoSyntec Environmental Inc to submit the pending TPRM Cyber Questionnaire.",
        ],
    },
    {
        "scenario_id": "SUP-03",
        "category": "Supplier Management (Coupa SIM) — Bank Update & Positive Confirmation",
        "invoice_number": "SUP-UPD-55109",
        "aliases": ["SUP-03", "SUP-UPD-55109", "Enviremedial Services LLC"],
        "coupa_id": "SUP-UPD-55109",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Enviremedial Services LLC",
        "official_email_domain": "enviremedial.example.com",
        "backing_po": "Coupa SIM Bank Update",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "3–5 Business Days SLA",
        "coupa_status": "Pending Out-of-Band Voice Positive Confirmation",
        "oracle_payment_status": "Remit-To Hold Pending Callback Verification",
        "eft_reference": None,
        "masked_bank_account": "Pending Positive Confirmation",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0016035",
        "diagnostic_summary": (
            "Enviremedial Services LLC (SUP-UPD-55109) Remit-To Bank Update (KB0016035): Triggered via "
            "Coupa Home > Update to Existing Supplier. Requires secure CSP profile submission plus mandatory "
            "out-of-band Positive Confirmation (voice callback verification) by Vendor Management (3–5 business days)."
        ),
        "recommended_next_steps": [
            "Allow 3–5 business days for Vendor Management out-of-band voice callback verification.",
        ],
    },
    {
        "scenario_id": "EXP-01",
        "category": "Employee Expense Support (Oracle iExpense)",
        "invoice_number": "EXP-992014",
        "aliases": ["EXP-01", "EXP-992014", "IEXPENSE", "MISSING RECEIPT AFFIDAVIT"],
        "coupa_id": "N/A (Oracle iExpense)",
        "oracle_voucher_id": "EXP-992014",
        "supplier_name": "Employee Expense Reimbursement",
        "official_email_domain": "enterprise-gbs.example.com",
        "backing_po": "Oracle iExpense",
        "billed_amount": "0.00 USD",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "Next Payroll/Expense Cycle",
        "coupa_status": "Self-Service iExpense Checklist (KB0016040)",
        "oracle_payment_status": "Awaiting Receipt / Itemization",
        "eft_reference": None,
        "masked_bank_account": "Oracle Employee Self-Service",
        "confidence_score": 99,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "Auto-Resolved (No Ticket Needed)",
        "kb_reference": "KB0016040",
        "diagnostic_summary": (
            "Oracle iExpense Self-Service (KB0016040, Ref EXP-992014): (1) Attach a signed Missing Receipt "
            "Affidavit for lost receipts > $75; (2) Use the Itemize tab in Oracle iExpense to separate hotel "
            "room rate, taxes, and personal room-service charges; (3) Update reimbursement bank accounts in "
            "Oracle Employee Self-Service > Manage Payment Methods."
        ),
        "recommended_next_steps": [
            "Attach signed Missing Receipt Affidavit (> $75), itemize hotel folio lines, and verify bank details in Employee Self-Service.",
        ],
    },
    {
        "scenario_id": "CSP-01",
        "category": "Coupa Supplier Portal (CSP) Support",
        "invoice_number": "CSP-INVITE-7721",
        "aliases": ["CSP-01", "CSP-INVITE-7721", "Keller Foundations Ltd", "PRJ-60511209"],
        "coupa_id": "CSP-INVITE-7721",
        "oracle_voucher_id": "N/A",
        "supplier_name": "Keller Foundations Ltd",
        "official_email_domain": "kellerfoundations.example.uk",
        "backing_po": "CSP Onboarding / Project Sync",
        "billed_amount": "0.00 GBP",
        "invoice_pdf_date": "N/A",
        "coupa_submission_date": "N/A",
        "calculated_net_due_date": "2-Hour Oracle->Coupa Sync",
        "coupa_status": "CSP Invite & Inactive Project PRJ-60511209 (KB0016050)",
        "oracle_payment_status": "N/A",
        "eft_reference": None,
        "masked_bank_account": "N/A",
        "confidence_score": 97,
        "requires_hitl_ticket": False,
        "target_servicenow_queue": "GBS-General-Helpdesk-Triage",
        "kb_reference": "KB0016050",
        "diagnostic_summary": (
            "Keller Foundations Ltd (CSP-INVITE-7721, KB0016050): (1) Re-send the CSP portal invitation via "
            "Suppliers > Contacts > Invite to CSP; (2) Contact the Project Accountant (PA) to reactivate "
            "Project PRJ-60511209 in Oracle so it syncs to Coupa within 2 hours."
        ),
        "recommended_next_steps": [
            "Re-trigger CSP invite under Suppliers > Contacts > Invite to CSP.",
            "Have the Project Accountant reactivate Project PRJ-60511209 in Oracle (2-hour sync to Coupa).",
        ],
    },
]


SUPPLIER_EXEMPTIONS_REGISTRY: dict[str, dict[str, str]] = {
    normalize_key("PACIFIC GRID ENERGY CORP"): {
        "supplier_name": "PACIFIC GRID ENERGY CORP",
        "supplier_id": "SUP-60119",
        "region": "Canada (NAM)",
        "category": "Regulated Electric & Gas Utility",
        "exemption_status": "EXEMPT",
        "submission_channel": "Email PDF invoice directly to ap-ebilling-can@enterprise-gbs.example.com referencing cost center or project number.",
        "kb_reference": "KB0015802",
    },
    normalize_key("AQUAFLOW UTILITIES LTD"): {
        "supplier_name": "AQUAFLOW UTILITIES LTD",
        "supplier_id": "SUP-10421",
        "region": "United Kingdom (EMEA)",
        "category": "Regulated Water Utility",
        "exemption_status": "EXEMPT",
        "submission_channel": "Email PDF invoice to ap-ebilling-uk@enterprise-gbs.example.com or upload via utility EDI feed.",
        "kb_reference": "KB0015802",
    },
    normalize_key("METRO MUNICIPAL WATER AUTHORITY"): {
        "supplier_name": "METRO MUNICIPAL WATER AUTHORITY",
        "supplier_id": "SUP-60882",
        "region": "United States (NAM)",
        "category": "Municipal Government Utility",
        "exemption_status": "EXEMPT",
        "submission_channel": "Email PDF invoice to ap-ebilling-us@enterprise-gbs.example.com.",
        "kb_reference": "KB0015802",
    },
    normalize_key("NOVATECH LEASING SERVICES"): {
        "supplier_name": "NOVATECH LEASING SERVICES",
        "supplier_id": "SUP-70441",
        "region": "United States (NAM)",
        "category": "IT Hardware & Equipment Leasing",
        "exemption_status": "NON-EXEMPT",
        "submission_channel": "Must submit via Coupa Supplier Portal (CSP). Emailed PDF invoices are automatically rejected.",
        "kb_reference": "KB0015802",
    },
    normalize_key("TITAN EARTHWORKS LLC"): {
        "supplier_name": "TITAN EARTHWORKS LLC",
        "supplier_id": "SUP-374355",
        "region": "United States (NAM)",
        "category": "Civil Subcontractor",
        "exemption_status": "NON-EXEMPT",
        "submission_channel": "Must submit via Coupa Supplier Portal (CSP) against an approved PO.",
        "kb_reference": "KB0015802",
    },
    normalize_key("CRESTLINE BUILDERS INC"): {
        "supplier_name": "CRESTLINE BUILDERS INC",
        "supplier_id": "SUP-44812",
        "region": "United States (NAM)",
        "category": "Construction Services",
        "exemption_status": "NON-EXEMPT",
        "submission_channel": "Must submit via Coupa Supplier Portal (CSP) against an approved PO.",
        "kb_reference": "KB0015802",
    },
}


ASSIGNMENT_GROUP_MATRIX: dict[str, dict[str, str]] = {
    "INVOICE_SUPPORT": {
        "assignment_group": "GBS-Global-AP-InvoiceProcessing",
        "default_priority": "P2 — High",
        "target_sla": "4 Business Hours",
    },
    "PAYMENT_SUPPORT": {
        "assignment_group": "GBS-Regional-Payments-Remittance",
        "default_priority": "P3 — Standard",
        "target_sla": "24 Business Hours",
    },
    "URGENT_PAYMENT": {
        "assignment_group": "GBS-EMEA-AP-UrgentPayments",
        "default_priority": "P2 — High",
        "target_sla": "4 Business Hours",
    },
    "LEGAL_ESCALATION": {
        "assignment_group": "GBS-Senior-AP-Escalations",
        "default_priority": "P1 — Critical",
        "target_sla": "2 Business Hours",
    },
    "VENDOR_SECURITY": {
        "assignment_group": "GBS-Vendor-Management-Security",
        "default_priority": "P2 — High",
        "target_sla": "4 Business Hours",
    },
    "GENERAL_TRIAGE": {
        "assignment_group": "GBS-General-Helpdesk-Triage",
        "default_priority": "P3 — Standard",
        "target_sla": "24 Business Hours",
    },
}


def find_golden_record(
    identifier: str,
    supplier_name: Optional[str] = None,
    po_number: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Finds a matching record in `GOLDEN_RECORDS` across normalized aliases."""
    candidates = [identifier]
    if po_number:
        candidates.append(po_number)
    if supplier_name:
        candidates.append(supplier_name)

    # Support comma/space-separated multi-invoice references such as "23469, 23104, 23288"
    expanded: list[str] = []
    for raw in candidates:
        expanded.append(raw)
        for part in re.split(r"[,;/\s]+", raw):
            if len(part.strip()) >= 3:
                expanded.append(part.strip())

    norm_targets = [normalize_key(c) for c in expanded if normalize_key(c)]
    for target in norm_targets:
        for record in GOLDEN_RECORDS:
            record_keys = [
                normalize_key(record["scenario_id"]),
                normalize_key(record["invoice_number"]),
                normalize_key(record["supplier_name"]),
                *[normalize_key(a) for a in record.get("aliases", [])],
            ]
            if target in record_keys:
                return dict(record)

    # Substring fallback on supplier name if provided
    for target in norm_targets:
        if len(target) >= 5:
            for record in GOLDEN_RECORDS:
                sup_norm = normalize_key(record["supplier_name"])
                if target in sup_norm or sup_norm in target:
                    return dict(record)

    return None
