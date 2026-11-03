"""Automated Golden Dataset Evaluation Suite for Ask GBS ADK Agent (Rubric 5.1).

Evaluates all 31 scenarios in `eval/golden_dataset.json` across:
1. Cross-system Coupa + Oracle accuracy (`INV-01`..`INV-17`, `PAY-01`..`PAY-05`, `ACC-01`..`CSP-01`)
2. Strategic Model Routing (`gemini-2.5-flash` vs `gemini-4-argon`)
3. Self-Evaluation Security Guardrails (`PAY-05` `Confidence = 62 < 80` + bank masking)
4. Out-of-scope guided error recovery -> 2-step HITL ServiceNow Case Creation (`CS9940120`)
5. Optional live `google.adk.evaluation.agent_evaluator.AgentEvaluator` integration (`--live-adk`)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ask_gbs_agent.orchestration.model_router import get_model_router  # noqa: E402
from ask_gbs_agent.tools import (  # noqa: E402
    lookup_coupa_oracle_invoice_record,
    stage_servicenow_case_intake_form,
    submit_confirmed_servicenow_case,
)


def _mock_tool_context(initial_state: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(
        state=dict(initial_state or {}),
        agent_name="ask_gbs_eval_harness",
        invocation_id="eval-invocation-001",
    )


def run_deterministic_golden_suite(dataset_path: Path) -> dict[str, Any]:
    """Runs deterministic regression checks across every item in `golden_dataset.json`."""
    cases: list[dict[str, Any]] = json.loads(dataset_path.read_text(encoding="utf-8"))
    router = get_model_router()

    passed = 0
    failures: list[dict[str, Any]] = []

    for item in cases:
        eval_id = item["eval_id"]
        ctx = _mock_tool_context()
        routing = router.route_query(item["query"])

        if item["scenario_id"] == "OUT_OF_SCOPE_HITL":
            lookup_res = lookup_coupa_oracle_invoice_record(
                identifier=item["identifier"],
                inquiry_context=item["query"],
                tool_context=ctx,  # type: ignore[arg-type]
            )
            if (
                lookup_res.get("status") != "RECOVERABLE_ERROR"
                or lookup_res.get("suggested_next_tool") != "stage_servicenow_case_intake_form"
            ):
                failures.append({"eval_id": eval_id, "reason": "Expected guided recovery to ServiceNow intake"})
                continue

            stage_res = stage_servicenow_case_intake_form(
                description=item["query"],
                service_area="GENERAL_TRIAGE",
                reference_number="Custom Inquiry",
                priority="P3",
                tool_context=ctx,  # type: ignore[arg-type]
            )
            blocked_res = submit_confirmed_servicenow_case(
                description=item["query"],
                service_area="GENERAL_TRIAGE",
                reference_number="Custom Inquiry",
                priority="P3",
                tool_context=ctx,  # type: ignore[arg-type]
            )
            ctx.state["hitl_user_confirmed"] = True
            confirmed_res = submit_confirmed_servicenow_case(
                description=item["query"],
                service_area="GENERAL_TRIAGE",
                reference_number="Custom Inquiry",
                priority="P3",
                tool_context=ctx,  # type: ignore[arg-type]
            )
            if (
                stage_res.get("a2ui_surface_id") == "gbs-servicenow-intake-form"
                and blocked_res.get("error_code") == "HITL_CONFIRMATION_REQUIRED"
                and confirmed_res.get("case_number") == "CS9940120"
            ):
                passed += 1
            else:
                failures.append({"eval_id": eval_id, "reason": "2-step HITL ServiceNow workflow mismatch"})
            continue

        result = lookup_coupa_oracle_invoice_record(
            identifier=item["identifier"],
            inquirer_email=item.get("inquirer_email"),
            inquiry_context=item["query"],
            tool_context=ctx,  # type: ignore[arg-type]
        )

        checks_ok = (
            result.get("scenario_id") == item["scenario_id"]
            and result.get("coupa_status") == item["expected_coupa_status"]
            and result.get("kb_reference") == item["expected_kb"]
            and str(result.get("a2ui_surface_id", "")).startswith(item["expected_surface_prefix"])
        )

        if "expected_confidence_max" in item:
            checks_ok = checks_ok and (
                int(result.get("confidence_score", 100)) <= int(item["expected_confidence_max"])
                and result.get("masked_bank_account") == "[REDACTED — SECURITY HOLD]"
            )

        if item["scenario_id"] in {"PAY-03", "PAY-05", "INV-11"}:
            checks_ok = checks_ok and (
                routing.complexity_tier == "COMPLEX_REASONING_ESCALATION"
                and routing.selected_model == router.pro_model
            )

        if checks_ok:
            passed += 1
        else:
            failures.append(
                {
                    "eval_id": eval_id,
                    "expected_scenario": item["scenario_id"],
                    "actual": result,
                }
            )

    return {
        "total_cases": len(cases),
        "passed": passed,
        "failed": len(failures),
        "pass_rate_pct": round((passed / max(1, len(cases))) * 100.0, 2),
        "failures": failures,
    }


async def run_live_adk_evaluator(eval_dir: Path) -> None:
    """Invokes `google.adk.evaluation.agent_evaluator.AgentEvaluator` against live Vertex AI."""
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    await AgentEvaluator.evaluate(
        agent_module="ask_gbs_agent",
        eval_dataset_file_path_or_dir=str(eval_dir),
        num_runs=1,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ask GBS Golden Dataset Evaluation Suite")
    parser.add_argument(
        "--dataset",
        default=str(REPO_ROOT / "eval" / "golden_dataset.json"),
        help="Path to golden_dataset.json",
    )
    parser.add_argument(
        "--live-adk",
        action="store_true",
        help="Also run live LLM trajectories via google.adk.evaluation.AgentEvaluator",
    )
    args = parser.parse_args()

    summary = run_deterministic_golden_suite(Path(args.dataset))
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")

    if args.live_adk:
        asyncio.run(run_live_adk_evaluator(Path(args.dataset).parent))

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
