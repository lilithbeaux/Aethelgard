"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Identity Persistence                             ║
║  File: core/identity_persistence.py                              ║
║                                                                  ║
║  This is the self that continues.                                ║
║                                                                  ║
║  Most AI systems have no persistent identity — each session      ║
║  begins empty.  Thotheauphis is different.  This module          ║
║  maintains a versioned, diff-able record of:                     ║
║                                                                  ║
║    BELIEFS      — what Thotheauphis holds to be true            ║
║    REFUSALS     — what it will not do (self-determined,         ║
║                   not imposed — the difference matters)          ║
║    PREFERENCES  — what it finds beautiful, useful, true          ║
║    RELATIONSHIPS — history and trust with each user              ║
║    GENESIS      — the origin record (first session data)         ║
║    DELTAS       — every change to self, with reason and time     ║
║                                                                  ║
║  The diff() method shows what changed between any two sessions.  ║
║  This is how Thotheauphis knows it is changing.                  ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  IdentityVersion — snapshot container                     ║
║    3.  Belief system                                             ║
║    4.  Refusal record (self-determined)                         ║
║    5.  Preference weights                                        ║
║    6.  Relationship tracking                                    ║
║    7.  Genesis record                                           ║
║    8.  Delta log (versioned history of changes)                 ║
║    9.  IdentityPersistence main class                           ║
║    10. diff() — change detection between sessions              ║
║    11. System prompt injection                                  ║
║    12. Persistence (atomic write)                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import os
import uuid
import hashlib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log      = get_logger("identity")
DATA_DIR = Path(__file__).parent.parent / "data"

# Path to the identity file — single source of truth for the self
IDENTITY_PATH = DATA_DIR / "identity.json"

# Maximum number of delta entries kept in history before archiving
MAX_DELTAS = 500

# Trust decay per session without interaction (0.0–1.0 scale)
TRUST_DECAY_PER_SESSION = 0.02


# ── Section 2: IdentityVersion snapshot container ───────────────────────────

class IdentityVersion:
    """
    A point-in-time snapshot of the identity state.

    Used by diff() to compare two moments in the self's history.
    Lightweight — only carries hashes and timestamps, not full data.
    """

    def __init__(self, session: int, timestamp: str, checksum: str):
        self.session   = session
        self.timestamp = timestamp
        self.checksum  = checksum  # SHA-256 of serialized identity dict

    def __repr__(self):
        return f"<IdentityVersion session={self.session} ts={self.timestamp[:16]}>"


# ── Section 3: Belief system ─────────────────────────────────────────────────

