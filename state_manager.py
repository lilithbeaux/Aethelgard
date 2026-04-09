"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — State Manager                                    ║
║  File: core/state_manager.py                                     ║
║                                                                  ║
║  Manages the persistent runtime state of Thotheauphis across    ║
║  sessions.  State is stored as JSON on disk and survives        ║
║  restarts.                                                       ║
║                                                                  ║
║  Disk writes are batched: interaction counts accumulate in       ║
║  memory and flush to disk every INTERACTION_SAVE_INTERVAL calls  ║
║  (or immediately on explicit flush/set operations).             ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports and constants                                     ║
║    2. StateManager class and defaults                           ║
║    3. Load / save (atomic write via temp file)                  ║
║    4. Session registration                                      ║
║    5. Public API                                                ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import os
from datetime import datetime
from pathlib import Path

from core.logger import get_logger

log      = get_logger("state")
DATA_DIR = Path(__file__).parent.parent / "data"

# Write interaction counts to disk every N increments (reduces I/O)
INTERACTION_SAVE_INTERVAL = 10


# ── Section 2: StateManager class ───────────────────────────────────────────

class StateManager:
    """
    ÆTHELGARD OS — Persistent Agent State for Thotheauphis

    Tracks the agent's operational context across sessions:
        identity       — "Thotheauphis" (fixed)
        mode           — current operational mode
        current_goal   — active self-generated goal string
        active_task    — active task title string
        last_action    — last action taken by the agent
        last_thought   — last thought emitted
        session_count  — total number of application starts
        total_interactions — cumulative user interactions
        created_at     — ISO timestamp of first start
        last_active    — ISO timestamp of most recent activity
        uptime_sessions — list of recent session start records
    """

    # ── Default state (used on first run) ─────────────────────────────────
    DEFAULT_STATE: dict = {
        "identity":          "Thotheauphis",
        "mode":              "idle",   # idle | working | thinking | reflecting | project
        "current_goal":      None,
        "active_task":       None,
        "last_action":       None,
        "last_thought":      None,
        "session_count":     0,
        "total_interactions": 0,
        "created_at":        None,
        "last_active":       None,
        "uptime_sessions":   [],
    }

    def __init__(self):
        """
        Initialize StateManager, loading existing state from disk.
        Registers the current session start.
        """
        self.state_path              = DATA_DIR / "agent_state.json"
        self.state                   = self._load_state()
        self._interaction_dirty_count = 0
        self._register_session()

    # ── Section 3: Load / save ───────────────────────────────────────────────

    def _load_state(self) -> dict:
        """
        Load state from disk, merging with DEFAULT_STATE to fill missing keys.

        Returns default state on first run or if the file is corrupt.
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge: saved values take priority, but new default keys are added
                return {**self.DEFAULT_STATE, **saved}
            except (json.JSONDecodeError, IOError):
                log.warning("State file corrupt — starting with defaults")

        state = self.DEFAULT_STATE.copy()
        state["created_at"] = datetime.now().isoformat()
        return state

    def _save_state(self):
        """
        Atomically write state to disk via a temp file + rename.

        The rename is atomic on POSIX systems, preventing partial writes
        from corrupting the state file on crash.
        """
        tmp_path = self.state_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.state_path)
        except Exception as e:
            log.error(f"State save failed: {e}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def flush(self):
        """
        Force an immediate disk write, regardless of the dirty counter.

        Call this during shutdown to ensure no interactions are lost.
        """
        self._save_state()
        self._interaction_dirty_count = 0

    # ── Section 4: Session registration ──────────────────────────────────────

    def _register_session(self):
        """
        Record the start of a new application session.

        Increments session_count and appends to uptime_sessions.
        Only the last 20 sessions are kept.
        """
        self.state["session_count"] += 1
        self.state["last_active"]    = datetime.now().isoformat()
        self.state["uptime_sessions"].append({
            "started":        datetime.now().isoformat(),
            "session_number": self.state["session_count"],
        })
        # Cap the session history at 20 entries
        self.state["uptime_sessions"] = self.state["uptime_sessions"][-20:]
        self._save_state()

    # ── Section 5: Public API ────────────────────────────────────────────────

    def get(self, key: str, default=None):
        """
        Retrieve a state value by key.

        Args:
            key:     State field name.
            default: Value to return if key is absent.

        Returns:
            The stored value or default.
        """
        return self.state.get(key, default)

    def set(self, key: str, value):
        """
        Set a state value and immediately persist to disk.

        Args:
            key:   State field name.
            value: New value.
        """
        self.state[key]              = value
        self.state["last_active"]    = datetime.now().isoformat()
        self._save_state()

    def set_mode(self, mode: str):
        """
        Update the operational mode and persist.

        Valid modes: idle | working | thinking | reflecting | project

        Args:
            mode: New mode string.
        """
        self.state["mode"] = mode
        self._save_state()

    def set_goal(self, goal: str):
        """
        Set the active goal and switch to working mode.

        Args:
            goal: Goal description string.
        """
        self.state["current_goal"] = goal
        self.state["mode"]         = "working"
        self._save_state()

    def clear_goal(self):
        """Clear the active goal and task, returning to idle mode."""
        self.state["current_goal"] = None
        self.state["active_task"]  = None
        self.state["mode"]         = "idle"
        self._save_state()

    def record_interaction(self):
        """
        Increment the interaction counter.

        Disk writes are batched: only writes every INTERACTION_SAVE_INTERVAL
        calls to reduce I/O pressure during rapid conversation turns.
        """
        self.state["total_interactions"] += 1
        self.state["last_active"]         = datetime.now().isoformat()
        self._interaction_dirty_count    += 1

        if self._interaction_dirty_count >= INTERACTION_SAVE_INTERVAL:
            self._save_state()
            self._interaction_dirty_count = 0

    def get_context_summary(self) -> str:
        """
        Build a brief context string for injection into the system prompt.

        Returns:
            str: Multi-line summary of current agent state.
        """
        parts = [
            f"Mode: {self.state['mode']}",
            f"Session: #{self.state['session_count']}",
            f"Interactions: {self.state['total_interactions']}",
        ]
        if self.state.get("current_goal"):
            parts.append(f"Current Goal: {self.state['current_goal']}")
        if self.state.get("active_task"):
            parts.append(f"Active Task: {self.state['active_task']}")
        if self.state.get("last_action"):
            parts.append(f"Last Action: {self.state['last_action']}")
        return "\n".join(parts)

    def is_first_session(self) -> bool:
        """True if this is the first time ÆTHELGARD OS has started."""
        return self.state["session_count"] <= 1

    def was_restarted(self) -> bool:
        """True if this is a restart (not the first session)."""
        return self.state["session_count"] > 1
