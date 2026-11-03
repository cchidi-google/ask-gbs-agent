"""Centralized Pydantic settings for Ask GBS ADK Agent (`aecom-demo-uc1`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .secret_manager import SecretManagerResolver

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class GbsAgentSettings(BaseSettings):
    """Runtime settings for Ask GBS across local ADK, Cloud Run, and Agent Engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    google_cloud_project: str = Field(
        default="aecom-demo-uc1",
        alias="GOOGLE_CLOUD_PROJECT",
        description="Target Google Cloud Project ID hosting Vertex AI and Cloud Run.",
    )
    google_cloud_location: str = Field(
        default="us-central1",
        alias="GOOGLE_CLOUD_LOCATION",
        description="Primary Vertex AI and Cloud Run region.",
    )
    google_genai_use_vertexai: bool = Field(
        default=True,
        alias="GOOGLE_GENAI_USE_VERTEXAI",
        description="Whether google-genai / ADK uses Vertex AI endpoints.",
    )
    gemini_flash_model: str = Field(
        default="gemini-2.5-flash",
        alias="GEMINI_FLASH_MODEL",
        description="Fast low-latency Gemini model for deterministic diagnostics and KB guidance.",
    )
    gemini_pro_model: str = Field(
        default="gemini-4-argon",
        alias="GEMINI_PRO_MODEL",
        description="Frontier Gemini 4 Argon model for orchestration, multi-invoice legal holds, and security guardrails.",
    )
    gemini_enterprise_location: str = Field(
        default="global",
        alias="GEMINI_ENTERPRISE_LOCATION",
        description="Discovery Engine / Gemini Enterprise app location.",
    )
    gemini_enterprise_app_id: str = Field(
        default="ask-gbs-enterprise-app",
        alias="GEMINI_ENTERPRISE_APP_ID",
        description="Target Gemini Enterprise application identifier.",
    )
    gbs_memory_db_path: str = Field(
        default=str(PACKAGE_ROOT / "data" / "gbs_memory.db"),
        alias="GBS_MEMORY_DB_PATH",
        description="File path for persistent SQLite + FTS5 + Cosine Vector memory store.",
    )
    source_of_truth_path: str = Field(
        default=str(PACKAGE_ROOT / "data" / "gbs_source_of_truth_data.md"),
        description="Path to sanitized GBS Golden Dataset and ServiceNow KB Markdown source.",
    )
    enable_vertex_memory_bank: bool = Field(
        default=False,
        alias="ENABLE_VERTEX_MEMORY_BANK",
        description="Enables cloud synchronization with VertexAiMemoryBankService.",
    )
    enable_context_caching: bool = Field(
        default=False,
        alias="ENABLE_CONTEXT_CACHING",
        description="Enables Vertex AI CachedContent creation for large static KB payloads.",
    )
    enable_secret_manager: bool = Field(
        default=False,
        alias="ENABLE_SECRET_MANAGER",
        description="Enables live Google Cloud Secret Manager lookups.",
    )
    enable_cloud_logging: bool = Field(
        default=False,
        alias="ENABLE_CLOUD_LOGGING",
        description="Enables direct emission to Google Cloud Logging API.",
    )
    enable_cloud_trace: bool = Field(
        default=False,
        alias="ENABLE_CLOUD_TRACE",
        description="Enables OpenTelemetry CloudTraceSpanExporter to GCP.",
    )
    enable_cloud_dlp: bool = Field(
        default=False,
        alias="ENABLE_CLOUD_DLP",
        description="Enables Google Cloud DLP API inspection alongside deterministic regex scrubbing.",
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Structured logger verbosity level.",
    )

    def resolve_secret(
        self,
        secret_id: str,
        env_fallback_key: Optional[str] = None,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Resolves a secret through Google Cloud Secret Manager with local fallback."""
        resolver = SecretManagerResolver(
            project_id=self.google_cloud_project,
            enable_cloud_fetch=self.enable_secret_manager,
        )
        return resolver.get_secret(
            secret_id=secret_id,
            env_fallback_key=env_fallback_key,
            default=default,
        )


@lru_cache(maxsize=1)
def get_settings() -> GbsAgentSettings:
    """Returns a cached singleton of GbsAgentSettings."""
    return GbsAgentSettings()
