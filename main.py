"""FastAPI + Google ADK Server Wrapper for Cloud Run & Gemini Enterprise (`aecom-demo-uc1`).

Exposes standard ADK endpoints (`/run`, `/run_sse`, `/list-apps`) via
`google.adk.cli.fast_api.get_fast_api_app` alongside `/health` and `POST /warm`
to pre-warm SQLite/FTS5/Vector indices and model routing before live demos.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.memory.persistent_store import get_memory_service
from ask_gbs_agent.observability.structured_logger import get_structured_logger
from ask_gbs_agent.observability.tracing import configure_opentelemetry_tracing
from ask_gbs_agent.orchestration.model_router import get_model_router

ROOT_DIR = Path(__file__).resolve().parent
settings = get_settings()
logger = get_structured_logger("ask_gbs_agent.server")

configure_opentelemetry_tracing(
    project_id=settings.google_cloud_project,
    enable_cloud_trace=settings.enable_cloud_trace,
)

app: FastAPI = get_fast_api_app(
    agents_dir=str(ROOT_DIR),
    allow_origins=["*"],
    web=os.getenv("ADK_ENABLE_WEB_UI", "true").lower() == "true",
    otel_to_cloud=settings.enable_cloud_trace,
)


# Replace ADK's minimal default /health route with our AgentOps health metadata route
app.router.routes = [
    r for r in app.router.routes if getattr(r, "path", None) != "/health"
]


@app.get("/health", tags=["agentops"])
async def health_check() -> dict[str, Any]:
    """Liveness and readiness probe for Google Cloud Run."""
    return {
        "status": "ok",
        "service": "ask-gbs-agent",
        "project_id": settings.google_cloud_project,
        "region": settings.google_cloud_location,
        "a2ui_version": "v0.9",
    }


@app.post("/warm", tags=["agentops"])
async def prewarm_runtime() -> dict[str, Any]:
    """Pre-warms the SQLite/Vector RAG store, model router, and ADK orchestrator."""
    start_ts = time.perf_counter()
    mem = get_memory_service()
    sample_hits = mem.search_knowledge_base("KB0015901 INV00026056 Net 30 submission date", top_k=2)
    router = get_model_router()
    flash_check = router.route_query("Check status of INV00026056")
    pro_check = router.route_query("BioData Registry Online Second Payment Reminder 23469 23104 23288")
    elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)

    logger.info(
        "Runtime pre-warm completed for Gemini Enterprise live demo",
        warm_latency_ms=elapsed_ms,
        kb_hits=len(sample_hits),
        flash_model=flash_check.selected_model,
        pro_model=pro_check.selected_model,
    )
    return {
        "status": "warmed",
        "project_id": settings.google_cloud_project,
        "warm_latency_ms": elapsed_ms,
        "indexed_kb_hits_verified": len(sample_hits),
        "models_ready": [flash_check.selected_model, pro_check.selected_model],
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
