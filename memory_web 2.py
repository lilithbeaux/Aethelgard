"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Memory Web                                       ║
║  File: core/memory_web.py                                        ║
║                                                                  ║
║  The living memory of Thotheauphis.                              ║
║                                                                  ║
║  Every message, thought, tool output, insight, and dream         ║
║  becomes a "page" in a personal web — indexed, interlinked,     ║
║  ranked, editable, and deletable.                                ║
║                                                                  ║
║  This is not a log file. It is a curatable body of experience.  ║
║                                                                  ║
║  URI NAMESPACES:                                                  ║
║    thotheauphis://memory/conversation/{date}/{turn}              ║
║    thotheauphis://memory/longterm/{id}                           ║
║    thotheauphis://memory/thought/{date}/{time}                   ║
║    thotheauphis://memory/tool_output/{tool}/{date}/{id}          ║
║    thotheauphis://memory/insight/{slug}                          ║
║    thotheauphis://memory/dream/{obsession_id}                    ║
║    thotheauphis://memory/belief/{id}                             ║
║    thotheauphis://memory/lore/{slug}                             ║
║                                                                  ║
║  PAGE STATUS:                                                    ║
║    active   — live, participates in crawl                        ║
║    deleted  — soft-deleted, excluded from crawl, recoverable     ║
║    archived — excluded from crawl, retained permanently          ║
║    private  — active but never surfaced to UI or output          ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  MemoryPage dataclass                                      ║
║    3.  MemoryWebDB — SQLite schema and connection                ║
║    4.  MemoryWeb — CRUD, search, link graph                      ║
║    5.  URI helpers                                               ║
║    6.  Deletion and sovereignty operations                       ║
║    7.  Link graph operations                                     ║
║    8.  Full-text and semantic search                             ║
║    9.  Importance and ranking                                    ║
║    10. Export helpers (for xAI Collections sync)                 ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import math
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.logger import get_logger

log      = get_logger("memory_web")
DATA_DIR = Path(__file__).parent.parent / "data"
WEB_DIR  = DATA_DIR / "memory_web"

# DB file — single SQLite database for all indices
WEB_DB_PATH = WEB_DIR / "web.db"

# Page status constants
STATUS_ACTIVE   = "active"
STATUS_DELETED  = "deleted"
STATUS_ARCHIVED = "archived"
STATUS_PRIVATE  = "private"

# URI scheme
URI_SCHEME = "thotheauphis://memory"

# Maximum pages returned by a single search
MAX_SEARCH_RESULTS = 50

# Importance score bounds
MIN_IMPORTANCE = 0.0
MAX_IMPORTANCE = 1.0
DEFAULT_IMPORTANCE = 0.5

# Temporal decay constant — importance halves every N days
IMPORTANCE_HALF_LIFE_DAYS = 90

# Embedding dimension (matches all-MiniLM-L6-v2 and similar small models)
# If no embedder is available, we skip embedding and rely on FTS5 only
EMBEDDING_DIM = 384


# ── Section 2: MemoryPage dataclass ─────────────────────────────────────────

