"""Structured JSON Logger with Cloud Logging & PII Filter (Rubric 4.1).

Replaces ad-hoc standard-output console statements with structured JSON log records
enriched with OpenTelemetry `trace_id` and `span_id` fields, compatible with Google
Cloud Logging (`logging.googleapis.com`) and local JSON log aggregators.
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from typing import Any

from opentelemetry import trace

try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:  # pragma: no cover
    from pythonjsonlogger import jsonlogger  # type: ignore[attr-defined]

    JsonFormatter = jsonlogger.JsonFormatter  # type: ignore[misc,assignment]

from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.observability.pii_redactor import PiiLoggingFilter, get_pii_scrubber


class TraceContextJsonFormatter(JsonFormatter):
    """JSON formatter injecting GCP Cloud Logging trace correlation fields."""

    def __init__(self, *args: Any, project_id: str = "aecom-demo-uc1", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.project_id = project_id

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("severity", record.levelname)
        log_record.setdefault("service", "ask-gbs-agent")
        log_record.setdefault("project_id", self.project_id)

        current_span = trace.get_current_span()
        span_ctx = current_span.get_span_context() if current_span else None
        if span_ctx and span_ctx.is_valid:
            trace_hex = format(span_ctx.trace_id, "032x")
            span_hex = format(span_ctx.span_id, "016x")
            log_record["trace_id"] = trace_hex
            log_record["span_id"] = span_hex
            log_record["logging.googleapis.com/trace"] = (
                f"projects/{self.project_id}/traces/{trace_hex}"
            )
            log_record["logging.googleapis.com/spanId"] = span_hex
        else:
            log_record.setdefault("trace_id", "no-active-trace")
            log_record.setdefault("span_id", "no-active-span")


class StructuredJsonLogger:
    """Enterprise JSON logger integrated with `PiiLoggingFilter` and Cloud Logging."""

    def __init__(self, logger_name: str = "ask_gbs_agent") -> None:
        settings = get_settings()
        self.project_id = settings.google_cloud_project
        self.scrubber = get_pii_scrubber()
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        self.logger.propagate = False

        if not self.logger.handlers:
            pii_filter = PiiLoggingFilter(scrubber=self.scrubber)
            formatter = TraceContextJsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                project_id=self.project_id,
            )

            stream_handler = logging.StreamHandler(stream=sys.stdout)
            stream_handler.setFormatter(formatter)
            stream_handler.addFilter(pii_filter)
            self.logger.addHandler(stream_handler)

            if settings.enable_cloud_logging:
                try:
                    import google.cloud.logging as cloud_logging

                    gcp_client = cloud_logging.Client(project=self.project_id)
                    cloud_handler = gcp_client.get_default_handler()
                    cloud_handler.addFilter(pii_filter)
                    self.logger.addHandler(cloud_handler)
                except Exception as exc:
                    self.logger.warning(
                        "Cloud Logging handler unavailable; continuing with JSON stdout stream",
                        extra={"error_type": type(exc).__name__},
                    )

    def info(self, message: str, **metadata: Any) -> None:
        """Emits a PII-scrubbed INFO structured JSON log entry."""
        sanitized = self.scrubber.scrub_payload(metadata)
        self.logger.info(self.scrubber.scrub_text(message), extra=sanitized)

    def warning(self, message: str, **metadata: Any) -> None:
        """Emits a PII-scrubbed WARNING structured JSON log entry."""
        sanitized = self.scrubber.scrub_payload(metadata)
        self.logger.warning(self.scrubber.scrub_text(message), extra=sanitized)

    def error(self, message: str, **metadata: Any) -> None:
        """Emits a PII-scrubbed ERROR structured JSON log entry."""
        sanitized = self.scrubber.scrub_payload(metadata)
        self.logger.error(self.scrubber.scrub_text(message), extra=sanitized)


@lru_cache(maxsize=8)
def get_structured_logger(name: str = "ask_gbs_agent") -> StructuredJsonLogger:
    """Returns a configured singleton `StructuredJsonLogger`."""
    return StructuredJsonLogger(logger_name=name)
