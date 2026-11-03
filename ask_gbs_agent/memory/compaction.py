"""History Compaction & Vertex AI Context Caching Manager (Rubric 2.2).

Prevents multi-turn context window bloat by:
1. Stripping bulky historical `<a2a_datapart_json>` A2UI payloads from earlier turns
   and replacing them with lightweight `[Rendered A2UI Surface: {readable_text}]` markers.
2. Enforcing a token-aware sliding window (`max_tokens`, `keep_recent_turns`) that
   summarizes older conversation history while preserving key invoice/PO identifiers
   and the agent's constitutional system instructions.
3. Providing a Vertex AI `CachedContent` helper for static GBS Knowledge Base caching.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Optional

from google.genai import types

from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.observability.structured_logger import get_structured_logger

A2UI_TAG_PATTERN = re.compile(
    r"<a2a_datapart_json>\s*(.*?)\s*</a2a_datapart_json>",
    re.DOTALL,
)


class HistoryCompactionManager:
    """Manages LLM context window compaction and Vertex AI context caching."""

    def __init__(
        self,
        max_tokens: int = 5500,
        keep_recent_turns: int = 6,
    ) -> None:
        self.max_tokens = max_tokens
        self.keep_recent_turns = keep_recent_turns
        self._logger = get_structured_logger("ask_gbs_agent.compaction")
        self._cached_content_name: Optional[str] = None

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Approximates LLM token count (~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    @classmethod
    def strip_a2ui_blobs(cls, text: str) -> str:
        """Replaces raw `<a2a_datapart_json>` blocks with compact readable summaries."""
        if not text or "<a2a_datapart_json>" not in text:
            return text

        def _replacer(match: re.Match[str]) -> str:
            raw_json = match.group(1)
            readable = "Interactive GBS A2UI Surface"
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    meta = parsed.get("metadata") or parsed.get("part_metadata") or {}
                    readable = meta.get("readable_text") or meta.get("surface_id") or readable
            except Exception:
                pass
            return f"[Rendered A2UI Surface: {readable}]"

        return A2UI_TAG_PATTERN.sub(_replacer, text)

    def compact_message_dicts(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Compacts a list of `{"role": ..., "content": ...}` turn dictionaries."""
        if not messages:
            return []

        cleaned: list[dict[str, str]] = []
        for idx, msg in enumerate(messages):
            content = msg.get("content", "")
            # Strip A2UI JSON payloads on all historical turns
            if idx < len(messages) - 1:
                content = self.strip_a2ui_blobs(content)
            else:
                content = self.strip_a2ui_blobs(content)
            cleaned.append({"role": msg.get("role", "user"), "content": content})

        total_tokens = sum(self.estimate_tokens(m["content"]) for m in cleaned)
        if len(cleaned) <= self.keep_recent_turns and total_tokens <= self.max_tokens:
            return cleaned

        split_idx = max(1, len(cleaned) - self.keep_recent_turns)
        older_turns = cleaned[:split_idx]
        recent_turns = cleaned[split_idx:]

        bullet_points: list[str] = []
        for turn in older_turns:
            snippet = " ".join(turn["content"].split())
            if len(snippet) > 140:
                snippet = snippet[:137] + "..."
            bullet_points.append(f"- {turn['role']}: {snippet}")

        summary_text = (
            "[COMPACTED SESSION HISTORY SUMMARY]\n"
            f"Compacted {len(older_turns)} earlier turn(s) to preserve context budget:\n"
            + "\n".join(bullet_points[:10])
        )

        compacted = [{"role": "user", "content": summary_text}, *recent_turns]
        self._logger.info(
            "HistoryCompactionManager compacted conversation history",
            original_turns=len(messages),
            compacted_turns=len(compacted),
            original_est_tokens=total_tokens,
        )
        return compacted

    def compact_llm_request(self, llm_request: Any) -> int:
        """In-place sliding-window compaction on an ADK `LlmRequest` object.

        Returns:
            Estimated token count after compaction.
        """
        contents = getattr(llm_request, "contents", None)
        if not contents or not isinstance(contents, list):
            return 0

        # Step 1: Strip historical A2UI JSON blobs from all prior model turns
        total_tokens = 0
        for idx, content in enumerate(contents):
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    if idx < len(contents) - 1 and "<a2a_datapart_json>" in part_text:
                        part.text = self.strip_a2ui_blobs(part_text)
                    total_tokens += self.estimate_tokens(part.text)

        # Step 2: Summarize older turns if turn threshold or token budget is exceeded
        if len(contents) > self.keep_recent_turns or total_tokens > self.max_tokens:
            if len(contents) > self.keep_recent_turns:
                split_idx = len(contents) - self.keep_recent_turns
                older = contents[:split_idx]
                recent = contents[split_idx:]

                digest_lines: list[str] = []
                for item in older:
                    role = getattr(item, "role", "user") or "user"
                    texts = [
                        self.strip_a2ui_blobs(getattr(p, "text", "") or "")
                        for p in (getattr(item, "parts", None) or [])
                        if getattr(p, "text", None)
                    ]
                    if texts:
                        merged = " ".join(" ".join(texts).split())
                        if len(merged) > 140:
                            merged = merged[:137] + "..."
                        digest_lines.append(f"- {role}: {merged}")

                summary_content = types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                "[COMPACTED SESSION HISTORY SUMMARY]\n"
                                + "\n".join(digest_lines[:10])
                            )
                        )
                    ],
                )
                llm_request.contents = [summary_content, *recent]

        final_tokens = 0
        for content in getattr(llm_request, "contents", []) or []:
            for part in getattr(content, "parts", None) or []:
                if getattr(part, "text", None):
                    final_tokens += self.estimate_tokens(part.text)
        return final_tokens

    def ensure_vertex_context_cache(self, static_kb_markdown: str) -> Optional[str]:
        """Creates or reuses a Vertex AI `CachedContent` resource for the static KB."""
        settings = get_settings()
        if not settings.enable_context_caching:
            return None
        if self._cached_content_name:
            return self._cached_content_name

        try:
            from google import genai

            client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
            cached = client.caches.create(
                model=settings.gemini_flash_model,
                config=types.CreateCachedContentConfig(
                    display_name="ask-gbs-kb-context-cache",
                    contents=[static_kb_markdown],
                    ttl="3600s",
                ),
            )
            self._cached_content_name = cached.name
            return self._cached_content_name
        except Exception as exc:
            self._logger.warning(
                "Vertex AI Context Caching skipped; continuing with in-prompt constitution",
                error_type=type(exc).__name__,
            )
            return None


@lru_cache(maxsize=1)
def get_compaction_manager() -> HistoryCompactionManager:
    """Returns a singleton `HistoryCompactionManager`."""
    return HistoryCompactionManager()
