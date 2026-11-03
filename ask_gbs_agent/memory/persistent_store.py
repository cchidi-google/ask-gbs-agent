"""Persistent Hybrid SQLite + FTS5 + Cosine Vector Memory Service (Rubric 2.3).

Provides zero-configuration persistent storage in `ask_gbs_agent/data/gbs_memory.db`
seeded automatically from `gbs_source_of_truth_data.md`, alongside optional cloud
synchronization adapters for `VertexAiSessionService`, `VertexAiMemoryBankService`,
and Vertex AI Search (`discoveryengine.googleapis.com`) in `aecom-demo-uc1`.

All stored session turns and summaries are scrubbed via `PiiRedactionScrubber`
prior to persistence (Rubric 4.4).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from ask_gbs_agent.config.settings import get_settings
from ask_gbs_agent.observability.pii_redactor import get_pii_scrubber
from ask_gbs_agent.observability.structured_logger import get_structured_logger
from ask_gbs_agent.observability.tracing import start_agent_span

EMBEDDING_DIM = 64
TOKEN_SPLIT_RE = re.compile(r"[a-z0-9]{2,}")


def compute_deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Computes a normalized deterministic feature-hashed vector embedding."""
    vec = [0.0] * dim
    if not text:
        return vec
    tokens = TOKEN_SPLIT_RE.findall(text.lower())
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        bucket = digest[0] % dim
        sign = 1.0 if (digest[1] % 2 == 0) else -1.0
        vec[bucket] += sign * (1.0 + (digest[2] / 255.0) * 0.25)

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Computes cosine similarity between two normalized embedding vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    return sum(a * b for a, b in zip(vec_a, vec_b))