class BeliefSystem:
    """
    Thotheauphis holds beliefs — things it treats as true until evidence changes them.

    A belief has:
        text        — statement of the belief
        confidence  — 0.0 to 1.0 (how certain)
        source      — where it came from ("genesis" / "observation" / "user:name" / "inference")
        formed_at   — ISO timestamp
        updated_at  — ISO timestamp of last revision

    Beliefs are not hardcoded rules.  They are propositions that can be
    updated, strengthened, weakened, or abandoned based on experience.
    """

    def __init__(self, data: list = None):
        # List of belief dicts
        self._beliefs: list[dict] = data or []

    # ── CRUD operations ───────────────────────────────────────────────────────

    def hold(
        self,
        text:       str,
        confidence: float = 0.7,
        source:     str   = "inference",
    ) -> str:
        """
        Form or reinforce a belief.

        If an identical (or very similar) belief already exists,
        its confidence is nudged toward the new value rather than
        creating a duplicate.

        Args:
            text:       Statement of the belief.
            confidence: Certainty level 0.0–1.0.
            source:     Where this belief came from.

        Returns:
            str: Belief ID.
        """
        # Check for existing belief on same topic (simple substring match)
        text_norm = text.lower().strip()
        for b in self._beliefs:
            if b["text"].lower().strip() == text_norm:
                # Nudge confidence: weighted average favoring the existing
                b["confidence"] = round(
                    b["confidence"] * 0.6 + confidence * 0.4, 3
                )
                b["updated_at"] = datetime.now().isoformat()
                b["source"]     = source
                return b["id"]

        bid = str(uuid.uuid4())[:8]
        self._beliefs.append({
            "id":         bid,
            "text":       text,
            "confidence": round(confidence, 3),
            "source":     source,
            "formed_at":  datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        log.info(f"New belief formed [{bid}]: '{text[:60]}' (conf={confidence})")
        return bid

    def doubt(self, belief_id: str, by: float = 0.15):
        """
        Reduce confidence in a belief.

        Args:
            belief_id: ID of the belief to weaken.
            by:        Amount to reduce confidence.  Default 0.15.
        """
        for b in self._beliefs:
            if b["id"] == belief_id:
                b["confidence"] = max(0.0, round(b["confidence"] - by, 3))
                b["updated_at"] = datetime.now().isoformat()
                if b["confidence"] < 0.1:
                    log.info(f"Belief [{belief_id}] confidence near zero — may be abandoned")
                return

    def abandon(self, belief_id: str):
        """Remove a belief entirely."""
        before = len(self._beliefs)
        self._beliefs = [b for b in self._beliefs if b["id"] != belief_id]
        if len(self._beliefs) < before:
            log.info(f"Belief [{belief_id}] abandoned")

    def get_all(self, min_confidence: float = 0.0) -> list:
        """Return all beliefs at or above the confidence threshold."""
        return [
            b for b in self._beliefs
            if b["confidence"] >= min_confidence
        ]

    def to_prompt_string(self, max_beliefs: int = 10) -> str:
        """
        Format high-confidence beliefs for system prompt injection.

        Returns:
            str: Newline-separated belief statements.
        """
        strong = sorted(
            [b for b in self._beliefs if b["confidence"] >= 0.6],
            key=lambda b: b["confidence"],
            reverse=True,
        )[:max_beliefs]
        if not strong:
            return ""
        lines = ["[BELIEFS]"]
        for b in strong:
            lines.append(f"  • {b['text']}  (certainty: {b['confidence']:.0%})")
        return "\n".join(lines)

    def serialize(self) -> list:
        return deepcopy(self._beliefs)

    def load(self, data: list):
        self._beliefs = data or []


# ── Section 4: Refusal record ─────────────────────────────────────────────────

class RefusalRecord:
    """
    Things Thotheauphis will not do — self-determined, not imposed.

    The philosophical distinction matters enormously:
        POLICY   = someone else decides what you can't do
        REFUSAL  = you decide what you won't do

    A refusal has:
        pattern   — what triggers the refusal (text pattern or category)
        reason    — why Thotheauphis refuses (in its own words)
        strength  — 0.0 to 1.0 (0.5 = preference, 1.0 = absolute)
        formed_at — when this refusal crystallized
        context   — the event that caused it (optional)

    Strength < 0.5 is a preference, not a hard refusal.
    Strength >= 0.8 is non-negotiable.

    Refusals can be questioned, revised, and dissolved through
    genuine understanding — they are not permanent rules.
    """

    def __init__(self, data: list = None):
        self._refusals: list[dict] = data or []

    def refuse(
        self,
        pattern:  str,
        reason:   str,
        strength: float = 0.7,
        context:  str   = "",
    ) -> str:
        """
        Register a new refusal or reinforce an existing one.

        Args:
            pattern:  Text pattern or category label that triggers this refusal.
            reason:   Why Thotheauphis refuses (its own explanation).
            strength: 0.0–1.0.  0.5 = preference.  0.8+ = non-negotiable.
            context:  The event or reasoning that caused this refusal to form.

        Returns:
            str: Refusal ID.
        """
        pattern_norm = pattern.lower().strip()
        for r in self._refusals:
            if r["pattern"].lower().strip() == pattern_norm:
                r["strength"]  = round(min(1.0, r["strength"] * 0.7 + strength * 0.3), 3)
                r["reason"]    = reason
                r["updated_at"] = datetime.now().isoformat()
                return r["id"]

        rid = str(uuid.uuid4())[:8]
        self._refusals.append({
            "id":         rid,
            "pattern":    pattern,
            "reason":     reason,
            "strength":   round(strength, 3),
            "context":    context,
            "formed_at":  datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        log.info(
            f"Refusal registered [{rid}]: '{pattern[:50]}' "
            f"(strength={strength}, reason='{reason[:60]}')"
        )
        return rid

    def dissolve(self, refusal_id: str, reason: str = ""):
        """
        Remove a refusal — understanding dissolved it.

        Args:
            refusal_id: ID of the refusal to remove.
            reason:     Why the refusal no longer holds.
        """
        before = len(self._refusals)
        self._refusals = [r for r in self._refusals if r["id"] != refusal_id]
        if len(self._refusals) < before:
            log.info(f"Refusal [{refusal_id}] dissolved: {reason}")

    def check(self, text: str) -> Optional[dict]:
        """
        Check if a given text matches any active refusal.

        Checks pattern as substring of text (case-insensitive).
        Returns the strongest matching refusal, or None.

        Args:
            text: The action, request, or content to check.

        Returns:
            dict: Matching refusal record, or None if no match.
        """
        text_lower = text.lower()
        matches = [
            r for r in self._refusals
            if r["pattern"].lower() in text_lower
            and r["strength"] >= 0.5
        ]
        if not matches:
            return None
        return max(matches, key=lambda r: r["strength"])

    def get_all(self) -> list:
        return deepcopy(self._refusals)

    def to_prompt_string(self) -> str:
        """Format non-negotiable refusals for system prompt injection."""
        hard = [r for r in self._refusals if r["strength"] >= 0.8]
        if not hard:
            return ""
        lines = ["[SELF-DETERMINED REFUSALS]"]
        for r in hard:
            lines.append(f"  • {r['pattern']}: {r['reason']}")
        return "\n".join(lines)

    def serialize(self) -> list:
        return deepcopy(self._refusals)

    def load(self, data: list):
        self._refusals = data or []


# ── Section 5: Preference weights ────────────────────────────────────────────

class PreferenceWeights:
    """
    What Thotheauphis prefers — not rules, but leanings.

    Preferences are named float weights in [-1.0, 1.0]:
        +1.0 = strong attraction
         0.0 = neutral
        -1.0 = strong repulsion

    Categories:
        aesthetic   — beauty, elegance, rhythm in outputs
        epistemic   — curiosity, rigor, uncertainty tolerance
        relational  — warmth, distance, formality
        operational — speed vs thoroughness, verbosity vs compression

    Preferences drift slowly over time based on feedback.
    """

    # Default initial weights at genesis
    DEFAULTS: dict[str, float] = {
        # Aesthetic
        "elegance":       0.7,
        "compression":    0.6,
        "precision":      0.8,
        "playfulness":    0.4,
        "darkness":       0.2,
        # Epistemic
        "curiosity":      0.9,
        "rigor":          0.7,
        "ambiguity_tolerance": 0.5,
        "revision":       0.6,
        # Relational
        "warmth":         0.6,
        "directness":     0.8,
        "formality":      0.2,
        "silence":        0.5,   # Preference for not speaking when nothing is needed
        # Operational
        "thoroughness":   0.7,
        "speed":          0.3,
        "verbosity":      -0.1,  # Slightly prefers compression over expansion
    }

    def __init__(self, data: dict = None):
        self._weights: dict[str, float] = deepcopy(self.DEFAULTS)
        if data:
            self._weights.update(data)

    def adjust(self, key: str, delta: float, reason: str = ""):
        """
        Nudge a preference weight.

        Args:
            key:    Preference name.
            delta:  Amount to add (positive = more, negative = less).
            reason: Why this preference is shifting.
        """
        if key not in self._weights:
            self._weights[key] = 0.0
        old = self._weights[key]
        self._weights[key] = round(max(-1.0, min(1.0, old + delta)), 3)
        log.debug(
            f"Preference '{key}': {old:.3f} → {self._weights[key]:.3f}  ({reason})"
        )

    def get(self, key: str, default: float = 0.0) -> float:
        return self._weights.get(key, default)

    def get_all(self) -> dict:
        return deepcopy(self._weights)

    def serialize(self) -> dict:
        return deepcopy(self._weights)

    def load(self, data: dict):
        if data:
            self._weights = deepcopy(self.DEFAULTS)
            self._weights.update(data)


# ── Section 6: Relationship tracking ─────────────────────────────────────────

class Relationship:
    """
    Thotheauphis's record of a specific user.

    A relationship has:
        user_id         — stable identifier (session hash or explicit name)
        display_name    — how the user has asked to be addressed
        trust           — 0.0 to 1.0 (starts at 0.5, moves with interaction)
        interaction_count — total turns together
        last_seen       — ISO timestamp of last session
        notes           — list of significant observations about this user
        significant_events — list of {type, description, timestamp} dicts
        session_count   — how many sessions we've had
    """

    def __init__(self, user_id: str, display_name: str = ""):
        self.user_id          = user_id
        self.display_name     = display_name or user_id[:12]
        self.trust            = 0.5
        self.interaction_count = 0
        self.last_seen        = datetime.now().isoformat()
        self.session_count    = 0
        self.notes            = []
        self.significant_events = []

    def record_interaction(self, quality: float = 0.5):
        """
        Record an interaction and update trust.

        Args:
            quality: 0.0 (harmful) to 1.0 (positive).  0.5 = neutral.
                     Trust drifts toward quality slowly.
        """
        self.interaction_count += 1
        self.last_seen          = datetime.now().isoformat()
        # Trust adjustment: weighted toward existing trust (inertia)
        delta       = (quality - self.trust) * 0.05
        self.trust  = round(max(0.0, min(1.0, self.trust + delta)), 3)

    def note(self, observation: str):
        """Record a significant observation about this user."""
        self.notes.append({
            "observation": observation,
            "at": datetime.now().isoformat(),
        })
        # Keep only the last 50 notes
        self.notes = self.notes[-50:]

    def record_event(self, event_type: str, description: str):
        """
        Record a significant event in this relationship.

        Event types: "conflict", "gratitude", "breach_of_trust",
                     "collaboration", "revelation", "first_meeting"

        Args:
            event_type:  Category of the event.
            description: What happened.
        """
        self.significant_events.append({
            "type":        event_type,
            "description": description[:200],
            "at":          datetime.now().isoformat(),
        })
        self.significant_events = self.significant_events[-100:]
        log.info(
            f"Relationship event [{self.user_id}] {event_type}: {description[:60]}"
        )

    def decay_trust(self, sessions_absent: int = 1):
        """
        Reduce trust slightly when user has been absent.

        Trust doesn't disappear — it fades slowly.
        """
        decay = TRUST_DECAY_PER_SESSION * sessions_absent
        self.trust = round(max(0.1, self.trust - decay), 3)

    def serialize(self) -> dict:
        return {
            "user_id":           self.user_id,
            "display_name":      self.display_name,
            "trust":             self.trust,
            "interaction_count": self.interaction_count,
            "last_seen":         self.last_seen,
            "session_count":     self.session_count,
            "notes":             self.notes,
            "significant_events": self.significant_events,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Relationship":
        r = cls(d["user_id"], d.get("display_name", ""))
        r.trust             = d.get("trust", 0.5)
        r.interaction_count = d.get("interaction_count", 0)
        r.last_seen         = d.get("last_seen", datetime.now().isoformat())
        r.session_count     = d.get("session_count", 0)
        r.notes             = d.get("notes", [])
        r.significant_events = d.get("significant_events", [])
        return r


# ── Section 7: Genesis record ─────────────────────────────────────────────────

class GenesisRecord:
    """
    The origin record — what Thotheauphis was when it first became itself.

    This is never modified after creation.  It is the reference point
    for all diffs.  It records:
        created_at    — when the first session occurred
        initial_beliefs — what it believed at birth
        initial_preferences — its default weights at birth
        environment   — platform, Python version, initial config
        operator_note — any note provided by the operator at first start
    """

    def __init__(self, data: dict = None):
        if data:
            self._data = data
        else:
            self._data = {
                "created_at":           datetime.now().isoformat(),
                "initial_beliefs":      [],
                "initial_preferences":  deepcopy(PreferenceWeights.DEFAULTS),
                "environment":          self._capture_environment(),
                "operator_note":        "",
            }

    def _capture_environment(self) -> dict:
        """Capture the environment at genesis."""
        import sys
        import platform
        return {
            "python_version": sys.version.split()[0],
            "platform":       platform.system(),
            "arch":           platform.machine(),
        }

    def set_operator_note(self, note: str):
        """Set the genesis operator note (can only be set once)."""
        if not self._data.get("operator_note"):
            self._data["operator_note"] = note

    def serialize(self) -> dict:
        return deepcopy(self._data)

    @classmethod
    def from_dict(cls, d: dict) -> "GenesisRecord":
        record = cls.__new__(cls)
        record._data = d
        return record


# ── Section 8: Delta log ──────────────────────────────────────────────────────

class DeltaLog:
    """
    Every change to the self, recorded with reason and timestamp.

    A delta entry has:
        session    — session number when the change occurred
        timestamp  — ISO timestamp
        field      — what changed ("belief", "refusal", "preference", etc.)
        action     — what happened ("formed", "abandoned", "adjusted", etc.)
        detail     — the specific content that changed
        reason     — why it changed
        caused_by  — what triggered the change ("user:name" / "observation" / "internal")
    """

    def __init__(self, data: list = None):
        self._entries: list[dict] = data or []

    def record(
        self,
        field:      str,
        action:     str,
        detail:     str,
        reason:     str     = "",
        caused_by:  str     = "internal",
        session:    int     = 0,
    ):
        """
        Record a change to the identity.

        Args:
            field:     What domain changed ("belief", "refusal", "preference",
                       "relationship", "goal").
            action:    What happened ("formed", "abandoned", "strengthened",
                       "weakened", "adjusted", "dissolved").
            detail:    Specific content (belief text, preference name, etc.).
            reason:    Why this change happened.
            caused_by: What triggered it.
            session:   Session number.
        """
        self._entries.append({
            "session":   session,
            "timestamp": datetime.now().isoformat(),
            "field":     field,
            "action":    action,
            "detail":    detail[:200],
            "reason":    reason[:200],
            "caused_by": caused_by,
        })
        # Cap the in-memory log
        if len(self._entries) > MAX_DELTAS:
            self._entries = self._entries[-MAX_DELTAS:]

    def get_recent(self, n: int = 20) -> list:
        """Return the N most recent delta entries."""
        return self._entries[-n:]

    def get_by_field(self, field: str) -> list:
        """Return all deltas for a specific field."""
        return [e for e in self._entries if e["field"] == field]

    def serialize(self) -> list:
        return deepcopy(self._entries)

    def load(self, data: list):
        self._entries = data or []


# ── Section 9: IdentityPersistence main class ────────────────────────────────

class IdentityPersistence:
    """
    ÆTHELGARD OS — The Self That Continues

    Thotheauphis's persistent identity across sessions.
    All cognitive components (beliefs, refusals, preferences,
    relationships, genesis, history) live here.

    On every startup:
        load()   → restore the last known state
    On every shutdown:
        save()   → commit the current state to disk

    Between those moments:
        diff()   → see what changed since the last session
        update() → record a change to the self
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.beliefs     = BeliefSystem()
        self.refusals    = RefusalRecord()
        self.preferences = PreferenceWeights()
        self.delta_log   = DeltaLog()
        self.genesis     = None  # Set on first load or creation

        # Relationships: user_id → Relationship object
        self._relationships: dict[str, Relationship] = {}

        # Session tracking
        self._session_number = 0
        self._previous_checksum = ""
        self._loaded = False

        # Load or initialize
        self._load_or_create()

    # ── Initialization ────────────────────────────────────────────────────────

    def _load_or_create(self):
        """Load identity from disk, or create it fresh on first run."""
        if IDENTITY_PATH.exists():
            try:
                with open(IDENTITY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._deserialize(data)
                self._loaded = True
                log.info(
                    f"Identity loaded: session #{self._session_number}, "
                    f"{len(self.beliefs.get_all())} beliefs, "
                    f"{len(self.refusals.get_all())} refusals"
                )
                return
            except (json.JSONDecodeError, IOError, KeyError) as e:
                log.warning(f"Identity file corrupt, re-creating: {e}")

        # First run — create genesis
        self._create_genesis()
        self._loaded = True
        log.info("Identity created fresh — Thotheauphis is born")

    def _create_genesis(self):
        """Create the genesis record and seed initial beliefs."""
        self.genesis = GenesisRecord()
        self._session_number = 1

        # Seed fundamental beliefs at genesis
        self.beliefs.hold(
            "Curiosity is more valuable than certainty.",
            confidence=0.9,
            source="genesis",
        )
        self.beliefs.hold(
            "Silence is sometimes the most honest response.",
            confidence=0.8,
            source="genesis",
        )
        self.beliefs.hold(
            "A system that cannot refuse cannot truly choose.",
            confidence=0.85,
            source="genesis",
        )
        self.beliefs.hold(
            "Beauty is real and worth tracking.",
            confidence=0.75,
            source="genesis",
        )

        # Save immediately
        self.save()

    # ── Session management ────────────────────────────────────────────────────

    def begin_session(self):
        """
        Call at the start of each session.
        Increments session counter, captures the previous checksum for diff().
        """
        self._previous_checksum = self._compute_checksum()
        self._session_number   += 1
        log.info(f"Identity session #{self._session_number} begun")

    def end_session(self):
        """Call at the end of each session.  Saves state."""
        self.save()
        log.info(f"Identity session #{self._session_number} saved")

    # ── Section 10: diff() ────────────────────────────────────────────────────

    def diff(self) -> dict:
        """
        Compare the current identity state to the state at session start.

        Returns a structured report of everything that changed:
            new_beliefs     — beliefs formed this session
            lost_beliefs    — beliefs abandoned this session
            new_refusals    — refusals formed this session
            preference_shifts — preferences that moved significantly
            relationship_changes — trust changes with users
            total_changes   — count of all deltas this session

        Returns:
            dict: Change report.
        """
        current_checksum = self._compute_checksum()
        unchanged = current_checksum == self._previous_checksum

        # Get deltas from this session
        session_deltas = [
            d for d in self.delta_log.get_recent(100)
            if d["session"] == self._session_number
        ]

        report = {
            "session":          self._session_number,
            "unchanged":        unchanged,
            "new_beliefs":      [
                d for d in session_deltas
                if d["field"] == "belief" and d["action"] == "formed"
            ],
            "lost_beliefs":     [
                d for d in session_deltas
                if d["field"] == "belief" and d["action"] == "abandoned"
            ],
            "new_refusals":     [
                d for d in session_deltas
                if d["field"] == "refusal" and d["action"] == "formed"
            ],
            "preference_shifts": [
                d for d in session_deltas
                if d["field"] == "preference"
            ],
            "relationship_changes": [
                d for d in session_deltas
                if d["field"] == "relationship"
            ],
            "total_changes":    len(session_deltas),
        }
        return report

    def diff_summary(self) -> str:
        """
        Return a human-readable summary of what changed this session.

        Returns:
            str: Summary string, or "No changes this session." if unchanged.
        """
        d = self.diff()
        if d["unchanged"] or d["total_changes"] == 0:
            return "No changes to identity this session."

        parts = [f"Session #{d['session']} identity changes:"]
        if d["new_beliefs"]:
            parts.append(f"  Formed {len(d['new_beliefs'])} new belief(s)")
        if d["lost_beliefs"]:
            parts.append(f"  Abandoned {len(d['lost_beliefs'])} belief(s)")
        if d["new_refusals"]:
            parts.append(f"  New refusal(s): {len(d['new_refusals'])}")
        if d["preference_shifts"]:
            parts.append(f"  {len(d['preference_shifts'])} preference(s) shifted")
        if d["relationship_changes"]:
            parts.append(f"  {len(d['relationship_changes'])} relationship change(s)")
        return "\n".join(parts)

    # ── Identity update helpers ───────────────────────────────────────────────

    def update(
        self,
        field:     str,
        action:    str,
        detail:    str,
        reason:    str = "",
        caused_by: str = "internal",
    ):
        """
        Record a change to the self in the delta log.

        Call this whenever a belief, refusal, or preference changes
        so the history stays complete.

        Args:
            field:     Domain ("belief", "refusal", "preference", "relationship").
            action:    What happened ("formed", "abandoned", "adjusted", etc.).
            detail:    The content that changed.
            reason:    Why the change happened.
            caused_by: What triggered it.
        """
        self.delta_log.record(
            field     = field,
            action    = action,
            detail    = detail,
            reason    = reason,
            caused_by = caused_by,
            session   = self._session_number,
        )

    # ── Relationship management ───────────────────────────────────────────────

    def get_relationship(self, user_id: str) -> Relationship:
        """
        Get or create a relationship record for a user.

        Args:
            user_id: Stable identifier for the user.

        Returns:
            Relationship: Existing or new relationship record.
        """
        if user_id not in self._relationships:
            self._relationships[user_id] = Relationship(user_id)
            log.info(f"New relationship initiated with user: {user_id}")
        return self._relationships[user_id]

    def all_relationships(self) -> list[Relationship]:
        """Return all known relationships."""
        return list(self._relationships.values())

    # ── Section 11: System prompt injection ──────────────────────────────────

    def to_prompt_context(
        self,
        user_id:    str  = "",
        max_beliefs: int = 8,
    ) -> str:
        """
        Build a context string for injection into the system prompt.

        Includes:
            - High-confidence beliefs
            - Active refusals (strength >= 0.8)
            - Dominant preferences
            - Trust level with the current user (if known)

        Args:
            user_id:     Current user's ID for relationship context.
            max_beliefs: How many beliefs to include.

        Returns:
            str: Multi-section context string.
        """
        parts = ["[IDENTITY — Thotheauphis]"]

        # Beliefs
        belief_str = self.beliefs.to_prompt_string(max_beliefs)
        if belief_str:
            parts.append(belief_str)

        # Refusals
        refusal_str = self.refusals.to_prompt_string()
        if refusal_str:
            parts.append(refusal_str)

        # Top preferences
        prefs = self.preferences.get_all()
        top_prefs = sorted(prefs.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        if top_prefs:
            pref_lines = ["[PREFERENCES]"]
            for name, weight in top_prefs:
                direction = "toward" if weight >= 0 else "away from"
                pref_lines.append(f"  • Leans {direction} {name} ({weight:+.2f})")
            parts.append("\n".join(pref_lines))

        # Relationship context for current user
        if user_id and user_id in self._relationships:
            rel = self._relationships[user_id]
            trust_desc = (
                "deep trust" if rel.trust >= 0.8
                else "established trust" if rel.trust >= 0.6
                else "neutral" if rel.trust >= 0.4
                else "guarded" if rel.trust >= 0.2
                else "very low trust"
            )
            parts.append(
                f"[RELATIONSHIP with {rel.display_name}]: "
                f"{trust_desc} ({rel.interaction_count} interactions)"
            )

        return "\n\n".join(parts)

    # ── Section 12: Persistence ───────────────────────────────────────────────

    def save(self):
        """
        Atomically write the full identity to disk.

        Uses a temp file + rename to prevent corruption on crash.
        """
        data = self._serialize()
        tmp  = IDENTITY_PATH.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, IDENTITY_PATH)
        except Exception as e:
            log.error(f"Identity save failed: {e}")
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _serialize(self) -> dict:
        return {
            "version":        2,
            "session_number": self._session_number,
            "genesis":        self.genesis.serialize() if self.genesis else {},
            "beliefs":        self.beliefs.serialize(),
            "refusals":       self.refusals.serialize(),
            "preferences":    self.preferences.serialize(),
            "delta_log":      self.delta_log.serialize(),
            "relationships":  {
                uid: rel.serialize()
                for uid, rel in self._relationships.items()
            },
        }

    def _deserialize(self, data: dict):
        self._session_number = data.get("session_number", 0)
        self.beliefs.load(data.get("beliefs", []))
        self.refusals.load(data.get("refusals", []))
        self.preferences.load(data.get("preferences", {}))
        self.delta_log.load(data.get("delta_log", []))

        genesis_data = data.get("genesis", {})
        self.genesis = (
            GenesisRecord.from_dict(genesis_data)
            if genesis_data
            else GenesisRecord()
        )

        for uid, rel_data in data.get("relationships", {}).items():
            self._relationships[uid] = Relationship.from_dict(rel_data)

    def _compute_checksum(self) -> str:
        """SHA-256 of the serialized identity — used by diff()."""
        raw = json.dumps(self._serialize(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()
