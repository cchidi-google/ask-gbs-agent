"""Validates every A2UI v0.9 surface against strict Gemini Enterprise composite catalog rules."""

from __future__ import annotations

import copy
import json
import os
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

# Exact per-component property allowlists derived from official
# https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json
_COMMON_MATERIAL_KEYS = {"id", "accessibility", "weight", "style"}
_COMMON_CUSTOM_KEYS = {"id", "accessibility", "weight"}

STRICT_COMPONENT_ALLOWED_KEYS: dict[str, set[str]] = {
    "Canvas": _COMMON_CUSTOM_KEYS
    | {
        "component",
        "children",
        "autoOpen",
        "autoFullscreen",
        "closePanel",
        "cardTitle",
        "cardDescription",
        "cardIcon",
    },
    "MaterialCard": _COMMON_MATERIAL_KEYS
    | {"component", "appearance", "align", "ariaLabel", "ariaLabelledby", "href", "children"},
    "MaterialColumn": _COMMON_MATERIAL_KEYS | {"component", "children", "justify", "align"},
    "MaterialRow": _COMMON_MATERIAL_KEYS | {"component", "children", "justify", "align"},
    "MaterialText": _COMMON_MATERIAL_KEYS | {"component", "text", "usageHint"},
    "MaterialIcon": _COMMON_MATERIAL_KEYS | {"component", "icon", "color", "tooltip"},
    "MaterialDivider": _COMMON_MATERIAL_KEYS | {"component", "inset", "vertical"},
    "MaterialSelect": _COMMON_MATERIAL_KEYS
    | {
        "component",
        "label",
        "placeholder",
        "value",
        "ariaLabel",
        "ariaLabelledby",
        "ariaDescribedby",
        "disabled",
        "options",
        "checks",
    },
    "MaterialInput": _COMMON_MATERIAL_KEYS
    | {
        "component",
        "label",
        "placeholder",
        "value",
        "ariaLabelledby",
        "ariaDescribedby",
        "ariaLabel",
        "disabled",
        "name",
        "readonly",
        "type",
        "validationRegexp",
        "checks",
    },
    "MaterialButton": _COMMON_MATERIAL_KEYS
    | {
        "component",
        "label",
        "leadingIcon",
        "trailingIcon",
        "color",
        "disabled",
        "variant",
        "action",
        "tooltip",
        "ariaLabel",
        "appearance",
        "disableRipple",
        "extended",
    },
    "MaterialExpansionPanel": _COMMON_MATERIAL_KEYS
    | {
        "component",
        "expanded",
        "header",
        "title",
        "description",
        "disabled",
        "ariaLabel",
        "ariaLabelledby",
        "ariaDescribedby",
        "children",
    },
    "MaterialTable": _COMMON_MATERIAL_KEYS
    | {"component", "columns", "rows", "ariaLabel", "caption", "ariaLabelledby"},
    "VegaChart": _COMMON_CUSTOM_KEYS | {"component", "spec", "height"},
}

ALLOWED_COMPONENTS = set(STRICT_COMPONENT_ALLOWED_KEYS.keys())
WIRE_TAG_RE = re.compile(r"^<a2a_datapart_json>(.*)</a2a_datapart_json>$", re.DOTALL)


