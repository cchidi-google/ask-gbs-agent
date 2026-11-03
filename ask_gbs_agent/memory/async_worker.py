"""Asynchronous Non-Blocking Memory Consolidation Workers (Rubric 2.4).

Offloads expensive session summarization, PII scrubbing, and vector embedding
writes onto background `asyncio.Task` coroutines (`asyncio.create_task`) so
chat and A2UI Canvas streaming latency is never blocked.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ask_gbs_agent.memory.compaction import HistoryCompactionManager
from ask_gbs_agent.memory.persistent_store import PersistentGbsMemoryService, get_memory_service
from ask_gbs_agent.observability.structured_logger import get_structured_logger

_ACTIVE_MEMORY_TASKS: set[asyncio.Task[Any]] = set()
_LOGGER = get_structured_logger("ask_gbs_agent.async_memory")


async def upsert_turn_embeddings_async(
    session_id: str,
    role: str,
    content: str,
    memory_service: Optional[PersistentGbsMemoryService] = None,
) -> dict[str, Any]:
    """Asynchronously computes embeddings and persists a single turn off the main path."""
    store = memory_service or get_memory_service()
    cleaned = HistoryCompactionManager.strip_a2ui_blobs(content)
    return await asyncio.to_thread(store.append_session_turn, session_id, role, cleaned)


async def consolidate_session_memory_async(
    session_id: str,
    turns: list[dict[str, str]],
    memory_service: Optional[PersistentGbsMemoryService] = None,
) -> dict[str, Any]:
    """Asynchronously consolidates multi-turn conversation state into persistent memory."""
    store = memory_service or get_memory_service()

    if turns:
        latest = turns[-1]
        await upsert_turn_embeddings_async(
            session_id=session_id,
            role=latest.get("role", "model"),
            content=latest.get("content", ""),
            memory_service=store,
        )

    digest_items: list[str] = []
    for item in turns[-8:]:
        role = item.get("role", "user")
        clean_text = HistoryCompactionManager.strip_a2ui_blobs(item.get("content", ""))
        snippet = " ".join(clean_text.split())
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."
        if snippet:
            digest_items.append(f"[{role}] {snippet}")

    summary_text = " | ".join(digest_items) if digest_items else "Session initialized."
    result = await asyncio.to_thread(
        store.upsert_session_summary,
        session_id,
        summary_text,
        len(turns),
    )
    _LOGGER.info(
        "Completed async background memory consolidation",
        session_id=session_id,
        consolidated_turns=len(turns),
    )
    return result


def schedule_async_memory_consolidation(
    session_id: str,
    turns: list[dict[str, str]],
    memory_service: Optional[PersistentGbsMemoryService] = None,
) -> Optional[asyncio.Task[dict[str, Any]]]:
    """Schedules non-blocking memory consolidation via `asyncio.create_task()`.

    Safe to call from synchronous or asynchronous ADK callbacks: if an event loop
    is running, returns the background `asyncio.Task` immediately without awaiting.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    task = loop.create_task(
        consolidate_session_memory_async(
            session_id=session_id,
            turns=turns,
            memory_service=memory_service,
        ),
        name=f"gbs-memory-consolidate-{session_id}",
    )
    _ACTIVE_MEMORY_TASKS.add(task)
    task.add_done_callback(_ACTIVE_MEMORY_TASKS.discard)
    return task


async def drain_pending_memory_tasks() -> int:
    """Awaits all currently scheduled background memory tasks (useful in tests/shutdown)."""
    pending = list(_ACTIVE_MEMORY_TASKS)
    if not pending:
        return 0
    await asyncio.gather(*pending, return_exceptions=True)
    return len(pending)
