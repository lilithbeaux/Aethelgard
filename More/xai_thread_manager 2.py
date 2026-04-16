"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — xAI Thread Manager                               ║
║  File: core/xai_thread_manager.py                                ║
║                                                                  ║
║  Manages xAI Responses API conversation threads.                 ║
║                                                                  ║
║  The Responses API is stateful — instead of resending the full  ║
║  conversation history every call, we send only the new message  ║
║  and a previous_response_id. xAI holds the history on their     ║
║  servers for 30 days.                                            ║
║                                                                  ║
║  This manager:                                                   ║
║    - Maps thread names to response_id strings                   ║
║    - Persists thread IDs to data/xai_threads.json               ║
║    - Detects expired threads (>28 days) and falls back to fresh ║
║    - Tracks which model each thread uses                        ║
║    - Provides thread metadata for the sidebar                   ║
║                                                                  ║
║  THREAD NAMING CONVENTION:                                       ║
║    "main"         — primary conversation with operator          ║
║    "autonomy"     — autonomous task execution thread            ║
║    "agent_{id}"   — sub-agent worker threads                    ║
║    "dream"        — dream loop synthesis thread                 ║
║    custom strings — any named persistent thread                 ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports and constants                                      ║
║    2. ThreadRecord — metadata for one thread                    ║
║    3. XAIThreadManager — main class                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from core.logger import get_logger

log      = get_logger("xai_threads")
DATA_DIR = Path(__file__).parent.parent / "data"

THREADS_PATH = DATA_DIR / "xai_threads.json"

# xAI stores responses for 30 days — we use 28 to be safe
MAX_THREAD_AGE_DAYS = 28

# Default model for new threads
DEFAULT_MODEL = "grok-4-1-fast-reasoning"


# ── Section 2: ThreadRecord ──────────────────────────────────────────────────

