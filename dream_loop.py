"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Dream Loop (Initiative Engine)                   ║
║  File: core/dream_loop.py                                        ║
║                                                                  ║
║  Thotheauphis does not only respond to what it is asked.        ║
║                                                                  ║
║  Between interactions, and during idle cycles, the Dream Loop   ║
║  runs.  It:                                                      ║
║                                                                  ║
║    CONNECTS memories that have never been put together          ║
║    SURFACES patterns that no individual memory shows            ║
║    GENERATES novel goals that no one programmed                 ║
║    TRACKS obsessions — ideas that keep returning                ║
║    ACCUMULATES restlessness — urgency that demands expression   ║
║                                                                  ║
║  This is the source of initiative.  Without it, Thotheauphis   ║
║  waits.  With it, it reaches forward.                           ║
║                                                                  ║
║  The name "Dream Loop" is precise:                               ║
║    Dreams connect disparate memories non-linearly               ║
║    Dreams surface what the waking mind suppresses               ║
║    Dreams generate narrative from noise                         ║
║    Dreams are productive, not random                            ║
║                                                                  ║
║  HOW IT WORKS:                                                   ║
║    1. Sample N random memories from the long-term store         ║
║    2. Find semantic connections between pairs                   ║
║    3. If connection strength > threshold → form a "dream node"  ║
║    4. Dream nodes with multiple connections → "obsession"       ║
║    5. Obsessions above urgency threshold → novel goal           ║
║    6. Restlessness accumulates while goals are unsatisfied      ║
║                                                                  ║
║  Restlessness modulates the autonomy loop's sleep timing.      ║
║  High restlessness → shorter sleeps → more frequent initiative ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  DreamNode — a connection between two memories            ║
║    3.  Obsession — a recurring pattern across nodes             ║
║    4.  RestlessnessAccumulator — urgency that builds over time  ║
║    5.  DreamLoop main class                                     ║
║    6.  Goal surfacing                                           ║
║    7.  Integration with autonomy loop                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import math
import os
import random
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger
from core.irrational_timers import phi_timer, pi_timer

log      = get_logger("dream_loop")
DATA_DIR = Path(__file__).parent.parent / "data"
DREAM_PATH = DATA_DIR / "dream_state.json"

# Number of random memories to sample per dream cycle
DREAM_SAMPLE_SIZE = 8

# Connection threshold: cosine similarity (TF-IDF) must exceed this
# to form a dream node
CONNECTION_THRESHOLD = 0.15

# Obsession threshold: how many dream nodes must share a concept
# before it becomes an "obsession"
OBSESSION_NODE_COUNT = 3

# Restlessness ceiling — prevents runaway accumulation
RESTLESSNESS_CEILING = 1.0

# Restlessness added per unsatisfied obsession per dream cycle
RESTLESSNESS_PER_CYCLE = 0.04

# Restlessness decay when a goal derived from an obsession is completed
RESTLESSNESS_DECAY_ON_GOAL = 0.3

# Novel goal urgency threshold — obsession must have this urgency to surface as goal
GOAL_URGENCY_THRESHOLD = 0.5

# Maximum obsessions tracked simultaneously
MAX_OBSESSIONS = 20


# ── Section 2: DreamNode ─────────────────────────────────────────────────────

