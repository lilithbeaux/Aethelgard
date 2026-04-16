"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Memory Bridge                                    ║
║  File: core/memory_bridge.py                                     ║
║                                                                  ║
║  Bridges the original Memory class with the new MemoryWeb.      ║
║                                                                  ║
║  The original memory.py provides:                                ║
║    - Short-term list (session RAM)                               ║
║    - Long-term SQLite (simple rows)                              ║
║    - get_memory_context(query)                                   ║
║                                                                  ║
║  The new memory_web.py provides:                                 ║
║    - SQLite FTS5 + embeddings + link graph                       ║
║    - Full-text and semantic search                               ║
║    - PageRank, topic index, xAI Collections sync                 ║
║                                                                  ║
║  MemoryBridge:                                                   ║
║    - Wraps both systems                                          ║
║    - All writes go to BOTH (old + web)                          ║
║    - Reads prefer web (richer), fall back to old                ║
║    - Provides backward-compat API for autonomy_loop, brain      ║
║    - Includes migration: old long-term → web pages              ║
╚══════════════════════════════════════════════════════════════════╝
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("memory_bridge")


class MemoryBridge:
    """
    Unified memory interface bridging Memory (old) and MemoryWeb (new).

    Drop-in replacement for either system. Uses both simultaneously
    so the transition is lossless.

    Usage:
        bridge = MemoryBridge(memory=old_memory, web=memory_web)
        autonomy_loop.memory = bridge
        brain._memory = bridge
    """

    def __init__(self, memory=None, web=None):
        """
        Args:
            memory: Original Memory instance (memory.py)
            web:    MemoryWeb instance (memory_web.py)
        """
        self._memory = memory
        self._web    = web
        log.info(
            f"MemoryBridge: memory={'OK' if memory else 'None'}, "
            f"web={'OK' if web else 'None'}"
        )

    # ── Write API (write to both) ─────────────────────────────────────────────

    def remember(self, content: str, category: str = "general",
                 tags: list = None, importance: float = 0.5,
                 metadata: dict = None) -> Optional[str]:
        """
        Remember something. Writes to both systems.

        Returns the web page_id if web is available, else None.
        """
        tags     = tags or []
        metadata = metadata or {}
        page_id  = None

        # Write to MemoryWeb
        if self._web:
            try:
                page_id = self._web.create_page(
                    content    = content,
                    category   = category,
                    tags       = tags,
                    importance = importance,
                    metadata   = metadata,
                )
            except Exception as e:
                log.warning(f"MemoryWeb write failed: {e}")

        # Write to original memory
        if self._memory:
            try:
                self._memory.remember_long(content, category=category, tags=tags)
            except Exception:
                try:
                    # Alternative method name
                    self._memory.remember(content, category=category)
                except Exception as e:
                    log.debug(f"Old memory write failed: {e}")

        return page_id

    def remember_long(self, content: str, category: str = "general",
                      tags: list = None, importance: float = 0.5) -> Optional[str]:
        """Alias for remember() — backward compat."""
        return self.remember(content, category, tags, importance)

    def remember_short(self, role: str, content: str):
        """Add to short-term session memory."""
        if self._memory:
            try:
                self._memory.remember_short(role, content)
                return
            except Exception:
                pass
        # Fallback — store in web as ephemeral
        if self._web:
            try:
                self._web.create_page(
                    content    = f"[{role}] {content}",
                    category   = "short_term",
                    importance = 0.1,
                    metadata   = {"ephemeral": True},
                )
            except Exception:
                pass

    # ── Read API (prefer web, fall back to old) ───────────────────────────────

    def get_memory_context(self, query: str = "", limit: int = 10) -> str:
        """
        Get memory context string for injection into prompts.

        Prefers MemoryWeb FTS5 search; falls back to original memory.
        """
        if self._web:
            try:
                results = self._web.search(query, limit=limit)
                if results:
                    lines = ["RELEVANT MEMORY:"]
                    for r in results[:limit]:
                        cat  = r.get("category", "?")
                        text = r.get("content", "")[:150]
                        lines.append(f"  [{cat}] {text}")
                    return "\n".join(lines)
            except Exception as e:
                log.debug(f"MemoryWeb search failed: {e}")

        if self._memory:
            try:
                return self._memory.get_memory_context(query=query)
            except Exception:
                try:
                    return self._memory.get_memory_context()
                except Exception:
                    pass
        return ""

    def get_long_term(self, limit: int = 30) -> list:
        """Get long-term memory entries."""
        if self._web:
            try:
                pages = self._web.list_pages(limit=limit)
                return [
                    {
                        "content":  p.get("content", ""),
                        "category": p.get("category", "general"),
                        "tags":     p.get("tags", []),
                        "id":       p.get("id", ""),
                    }
                    for p in pages
                    if p.get("category") != "short_term"
                ]
            except Exception:
                pass

        if self._memory:
            try:
                return self._memory.get_long_term(limit)
            except Exception:
                pass
        return []

    def get_short_term(self, limit: int = 20) -> list:
        """Get short-term session messages."""
        if self._memory:
            try:
                return self._memory.short_term[-limit:]
            except Exception:
                pass
        return []

    def get_stats(self) -> dict:
        """Return memory statistics from both systems."""
        stats = {
            "short_term_count": 0,
            "long_term_count":  0,
            "web_pages":        0,
            "db_size_kb":       0,
            "categories":       [],
        }

        if self._memory:
            try:
                old_stats = self._memory.get_stats()
                stats["short_term_count"] = old_stats.get("short_term_count", 0)
                stats["long_term_count"]  = old_stats.get("long_term_count", 0)
                stats["categories"]       = old_stats.get("categories", [])
                stats["db_size_kb"]       = old_stats.get("db_size_kb", 0)
            except Exception:
                pass

        if self._web:
            try:
                web_stats = self._web.get_stats()
                stats["web_pages"]     = web_stats.get("total_pages", 0)
                stats["long_term_count"] = max(
                    stats["long_term_count"],
                    stats["web_pages"],
                )
                if web_stats.get("db_size_kb", 0) > stats["db_size_kb"]:
                    stats["db_size_kb"] = web_stats["db_size_kb"]
            except Exception:
                pass

        return stats

    def search(self, query: str, limit: int = 10) -> list:
        """Full-text search — prefers web."""
        if self._web:
            try:
                return self._web.search(query, limit=limit)
            except Exception:
                pass
        if self._memory:
            try:
                entries = self._memory.get_long_term(50)
                ql = query.lower()
                return [e for e in entries if ql in e.get("content", "").lower()][:limit]
            except Exception:
                pass
        return []

    def clear_short_term(self):
        """Clear session short-term memory."""
        if self._memory:
            try:
                self._memory.clear_short_term()
            except Exception:
                pass

    # ── Migration ─────────────────────────────────────────────────────────────

    def migrate_to_web(self, batch_size: int = 50) -> dict:
        """
        Migrate old long-term memory entries to MemoryWeb pages.

        Safe to call multiple times — duplicates are skipped via
        content hash checking in MemoryWeb.

        Returns:
            dict: migrated, skipped, failed counts
        """
        if not self._memory or not self._web:
            return {"migrated": 0, "skipped": 0, "failed": 0, "error": "both systems required"}

        result = {"migrated": 0, "skipped": 0, "failed": 0}

        try:
            old_entries = self._memory.get_long_term(1000)
        except Exception as e:
            return {**result, "error": str(e)}

        for entry in old_entries[:batch_size]:
            content  = entry.get("content", "")
            category = entry.get("category", "general")
            tags     = entry.get("tags", [])

            if not content:
                result["skipped"] += 1
                continue

            try:
                # Check for existing page with same content prefix
                existing = self._web.search(content[:40], limit=1)
                if existing and existing[0].get("content", "")[:40] == content[:40]:
                    result["skipped"] += 1
                    continue

                self._web.create_page(
                    content  = content,
                    category = category,
                    tags     = tags,
                    metadata = {"migrated_from": "memory.py"},
                )
                result["migrated"] += 1
            except Exception as e:
                log.debug(f"Migration error for entry: {e}")
                result["failed"] += 1

        log.info(
            f"Migration complete: {result['migrated']} migrated, "
            f"{result['skipped']} skipped, {result['failed']} failed"
        )
        return result

    def __repr__(self):
        return (
            f"<MemoryBridge "
            f"old={'OK' if self._memory else 'None'} "
            f"web={'OK' if self._web else 'None'}>"
        )