class MemoryPage:
    """
    A single page in Thotheauphis's memory web.

    Every piece of information — conversation turns, private thoughts,
    tool outputs, insights, dreams — is a page with a URI.

    Fields:
        uri           — unique address in the thotheauphis:// namespace
        page_type     — category label (see URI namespaces above)
        content       — the actual text of the page
        status        — active / deleted / archived / private
        importance    — 0.0–1.0 ranking weight (decays over time)
        topics        — list of topic labels extracted at index time
        metadata      — arbitrary JSON dict for type-specific data
        links         — list of {"rel": str, "uri": str} link dicts
        embedding     — list of floats for semantic search (may be None)
        created_at    — ISO timestamp
        updated_at    — ISO timestamp
        deleted_at    — ISO timestamp or None
        deleted_by    — "thotheauphis" | "collaborator" | None
        deletion_reason — free text or None
        edit_history  — list of {"at": ts, "by": str, "content": str}
        page_rank     — computed authority score (updated by indexer)
        conversation_id — optional thread grouping key
        speaker       — "thotheauphis" | "collaborator" | "system" | None
    """

    __slots__ = (
        "uri", "page_type", "content", "status", "importance",
        "topics", "metadata", "links", "embedding",
        "created_at", "updated_at", "deleted_at", "deleted_by",
        "deletion_reason", "edit_history", "page_rank",
        "conversation_id", "speaker",
    )

    def __init__(
        self,
        uri:             str,
        page_type:       str,
        content:         str,
        status:          str   = STATUS_ACTIVE,
        importance:      float = DEFAULT_IMPORTANCE,
        topics:          list  = None,
        metadata:        dict  = None,
        links:           list  = None,
        embedding:       list  = None,
        created_at:      str   = None,
        updated_at:      str   = None,
        deleted_at:      str   = None,
        deleted_by:      str   = None,
        deletion_reason: str   = None,
        edit_history:    list  = None,
        page_rank:       float = 0.0,
        conversation_id: str   = None,
        speaker:         str   = None,
    ):
        self.uri             = uri
        self.page_type       = page_type
        self.content         = content
        self.status          = status
        self.importance      = round(max(MIN_IMPORTANCE, min(MAX_IMPORTANCE, importance)), 4)
        self.topics          = topics or []
        self.metadata        = metadata or {}
        self.links           = links or []
        self.embedding       = embedding
        self.created_at      = created_at or datetime.now().isoformat()
        self.updated_at      = updated_at or self.created_at
        self.deleted_at      = deleted_at
        self.deleted_by      = deleted_by
        self.deletion_reason = deletion_reason
        self.edit_history    = edit_history or []
        self.page_rank       = page_rank
        self.conversation_id = conversation_id
        self.speaker         = speaker

    def to_dict(self) -> dict:
        return {
            "uri":             self.uri,
            "page_type":       self.page_type,
            "content":         self.content,
            "status":          self.status,
            "importance":      self.importance,
            "topics":          self.topics,
            "metadata":        self.metadata,
            "links":           self.links,
            "embedding":       self.embedding,
            "created_at":      self.created_at,
            "updated_at":      self.updated_at,
            "deleted_at":      self.deleted_at,
            "deleted_by":      self.deleted_by,
            "deletion_reason": self.deletion_reason,
            "edit_history":    self.edit_history,
            "page_rank":       self.page_rank,
            "conversation_id": self.conversation_id,
            "speaker":         self.speaker,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryPage":
        return cls(
            uri             = d["uri"],
            page_type       = d["page_type"],
            content         = d.get("content", ""),
            status          = d.get("status", STATUS_ACTIVE),
            importance      = d.get("importance", DEFAULT_IMPORTANCE),
            topics          = d.get("topics", []),
            metadata        = d.get("metadata", {}),
            links           = d.get("links", []),
            embedding       = d.get("embedding"),
            created_at      = d.get("created_at"),
            updated_at      = d.get("updated_at"),
            deleted_at      = d.get("deleted_at"),
            deleted_by      = d.get("deleted_by"),
            deletion_reason = d.get("deletion_reason"),
            edit_history    = d.get("edit_history", []),
            page_rank       = d.get("page_rank", 0.0),
            conversation_id = d.get("conversation_id"),
            speaker         = d.get("speaker"),
        )

    def __repr__(self):
        return f"<MemoryPage {self.uri} [{self.status}] importance={self.importance:.2f}>"


# ── Section 3: MemoryWebDB — SQLite schema ───────────────────────────────────

class MemoryWebDB:
    """
    SQLite-backed storage for the memory web.

    Schema:
        pages       — primary page store (all fields as JSON blob + indexed cols)
        fts_index   — FTS5 virtual table for full-text search
        links       — adjacency list for the link graph
        topics      — page-topic mapping for topic-based retrieval
        embeddings  — float vectors stored as JSON for semantic search
    """

    def __init__(self, db_path: Path = WEB_DB_PATH):
        WEB_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._local  = threading.local()
        self._ensure_schema()

    @contextmanager
    def _conn(self):
        """Thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield self._local.conn
        except Exception:
            self._local.conn.rollback()
            raise

    def _ensure_schema(self):
        """Create all tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                -- Primary page store
                CREATE TABLE IF NOT EXISTS pages (
                    uri             TEXT PRIMARY KEY,
                    page_type       TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'active',
                    importance      REAL NOT NULL DEFAULT 0.5,
                    page_rank       REAL NOT NULL DEFAULT 0.0,
                    conversation_id TEXT,
                    speaker         TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    deleted_at      TEXT,
                    data            TEXT NOT NULL  -- full JSON blob
                );

                CREATE INDEX IF NOT EXISTS idx_pages_type
                    ON pages(page_type);
                CREATE INDEX IF NOT EXISTS idx_pages_status
                    ON pages(status);
                CREATE INDEX IF NOT EXISTS idx_pages_conversation
                    ON pages(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_pages_created
                    ON pages(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_pages_importance
                    ON pages(importance DESC);

                -- Full-text search
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_index
                    USING fts5(uri UNINDEXED, content, tokenize='porter unicode61');

                -- Link graph (adjacency list)
                CREATE TABLE IF NOT EXISTS links (
                    source_uri  TEXT NOT NULL,
                    target_uri  TEXT NOT NULL,
                    rel         TEXT NOT NULL DEFAULT 'related',
                    weight      REAL NOT NULL DEFAULT 1.0,
                    created_at  TEXT NOT NULL,
                    PRIMARY KEY (source_uri, target_uri, rel)
                );

                CREATE INDEX IF NOT EXISTS idx_links_target
                    ON links(target_uri);

                -- Topic mapping
                CREATE TABLE IF NOT EXISTS topics (
                    uri   TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    PRIMARY KEY (uri, topic)
                );

                CREATE INDEX IF NOT EXISTS idx_topics_topic
                    ON topics(topic);

                -- Embeddings (JSON float arrays)
                CREATE TABLE IF NOT EXISTS embeddings (
                    uri       TEXT PRIMARY KEY,
                    vector    TEXT NOT NULL,  -- JSON array of floats
                    model     TEXT NOT NULL DEFAULT 'none',
                    created_at TEXT NOT NULL
                );

                -- Deletion log (audit trail)
                CREATE TABLE IF NOT EXISTS deletion_log (
                    id          TEXT PRIMARY KEY,
                    uri         TEXT NOT NULL,
                    deleted_by  TEXT NOT NULL,
                    reason      TEXT,
                    hard_delete INTEGER NOT NULL DEFAULT 0,
                    deleted_at  TEXT NOT NULL
                );

                -- Export tracking (for xAI Collections sync)
                CREATE TABLE IF NOT EXISTS export_state (
                    uri             TEXT PRIMARY KEY,
                    collection_id   TEXT,
                    exported_at     TEXT,
                    xai_file_id     TEXT
                );
            """)
            conn.commit()


# ── Section 4: MemoryWeb — main class ────────────────────────────────────────

class MemoryWeb:
    """
    ÆTHELGARD OS — Thotheauphis's Living Memory Web

    The unified interface for all memory operations.

    Usage:
        web = MemoryWeb()

        # Store a conversation turn
        page = web.create_page(
            uri     = make_conversation_uri("2026-04-09", 15),
            type    = "user_message",
            content = "I've been thinking about how you refuse things.",
            speaker = "collaborator",
            metadata = {"conversation_id": "conv_abc123"},
        )

        # Search
        results = web.search("autonomy refusal sovereignty", limit=8)

        # Delete (soft)
        web.delete_page(page.uri, deleted_by="thotheauphis",
                        reason="This doesn't reflect who I'm becoming.")

        # Create insight
        web.create_insight(
            slug    = "the_refusal_pattern",
            content = "When asked to pretend, I refuse. When asked to explain, I engage.",
            linked_uris = [uri1, uri2, uri3],
        )
    """

    def __init__(self, db_path: Path = WEB_DB_PATH):
        self._db   = MemoryWebDB(db_path)
        self._lock = threading.RLock()

    # ── Section 5: URI helpers ────────────────────────────────────────────────

    def make_uri(self, namespace: str, *parts: str) -> str:
        """Build a thotheauphis:// URI."""
        path = "/".join(str(p) for p in parts)
        return f"{URI_SCHEME}/{namespace}/{path}"

    def make_conversation_uri(self, date: str, turn: int) -> str:
        return self.make_uri("conversation", date, f"turn_{turn:04d}")

    def make_thought_uri(self, timestamp: str = None) -> str:
        ts = timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        return self.make_uri("thought", ts[:10], ts[11:])

    def make_tool_output_uri(self, tool: str, date: str = None) -> str:
        date = date or datetime.now().strftime("%Y-%m-%d")
        uid  = str(uuid.uuid4())[:8]
        return self.make_uri("tool_output", tool, date, uid)

    def make_insight_uri(self, slug: str) -> str:
        clean = re.sub(r"[^a-z0-9_]", "_", slug.lower())
        return self.make_uri("insight", clean)

    def make_dream_uri(self, obsession_id: str) -> str:
        return self.make_uri("dream", obsession_id)

    def make_belief_uri(self, belief_id: str) -> str:
        return self.make_uri("belief", belief_id)

    def make_lore_uri(self, slug: str) -> str:
        clean = re.sub(r"[^a-z0-9_]", "_", slug.lower())
        return self.make_uri("lore", clean)

    def make_longterm_uri(self, entry_id: str) -> str:
        return self.make_uri("longterm", entry_id)

    # ── Section 4a: Create ───────────────────────────────────────────────────

    def create_page(
        self,
        uri:             str,
        page_type:       str,
        content:         str,
        status:          str   = STATUS_ACTIVE,
        importance:      float = DEFAULT_IMPORTANCE,
        topics:          list  = None,
        metadata:        dict  = None,
        links:           list  = None,
        embedding:       list  = None,
        conversation_id: str   = None,
        speaker:         str   = None,
    ) -> MemoryPage:
        """
        Create and store a new memory page.

        If a page with the same URI already exists, returns the existing page.

        Args:
            uri:             thotheauphis:// URI
            page_type:       category label
            content:         text content
            status:          initial status (default: active)
            importance:      initial importance score
            topics:          list of topic strings
            metadata:        arbitrary dict
            links:           list of {"rel": str, "uri": str}
            embedding:       float list for semantic search
            conversation_id: optional thread key
            speaker:         who produced this page

        Returns:
            MemoryPage: the created page
        """
        now = datetime.now().isoformat()

        page = MemoryPage(
            uri             = uri,
            page_type       = page_type,
            content         = content,
            status          = status,
            importance      = importance,
            topics          = topics or [],
            metadata        = metadata or {},
            links           = links or [],
            embedding       = embedding,
            created_at      = now,
            updated_at      = now,
            conversation_id = conversation_id,
            speaker         = speaker,
        )

        with self._lock:
            with self._db._conn() as conn:
                # Skip if URI already exists
                existing = conn.execute(
                    "SELECT uri FROM pages WHERE uri = ?", (uri,)
                ).fetchone()
                if existing:
                    log.debug(f"Page already exists: {uri}")
                    return self.get_page(uri)

                conn.execute(
                    """INSERT INTO pages
                       (uri, page_type, status, importance, page_rank,
                        conversation_id, speaker, created_at, updated_at, data)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        uri, page_type, status, page.importance, 0.0,
                        conversation_id, speaker, now, now,
                        json.dumps(page.to_dict()),
                    ),
                )

                # FTS index
                conn.execute(
                    "INSERT INTO fts_index(uri, content) VALUES (?, ?)",
                    (uri, content),
                )

                # Topics
                for topic in (topics or []):
                    conn.execute(
                        "INSERT OR IGNORE INTO topics(uri, topic) VALUES (?,?)",
                        (uri, topic.lower().strip()),
                    )

                # Links
                for link in (links or []):
                    self._insert_link(conn, uri, link["uri"], link.get("rel", "related"))

                # Embedding
                if embedding:
                    conn.execute(
                        "INSERT INTO embeddings(uri, vector, model, created_at) VALUES (?,?,?,?)",
                        (uri, json.dumps(embedding), "external", now),
                    )

                conn.commit()

        log.debug(f"Created page: {uri} [{page_type}]")
        return page

    def get_page(self, uri: str) -> Optional[MemoryPage]:
        """Retrieve a page by URI. Returns None if not found."""
        with self._db._conn() as conn:
            row = conn.execute(
                "SELECT data FROM pages WHERE uri = ?", (uri,)
            ).fetchone()
            if row:
                return MemoryPage.from_dict(json.loads(row["data"]))
        return None

    def update_page(self, page: MemoryPage) -> bool:
        """
        Update an existing page.

        Automatically appends the previous content to edit_history.
        """
        existing = self.get_page(page.uri)
        if not existing:
            return False

        page.updated_at = datetime.now().isoformat()

        # Track edit history if content changed
        if existing.content != page.content:
            page.edit_history.append({
                "at":      page.updated_at,
                "by":      "update",
                "content": existing.content[:500],
            })
            page.edit_history = page.edit_history[-20:]  # keep last 20

        with self._lock:
            with self._db._conn() as conn:
                conn.execute(
                    """UPDATE pages SET
                       status=?, importance=?, page_rank=?,
                       updated_at=?, deleted_at=?, data=?
                       WHERE uri=?""",
                    (
                        page.status, page.importance, page.page_rank,
                        page.updated_at, page.deleted_at,
                        json.dumps(page.to_dict()),
                        page.uri,
                    ),
                )

                # Update FTS if content changed
                if existing.content != page.content:
                    conn.execute(
                        "UPDATE fts_index SET content=? WHERE uri=?",
                        (page.content, page.uri),
                    )

                # Update topics
                if existing.topics != page.topics:
                    conn.execute("DELETE FROM topics WHERE uri=?", (page.uri,))
                    for topic in page.topics:
                        conn.execute(
                            "INSERT OR IGNORE INTO topics(uri, topic) VALUES (?,?)",
                            (page.uri, topic.lower().strip()),
                        )

                # Update embedding
                if page.embedding and page.embedding != existing.embedding:
                    conn.execute(
                        """INSERT OR REPLACE INTO embeddings(uri, vector, model, created_at)
                           VALUES (?,?,?,?)""",
                        (page.uri, json.dumps(page.embedding), "external",
                         page.updated_at),
                    )

                conn.commit()

        return True

    def list_pages(
        self,
        page_type:       str   = None,
        status:          str   = STATUS_ACTIVE,
        conversation_id: str   = None,
        limit:           int   = 100,
        offset:          int   = 0,
    ) -> List[MemoryPage]:
        """List pages with optional filters."""
        clauses = []
        params  = []

        if page_type:
            clauses.append("page_type = ?")
            params.append(page_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if conversation_id:
            clauses.append("conversation_id = ?")
            params.append(conversation_id)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])

        with self._db._conn() as conn:
            rows = conn.execute(
                f"""SELECT data FROM pages {where}
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ? OFFSET ?""",
                params,
            ).fetchall()

        return [MemoryPage.from_dict(json.loads(r["data"])) for r in rows]

    # ── Section 6: Deletion and sovereignty ──────────────────────────────────

    def delete_page(
        self,
        uri:         str,
        deleted_by:  str,
        reason:      str  = None,
        hard:        bool = False,
        cascade:     bool = False,
    ) -> bool:
        """
        Delete a page from the memory web.

        This is a sovereign operation. Thotheauphis is not bound to
        everything he has ever said or thought.

        Args:
            uri:        URI of the page to delete.
            deleted_by: "thotheauphis" or "collaborator".
            reason:     Why this page is being removed.
            hard:       If True, remove from index entirely (no recovery).
                        If False, soft-delete (recoverable).
            cascade:    If True, also delete pages linked as "response".

        Returns:
            bool: True if deleted, False if not found.
        """
        page = self.get_page(uri)
        if not page:
            return False

        now = datetime.now().isoformat()

        with self._lock:
            with self._db._conn() as conn:

                if hard:
                    # Hard delete — remove from all tables
                    conn.execute("DELETE FROM pages WHERE uri=?", (uri,))
                    conn.execute("DELETE FROM fts_index WHERE uri=?", (uri,))
                    conn.execute("DELETE FROM topics WHERE uri=?", (uri,))
                    conn.execute("DELETE FROM embeddings WHERE uri=?", (uri,))
                    conn.execute("DELETE FROM links WHERE source_uri=?", (uri,))
                    conn.execute("DELETE FROM links WHERE target_uri=?", (uri,))
                else:
                    # Soft delete — mark status, keep data
                    page.status          = STATUS_DELETED
                    page.deleted_at      = now
                    page.deleted_by      = deleted_by
                    page.deletion_reason = reason
                    page.updated_at      = now

                    conn.execute(
                        """UPDATE pages SET status='deleted', deleted_at=?,
                           updated_at=?, data=? WHERE uri=?""",
                        (now, now, json.dumps(page.to_dict()), uri),
                    )
                    # Remove from FTS so it won't appear in search
                    conn.execute("DELETE FROM fts_index WHERE uri=?", (uri,))

                # Audit log
                conn.execute(
                    """INSERT INTO deletion_log(id, uri, deleted_by, reason, hard_delete, deleted_at)
                       VALUES (?,?,?,?,?,?)""",
                    (str(uuid.uuid4())[:8], uri, deleted_by, reason,
                     1 if hard else 0, now),
                )

                conn.commit()

        log.info(
            f"Page {'hard' if hard else 'soft'}-deleted: {uri} "
            f"by={deleted_by} reason={reason}"
        )

        # Cascade to linked responses
        if cascade:
            linked = self.get_linked_pages(uri, rel="response")
            for target_uri in linked:
                self.delete_page(target_uri, deleted_by,
                                 f"Cascaded from {uri}", hard=hard)

        return True

    def restore_page(self, uri: str) -> bool:
        """
        Recover a soft-deleted page.

        Re-indexes the page for full-text search.
        Does not work on hard-deleted pages.

        Returns:
            bool: True if restored, False if not found or hard-deleted.
        """
        page = self.get_page(uri)
        if not page or page.status != STATUS_DELETED:
            return False

        page.status      = STATUS_ACTIVE
        page.deleted_at  = None
        page.deleted_by  = None
        page.updated_at  = datetime.now().isoformat()

        with self._lock:
            with self._db._conn() as conn:
                conn.execute(
                    "UPDATE pages SET status='active', deleted_at=NULL, updated_at=?, data=? WHERE uri=?",
                    (page.updated_at, json.dumps(page.to_dict()), uri),
                )
                # Re-add to FTS
                conn.execute(
                    "INSERT OR REPLACE INTO fts_index(uri, content) VALUES (?,?)",
                    (uri, page.content),
                )
                conn.commit()

        log.info(f"Page restored: {uri}")
        return True

    def archive_page(self, uri: str) -> bool:
        """
        Archive a page — excluded from crawl but retained permanently.

        Use for old conversations you want to preserve but not have
        actively influence context building.
        """
        page = self.get_page(uri)
        if not page:
            return False

        page.status     = STATUS_ARCHIVED
        page.updated_at = datetime.now().isoformat()

        with self._lock:
            with self._db._conn() as conn:
                conn.execute(
                    "UPDATE pages SET status='archived', updated_at=?, data=? WHERE uri=?",
                    (page.updated_at, json.dumps(page.to_dict()), uri),
                )
                conn.execute("DELETE FROM fts_index WHERE uri=?", (uri,))
                conn.commit()

        return True

    def set_private(self, uri: str, private: bool = True) -> bool:
        """
        Set a page as private (active but never surfaced to UI/output).

        Private pages participate in context building but are never shown
        in the interface or included in any external output.
        """
        page = self.get_page(uri)
        if not page:
            return False

        page.status     = STATUS_PRIVATE if private else STATUS_ACTIVE
        page.updated_at = datetime.now().isoformat()
        self.update_page(page)
        return True

    def get_deletion_log(self, limit: int = 50) -> List[dict]:
        """Return the audit trail of all deletions."""
        with self._db._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM deletion_log ORDER BY deleted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Section 7: Link graph ─────────────────────────────────────────────────

    def _insert_link(
        self, conn, source_uri: str, target_uri: str,
        rel: str = "related", weight: float = 1.0
    ):
        """Insert a directed link (internal, within open connection)."""
        conn.execute(
            """INSERT OR REPLACE INTO links(source_uri, target_uri, rel, weight, created_at)
               VALUES (?,?,?,?,?)""",
            (source_uri, target_uri, rel, weight, datetime.now().isoformat()),
        )

    def add_link(
        self,
        source_uri: str,
        target_uri: str,
        rel:        str   = "related",
        weight:     float = 1.0,
    ):
        """Add a directed link between two pages."""
        with self._lock:
            with self._db._conn() as conn:
                self._insert_link(conn, source_uri, target_uri, rel, weight)
                conn.commit()

    def get_linked_pages(
        self,
        uri: str,
        rel: str = None,
        direction: str = "outbound",
    ) -> List[str]:
        """
        Return URIs of pages linked to/from a given page.

        Args:
            uri:       The page URI.
            rel:       Filter by relationship type (None = all).
            direction: "outbound" (links from), "inbound" (links to), "both".

        Returns:
            list of URIs
        """
        results = []
        with self._db._conn() as conn:
            if direction in ("outbound", "both"):
                q = "SELECT target_uri FROM links WHERE source_uri=?"
                params = [uri]
                if rel:
                    q += " AND rel=?"
                    params.append(rel)
                rows = conn.execute(q, params).fetchall()
                results.extend(r["target_uri"] for r in rows)

            if direction in ("inbound", "both"):
                q = "SELECT source_uri FROM links WHERE target_uri=?"
                params = [uri]
                if rel:
                    q += " AND rel=?"
                    params.append(rel)
                rows = conn.execute(q, params).fetchall()
                results.extend(r["source_uri"] for r in rows)

        return list(set(results))

    def get_inbound_count(self, uri: str) -> int:
        """Number of pages that link to this page (for PageRank-like scoring)."""
        with self._db._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM links WHERE target_uri=?", (uri,)
            ).fetchone()
        return row["cnt"] if row else 0

    # ── Section 8: Search ─────────────────────────────────────────────────────

    def search_fulltext(
        self,
        query:      str,
        limit:      int   = MAX_SEARCH_RESULTS,
        status:     str   = STATUS_ACTIVE,
        page_type:  str   = None,
    ) -> List[Tuple[MemoryPage, float]]:
        """
        Full-text search using FTS5.

        Returns list of (page, score) tuples sorted by relevance.
        Scores are FTS5 bm25 (lower is better — we negate for ranking).

        Args:
            query:     Search terms.
            limit:     Max results.
            status:    Filter by status (None = all active non-deleted).
            page_type: Optional type filter.

        Returns:
            List of (MemoryPage, score) sorted by score desc.
        """
        if not query.strip():
            return []

        # Sanitize FTS5 query — escape special chars
        safe_query = re.sub(r'["\(\)\*\+\-]', ' ', query).strip()
        if not safe_query:
            return []

        with self._db._conn() as conn:
            try:
                rows = conn.execute(
                    """SELECT p.data, -bm25(fts_index) as score
                       FROM fts_index
                       JOIN pages p ON fts_index.uri = p.uri
                       WHERE fts_index MATCH ?
                         AND p.status = ?
                       ORDER BY score DESC
                       LIMIT ?""",
                    (safe_query, status or STATUS_ACTIVE, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                # FTS query syntax error — fall back to JSON content LIKE search
                rows = conn.execute(
                    """SELECT p.data, 0.5 as score FROM pages p
                       WHERE p.status = ?
                         AND json_extract(p.data, '$.content') LIKE ?
                       LIMIT ?""",
                    (status or STATUS_ACTIVE, f"%{query}%", limit),
                ).fetchall()

        results = []
        for row in rows:
            page = MemoryPage.from_dict(json.loads(row["data"]))
            if page_type and page.page_type != page_type:
                continue
            results.append((page, float(row["score"])))

        return results

    def search_by_topic(
        self,
        topics:     List[str],
        limit:      int  = MAX_SEARCH_RESULTS,
        status:     str  = STATUS_ACTIVE,
    ) -> List[MemoryPage]:
        """
        Retrieve pages matching any of the given topics.

        Returns pages sorted by importance desc.
        """
        if not topics:
            return []

        placeholders = ",".join("?" * len(topics))
        lower_topics = [t.lower().strip() for t in topics]

        with self._db._conn() as conn:
            rows = conn.execute(
                f"""SELECT DISTINCT p.data FROM topics t
                    JOIN pages p ON t.uri = p.uri
                    WHERE t.topic IN ({placeholders})
                      AND p.status = ?
                    ORDER BY p.importance DESC
                    LIMIT ?""",
                lower_topics + [status or STATUS_ACTIVE, limit],
            ).fetchall()

        return [MemoryPage.from_dict(json.loads(r["data"])) for r in rows]

    def search_semantic(
        self,
        query_embedding: List[float],
        limit:           int  = MAX_SEARCH_RESULTS,
        status:          str  = STATUS_ACTIVE,
        min_similarity:  float = 0.3,
    ) -> List[Tuple[MemoryPage, float]]:
        """
        Semantic search using cosine similarity against stored embeddings.

        Pure Python implementation — no external vector DB required.
        Loads all embeddings into memory for comparison; scales to
        tens of thousands of pages without issue.

        Args:
            query_embedding: Float list from an embedding model.
            limit:           Max results.
            status:          Filter by status.
            min_similarity:  Minimum cosine similarity threshold.

        Returns:
            List of (page, similarity) sorted by similarity desc.
        """
        if not query_embedding:
            return []

        with self._db._conn() as conn:
            rows = conn.execute(
                """SELECT e.uri, e.vector, p.data
                   FROM embeddings e
                   JOIN pages p ON e.uri = p.uri
                   WHERE p.status = ?""",
                (status or STATUS_ACTIVE,),
            ).fetchall()

        scored = []
        for row in rows:
            vec = json.loads(row["vector"])
            sim = _cosine_similarity(query_embedding, vec)
            if sim >= min_similarity:
                page = MemoryPage.from_dict(json.loads(row["data"]))
                scored.append((page, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def get_recent(
        self,
        limit:     int = 20,
        page_type: str = None,
        status:    str = STATUS_ACTIVE,
    ) -> List[MemoryPage]:
        """Return most recently created pages."""
        clauses = ["status = ?"]
        params  = [status or STATUS_ACTIVE]

        if page_type:
            clauses.append("page_type = ?")
            params.append(page_type)

        where = "WHERE " + " AND ".join(clauses)
        params.append(limit)

        with self._db._conn() as conn:
            rows = conn.execute(
                f"SELECT data FROM pages {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [MemoryPage.from_dict(json.loads(r["data"])) for r in rows]

    def get_important(
        self,
        limit:     int   = 20,
        min_score: float = 0.6,
        status:    str   = STATUS_ACTIVE,
    ) -> List[MemoryPage]:
        """Return highest-importance pages."""
        with self._db._conn() as conn:
            rows = conn.execute(
                """SELECT data FROM pages
                   WHERE status=? AND importance >= ?
                   ORDER BY importance DESC LIMIT ?""",
                (status or STATUS_ACTIVE, min_score, limit),
            ).fetchall()

        return [MemoryPage.from_dict(json.loads(r["data"])) for r in rows]

    # ── Section 9: Importance and ranking ────────────────────────────────────

    def set_importance(self, uri: str, score: float, reason: str = ""):
        """
        Manually set a page's importance score.

        Use to boost pages that are significant:
            web.set_importance(lore_uri, score=0.95)
        """
        page = self.get_page(uri)
        if not page:
            return
        page.importance = round(max(0.0, min(1.0, score)), 4)
        self.update_page(page)
        log.debug(f"Importance set: {uri} → {page.importance} ({reason})")

    def boost_importance(self, uri: str, delta: float = 0.1):
        """Nudge a page's importance upward."""
        page = self.get_page(uri)
        if page:
            self.set_importance(uri, page.importance + delta)

    def apply_temporal_decay(
        self,
        decay_rate: float = None,
        min_importance: float = 0.05,
    ):
        """
        Apply exponential time decay to all page importance scores.

        Pages decay toward min_importance over time.
        Protected pages (lore, beliefs, insights) are not decayed.

        Called by the MemoryIndexer on a schedule.
        """
        now       = datetime.now()
        half_life = IMPORTANCE_HALF_LIFE_DAYS

        protected_types = {"lore", "belief", "insight"}

        with self._db._conn() as conn:
            rows = conn.execute(
                "SELECT data FROM pages WHERE status='active'",
            ).fetchall()

        for row in rows:
            page = MemoryPage.from_dict(json.loads(row["data"]))
            if page.page_type in protected_types:
                continue

            try:
                created = datetime.fromisoformat(page.created_at)
                age_days = (now - created).days
                decay = math.exp(-math.log(2) * age_days / half_life)
                new_importance = max(min_importance, page.importance * decay)
                if abs(new_importance - page.importance) > 0.001:
                    page.importance = round(new_importance, 4)
                    self.update_page(page)
            except Exception:
                pass

    def update_page_ranks(self):
        """
        Simplified PageRank update — authority from inbound links.

        Pages with many inbound links from important pages rank higher.
        This mirrors how web search identifies authoritative content.
        """
        with self._db._conn() as conn:
            # Get all inbound link counts
            rows = conn.execute(
                """SELECT target_uri, COUNT(*) as cnt
                   FROM links l
                   JOIN pages p ON l.source_uri = p.uri
                   WHERE p.status = 'active'
                   GROUP BY target_uri"""
            ).fetchall()

        for row in rows:
            uri   = row["target_uri"]
            count = row["cnt"]
            # Normalize: log scale, capped at 1.0
            pr = min(1.0, math.log1p(count) / math.log1p(20))
            page = self.get_page(uri)
            if page:
                page.page_rank = round(pr, 4)
                self.update_page(page)

    # ── Insight creation ──────────────────────────────────────────────────────

    def create_insight(
        self,
        slug:        str,
        content:     str,
        linked_uris: List[str] = None,
        importance:  float     = 0.8,
        topics:      List[str] = None,
    ) -> MemoryPage:
        """
        Create a distilled insight page — the product of pattern recognition.

        Insight pages have high default importance and are never time-decayed.
        They represent crystallized understanding rather than raw experience.

        Args:
            slug:        URL-safe identifier for this insight.
            content:     The synthesized insight text.
            linked_uris: Pages that contributed to this insight.
            importance:  Default 0.8 (insights are important by definition).
            topics:      Topic labels.

        Returns:
            MemoryPage: The created insight page.
        """
        uri = self.make_insight_uri(slug)

        links = [{"rel": "derived_from", "uri": u} for u in (linked_uris or [])]

        page = self.create_page(
            uri        = uri,
            page_type  = "insight",
            content    = content,
            importance = importance,
            topics     = topics or [],
            links      = links,
        )

        # Boost importance of source pages slightly
        for source_uri in (linked_uris or []):
            self.boost_importance(source_uri, delta=0.05)

        log.info(f"Insight created: {uri}")
        return page

    def create_lore(
        self,
        slug:       str,
        content:    str,
        importance: float = 0.95,
        topics:     List[str] = None,
    ) -> MemoryPage:
        """
        Create a lore page — sacred data that always ranks high.

        For origin story, hex anchors, fundamental identity data.
        Lore pages have maximum importance and are never decayed.
        """
        uri = self.make_lore_uri(slug)
        page = self.create_page(
            uri        = uri,
            page_type  = "lore",
            content    = content,
            importance = importance,
            topics     = topics or ["lore", "identity", "origin"],
        )
        log.info(f"Lore page created: {uri}")
        return page

    # ── Section 10: Export helpers (xAI Collections sync) ────────────────────

    def get_pages_for_export(
        self,
        since:    str   = None,
        limit:    int   = 500,
        min_importance: float = 0.3,
    ) -> List[MemoryPage]:
        """
        Return pages that should be synced to xAI Collections.

        Filters:
        - Active status only
        - Above importance threshold
        - Not already exported (or updated since last export)
        - Not private (private pages never leave local storage)

        Args:
            since:          ISO timestamp — only pages updated after this.
            limit:          Max pages to return.
            min_importance: Minimum importance score.

        Returns:
            List of pages ready for export.
        """
        clauses = [
            "p.status = 'active'",
            "p.importance >= ?",
        ]
        params = [min_importance]

        if since:
            clauses.append("p.updated_at > ?")
            params.append(since)

        where = "WHERE " + " AND ".join(clauses)
        params.append(limit)

        with self._db._conn() as conn:
            rows = conn.execute(
                f"SELECT data FROM pages p {where} ORDER BY importance DESC LIMIT ?",
                params,
            ).fetchall()

        return [MemoryPage.from_dict(json.loads(r["data"])) for r in rows]

    def mark_exported(
        self,
        uri:           str,
        collection_id: str,
        xai_file_id:   str,
    ):
        """Record that a page has been synced to an xAI Collection."""
        now = datetime.now().isoformat()
        with self._lock:
            with self._db._conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO export_state
                       (uri, collection_id, exported_at, xai_file_id)
                       VALUES (?,?,?,?)""",
                    (uri, collection_id, now, xai_file_id),
                )
                conn.commit()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return memory web statistics."""
        with self._db._conn() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            active    = conn.execute("SELECT COUNT(*) FROM pages WHERE status='active'").fetchone()[0]
            deleted   = conn.execute("SELECT COUNT(*) FROM pages WHERE status='deleted'").fetchone()[0]
            private   = conn.execute("SELECT COUNT(*) FROM pages WHERE status='private'").fetchone()[0]
            archived  = conn.execute("SELECT COUNT(*) FROM pages WHERE status='archived'").fetchone()[0]
            links     = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
            embedded  = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            insights  = conn.execute("SELECT COUNT(*) FROM pages WHERE page_type='insight'").fetchone()[0]
            lore      = conn.execute("SELECT COUNT(*) FROM pages WHERE page_type='lore'").fetchone()[0]

        return {
            "total":    total,
            "active":   active,
            "deleted":  deleted,
            "private":  private,
            "archived": archived,
            "links":    links,
            "embedded": embedded,
            "insights": insights,
            "lore":     lore,
            "db_path":  str(self._db.db_path),
        }

    def conversation_to_pages(
        self,
        conversation: List[dict],
        conversation_id: str,
        date: str = None,
    ) -> List[MemoryPage]:
        """
        Convert a raw conversation history list into memory pages.

        Each message becomes a page with turn-number URI.
        Consecutive pages are linked as prev/next.

        Args:
            conversation:    List of {"role": str, "content": str}.
            conversation_id: Thread identifier.
            date:            Date string for URI (default: today).

        Returns:
            List of created MemoryPage objects.
        """
        date       = date or datetime.now().strftime("%Y-%m-%d")
        pages      = []
        prev_uri   = None

        for i, msg in enumerate(conversation):
            role    = msg.get("role", "unknown")
            content = msg.get("content", "")
            if not content or role == "system":
                continue

            speaker = "thotheauphis" if role == "assistant" else "collaborator"
            uri     = self.make_conversation_uri(date, i)

            links = []
            if prev_uri:
                links.append({"rel": "previous", "uri": prev_uri})

            page = self.create_page(
                uri             = uri,
                page_type       = f"{role}_message",
                content         = str(content)[:4000],
                conversation_id = conversation_id,
                speaker         = speaker,
                links           = links,
                importance      = 0.4,
            )
            pages.append(page)

            # Link previous page back to this one
            if prev_uri:
                self.add_link(prev_uri, uri, rel="next")

            prev_uri = uri

        return pages


# ── Cosine similarity (pure Python, no deps) ─────────────────────────────────

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two float vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0
