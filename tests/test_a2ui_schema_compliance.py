"""Validates every A2UI v0.9 surface against all 10 Gemini Enterprise composite catalog rules."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from ask_gbs_agent.plugins.a2ui_canvas_plugin import (
    A2UI_MIME_TYPE,
    A2UI_VERSION,
    GE_COMPOSITE_CATALOG_ID,
    KB_ARTICLES_CATALOG,
    MAX_EXPANSION_TITLE_LEN,
    build_interactive_kb_canvas,
    build_invoice_payment_status_card,
    build_missing_identifier_lookup_card,
    build_multi_invoice_reconciliation_canvas,
    build_servicenow_intake_form_card,
    build_servicenow_receipt_card,
    build_urgent_payment_intake_card,
)
from ask_gbs_agent.tools.golden_catalog import find_golden_record

ALLOWED_COMPONENTS = {
    "Canvas",
    "MaterialCard",
    "MaterialColumn",
    "MaterialRow",
    "MaterialText",
    "MaterialIcon",
    "MaterialDivider",
    "MaterialSelect",
    "MaterialInput",
    "MaterialButton",
    "MaterialExpansionPanel",
    "RichTable",
    "Chart",
}

WIRE_TAG_RE = re.compile(r"^<a2a_datapart_json>(.*)</a2a_datapart_json>$", re.DOTALL)


def assert_ten_a2ui_catalog_rules(packaged: dict[str, Any], expected_root_type: str) -> None:
    """Asserts all 10 Gemini Enterprise A2UI v0.9 composite catalog rules on `packaged`."""
    # Rule 10: <a2a_datapart_json> wire envelope & metadata
    match = WIRE_TAG_RE.match(packaged["wire_tag"])
    assert match is not None, "Missing <a2a_datapart_json> wire tag wrapper"
    envelope = json.loads(match.group(1))
    assert envelope["mimeType"] == A2UI_MIME_TYPE
    assert envelope["metadata"]["mimeType"] == A2UI_MIME_TYPE
    assert len(envelope["metadata"]["readable_text"]) >= 10

    messages = envelope["data"]
    assert isinstance(messages, list) and len(messages) >= 2

    # Rule 1: Every message declares version == "v0.9"
    for msg in messages:
        assert msg.get("version") == A2UI_VERSION

    # Rule 2: createSurface catalogId & consistent surfaceId across all messages
    create_surface = messages[0].get("createSurface")
    assert create_surface is not None
    assert create_surface["catalogId"] == GE_COMPOSITE_CATALOG_ID
    surface_id = create_surface["surfaceId"]
    assert surface_id == packaged["surface_id"]

    update_comp = messages[1].get("updateComponents")
    assert update_comp is not None
    assert update_comp["surfaceId"] == surface_id
    for extra_msg in messages[2:]:
        if "updateDataModel" in extra_msg:
            assert extra_msg["updateDataModel"]["surfaceId"] == surface_id

    components = update_comp["components"]
    assert isinstance(components, list) and len(components) >= 2

    # Rule 3 & Rule 4: Unique component IDs and exactly one id="root"
    comp_ids = [c["id"] for c in components]
    assert len(comp_ids) == len(set(comp_ids)), "Duplicate component IDs found"
    roots = [c for c in components if c["id"] == "root"]
    assert len(roots) == 1
    root_comp = roots[0]
    assert root_comp["component"] == expected_root_type

    # Rule 5: Allowed component types + Canvas `content` vs MaterialCard `child`
    id_set = set(comp_ids)
    if expected_root_type == "Canvas":
        assert "content" in root_comp and root_comp["content"] in id_set
    elif expected_root_type == "MaterialCard":
        assert "child" in root_comp and root_comp["child"] in id_set

    # Rule 6, 7, 8, 9: Component-specific structural & graph integrity checks
    for comp in components:
        ctype = comp["component"]
        assert ctype in ALLOWED_COMPONENTS, f"Unsupported A2UI component: {ctype}"

        if "child" in comp:
            assert comp["child"] in id_set, f"Dangling child ref {comp['child']}"
            assert comp["child"] != comp["id"], "Self-referential cycle detected"
        if "content" in comp and isinstance(comp["content"], str):
            assert comp["content"] in id_set, f"Dangling content ref {comp['content']}"
        if "children" in comp:
            for cid in comp["children"]:
                assert cid in id_set, f"Dangling children ref {cid}"
                assert cid != comp["id"]

        # Rule 7: RichTable spec: {} and numeric floats
        if ctype == "RichTable":
            assert isinstance(comp.get("spec"), dict)
            rows = comp.get("rows", [])
            assert len(rows) >= 3
            for row in rows:
                assert isinstance(row["amount_gbp"], float)

        # Rule 8: MaterialExpansionPanel title <= 62 chars
        if ctype == "MaterialExpansionPanel":
            assert len(comp["title"]) <= MAX_EXPANSION_TITLE_LEN

        # Rule 9: MaterialButton action event structure
        if ctype == "MaterialButton":
            event = comp.get("action", {}).get("event", {})
            assert isinstance(event.get("name"), str) and len(event["name"]) > 0
            assert isinstance(event.get("context"), dict)


def test_surface_a_servicenow_intake_card_compliance() -> None:
    pkg = build_servicenow_intake_form_card()
    assert pkg["surface_id"] == "gbs-servicenow-intake-form"
    assert_ten_a2ui_catalog_rules(pkg, expected_root_type="MaterialCard")


def test_surface_b_servicenow_receipt_card_compliance() -> None:
    pkg = build_servicenow_receipt_card(case_number="CS9940120")
    assert pkg["surface_id"] == "gbs-servicenow-receipt-CS9940120"
    assert_ten_a2ui_catalog_rules(pkg, expected_root_type="MaterialCard")


def test_surface_c_missing_identifier_card_compliance() -> None:
    pkg = build_missing_identifier_lookup_card()
    assert pkg["surface_id"] == "gbs-missing-identifier-card"
    assert_ten_a2ui_catalog_rules(pkg, expected_root_type="MaterialCard")


def test_surface_d_invoice_status_card_compliance() -> None:
    pay01 = find_golden_record("INV00026056")
    assert pay01 is not None
    pkg = build_invoice_payment_status_card(pay01)
    assert pkg["surface_id"] == "gbs-invoice-status-INV00026056"
    assert_ten_a2ui_catalog_rules(pkg, expected_root_type="MaterialCard")


def test_surface_e_multi_invoice_reconciliation_canvas_compliance() -> None:
    pkg = build_multi_invoice_reconciliation_canvas()
    assert pkg["surface_id"] == "gbs-biodata-reconciliation-canvas"
    assert_ten_a2ui_catalog_rules(pkg, expected_root_type="Canvas")


@pytest.mark.parametrize("kb_id", sorted(KB_ARTICLES_CATALOG.keys()))
def test_surface_e_all_kb_canvases_compliance(kb_id: str) -> None:
    pkg = build_interactive_kb_canvas(kb_article_id=kb_id, topic_focus="Live Demo Validation")
    assert_ten_a2ui_catalog_rules(pkg, expected_root_type="Canvas")


def test_urgent_payment_acceleration_card_compliance() -> None:
    pkg = build_urgent_payment_intake_card(invoice_number="INV00026056")
    assert_ten_a2ui_catalog_rules(pkg, expected_root_type="MaterialCard")
