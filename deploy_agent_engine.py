"""Deploys Ask GBS `root_agent` to Vertex AI Agent Engine in `aecom-demo-uc1`."""

from __future__ import annotations

import argparse
import os

import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

from ask_gbs_agent.agent import root_agent
from ask_gbs_agent.observability.structured_logger import get_structured_logger

logger = get_structured_logger("ask_gbs_agent.deploy_agent_engine")


def deploy_to_agent_engine(
    project_id: str = "aecom-demo-uc1",
    location: str = "us-central1",
    staging_bucket: str | None = None,
    dry_run: bool = False,
) -> str:
    """Packages and deploys `root_agent` to Vertex AI Agent Engine (`ReasoningEngine`)."""
    resolved_bucket = staging_bucket or f"gs://{project_id}-ask-gbs-staging"
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", location)
    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=resolved_bucket,
    )
    adk_app = AdkApp(agent=root_agent, enable_tracing=True)

    if dry_run:
        logger.info(
            "Validated AdkApp packaging in dry-run mode",
            project_id=project_id,
            location=location,
            staging_bucket=resolved_bucket,
        )
        return f"projects/{project_id}/locations/{location}/reasoningEngines/dry-run-verified"

    remote_agent = agent_engines.create(
        agent_engine=adk_app,
        display_name="Ask GBS — Enterprise Finance & Procurement Helpdesk",
        description=(
            "Multi-agent ADK assistant for Supplier Invoice Support, Payment Diagnostics, "
            "Coupa KB Guidance, and 2-Step ServiceNow Case Creation with A2UI v0.9 Canvas."
        ),
        requirements=[
            "google-adk>=1.0.0",
            "google-genai>=1.0.0",
            "google-cloud-aiplatform>=1.70.0",
            "google-cloud-secret-manager>=2.20.0",
            "google-cloud-logging>=3.11.0",
            "google-cloud-dlp>=3.21.0",
            "opentelemetry-api>=1.25.0",
            "opentelemetry-sdk>=1.25.0",
            "opentelemetry-exporter-gcp-trace>=1.7.0",
            "python-json-logger>=2.0.7",
            "pydantic>=2.7.0",
            "pydantic-settings>=2.3.0",
        ],
        extra_packages=["ask_gbs_agent"],
    )
    resource_name = str(remote_agent.resource_name)
    logger.info(
        "Successfully deployed Ask GBS to Vertex AI Agent Engine",
        resource_name=resource_name,
    )
    return resource_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy Ask GBS to Vertex AI Agent Engine")
    parser.add_argument("--project_id", default="aecom-demo-uc1")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--staging_bucket", default=None)
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    deploy_to_agent_engine(
        project_id=args.project_id,
        location=args.location,
        staging_bucket=args.staging_bucket,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
