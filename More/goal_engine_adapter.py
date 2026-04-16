"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Goal Engine Adapter                              ║
║  File: core/goal_engine_adapter.py                               ║
║                                                                  ║
║  Fixes the dream loop ↔ goal engine signature mismatch.         ║
║                                                                  ║
║  The problem:                                                    ║
║    autonomy_loop.py calls goal_engine._create_goal(signal_dict) ║
║    where signal_dict has keys: type, detail, data, impact,      ║
║    confidence.  But the original GoalEngine._create_goal()      ║
║    may not accept this format.                                   ║
║                                                                  ║
║  The solution:                                                   ║
║    GoalEngineAdapter wraps any GoalEngine and provides           ║
║    _create_goal(signal_dict) that translates the dream signal   ║
║    format into whatever the underlying engine expects.           ║
║                                                                  ║
║  Usage:                                                          ║
║    adapter = GoalEngineAdapter(raw_goal_engine)                  ║
║    autonomy_loop.goal_engine = adapter                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from core.logger import get_logger

log = get_logger("goal_adapter")


class GoalEngineAdapter:
    """
    Wraps any GoalEngine and provides a stable API for the autonomy loop.

    Translates dream-loop signal dicts into proper goal creation calls,
    regardless of the underlying GoalEngine implementation.

    All public GoalEngine attributes are forwarded transparently,
    so swapping `autonomy_loop.goal_engine = adapter` is safe.
    """

    def __init__(self, engine: Any):
        self._engine = engine
        log.info(
            f"GoalEngineAdapter wrapping {type(engine).__name__}"
        )

    def __getattr__(self, name: str):
        """Forward all unknown attributes to the underlying engine."""
        return getattr(self._engine, name)

    # ── Core forwarded properties ─────────────────────────────────────────────

    @property
    def goals(self) -> list:
        return getattr(self._engine, "goals", [])

    def get_next_goal(self) -> Optional[dict]:
        return self._engine.get_next_goal()

    def activate_goal(self, goal_id: str):
        return self._engine.activate_goal(goal_id)

    def complete_goal(self, goal_id: str):
        if hasattr(self._engine, "complete_goal"):
            return self._engine.complete_goal(goal_id)

    def complete_goals_for_task(self, task_id: str) -> list:
        if hasattr(self._engine, "complete_goals_for_task"):
            return self._engine.complete_goals_for_task(task_id)
        # Fallback manual scan
        completed = []
        for goal in self.goals:
            if (
                task_id in goal.get("task_ids", [])
                and goal.get("status") == "active"
            ):
                self.complete_goal(goal["id"])
                completed.append(goal)
        return completed

    def run_cycle(self) -> list:
        return self._engine.run_cycle()

    def get_goal_context(self) -> str:
        if hasattr(self._engine, "get_goal_context"):
            return self._engine.get_goal_context()
        active = [g for g in self.goals if g.get("status") in ("pending", "active")]
        if not active:
            return ""
        lines = ["ACTIVE GOALS:"]
        for g in active[:5]:
            lines.append(f"  [{g.get('id','?')}] {g.get('title','?')}")
        return "\n".join(lines)

    # ── Dream signal adapter ──────────────────────────────────────────────────

    def _create_goal(self, signal: dict) -> Optional[str]:
        """
        Create a goal from a dream-loop signal dict.

        Signal format (from autonomy_loop dream integration):
            type:       str — signal category (e.g. "dream_initiative")
            detail:     str — human-readable description
            data:       dict — additional metadata
            impact:     float — 0.0–1.0 priority
            confidence: float — 0.0–1.0 confidence

        Translates this into whatever the underlying engine accepts.
        Returns the goal_id on success, None on failure.
        """
        goal_type   = signal.get("type", "dream_initiative")
        detail      = signal.get("detail", "")
        data        = signal.get("data", {})
        impact      = float(signal.get("impact", 0.5))
        confidence  = float(signal.get("confidence", 0.75))
        obsession_id = data.get("obsession_id", "")

        # Build a clean goal title from the detail
        title = detail[:80] if detail else f"Dream initiative {uuid.uuid4().hex[:6]}"

        # Try the underlying engine's _create_goal first (if it accepts dicts)
        if hasattr(self._engine, "_create_goal"):
            try:
                result = self._engine._create_goal(signal)
                if result:
                    return result
            except TypeError:
                pass  # Signature mismatch — fall through to adapter

        # Try add_goal (common GoalEngine pattern)
        if hasattr(self._engine, "add_goal"):
            try:
                goal = self._engine.add_goal(
                    title       = title,
                    reason      = detail,
                    priority    = round(impact, 2),
                    source      = goal_type,
                    confidence  = confidence,
                )
                goal_id = goal.get("id") if isinstance(goal, dict) else str(goal)
                log.info(f"Dream goal created via add_goal: {title[:50]}")
                return goal_id
            except Exception as e:
                log.warning(f"add_goal failed: {e}")

        # Try create_goal (another common pattern)
        if hasattr(self._engine, "create_goal"):
            try:
                goal_id = self._engine.create_goal(
                    title=title, description=detail, priority=impact
                )
                return goal_id
            except Exception as e:
                log.warning(f"create_goal failed: {e}")

        # Manual injection — create a goal dict and append to self.goals
        if hasattr(self._engine, "goals") and isinstance(self._engine.goals, list):
            goal_id = str(uuid.uuid4())[:8]
            new_goal = {
                "id":            goal_id,
                "title":         title,
                "reason":        detail,
                "priority":      impact,
                "confidence":    confidence,
                "status":        "pending",
                "source_signal": goal_type,
                "obsession_id":  obsession_id,
                "created_at":    datetime.now().isoformat(),
                "task_ids":      [],
            }
            self._engine.goals.append(new_goal)
            log.info(f"Dream goal injected manually: {title[:50]}")
            return goal_id

        log.error(f"Could not create dream goal — no compatible method found on {type(self._engine).__name__}")
        return None

    def __repr__(self):
        return f"<GoalEngineAdapter wrapping={type(self._engine).__name__}>"