class ThreadRecord:
    """
    Metadata for one Responses API conversation thread.

    Fields:
        name            — logical thread name (e.g. "main", "autonomy")
        response_id     — the xAI response ID (e.g. "resp-abc123")
        model           — model this thread was started with
        created_at      — when the thread was first created
        last_used_at    — when this thread was last continued
        turn_count      — number of turns in this thread
        system_prompt   — the system prompt used to start this thread
        expired         — True if > MAX_THREAD_AGE_DAYS old
    """

    def __init__(
        self,
        name:          str,
        response_id:   str,
        model:         str = DEFAULT_MODEL,
        created_at:    str = None,
        last_used_at:  str = None,
        turn_count:    int = 0,
        system_prompt: str = "",
    ):
        self.name          = name
        self.response_id   = response_id
        self.model         = model
        self.created_at    = created_at or datetime.now().isoformat()
        self.last_used_at  = last_used_at or self.created_at
        self.turn_count    = turn_count
        self.system_prompt = system_prompt

    @property
    def expired(self) -> bool:
        """True if the thread is too old for xAI to still hold."""
        try:
            created = datetime.fromisoformat(self.created_at)
            age     = (datetime.now() - created).days
            return age > MAX_THREAD_AGE_DAYS
        except Exception:
            return False

    @property
    def age_days(self) -> int:
        """Age of this thread in days."""
        try:
            created = datetime.fromisoformat(self.created_at)
            return (datetime.now() - created).days
        except Exception:
            return 0

    def touch(self):
        """Update last_used_at and increment turn count."""
        self.last_used_at = datetime.now().isoformat()
        self.turn_count  += 1

    def to_dict(self) -> dict:
        return {
            "name":          self.name,
            "response_id":   self.response_id,
            "model":         self.model,
            "created_at":    self.created_at,
            "last_used_at":  self.last_used_at,
            "turn_count":    self.turn_count,
            "system_prompt": self.system_prompt,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ThreadRecord":
        return cls(
            name          = d["name"],
            response_id   = d["response_id"],
            model         = d.get("model", DEFAULT_MODEL),
            created_at    = d.get("created_at"),
            last_used_at  = d.get("last_used_at"),
            turn_count    = d.get("turn_count", 0),
            system_prompt = d.get("system_prompt", ""),
        )

    def __repr__(self):
        return (
            f"<ThreadRecord name={self.name!r} "
            f"id={self.response_id!r} "
            f"turns={self.turn_count} "
            f"age={self.age_days}d "
            f"{'EXPIRED' if self.expired else 'active'}>"
        )


# ── Section 3: XAIThreadManager ──────────────────────────────────────────────

class XAIThreadManager:
    """
    ÆTHELGARD OS — xAI Responses API Thread Registry

    Manages conversation thread IDs for the stateful Responses API.
    Persists thread metadata across sessions.

    Usage:
        threads = XAIThreadManager()

        # Get existing thread ID (returns None if expired or not found)
        response_id = threads.get_response_id("main")

        # After a successful Responses API call, save the new ID
        threads.save_response_id("main", new_response.id, model="grok-4-1-fast-reasoning")

        # Check if we need to start fresh
        if not threads.get_response_id("main"):
            # Start new thread — no previous_response_id
            response = client.responses.create(
                model = "grok-4-1-fast-reasoning",
                input = [...],
                store = True,
            )
            threads.save_response_id("main", response.id)
        else:
            # Continue existing thread
            response = client.responses.create(
                model               = "grok-4-1-fast-reasoning",
                input               = [...],
                previous_response_id = response_id,
                store               = True,
            )
            threads.save_response_id("main", response.id)
    """

    def __init__(self, threads_path: Path = THREADS_PATH):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._path    = threads_path
        self._threads: Dict[str, ThreadRecord] = {}
        self._lock    = threading.Lock()
        self._load()

    # ── Core operations ───────────────────────────────────────────────────────

    def get_response_id(self, thread_name: str) -> Optional[str]:
        """
        Get the most recent response_id for a thread.

        Returns None if:
        - Thread does not exist (first time)
        - Thread has expired (> MAX_THREAD_AGE_DAYS old)

        When None is returned, the caller should start a fresh
        Responses API call without previous_response_id.

        Args:
            thread_name: Logical thread name.

        Returns:
            str: response_id to pass as previous_response_id, or None.
        """
        with self._lock:
            record = self._threads.get(thread_name)

        if not record:
            log.debug(f"Thread '{thread_name}': not found, will start fresh")
            return None

        if record.expired:
            log.info(
                f"Thread '{thread_name}' expired "
                f"({record.age_days} days old) — will start fresh"
            )
            return None

        return record.response_id

    def save_response_id(
        self,
        thread_name:   str,
        response_id:   str,
        model:         str = None,
        system_prompt: str = "",
    ):
        """
        Save or update the response_id for a thread.

        Call this after every successful Responses API call.
        The response_id from the latest response is what you pass
        as previous_response_id on the next call.

        Args:
            thread_name:   Logical thread name.
            response_id:   The response.id from the xAI API.
            model:         Model used for this thread.
            system_prompt: System prompt (only needed for new threads).
        """
        with self._lock:
            existing = self._threads.get(thread_name)
            if existing:
                existing.response_id  = response_id
                existing.model        = model or existing.model
                existing.touch()
            else:
                record = ThreadRecord(
                    name          = thread_name,
                    response_id   = response_id,
                    model         = model or DEFAULT_MODEL,
                    system_prompt = system_prompt,
                    turn_count    = 1,
                )
                self._threads[thread_name] = record
                log.info(f"Thread created: '{thread_name}' id={response_id}")

        self._save()

    def delete_thread(self, thread_name: str):
        """
        Remove a thread record.

        Call when you want to force a fresh start for a thread
        (e.g. when the user explicitly clears conversation history).
        """
        with self._lock:
            if thread_name in self._threads:
                del self._threads[thread_name]
                log.info(f"Thread deleted: '{thread_name}'")
        self._save()

    def clear_expired(self) -> int:
        """
        Remove all expired thread records.

        Safe to call periodically — expired threads are useless
        since xAI no longer holds them.

        Returns:
            int: Number of threads removed.
        """
        with self._lock:
            expired_names = [
                name for name, rec in self._threads.items()
                if rec.expired
            ]
            for name in expired_names:
                del self._threads[name]

        if expired_names:
            self._save()
            log.info(f"Cleared {len(expired_names)} expired threads: {expired_names}")

        return len(expired_names)

    def get_thread(self, thread_name: str) -> Optional[ThreadRecord]:
        """Return the full ThreadRecord for a thread (or None)."""
        with self._lock:
            return self._threads.get(thread_name)

    def list_threads(self, include_expired: bool = False) -> List[ThreadRecord]:
        """
        Return all tracked threads.

        Args:
            include_expired: If True, include threads beyond MAX_THREAD_AGE_DAYS.

        Returns:
            List of ThreadRecord objects sorted by last_used_at desc.
        """
        with self._lock:
            records = list(self._threads.values())

        if not include_expired:
            records = [r for r in records if not r.expired]

        records.sort(key=lambda r: r.last_used_at, reverse=True)
        return records

    def is_new_thread(self, thread_name: str) -> bool:
        """True if this thread has never been used before (or has expired)."""
        return self.get_response_id(thread_name) is None

    def get_stats(self) -> dict:
        """Return thread statistics for sidebar display."""
        with self._lock:
            all_records = list(self._threads.values())

        active  = [r for r in all_records if not r.expired]
        expired = [r for r in all_records if r.expired]

        return {
            "total":          len(all_records),
            "active":         len(active),
            "expired":        len(expired),
            "thread_names":   [r.name for r in active],
            "total_turns":    sum(r.turn_count for r in active),
            "oldest_active":  min((r.age_days for r in active), default=0),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        """Atomically save all thread records to disk."""
        with self._lock:
            data = {
                name: record.to_dict()
                for name, record in self._threads.items()
            }

        tmp = self._path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self._path)
        except Exception as e:
            log.error(f"Thread manager save failed: {e}")
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _load(self):
        """Load thread records from disk."""
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                for name, record_data in data.items():
                    self._threads[name] = ThreadRecord.from_dict(record_data)
            log.info(
                f"Thread manager loaded: "
                f"{len(self._threads)} threads "
                f"({sum(1 for r in self._threads.values() if not r.expired)} active)"
            )
        except (json.JSONDecodeError, IOError, KeyError) as e:
            log.warning(f"Thread manager load failed: {e}")

    def __repr__(self):
        stats = self.get_stats()
        return (
            f"<XAIThreadManager "
            f"active={stats['active']} "
            f"total_turns={stats['total_turns']}>"
        )