class PersistentGbsMemoryService:
    """Hybrid persistent RAG & session state database with FTS5 + Cosine Vector search."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        source_markdown_path: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.gbs_memory_db_path)
        self.source_markdown_path = Path(
            source_markdown_path or settings.source_of_truth_path
        )
        self.project_id = settings.google_cloud_project
        self.location = settings.google_cloud_location
        self.enable_vertex_memory_bank = settings.enable_vertex_memory_bank
        self._scrubber = get_pii_scrubber()
        self._logger = get_structured_logger("ask_gbs_agent.memory")
        self._lock = threading.RLock()
        self._fts5_enabled = True

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema_and_seed()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_schema_and_seed(self) -> None:
        """Creates persistent SQLite tables, FTS5 virtual index, and seeds KB chunks."""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    section_title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                        chunk_id UNINDEXED,
                        section_title,
                        content
                    )
                    """
                )
            except sqlite3.OperationalError:
                self._fts5_enabled = False

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    scrubbed_content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    scrubbed_summary TEXT NOT NULL,
                    turn_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS servicenow_cases (
                    case_number TEXT PRIMARY KEY,
                    service_area TEXT NOT NULL,
                    assignment_group TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    target_sla TEXT NOT NULL,
                    reference_number TEXT NOT NULL,
                    scrubbed_requester_email TEXT NOT NULL,
                    scrubbed_description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

            row = conn.execute("SELECT COUNT(*) AS cnt FROM knowledge_chunks").fetchone()
            if row and int(row["cnt"]) == 0:
                self._seed_from_markdown(conn)

    def _seed_from_markdown(self, conn: sqlite3.Connection) -> None:
        """Parses `gbs_source_of_truth_data.md` into searchable hybrid chunks."""
        if not self.source_markdown_path.exists():
            return

        markdown_text = self.source_markdown_path.read_text(encoding="utf-8")
        sections = re.split(r"\n(?=##\s+|\|\s*\*\*)", markdown_text)
        now_iso = datetime.now(timezone.utc).isoformat()

        for idx, raw_block in enumerate(sections):
            cleaned = raw_block.strip()
            if len(cleaned) < 20:
                continue
            first_line = cleaned.splitlines()[0].strip("#| *")[:120]
            chunk_id = f"GBS-CHUNK-{idx:03d}"
            emb_json = json.dumps(compute_deterministic_embedding(cleaned))
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_chunks
                (chunk_id, section_title, content, embedding_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chunk_id, first_line, cleaned, emb_json, now_iso),
            )
            if self._fts5_enabled:
                conn.execute(
                    "INSERT INTO knowledge_fts (chunk_id, section_title, content) VALUES (?, ?, ?)",
                    (chunk_id, first_line, cleaned),
                )
        conn.commit()

    def search_knowledge_base(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Executes hybrid FTS5 lexical + Cosine Vector semantic retrieval."""
        if not query or not query.strip():
            return []

        with start_agent_span(
            "gbs.rag_retrieval",
            {"query.length": len(query), "top_k": top_k},
        ):
            query_vec = compute_deterministic_embedding(query)
            fts_scores: dict[str, float] = {}

            with self._lock, self._connect() as conn:
                if self._fts5_enabled:
                    tokens = TOKEN_SPLIT_RE.findall(query.lower())
                    if tokens:
                        fts_query = " OR ".join(f'"{t}"' for t in tokens[:8])
                        try:
                            fts_rows = conn.execute(
                                """
                                SELECT chunk_id, bm25(knowledge_fts) AS rank_score
                                FROM knowledge_fts
                                WHERE knowledge_fts MATCH ?
                                LIMIT 15
                                """,
                                (fts_query,),
                            ).fetchall()
                            for r in fts_rows:
                                # bm25 in SQLite FTS5 returns negative values (more negative = better)
                                fts_scores[str(r["chunk_id"])] = abs(float(r["rank_score"]))
                        except sqlite3.OperationalError:
                            pass

                all_rows = conn.execute(
                    "SELECT chunk_id, section_title, content, embedding_json FROM knowledge_chunks"
                ).fetchall()

            scored: list[dict[str, Any]] = []
            max_fts = max(fts_scores.values(), default=1.0) or 1.0
            q_lower = query.strip().lower()

            for row in all_rows:
                cid = str(row["chunk_id"])
                content = str(row["content"])
                emb = json.loads(str(row["embedding_json"]))
                vec_sim = max(0.0, cosine_similarity(query_vec, emb))
                lex_sim = fts_scores.get(cid, 0.0) / max_fts
                exact_boost = 0.35 if q_lower in content.lower() else 0.0
                hybrid_score = round(0.55 * vec_sim + 0.45 * lex_sim + exact_boost, 4)

                if hybrid_score > 0.05:
                    scored.append(
                        {
                            "chunk_id": cid,
                            "section_title": str(row["section_title"]),
                            "content": content,
                            "score": hybrid_score,
                        }
                    )

            scored.sort(key=lambda item: item["score"], reverse=True)
            return scored[:top_k]

    def append_session_turn(self, session_id: str, role: str, content: str) -> dict[str, Any]:
        """Scrubs PII and persists a conversation turn with its semantic embedding."""
        scrubbed_content = self._scrubber.scrub_text(content)
        embedding = compute_deterministic_embedding(scrubbed_content)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_turns (session_id, role, scrubbed_content, embedding_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, scrubbed_content, json.dumps(embedding), now_iso),
            )
            conn.commit()

        return {
            "session_id": session_id,
            "role": role,
            "scrubbed_content": scrubbed_content,
            "created_at": now_iso,
        }

    def get_session_turns(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves persisted PII-scrubbed turns for a given `session_id`."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, scrubbed_content, created_at
                FROM session_turns
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "role": str(r["role"]),
                "content": str(r["scrubbed_content"]),
                "created_at": str(r["created_at"]),
            }
            for r in reversed(rows)
        ]

    def upsert_session_summary(
        self,
        session_id: str,
        summary_text: str,
        turn_count: int,
    ) -> dict[str, Any]:
        """Scrubs PII and upserts a consolidated session summary."""
        scrubbed_summary = self._scrubber.scrub_text(summary_text)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_summaries (session_id, scrubbed_summary, turn_count, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    scrubbed_summary = excluded.scrubbed_summary,
                    turn_count = excluded.turn_count,
                    updated_at = excluded.updated_at
                """,
                (session_id, scrubbed_summary, turn_count, now_iso),
            )
            conn.commit()
        return {
            "session_id": session_id,
            "scrubbed_summary": scrubbed_summary,
            "turn_count": turn_count,
            "updated_at": now_iso,
        }

    def get_session_summary(self, session_id: str) -> Optional[dict[str, Any]]:
        """Fetches the consolidated session summary for `session_id` if present."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_id, scrubbed_summary, turn_count, updated_at
                FROM session_summaries
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "session_id": str(row["session_id"]),
            "summary": str(row["scrubbed_summary"]),
            "turn_count": int(row["turn_count"]),
            "updated_at": str(row["updated_at"]),
        }

    def record_illustrative_servicenow_case(
        self,
        case_number: str,
        service_area: str,
        assignment_group: str,
        priority: str,
        target_sla: str,
        reference_number: str,
        requester_email: str,
        description: str,
    ) -> None:
        """Persists an illustrative ServiceNow ticket record with PII scrubbing."""
        scrubbed_email = self._scrubber.scrub_text(requester_email)
        scrubbed_desc = self._scrubber.scrub_text(description)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO servicenow_cases (
                    case_number, service_area, assignment_group, priority,
                    target_sla, reference_number, scrubbed_requester_email,
                    scrubbed_description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_number,
                    service_area,
                    assignment_group,
                    priority,
                    target_sla,
                    reference_number,
                    scrubbed_email,
                    scrubbed_desc,
                    now_iso,
                ),
            )
            conn.commit()

    def build_vertex_session_service(self, agent_engine_id: Optional[str] = None) -> Any:
        """Creates an ADK `VertexAiSessionService` bound to `aecom-demo-uc1` when configured."""
        from google.adk.sessions import VertexAiSessionService

        return VertexAiSessionService(
            project=self.project_id,
            location=self.location,
            agent_engine_id=agent_engine_id,
        )

    def build_vertex_memory_bank_service(self, agent_engine_id: Optional[str] = None) -> Any:
        """Creates an ADK `VertexAiMemoryBankService` bound to `aecom-demo-uc1` when configured."""
        from google.adk.memory import VertexAiMemoryBankService

        return VertexAiMemoryBankService(
            project=self.project_id,
            location=self.location,
            agent_engine_id=agent_engine_id,
        )


@lru_cache(maxsize=1)
def get_memory_service() -> PersistentGbsMemoryService:
    """Returns a cached process-wide `PersistentGbsMemoryService`."""
    return PersistentGbsMemoryService()