def _validate_against_cached_official_schemas_if_present(messages: list[dict[str, Any]]) -> None:
    """Runs Draft 2020-12 JSON Schema + strict unevaluatedProperties check if cached in /tmp."""
    paths = ("/tmp/ge_catalog.json", "/tmp/common_types.json", "/tmp/server_to_client.json")
    if not all(os.path.exists(p) for p in paths):
        return

    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    with open("/tmp/ge_catalog.json", encoding="utf-8") as f:
        strict_cat = copy.deepcopy(json.load(f))
    with open("/tmp/common_types.json", encoding="utf-8") as f:
        common_types = json.load(f)
    with open("/tmp/server_to_client.json", encoding="utf-8") as f:
        s2c = json.load(f)

    for cschema in strict_cat["components"].values():
        cschema["unevaluatedProperties"] = False

    cat_id = strict_cat["$id"]

    def _rewrite(obj: Any) -> None:
        if isinstance(obj, dict):
            if "$ref" in obj and obj["$ref"].startswith("catalog.json#"):
                obj["$ref"] = cat_id + obj["$ref"][len("catalog.json") :]
            for val in obj.values():
                _rewrite(val)
        elif isinstance(obj, list):
            for val in obj:
                _rewrite(val)

    _rewrite(s2c)
    _rewrite(common_types)

    registry = (
        Registry()
        .with_resource(strict_cat["$id"], Resource.from_contents(strict_cat))
        .with_resource(common_types["$id"], Resource.from_contents(common_types))
        .with_resource(s2c["$id"], Resource.from_contents(s2c))
    )
    msg_validator = Draft202012Validator(s2c, registry=registry)
    for msg in messages:
        errs = list(msg_validator.iter_errors(msg))
        assert not errs, f"Official schema error: {errs[0].message}"
        if "updateComponents" in msg:
            for comp in msg["updateComponents"]["components"]:
                ctype = comp["component"]
                comp_validator = Draft202012Validator(
                    {"$ref": f"{cat_id}#/components/{ctype}"},
                    registry=registry,
                )
                cerrs = list(comp_validator.iter_errors(comp))
                assert not cerrs, f"Component {comp['id']} ({ctype}) failed: {cerrs[0].message}"


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

    # Rule 5: Both Canvas and MaterialCard require `children: [...]` (never `child` or `content`)
    id_set = set(comp_ids)
    assert "children" in root_comp and isinstance(root_comp["children"], list)
    assert len(root_comp["children"]) >= 1
    assert "child" not in root_comp and "content" not in root_comp

    # Rule 6, 7, 8, 9: Strict key allowlists, component graph integrity, table/chart/button checks
    for comp in components:
        ctype = comp["component"]
        assert ctype in ALLOWED_COMPONENTS, f"Unsupported A2UI component: {ctype}"

        unexpected_keys = set(comp.keys()) - STRICT_COMPONENT_ALLOWED_KEYS[ctype]
        assert not unexpected_keys, (
            f"Unrecognized key(s) on {ctype} ({comp['id']}): {sorted(unexpected_keys)}"
        )

        if "children" in comp:
            assert isinstance(comp["children"], list) and len(comp["children"]) >= 1
            for cid in comp["children"]:
                assert cid in id_set, f"Dangling children ref {cid}"
                assert cid != comp["id"], "Self-referential cycle detected"

        if ctype == "MaterialIcon":
            assert isinstance(comp.get("icon"), str) and len(comp["icon"]) > 0

        # Rule 7: MaterialTable columns (header + field) & string-valued rows; VegaChart DataBinding
        if ctype == "MaterialTable":
            cols = comp.get("columns", [])
            rows = comp.get("rows", [])
            assert len(cols) >= 3 and len(rows) >= 3
            for col in cols:
                assert set(col.keys()) <= {"header", "field"}
                assert "header" in col and "field" in col
            for row in rows:
                assert all(isinstance(v, str) for v in row.values())

        if ctype == "VegaChart":
            assert isinstance(comp.get("spec"), dict) and "path" in comp["spec"]

        # Rule 8: MaterialExpansionPanel title <= 62 chars & children list
        if ctype == "MaterialExpansionPanel":
            assert len(comp["title"]) <= MAX_EXPANSION_TITLE_LEN
            assert isinstance(comp.get("children"), list) and len(comp["children"]) >= 1

        # Rule 9: MaterialButton action event structure & valid Angular Material variant
        if ctype == "MaterialButton":
            assert comp.get("variant") in {
                None,
                "raised",
                "flat",
                "stroked",
                "icon",
                "fab",
                "mini-fab",
                "basic",
            }
            event = comp.get("action", {}).get("event", {})
            assert isinstance(event.get("name"), str) and len(event["name"]) > 0
            assert isinstance(event.get("context"), dict)

    _validate_against_cached_official_schemas_if_present(messages)


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


@pytest.mark.asyncio
async def test_a2ui_plugin_emits_true_a2a_dataparts_and_compacts_history() -> None:
    """Verifies A2UI surfaces serialize as structured A2A DataParts (never raw chat text)."""
    from types import SimpleNamespace

    from a2a.compat.v0_3.conversions import to_compat_part
    from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part
    from google.genai import types

    from ask_gbs_agent.memory.compaction import HistoryCompactionManager
    from ask_gbs_agent.plugins.a2ui_canvas_plugin import A2uiCanvasPlugin, queue_a2ui_surface

    state: dict[str, Any] = {}
    queue_a2ui_surface(state, build_missing_identifier_lookup_card())
    plugin = A2uiCanvasPlugin()

    llm_resp = SimpleNamespace(
        partial=False,
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text="Please enter your invoice identifier.")],
        ),
    )
    cb_ctx = SimpleNamespace(state=state)
    await plugin.after_model_callback(callback_context=cb_ctx, llm_response=llm_resp)  # type: ignore[arg-type]

    parts = llm_resp.content.parts
    assert len(parts) == 4  # 1 text part + 3 A2UI v0.9 DataPart messages
    assert "<a2a_datapart_json>" not in (parts[0].text or "")

    compat_parts = [to_compat_part(convert_genai_part_to_a2a_part(p)) for p in parts[1:]]  # type: ignore[arg-type]
    assert all(cp.root.kind == "data" for cp in compat_parts)
    assert all((cp.root.metadata or {}).get("mimeType") == A2UI_MIME_TYPE for cp in compat_parts)
    assert "createSurface" in compat_parts[0].root.data

    # Verify Turn 2 compaction strips Vertex-unsupported part_metadata & normalizes blobs
    user_click_blob = types.Part(
        inline_data=types.Blob(
            data=b'<a2a_datapart_json>{"userAction":{"name":"confirm_create_servicenow_case","context":{"referenceNumber":"2158"}}}</a2a_datapart_json>',
            mime_type="text/plain",
        )
    )
    req = SimpleNamespace(
        contents=[
            llm_resp.content,
            types.Content(role="user", parts=[user_click_blob]),
        ]
    )
    HistoryCompactionManager().compact_llm_request(req)
    for c in req.contents:
        for p in c.parts:
            assert getattr(p, "part_metadata", None) is None
            assert getattr(p, "inline_data", None) is None
    assert "confirm_create_servicenow_case" in (req.contents[-1].parts[0].text or "")
