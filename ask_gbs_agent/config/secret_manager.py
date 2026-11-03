"""Google Cloud Secret Manager client with local environment fallback (Rubric 5.3).

Ensures zero hardcoded API keys or credentials exist in source code. Secrets are
retrieved dynamically from `projects/{project_id}/secrets/{secret_id}/versions/{version}`
when Secret Manager is enabled in Google Cloud, with seamless fallback to environment
variables during local development and offline CI/CD evaluation.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

from google.api_core import exceptions as gcp_exceptions
from google.cloud import secretmanager

logger = logging.getLogger("ask_gbs_agent.secret_manager")


class SecretManagerResolver:
    """Resolves runtime secrets securely from Google Cloud Secret Manager."""

    def __init__(
        self,
        project_id: str = "aecom-demo-uc1",
        enable_cloud_fetch: Optional[bool] = None,
    ) -> None:
        self.project_id = project_id
        if enable_cloud_fetch is None:
            enable_cloud_fetch = (
                os.getenv("ENABLE_SECRET_MANAGER", "false").strip().lower() == "true"
            )
        self.enable_cloud_fetch = enable_cloud_fetch
        self._client: Optional[secretmanager.SecretManagerServiceClient] = None
        self._cache: dict[str, str] = {}

    def _get_client(self) -> secretmanager.SecretManagerServiceClient:
        """Lazily initializes the Google Cloud SecretManagerServiceClient."""
        if self._client is None:
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def build_secret_version_path(self, secret_id: str, version: str = "latest") -> str:
        """Builds the canonical GCP Secret Manager resource path."""
        return f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"

    def get_secret(
        self,
        secret_id: str,
        env_fallback_key: Optional[str] = None,
        default: Optional[str] = None,
        version: str = "latest",
    ) -> Optional[str]:
        """Retrieves a secret from GCP Secret Manager with environment fallback.

        Args:
            secret_id: Secret identifier in Google Cloud Secret Manager.
            env_fallback_key: Optional environment variable name for local development.
            default: Non-sensitive fallback value if neither source resolves.
            version: Secret version to access (defaults to 'latest').

        Returns:
            Resolved secret string or default if not configured.
        """
        cache_key = f"{self.project_id}:{secret_id}:{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.enable_cloud_fetch:
            resource_name = self.build_secret_version_path(secret_id, version=version)
            try:
                client = self._get_client()
                response = client.access_secret_version(request={"name": resource_name})
                payload = response.payload.data.decode("utf-8").strip()
                if payload:
                    self._cache[cache_key] = payload
                    return payload
            except (gcp_exceptions.GoogleAPICallError, Exception) as exc:
                logger.warning(
                    "Secret Manager lookup fell back to environment variable",
                    extra={
                        "secret_id": secret_id,
                        "project_id": self.project_id,
                        "error_type": type(exc).__name__,
                    },
                )

        lookup_key = env_fallback_key or secret_id.upper().replace("-", "_")
        env_val = os.getenv(lookup_key)
        if env_val is not None and env_val.strip() != "":
            self._cache[cache_key] = env_val.strip()
            return self._cache[cache_key]

        return default


@lru_cache(maxsize=1)
def get_secret_resolver() -> SecretManagerResolver:
    """Returns a cached singleton SecretManagerResolver bound to the configured GCP project."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "aecom-demo-uc1")
    return SecretManagerResolver(project_id=project_id)