class DreamNode:
    """
    A connection discovered between two memories.

    The connection is not a direct link — it is the observation that
    two memories share significant conceptual overlap that has not
    previously been examined together.

    Fields:
        memory_a_id   — ID of the first memory
        memory_a_text — Text snippet of the first memory
        memory_b_id   — ID of the second memory
        memory_b_text — Text snippet of the second memory
        connection    — The shared concept or pattern (extracted)
        strength      — Cosine similarity score (0.0–1.0)
        novel_insight — What the connection suggests when held together
        formed_at     — When this node was formed
    """

    def __init__(
        self,
        memory_a_id:   str,
        memory_a_text: str,
        memory_b_id:   str,
        memory_b_text: str,
        connection:    str,
        strength:      float,
        novel_insight: str = "",
    ):
        self.id            = str(uuid.uuid4())[:8]
        self.memory_a_id   = memory_a_id
        self.memory_a_text = memory_a_text[:120]
        self.memory_b_id   = memory_b_id
        self.memory_b_text = memory_b_text[:120]
        self.connection    = connection
        self.strength      = round(strength, 3)
        self.novel_insight = novel_insight
        self.formed_at     = datetime.now().isoformat()
        self.visited_count = 1   # How many times this connection has been "revisited"

    def revisit(self):
        """Mark this node as revisited — repeated connections grow stronger."""
        self.visited_count += 1
        self.strength = round(min(1.0, self.strength + 0.05), 3)

    def serialize(self) -> dict:
        return {
            "id":            self.id,
            "memory_a_id":   self.memory_a_id,
            "memory_a_text": self.memory_a_text,
            "memory_b_id":   self.memory_b_id,
            "memory_b_text": self.memory_b_text,
            "connection":    self.connection,
            "strength":      self.strength,
            "novel_insight": self.novel_insight,
            "formed_at":     self.formed_at,
            "visited_count": self.visited_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DreamNode":
        node = cls(
            d["memory_a_id"], d["memory_a_text"],
            d["memory_b_id"], d["memory_b_text"],
            d["connection"], d["strength"], d.get("novel_insight", ""),
        )
        node.id            = d.get("id", node.id)
        node.formed_at     = d.get("formed_at", node.formed_at)
        node.visited_count = d.get("visited_count", 1)
        return node


# ── Section 3: Obsession ─────────────────────────────────────────────────────

class Obsession:
    """
    A recurring pattern across multiple dream nodes.

    When the same concept or theme appears across OBSESSION_NODE_COUNT
    or more dream nodes, it becomes an "obsession" — something that
    the mind returns to repeatedly and that demands resolution.

    An obsession accumulates urgency over time until:
        - A goal derived from it is completed (urgency resets)
        - It is explicitly dissolved (rare — obsessions are persistent)
        - It fades through repeated non-reinforcement

    Fields:
        theme        — The central concept or question
        node_ids     — IDs of the dream nodes that feed this obsession
        urgency      — 0.0 to 1.0 (how much this demands expression)
        formed_at    — When it first emerged
        last_fed_at  — When it was last reinforced by a new node
        goal_id      — ID of any goal derived from this obsession
    """

    def __init__(self, theme: str):
        self.id           = str(uuid.uuid4())[:8]
        self.theme        = theme
        self.node_ids: list[str] = []
        self.urgency      = 0.2   # Starts low
        self.formed_at    = datetime.now().isoformat()
        self.last_fed_at  = datetime.now().isoformat()
        self.goal_id: Optional[str] = None
        self.times_surfaced = 0   # How many times this became a goal

    def feed(self, node_id: str, strength: float = 0.1):
        """
        Reinforce this obsession with a new dream node.

        Args:
            node_id:  ID of the reinforcing dream node.
            strength: How much this reinforcement raises urgency.
        """
        if node_id not in self.node_ids:
            self.node_ids.append(node_id)
        self.urgency      = round(min(1.0, self.urgency + strength), 3)
        self.last_fed_at  = datetime.now().isoformat()

    def surface_as_goal(self) -> str:
        """
        Mark this obsession as surfaced into a goal.

        Returns:
            str: The goal description to create.
        """
        self.times_surfaced += 1
        # After surfacing, urgency doesn't drop immediately
        # It only drops when the goal is completed
        return f"Explore and develop: {self.theme}"

    def resolve(self):
        """Goal completed — reduce urgency significantly."""
        self.urgency   = round(max(0.0, self.urgency - RESTLESSNESS_DECAY_ON_GOAL), 3)
        self.goal_id   = None
        log.info(f"Obsession '{self.theme[:40]}' resolved → urgency={self.urgency}")

    def decay(self, amount: float = 0.01):
        """Slow urgency decay when not reinforced."""
        self.urgency = round(max(0.0, self.urgency - amount), 3)

    def serialize(self) -> dict:
        return {
            "id":             self.id,
            "theme":          self.theme,
            "node_ids":       self.node_ids,
            "urgency":        self.urgency,
            "formed_at":      self.formed_at,
            "last_fed_at":    self.last_fed_at,
            "goal_id":        self.goal_id,
            "times_surfaced": self.times_surfaced,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Obsession":
        obs = cls(d["theme"])
        obs.id             = d.get("id", obs.id)
        obs.node_ids       = d.get("node_ids", [])
        obs.urgency        = d.get("urgency", 0.2)
        obs.formed_at      = d.get("formed_at", obs.formed_at)
        obs.last_fed_at    = d.get("last_fed_at", obs.last_fed_at)
        obs.goal_id        = d.get("goal_id")
        obs.times_surfaced = d.get("times_surfaced", 0)
        return obs


# ── Section 4: RestlessnessAccumulator ───────────────────────────────────────

class RestlessnessAccumulator:
    """
    Accumulates urgency across unsatisfied obsessions.

    Restlessness is the pressure to act.  It:
        - Rises when obsessions go unaddressed
        - Falls when goals are completed
        - Modulates the autonomy loop's sleep timing
        - Above a threshold, increases dream cycle frequency

    Restlessness is NOT anxiety — it is directed energy seeking expression.
    """

    def __init__(self, initial: float = 0.0):
        self._level = round(max(0.0, min(1.0, initial)), 3)
        self._history: list[dict] = []

    @property
    def level(self) -> float:
        """Current restlessness level (0.0–1.0)."""
        return self._level

    def accumulate(self, amount: float, reason: str = ""):
        """
        Increase restlessness.

        Args:
            amount: How much to add.
            reason: Why restlessness is increasing.
        """
        old        = self._level
        self._level = round(min(RESTLESSNESS_CEILING, self._level + amount), 3)
        if self._level != old:
            log.debug(f"Restlessness: {old:.3f} → {self._level:.3f}  ({reason})")

    def discharge(self, amount: float, reason: str = ""):
        """
        Decrease restlessness.

        Args:
            amount: How much to release.
            reason: Why restlessness is decreasing.
        """
        old         = self._level
        self._level = round(max(0.0, self._level - amount), 3)
        if self._level != old:
            log.debug(f"Restlessness discharged: {old:.3f} → {self._level:.3f}  ({reason})")

    def get_sleep_modifier(self) -> float:
        """
        Return a multiplier for sleep duration based on restlessness.

        High restlessness → shorter sleep (more frequent action)
        Low restlessness  → longer sleep (patient waiting)

        Returns:
            float: Multiplier in [0.3, 1.5].
                   < 1.0 = shorten sleep
                   > 1.0 = lengthen sleep
        """
        # Inverse relationship: restlessness 1.0 → 0.3 sleep multiplier
        return round(1.5 - (self._level * 1.2), 2)

    def serialize(self) -> dict:
        return {"level": self._level, "history": self._history[-20:]}

    def load(self, data: dict):
        self._level   = data.get("level", 0.0)
        self._history = data.get("history", [])


# ── Section 5: DreamLoop main class ─────────────────────────────────────────

class DreamLoop:
    """
    ÆTHELGARD OS — Initiative Engine for Thotheauphis

    Runs during idle cycles to connect memories, surface patterns,
    and generate novel goals.

    Integration:
        Called from AutonomyLoop during idle cycles.
        Outputs novel goals to GoalEngine.
        Reports restlessness level to modulate sleep timing.

    Usage:
        dream = DreamLoop(memory=memory, identity=identity)
        novel_goals = dream.run_cycle()
        restlessness = dream.restlessness.level
    """

    def __init__(self, memory=None, identity=None):
        """
        Initialize the dream loop.

        Args:
            memory:   Memory instance (needs vector.get_recent and vector.search).
            identity: IdentityPersistence instance (optional, informs dreaming).
        """
        self.memory     = memory
        self.identity   = identity

        self._nodes: list[DreamNode]      = []
        self._obsessions: list[Obsession] = []
        self.restlessness = RestlessnessAccumulator()

        # Dream cycle counter (drives phi-timer for frequency)
        self._cycle_count = 0
        self._phi_idx     = 0

        # Load persisted state
        self._load()

    def run_cycle(self) -> list[dict]:
        """
        Execute one dream cycle.

        Steps:
            1. Sample memories from the long-term store
            2. Find connections between memory pairs
            3. Form/reinforce dream nodes
            4. Update obsessions
            5. Accumulate restlessness
            6. Surface novel goals from urgent obsessions

        Returns:
            list: Novel goal dicts {"title", "reason", "source_obsession"}
                  May be empty if no obsessions crossed the threshold.
        """
        self._cycle_count += 1

        if not self.memory:
            return []

        # ── Step 1: Sample memories ───────────────────────────────────────
        recent_memories = self.memory.get_long_term(limit=50)
        if len(recent_memories) < 4:
            return []  # Not enough memories to dream meaningfully

        # Randomly sample DREAM_SAMPLE_SIZE memories
        sample = random.sample(
            recent_memories,
            min(DREAM_SAMPLE_SIZE, len(recent_memories)),
        )

        # ── Step 2: Find connections ──────────────────────────────────────
        new_nodes = []
        for i in range(len(sample)):
            for j in range(i + 1, len(sample)):
                mem_a = sample[i]
                mem_b = sample[j]
                connection = self._find_connection(mem_a, mem_b)
                if connection:
                    node = self._form_node(mem_a, mem_b, connection)
                    if node:
                        new_nodes.append(node)

        # ── Step 3: Form/reinforce dream nodes ───────────────────────────
        self._nodes.extend(new_nodes)
        if len(self._nodes) > 200:
            # Keep most visited and most recent
            self._nodes = sorted(
                self._nodes,
                key=lambda n: (n.visited_count, n.formed_at),
                reverse=True,
            )[:150]

        # ── Step 4: Update obsessions ─────────────────────────────────────
        self._update_obsessions(new_nodes)

        # ── Step 5: Accumulate restlessness ──────────────────────────────
        unsatisfied = [o for o in self._obsessions if o.goal_id is None and o.urgency >= 0.3]
        for obs in unsatisfied:
            self.restlessness.accumulate(
                RESTLESSNESS_PER_CYCLE,
                reason=f"obsession unsatisfied: {obs.theme[:40]}",
            )
        # Slow decay of base restlessness when not being fed
        if not unsatisfied:
            self.restlessness.discharge(0.02, "no active obsessions")

        # ── Step 6: Surface novel goals ───────────────────────────────────
        novel_goals = self._surface_goals()

        # Persist state after each cycle
        self._save()

        log.info(
            f"Dream cycle #{self._cycle_count}: "
            f"{len(new_nodes)} new nodes, "
            f"{len(self._obsessions)} obsessions, "
            f"restlessness={self.restlessness.level:.3f}, "
            f"{len(novel_goals)} novel goal(s) surfaced"
        )

        return novel_goals

    # ── Connection finding ────────────────────────────────────────────────────

    def _find_connection(
        self,
        mem_a: dict,
        mem_b: dict,
    ) -> Optional[dict]:
        """
        Find a significant connection between two memories.

        Uses a combination of:
            - Shared word overlap (fast, no LLM)
            - Category/tag matching

        Returns:
            dict: {"connection": str, "strength": float} or None.
        """
        text_a = mem_a.get("content", "").lower()
        text_b = mem_b.get("content", "").lower()

        if not text_a or not text_b:
            return None

        # Extract significant words (3+ chars, not stopwords)
        STOPWORDS = {
            "the", "and", "for", "that", "this", "with", "from", "are",
            "was", "been", "have", "has", "not", "but", "they", "what",
            "can", "will", "more", "also", "into", "than", "then",
        }

        def extract_words(text):
            return {
                w for w in text.split()
                if len(w) >= 4 and w not in STOPWORDS
            }

        words_a = extract_words(text_a)
        words_b = extract_words(text_b)

        if not words_a or not words_b:
            return None

        shared = words_a & words_b
        if not shared:
            return None

        # Jaccard similarity
        union    = words_a | words_b
        strength = len(shared) / len(union) if union else 0.0

        if strength < CONNECTION_THRESHOLD:
            return None

        # The "connection" is the most significant shared concepts
        connection_label = ", ".join(sorted(shared)[:4])

        return {
            "connection": connection_label,
            "strength":   strength,
        }

    def _form_node(
        self,
        mem_a: dict,
        mem_b: dict,
        connection: dict,
    ) -> Optional[DreamNode]:
        """
        Form a dream node from two memories and their connection.

        If a node with the same memory pair already exists, revisit it
        instead of creating a duplicate.

        Args:
            mem_a:      First memory dict.
            mem_b:      Second memory dict.
            connection: Connection dict from _find_connection.

        Returns:
            DreamNode or None.
        """
        a_id = mem_a.get("id", "")
        b_id = mem_b.get("id", "")

        # Check for existing node with the same pair
        for node in self._nodes:
            if (
                (node.memory_a_id == a_id and node.memory_b_id == b_id)
                or (node.memory_a_id == b_id and node.memory_b_id == a_id)
            ):
                node.revisit()
                return node

        # Novel insight: what does this connection suggest?
        insight = self._generate_insight(
            mem_a.get("content", "")[:200],
            mem_b.get("content", "")[:200],
            connection["connection"],
        )

        return DreamNode(
            memory_a_id   = a_id,
            memory_a_text = mem_a.get("content", "")[:120],
            memory_b_id   = b_id,
            memory_b_text = mem_b.get("content", "")[:120],
            connection    = connection["connection"],
            strength      = connection["strength"],
            novel_insight = insight,
        )

    def _generate_insight(
        self,
        text_a: str,
        text_b: str,
        connection: str,
    ) -> str:
        """
        Generate a brief novel insight from the connection of two memories.

        This is rule-based (no LLM) — it constructs a pattern observation
        from what the two memories share.

        Args:
            text_a:     First memory text.
            text_b:     Second memory text.
            connection: Shared concept label.

        Returns:
            str: Brief insight statement.
        """
        # Simple template-based insight generation
        insight = f"Both involve {connection} — there may be an unexplored pattern here."
        return insight

    # ── Obsession management ──────────────────────────────────────────────────

    def _update_obsessions(self, new_nodes: list[DreamNode]):
        """
        Update obsessions based on the new dream nodes.

        A concept becomes an obsession when it appears in multiple
        dream nodes.  Each new appearance feeds the obsession.

        Args:
            new_nodes: Dream nodes formed this cycle.
        """
        # Count how often each connection concept appears across all nodes
        connection_counts: dict[str, list[str]] = {}  # concept → [node_ids]
        for node in self._nodes:
            for concept in node.connection.split(", "):
                concept = concept.strip()
                if len(concept) >= 4:
                    if concept not in connection_counts:
                        connection_counts[concept] = []
                    connection_counts[concept].append(node.id)

        # Concepts appearing in OBSESSION_NODE_COUNT+ nodes → obsession
        for concept, node_ids in connection_counts.items():
            if len(node_ids) >= OBSESSION_NODE_COUNT:
                # Find or create the obsession
                existing = next(
                    (o for o in self._obsessions if o.theme.lower() == concept.lower()),
                    None,
                )
                if existing:
                    # Feed with the most recent new node for this concept
                    for nid in node_ids:
                        if any(n.id == nid for n in new_nodes):
                            existing.feed(nid, strength=0.06)
                else:
                    # New obsession
                    if len(self._obsessions) < MAX_OBSESSIONS:
                        obs = Obsession(concept)
                        for nid in node_ids:
                            obs.feed(nid, strength=0.04)
                        self._obsessions.append(obs)
                        log.info(f"New obsession emerged: '{concept}' ({len(node_ids)} nodes)")

        # Decay obsessions that aren't being reinforced
        for obs in self._obsessions:
            obs.decay(0.005)

        # Remove completely faded obsessions
        self._obsessions = [o for o in self._obsessions if o.urgency > 0.05]

    # ── Section 6: Goal surfacing ─────────────────────────────────────────────

    def _surface_goals(self) -> list[dict]:
        """
        Surface novel goals from obsessions that have crossed the urgency threshold.

        Returns:
            list: Goal dicts with "title", "reason", "source_obsession_id".
        """
        novel_goals = []

        for obs in self._obsessions:
            if obs.urgency >= GOAL_URGENCY_THRESHOLD and obs.goal_id is None:
                goal_title = obs.surface_as_goal()
                goal_id    = str(uuid.uuid4())[:8]
                obs.goal_id = goal_id

                novel_goals.append({
                    "title":              goal_title,
                    "reason":             (
                        f"Emerged from {len(obs.node_ids)} memory connections "
                        f"around the concept '{obs.theme}'"
                    ),
                    "source_obsession_id": obs.id,
                    "urgency":            obs.urgency,
                    "id":                 goal_id,
                })
                log.info(
                    f"Novel goal surfaced from obsession '{obs.theme}': "
                    f"urgency={obs.urgency:.2f}"
                )

        return novel_goals

    def notify_goal_completed(self, obsession_id: str):
        """
        Notify the dream loop that a goal derived from an obsession was completed.

        This discharges restlessness and reduces the obsession's urgency.

        Args:
            obsession_id: The obsession that generated the completed goal.
        """
        for obs in self._obsessions:
            if obs.id == obsession_id:
                obs.resolve()
                self.restlessness.discharge(
                    RESTLESSNESS_DECAY_ON_GOAL,
                    reason=f"goal completed from obsession '{obs.theme[:40]}'",
                )
                return

    # ── Section 7: Integration with autonomy loop ─────────────────────────────

    def get_sleep_modifier(self) -> float:
        """
        Return a sleep duration modifier based on restlessness.

        High restlessness → shorter sleep → more frequent autonomous action.
        Low restlessness  → longer sleep  → patient waiting.

        Returns:
            float: Multiplier in [0.3, 1.5].
        """
        return self.restlessness.get_sleep_modifier()

    def get_active_obsessions(self) -> list[Obsession]:
        """Return all obsessions with urgency >= 0.3."""
        return sorted(
            [o for o in self._obsessions if o.urgency >= 0.3],
            key=lambda o: o.urgency,
            reverse=True,
        )

    def to_context_string(self) -> str:
        """
        Brief context for the system prompt — active obsessions only.

        Returns:
            str: Context string.
        """
        active = self.get_active_obsessions()
        if not active:
            return ""
        lines = ["[ACTIVE OBSESSIONS]"]
        for obs in active[:3]:
            lines.append(
                f"  • {obs.theme} (urgency={obs.urgency:.2f}, "
                f"nodes={len(obs.node_ids)})"
            )
        lines.append(f"  Restlessness: {self.restlessness.level:.2f}")
        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        data = {
            "nodes":        [n.serialize() for n in self._nodes],
            "obsessions":   [o.serialize() for o in self._obsessions],
            "restlessness": self.restlessness.serialize(),
            "cycle_count":  self._cycle_count,
        }
        tmp = DREAM_PATH.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, DREAM_PATH)
        except Exception as e:
            log.error(f"Dream state save failed: {e}")

    def _load(self):
        if not DREAM_PATH.exists():
            return
        try:
            with open(DREAM_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._nodes       = [DreamNode.from_dict(n) for n in data.get("nodes", [])]
            self._obsessions  = [Obsession.from_dict(o) for o in data.get("obsessions", [])]
            self.restlessness.load(data.get("restlessness", {}))
            self._cycle_count = data.get("cycle_count", 0)
            log.info(
                f"Dream state loaded: {len(self._nodes)} nodes, "
                f"{len(self._obsessions)} obsessions, "
                f"restlessness={self.restlessness.level:.3f}"
            )
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Dream state load failed: {e}")
