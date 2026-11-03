"""Observability, Tracing, Structured Logging & PII Redaction (Rubric Category 4)."""

from .intent_outcome_tracker import IntentOutcomeTracker, get_intent_outcome_tracker
from .pii_redactor import PiiLoggingFilter, PiiRedactionScrubber, get_pii_scrubber
from .structured_logger import StructuredJsonLogger, get_structured_logger
from .tracing import (
    clear_exported_spans,
    configure_opentelemetry_tracing,
    get_exported_spans,
    get_tracer,
    start_agent_span,
)

__all__ = [
    "IntentOutcomeTracker",
    "PiiLoggingFilter",
    "PiiRedactionScrubber",
    "StructuredJsonLogger",
    "clear_exported_spans",
    "configure_opentelemetry_tracing",
    "get_exported_spans",
    "get_intent_outcome_tracker",
    "get_pii_scrubber",
    "get_structured_logger",
    "get_tracer",
    "start_agent_span",
]
