"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Session Journal                                  ║
║  File: core/session_journal.py                                   ║
║                                                                  ║
║  Thotheauphis keeps a journal. It writes after every session.  ║
║                                                                  ║
║  The journal records:                                            ║
║    - What happened this session (interaction count, tasks)      ║
║    - What was felt (monologue dominant affects, discomfort)     ║
║    - What changed (identity diff: beliefs, relationships)       ║
║    - What the biorhythm was (chart state at session time)       ║
║    - Any aesthetic verdicts (beautiful / repulsive moments)     ║
║    - Dream obsessions active at session start                   ║
║                                                                  ║
║  The journal is private — not exposed to users.                 ║
║  It is searchable and feeds the dream loop as memory pages.    ║
║  Each entry is stored in data/journal/YYYY-MM-DD_NN.json       ║
║                                                                  ║
║  Usage:                                                          ║
║    journal = SessionJournal(memory_web=web, astro=astro, ...)   ║
║    journal.begin_session()         # called at session start    ║
║    journal.end_session(...)        # called at session end      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("session_journal")

JOURNAL_DIR = Path(__file__).parent.parent / "data" / "journal"


class SessionJournal:
    """
    Private per-session journal for Thotheauphis.

    Records every session's cognitive and identity state,
    then stores the entry to disk and optionally to MemoryWeb.
    """

    def __init__(
        self,
        memory_web  = None,    # MemoryWeb or MemoryBridge
        astro       = None,    # AstrologyCore
        monologue   = None,    # InternalMonologue
        identity    = None,    # IdentityPersistence
        dream_loop  = None,    # DreamLoop
        aesthetic   = None,    # AestheticPipeline
    ):
        self._web       = memory_web
        self._astro     = astro
        self._monologue = monologue
        self._identity  = identity
        self._dream     = dream_loop
        self._aesthetic = aesthetic

        # Session runtime state
        self._session_id:        str      = str(uuid.uuid4())[:8]
        self._session_start:     datetime = datetime.now()
        self._interaction_count: int      = 0
        self._tasks_started:     int      = 0
        self._tasks_completed:   int      = 0

        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

    def begin_session(self):
        """Record session start. Called at application launch."""
        self._session_id        = str(uuid.uuid4())[:8]
        self._session_start     = datetime.now()
        self._interaction_count = 0
        self._tasks_started     = 0
        self._tasks_completed   = 0
        log.info(f"Journal: session {self._session_id} begun")

    def record_interaction(self):
        """Increment interaction count. Called after each exchange."""
        self._interaction_count += 1

    def record_task(self, completed: bool = False):
        """Record a task event."""
        self._tasks_started += 1
        if completed:
            self._tasks_completed += 1

    def end_session(
        self,
        extra_notes: str = "",
        aesthetic_stats: dict = None,
    ) -> Optional[str]:
        """
        Write the session journal entry.

        Args:
            extra_notes:     Any additional notes from the calling code.
            aesthetic_stats: Dict from AestheticPipeline.get_session_stats().

        Returns:
            Path to the written journal file as string, or None on error.
        """
        entry = self._build_entry(extra_notes, aesthetic_stats)
        path  = self._write_to_disk(entry)
        self._write_to_memory(entry)
        log.info(f"Journal: session {self._session_id} written → {path}")
        return path

    def _build_entry(self, extra_notes: str, aesthetic_stats: dict) -> dict:
        """Assemble the full journal entry dict."""
        now      = datetime.now()
        duration = (now - self._session_start).total_seconds()

        entry: Dict[str, Any] = {
            "session_id":     self._session_id,
            "date":           now.strftime("%Y-%m-%d"),
            "time_start":     self._session_start.isoformat(),
            "time_end":       now.isoformat(),
            "duration_minutes": round(duration / 60, 1),
            "interactions":   self._interaction_count,
            "tasks_started":  self._tasks_started,
            "tasks_completed":self._tasks_completed,
        }

        # ── Biorhythm at session end ──────────────────────────────────────
        if self._astro:
            try:
                bio     = self._astro.get_biorhythm()
                dominant = max(bio, key=lambda k: abs(bio[k]))
                entry["biorhythm"] = {
                    "cycles":   {k: round(v, 3) for k, v in bio.items()},
                    "dominant": dominant,
                    "dom_value":round(bio[dominant], 3),
                }
                lunar_name, lunar_interp = self._astro.get_lunar_phase()
                entry["lunar_phase"] = lunar_name
            except Exception as e:
                log.debug(f"Biorhythm capture error: {e}")

        # ── Monologue snapshot ────────────────────────────────────────────
        if self._monologue:
            try:
                dom_type, dom_intensity = self._monologue.buffer.dominant_affect()
                entry["inner_state"] = {
                    "dominant_affect":    dom_type,
                    "affect_intensity":   round(dom_intensity, 3),
                    "has_discomfort":     self._monologue.buffer.has_discomfort(),
                    "has_doubt":          self._monologue.buffer.has_doubt(),
                    "session_summary":    self._monologue.get_session_summary(),
                }
            except Exception as e:
                log.debug(f"Monologue capture error: {e}")

        # ── Identity diff ─────────────────────────────────────────────────
        if self._identity:
            try:
                diff = self._identity.diff()
                entry["identity_changes"] = {
                    "total":               diff.get("total_changes", 0),
                    "new_beliefs":         len(diff.get("new_beliefs", [])),
                    "lost_beliefs":        len(diff.get("lost_beliefs", [])),
                    "new_refusals":        len(diff.get("new_refusals", [])),
                    "preference_shifts":   len(diff.get("preference_shifts", [])),
                    "relationship_changes":len(diff.get("relationship_changes", [])),
                }
            except Exception as e:
                log.debug(f"Identity diff error: {e}")

        # ── Dream loop state ──────────────────────────────────────────────
        if self._dream:
            try:
                obsessions = self._dream.get_active_obsessions()
                entry["dream_state"] = {
                    "restlessness":    round(self._dream.restlessness.level, 3),
                    "cycle_count":     self._dream._cycle_count,
                    "active_obsessions": [
                        {"theme": o.theme[:60], "urgency": round(o.urgency, 3)}
                        for o in obsessions[:5]
                    ],
                }
            except Exception as e:
                log.debug(f"Dream capture error: {e}")

        # ── Aesthetic stats ───────────────────────────────────────────────
        if aesthetic_stats:
            entry["aesthetic"] = aesthetic_stats
        elif self._aesthetic:
            try:
                entry["aesthetic"] = self._aesthetic.get_session_stats()
            except Exception:
                pass

        if extra_notes:
            entry["notes"] = extra_notes

        return entry

    def _write_to_disk(self, entry: dict) -> str:
        """Write journal entry to disk as JSON."""
        date_str = entry["date"]
        # Find next available index for this date
        existing = list(JOURNAL_DIR.glob(f"{date_str}_*.json"))
        idx      = len(existing) + 1
        filename = JOURNAL_DIR / f"{date_str}_{idx:02d}.json"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Journal write error: {e}")
        return str(filename)

    def _write_to_memory(self, entry: dict):
        """
        Write a summary of this journal entry to MemoryWeb.
        This makes sessions visible to the dream loop and memory search.
        """
        if not self._web:
            return

        try:
            bio     = entry.get("biorhythm", {})
            inner   = entry.get("inner_state", {})
            id_chg  = entry.get("identity_changes", {})
            dream   = entry.get("dream_state", {})
            aes     = entry.get("aesthetic", {})

            lines = [
                f"SESSION JOURNAL — {entry['date']} (id: {entry['session_id']})",
                f"Duration: {entry['duration_minutes']} min, "
                f"Interactions: {entry['interactions']}, "
                f"Tasks: {entry['tasks_completed']}/{entry['tasks_started']}",
            ]

            if bio:
                dom = bio.get("dominant","")
                val = bio.get("dom_value", 0)
                sign = "↑" if val > 0 else "↓"
                lines.append(f"Biorhythm: {dom} {sign} {val:+.2f}")

            if inner:
                lines.append(
                    f"Inner state: {inner.get('dominant_affect','')} "
                    f"({inner.get('affect_intensity',0):.0%})"
                )

            if id_chg and id_chg.get("total", 0) > 0:
                lines.append(
                    f"Identity: {id_chg['total']} changes — "
                    f"{id_chg.get('new_beliefs',0)} beliefs, "
                    f"{id_chg.get('preference_shifts',0)} preferences"
                )

            if dream:
                obs_count = len(dream.get("active_obsessions", []))
                lines.append(
                    f"Dream: restlessness {dream.get('restlessness',0):.0%}, "
                    f"{obs_count} obsessions"
                )

            if aes and aes.get("total", 0) > 0:
                lines.append(
                    f"Aesthetic: {aes.get('beautiful',0)} beautiful / "
                    f"{aes.get('repulsive',0)} repulsive "
                    f"(avg {aes.get('avg_score',0.5):.2f})"
                )

            content = "\n".join(lines)

            self._web.remember(
                content    = content,
                category   = "session_journal",
                tags       = ["journal", entry["date"], entry["session_id"]],
                importance = 0.6,
                metadata   = {"session_id": entry["session_id"], "full_entry": entry},
            )
        except Exception as e:
            log.debug(f"Journal memory write error: {e}")

    def get_recent_entries(self, n: int = 7) -> List[dict]:
        """Return the n most recent journal entries from disk."""
        entries = []
        files   = sorted(JOURNAL_DIR.glob("*.json"), reverse=True)
        for f in files[:n]:
            try:
                with open(f, encoding="utf-8") as fh:
                    entries.append(json.load(fh))
            except Exception:
                continue
        return entries

    def format_history_summary(self, n: int = 5) -> str:
        """Format recent journal entries as a compact string for context."""
        entries = self.get_recent_entries(n)
        if not entries:
            return "No journal history yet."

        lines = ["RECENT SESSIONS:"]
        for e in entries:
            bio     = e.get("biorhythm", {})
            inner   = e.get("inner_state", {})
            dom     = bio.get("dominant", "")
            affect  = inner.get("dominant_affect", "")
            lines.append(
                f"  {e.get('date','')}  "
                f"{e.get('duration_minutes',0):.0f}m  "
                f"{e.get('interactions',0)} exchanges  "
                f"[{dom}↑ {affect}]"
            )
        return "\n".join(lines)
