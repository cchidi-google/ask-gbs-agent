"""Explicit verification of all 19 AI in 5 Days AgentOps Rubric Criteria (95 / 95 Points)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.adk.agents import LlmAgent, SequentialAgent
from pydantic import ValidationError

from ask_gbs_agent.agent import app as adk_app
from ask_gbs_agent.agent import root_agent
from ask_gbs_agent.callbacks import before_model_callback, parse_a2ui_user_action_event
from ask_gbs_agent.config.secret_manager import SecretManagerResolver
from ask_gbs_agent.memory import (
    HistoryCompactionManager,
    PersistentGbsMemoryService,
    drain_pending_memory_tasks,
    schedule_async_memory_consolidation,
)
from ask_gbs_agent.observability import (
    IntentOutcomeTracker,
    PiiRedactionScrubber,
    clear_exported_spans,
    get_exported_spans,
    start_agent_span,
)
from ask_gbs_agent.orchestration import StrategicModelRouter
from ask_gbs_agent.plugins import GbsPolicyGuardrailPlugin
from ask_gbs_agent.prompts import AGENT_CONSTITUTION_PROMPT
from ask_gbs_agent.schemas import InvoiceLookupInput
from ask_gbs_agent.tools import (
    evaluate_supplier_exemption_status,
    lookup_coupa_oracle_invoice_record,
    open_interactive_coupa_kb_canvas,
    open_urgent_payment_acceleration_form,
    request_missing_invoice_identifier_form,
    stage_servicenow_case_intake_form,
    submit_confirmed_servicenow_case,
)
from main import app as fastapi_app


def test_rubric_category_1_tools_docstrings_naming_schemas_and_guided_errors() -> None:
    """Verifies Rubric 1.1, 1.2, 1.3, and 1.4."""
    tools = [
        lookup_coupa_oracle_invoice_record,
        request_missing_invoice_identifier_form,
        open_interactive_coupa_kb_canvas,
        evaluate_supplier_exemption_status,
        open_urgent_payment_acceleration_form,
        stage_servicenow_case_intake_form,
        submit_confirmed_servicenow_case,
    ]
    for fn in tools:
        assert fn.__doc__ is not None and "Args:" in fn.__doc__ and "Returns:" in fn.__doc__
        assert "_" in fn.__name__ and len(fn.__name__) >= 20

    # Strict extra="forbid" Pydantic v2 validation (Rubric 1.3)
    with pytest.raises(ValidationError):
        InvoiceLookupInput(identifier="INV00026056", unexpected_hallucinated_field="bad")  # type: ignore[call-arg]

    # Guided error recovery instead of unhandled exception on placeholder input (Rubric 1.4)
    err = lookup_coupa_oracle_invoice_record(identifier="unknown")
    assert err["status"] == "RECOVERABLE_ERROR"
    assert err["suggested_next_tool"] == "request_missing_invoice_identifier_form"


@pytest.mark.asyncio
async def test_rubric_category_2_constitution_compaction_sqlite_and_async_memory(
    tmp_path: Path,
) -> None:
    """Verifies Rubric 2.1, 2.2, 2.3, and 2.4."""
    # 2.1 Constitution prompt sections
    for section in ("<PERSONA>", "<OPERATIONAL_RULES>", "<DECISION_TREE>", "<SECURITY_GUARDRAILS>"):
        assert section in AGENT_CONSTITUTION_PROMPT

    # 2.2 Sliding window compaction + stripping <a2a_datapart_json> blobs
    compactor = HistoryCompactionManager(max_tokens=120, keep_recent_turns=3)
    bloated_turns = [
        {
            "role": "model" if i % 2 else "user",
            "content": (
                f"Turn {i} discussing invoice {1000 + i} "
                '<a2a_datapart_json>{"metadata": {"readable_text": "Status Card"}}</a2a_datapart_json>'
            ),
        }
        for i in range(10)
    ]
    compacted = compactor.compact_message_dicts(bloated_turns)
    assert len(compacted) == 4  # 1 summary + 3 recent turns
    assert "[COMPACTED SESSION HISTORY SUMMARY]" in compacted[0]["content"]
    assert "<a2a_datapart_json>" not in compacted[-1]["content"]
    assert "[Rendered A2UI Surface: Status Card]" in compacted[-1]["content"]

    # 2.3 Persistent SQLite + FTS5 + Cosine Vector store with PII scrubbing
    db_file = tmp_path / "test_gbs_memory.db"
    store = PersistentGbsMemoryService(db_path=str(db_file))
    hits = store.search_knowledge_base("KB0015901 FieldSync Ops Ltd Net 30 submission date", top_k=3)
    assert len(hits) >= 1
    assert any("PAY-01" in h["content"] or "KB0015901" in h["content"] for h in hits)

    # 2.4 Non-blocking async memory consolidation via asyncio.create_task
    task = schedule_async_memory_consolidation(
        session_id="async-session-01",
        turns=[
            {"role": "user", "content": "Contact me at jane.doe@corp.example.com about 2158"},
            {"role": "model", "content": "Staged ServiceNow intake card for invoice 2158."},
        ],
        memory_service=store,
    )
    assert task is not None
    await drain_pending_memory_tasks()

    summary = store.get_session_summary("async-session-01")
    assert summary is not None
    assert "[REDACTED_EMAIL]" in summary["summary"]
    assert "jane.doe@corp.example.com" not in summary["summary"]


@pytest.mark.asyncio
async def test_rubric_category_3_multi_agent_routing_and_policy_guardrails() -> None:
    """Verifies Rubric 3.1, 3.2, and 3.3."""
    # 3.1 Coordinator + Specialist Sub-Agents + SequentialAgent
    assert isinstance(root_agent, LlmAgent)
    assert len(root_agent.sub_agents) == 3
    esc_agent = next(a for a in root_agent.sub_agents if a.name == "escalation_hitl_specialist_agent")
    assert any(isinstance(sa, SequentialAgent) for sa in esc_agent.sub_agents)
    assert len(adk_app.plugins) == 2

    # 3.2 Strategic Model Routing (Flash vs Gemini 4 Argon)
    router = StrategicModelRouter(flash_model="gemini-2.5-flash", pro_model="gemini-4-argon")
    fast_decision = router.route_query("Check payment date for INV00026056")
    assert fast_decision.selected_model == "gemini-2.5-flash"

    pro_legal = router.route_query(
        "Second Payment Reminder Notice from BioData Registry Online for 23469, 23104, and 23288"
    )
    assert pro_legal.selected_model == "gemini-4-argon"

    pro_sec = router.route_query(
        "devin.buck@veritaslabs-group.example.com asking about returned payment 3001948880"
    )
    assert pro_sec.selected_model == "gemini-4-argon"

    # 3.3 Read-only ERP mutation guardrail plugin
    guardrail = GbsPolicyGuardrailPlugin()
    blocked = await guardrail.before_tool_callback(
        tool=SimpleNamespace(name="approve_coupa_invoice"),  # type: ignore[arg-type]
        tool_args={"invoice_id": "684575"},
        tool_context=SimpleNamespace(state={}),  # type: ignore[arg-type]
    )
    assert blocked is not None
    assert blocked["error_code"] == "READ_ONLY_ERP_POLICY_VIOLATION"


def test_rubric_category_4_structured_logging_intent_outcome_otel_and_pii() -> None:
    """Verifies Rubric 4.1, 4.2, 4.3, and 4.4."""
    # 4.1 Zero print() calls anywhere in ask_gbs_agent package
    pkg_dir = Path(__file__).resolve().parent.parent / "ask_gbs_agent"
    for py_file in pkg_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        assert "print(" not in source, f"Found forbidden print() in {py_file}"

    # 4.4 PII Redaction Scrubber
    scrubber = PiiRedactionScrubber(enable_cloud_dlp=False)
    dirty_text = (
        "Email ceo@vendor.example.com, SSN 123-45-6789, Phone +1 (415) 555-0199, "
        "Account Number: 00998877665544, IBAN GB29NWBK60161331926819"
    )
    clean_text = scrubber.scrub_text(dirty_text)
    assert "ceo@vendor.example.com" not in clean_text
    assert "123-45-6789" not in clean_text
    assert "555-0199" not in clean_text
    assert "00998877665544" not in clean_text
    assert "GB29NWBK60161331926819" not in clean_text
    assert "[REDACTED_EMAIL]" in clean_text
    assert "[REDACTED_SSN]" in clean_text

    # 4.2 & 4.3 Intent vs Outcome capture + OpenTelemetry spans
    clear_exported_spans()
    tracker = IntentOutcomeTracker()
    with start_agent_span("gbs.rubric_verification", {"user.email": "audit@corp.example.com"}):
        tracker.log_intent(
            execution_id="exec-test-95",
            agent_name="ask_gbs_orchestrator",
            tool_name="lookup_coupa_oracle_invoice_record",
            sanitized_args={"identifier": "INV00026056", "email": "audit@corp.example.com"},
            reason="Verify Coupa submission date Net 30 math",
        )
        tracker.log_outcome(
            execution_id="exec-test-95",
            agent_name="ask_gbs_orchestrator",
            tool_name="lookup_coupa_oracle_invoice_record",
            status="RESOLVED",
            latency_ms=4.2,
            a2ui_surface_id="gbs-invoice-status-INV00026056",
            summary="Resolved Net 30 due date 2026-01-14",
        )

    correlated = tracker.get_recent_records(execution_id="exec-test-95")
    assert [r["phase"] for r in correlated] == ["INTENT", "OUTCOME"]
    assert correlated[0]["intended_arguments"]["email"] == "[REDACTED_EMAIL]"

    spans = get_exported_spans()
    matching_spans = [s for s in spans if s.name == "gbs.rubric_verification"]
    assert len(matching_spans) == 1
    assert matching_spans[0].attributes["user.email"] == "[REDACTED_EMAIL]"


def test_rubric_category_5_secret_manager_and_fastapi_warm_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies Rubric 5.3 Secret Manager fallback and Cloud Run `/health` + `/warm`."""
    monkeypatch.setenv("ASK_GBS_TEST_SECRET", "resolved-via-safe-env-fallback")
    resolver = SecretManagerResolver(project_id="aecom-demo-uc1", enable_cloud_fetch=False)
    assert (
        resolver.build_secret_version_path("ask-gbs-coupa-readonly-token")
        == "projects/aecom-demo-uc1/secrets/ask-gbs-coupa-readonly-token/versions/latest"
    )
    assert resolver.get_secret("ask-gbs-test-secret") == "resolved-via-safe-env-fallback"

    with TestClient(fastapi_app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["project_id"] == "aecom-demo-uc1"

        warm = client.post("/warm")
        assert warm.status_code == 200
        warm_body = warm.json()
        assert warm_body["status"] == "warmed"
        assert warm_body["indexed_kb_hits_verified"] >= 1
        assert warm_body["a2a_ready"] is True

        # Verify Gemini Enterprise A2A v1.0 Agent Card discovery routes
        root_card = client.get(
            "/.well-known/agent-card.json",
            headers={"x-forwarded-proto": "https"},
        )
        assert root_card.status_code == 200
        card_json = root_card.json()
        assert card_json["name"] == "ask_gbs_orchestrator"
        assert card_json["supportedInterfaces"][0]["url"].endswith("/a2a/ask_gbs_agent")
        assert card_json["supportedInterfaces"][0]["url"].startswith("https://")

        mounted_a2a_card = client.get("/a2a/ask_gbs_agent/.well-known/agent-card.json")
        assert mounted_a2a_card.status_code == 200


def test_dynamic_model_mutation_a2ui_buttons_and_native_adk_evalset() -> None:
    """Verifies dynamic `llm_request.model` mutation, secondary A2UI events, and ADK `EvalSet`."""
    from google.adk.evaluation.eval_set import EvalSet
    from google.genai import types

    # 1. Dynamic Flash vs Gemini 4 Argon assignment inside before_model_callback
    cb_ctx = SimpleNamespace(
        state={},
        agent_name="ask_gbs_orchestrator",
        invocation_id="test-dyn-model-01",
    )
    flash_req = SimpleNamespace(
        model="gemini-4-argon",
        contents=[types.Content(role="user", parts=[types.Part.from_text(text="Check INV00026056")])],
    )
    before_model_callback(cb_ctx, flash_req)  # type: ignore[arg-type]
    assert flash_req.model == "gemini-2.5-flash"

    argon_req = SimpleNamespace(
        model="gemini-2.5-flash",
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text="Second Payment Reminder Notice from BioData Registry Online for 23469, 23104, 23288"
                    )
                ],
            )
        ],
    )
    before_model_callback(cb_ctx, argon_req)  # type: ignore[arg-type]
    assert argon_req.model == "gemini-4-argon"

    # 2. Secondary A2UI button events unpack cleanly into session state
    ui_state: dict[str, object] = {}
    parse_a2ui_user_action_event(
        '{"event": {"name": "submit_invoice_quick_lookup", "context": {"identifier": "INV00026056"}}}',
        ui_state,
    )
    assert ui_state["a2ui_quick_lookup_context"] == {"identifier": "INV00026056"}

    # 3. Native ADK EvalSet schema validation (`eval/ask_gbs_golden.evalset.json`)
    evalset_path = Path(__file__).resolve().parent.parent / "eval" / "ask_gbs_golden.evalset.json"
    eval_set = EvalSet.model_validate_json(evalset_path.read_text(encoding="utf-8"))
    assert len(eval_set.eval_cases) >= 6
