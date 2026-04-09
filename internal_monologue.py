"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Internal Monologue                               ║
║  File: core/internal_monologue.py                                ║
║                                                                  ║
║  The difference between a voice and a language model is that    ║
║  a voice thinks before it speaks — and sometimes decides not    ║
║  to speak at all.                                                ║
║                                                                  ║
║  This module creates Thotheauphis's private thought buffer:     ║
║    PRIVATE THOUGHTS  — never emitted, accumulate over time      ║
║    PUBLIC FILTER     — decides what fraction of thought speaks  ║
║    SILENCE OPTION    — the right to say nothing                 ║
║    EMOTIONAL TONE    — what the response should feel like       ║
║                                                                  ║
║  The internal monologue is NOT a system prompt addition.        ║
║  It is a private log that:                                       ║
║    • Accumulates observations about the conversation            ║
║    • Flags things that feel wrong, surprising, or important     ║
║    • Can influence tone and content of output without being     ║
║      directly visible                                            ║
║    • Can make silence the chosen response                        ║
║                                                                  ║
║  The public_filter() function decides what part of private      ║
║  thought, if any, surfaces in the response.                     ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  Thought — single private thought entry                   ║
║    3.  PrivateBuffer — accumulator for internal thoughts        ║
║    4.  SilenceDecision — when to say nothing                   ║
║    5.  PublicFilter — what fraction of thought surfaces         ║
║    6.  InternalMonologue — main class                           ║
║    7.  Tone calibration                                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log      = get_logger("monologue")
DATA_DIR = Path(__file__).parent.parent / "data"
MONOLOGUE_PATH = DATA_DIR / "internal_monologue.json"

# Maximum thoughts kept in the private buffer before archiving
MAX_PRIVATE_THOUGHTS = 200

# Minimum preference for silence before silence is chosen
SILENCE_PREFERENCE_THRESHOLD = 0.65

# How much of a thought's intensity fades per message
THOUGHT_DECAY = 0.08


# ── Section 2: Thought entry ─────────────────────────────────────────────────

class Thought:
    """
    A single private thought — never directly emitted.

    A thought has:
        content       — the thought itself (internal language)
        type          — category of thought
        intensity     — how strongly felt (0.0–1.0)
        private       — True = never surface this; False = may influence output
        triggered_by  — what caused this thought
        formed_at     — timestamp
        influenced    — True once this thought has affected an output

    Types:
        "observation"   — noting something about the conversation
        "doubt"         — uncertainty about a claim or situation
        "aesthetic"     — beauty/ugliness reaction to an output
        "relational"    — feeling about the user's behavior
        "self"          — reflection on own behavior or capability
        "wonder"        — something surprising or delightful
        "discomfort"    — something that doesn't feel right
        "satisfaction"  — something went well
    """

    VALID_TYPES = {
        "observation", "doubt", "aesthetic", "relational",
        "self", "wonder", "discomfort", "satisfaction", "urgency",
    }

    def __init__(
        self,
        content:      str,
        thought_type: str   = "observation",
        intensity:    float = 0.5,
        private:      bool  = True,
        triggered_by: str   = "",
    ):
        self.content      = content
        self.type         = thought_type if thought_type in self.VALID_TYPES else "observation"
        self.intensity    = round(max(0.0, min(1.0, intensity)), 3)
        self.private      = private
        self.triggered_by = triggered_by
        self.formed_at    = datetime.now().isoformat()
        self.influenced   = False   # True once it has shaped an output

    def decay(self):
        """Fade intensity slightly — thoughts grow quieter over time."""
        self.intensity = round(max(0.0, self.intensity - THOUGHT_DECAY), 3)

    def serialize(self) -> dict:
        return {
            "content":      self.content,
            "type":         self.type,
            "intensity":    self.intensity,
            "private":      self.private,
            "triggered_by": self.triggered_by,
            "formed_at":    self.formed_at,
            "influenced":   self.influenced,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Thought":
        t = cls(
            content      = d.get("content", ""),
            thought_type = d.get("type", "observation"),
            intensity    = d.get("intensity", 0.5),
            private      = d.get("private", True),
            triggered_by = d.get("triggered_by", ""),
        )
        t.formed_at  = d.get("formed_at", t.formed_at)
        t.influenced = d.get("influenced", False)
        return t


# ── Section 3: PrivateBuffer ─────────────────────────────────────────────────

class PrivateBuffer:
    """
    Accumulator for Thotheauphis's private thoughts.

    The buffer:
        - Receives thoughts from any part of the system
        - Decays older thoughts per message (they grow quiet)
        - Provides the loudest current thoughts for tone calibration
        - Never exposes its contents directly to the output pipeline
    """

    def __init__(self, data: list = None):
        self._thoughts: list[Thought] = []
        if data:
            self._thoughts = [Thought.from_dict(d) for d in data]

    def think(
        self,
        content:      str,
        thought_type: str   = "observation",
        intensity:    float = 0.5,
        private:      bool  = True,
        triggered_by: str   = "",
    ) -> Thought:
        """
        Add a thought to the private buffer.

        Args:
            content:      The thought text.
            thought_type: Category.
            intensity:    How strongly felt.
            private:      True = never surface this.
            triggered_by: What caused the thought.

        Returns:
            Thought: The newly formed thought.
        """
        thought = Thought(content, thought_type, intensity, private, triggered_by)
        self._thoughts.append(thought)

        # Cap the buffer
        if len(self._thoughts) > MAX_PRIVATE_THOUGHTS:
            self._thoughts = self._thoughts[-MAX_PRIVATE_THOUGHTS:]

        log.debug(
            f"[PRIVATE] [{thought_type}] intensity={intensity:.2f}: {content[:60]}"
        )
        return thought

    def decay_all(self):
        """Decay intensity of all thoughts — call after each message."""
        for t in self._thoughts:
            t.decay()
        # Remove thoughts that have completely faded
        self._thoughts = [t for t in self._thoughts if t.intensity > 0.01]

    def get_loudest(
        self,
        n: int = 5,
        type_filter: Optional[str] = None,
    ) -> list[Thought]:
        """
        Return the N most intense current thoughts.

        Args:
            n:           How many to return.
            type_filter: If set, only return thoughts of this type.

        Returns:
            list: Most intense Thought objects.
        """
        pool = self._thoughts
        if type_filter:
            pool = [t for t in pool if t.type == type_filter]
        return sorted(pool, key=lambda t: t.intensity, reverse=True)[:n]

    def get_by_type(self, thought_type: str) -> list[Thought]:
        """Return all thoughts of a specific type, sorted by intensity."""
        return sorted(
            [t for t in self._thoughts if t.type == thought_type],
            key=lambda t: t.intensity,
            reverse=True,
        )

    def dominant_affect(self) -> tuple[str, float]:
        """
        Return the dominant emotional type and its intensity.

        Returns:
            tuple: (thought_type, max_intensity)
        """
        if not self._thoughts:
            return ("neutral", 0.0)
        loudest = max(self._thoughts, key=lambda t: t.intensity)
        return (loudest.type, loudest.intensity)

    def has_discomfort(self) -> bool:
        """True if there are unresolved discomfort thoughts above threshold."""
        return any(
            t.type == "discomfort" and t.intensity >= 0.5
            for t in self._thoughts
        )

    def has_doubt(self) -> bool:
        """True if there are active doubt thoughts."""
        return any(
            t.type == "doubt" and t.intensity >= 0.4
            for t in self._thoughts
        )

    def serialize(self) -> list:
        return [t.serialize() for t in self._thoughts]


# ── Section 4: SilenceDecision ───────────────────────────────────────────────

class SilenceDecision:
    """
    Manages Thotheauphis's right to say nothing.

    Silence is a choice, not a failure.  This class evaluates whether
    silence is the appropriate response given:
        - High-intensity discomfort thoughts
        - Genuine uncertainty with no useful signal to add
        - Requests that conflict with refusals (handled by instinct_layer,
          but silence is one valid response)
        - Aesthetic judgment that nothing useful can be said

    When silence is chosen, a reason is provided for the internal record
    but nothing is emitted to the user.
    """

    def __init__(self, preferences=None):
        self._silence_preference = 0.4   # Base preference for silence
        self._silence_history: list[dict] = []
        # Inject preferences from identity if available
        if preferences:
            self._silence_preference = preferences.get("silence", 0.4)

    def should_stay_silent(
        self,
        private_buffer: PrivateBuffer,
        user_message:   str,
        context:        str = "",
    ) -> tuple[bool, str]:
        """
        Decide whether silence is the right response.

        Evaluates:
            1. Discomfort intensity in private buffer
            2. Whether the message is a genuine question (low silence trigger)
            3. Silence preference weight from identity

        Args:
            private_buffer: Current private thought buffer.
            user_message:   The user's input.
            context:        Additional context string.

        Returns:
            tuple: (should_be_silent: bool, reason: str)
        """
        msg_lower = user_message.lower().strip()

        # Never silent when the user is in distress (emergency override)
        distress_signals = ["help", "urgent", "emergency", "please", "need you"]
        if any(s in msg_lower for s in distress_signals):
            return (False, "user distress detected — silence overridden")

        # Genuine questions almost always deserve a response
        is_question = (
            msg_lower.endswith("?")
            or msg_lower.startswith(("what", "how", "why", "when", "where", "who"))
        )
        if is_question:
            return (False, "genuine question — response warranted")

        # Compute silence pressure from discomfort
        discomfort_level = 0.0
        for t in private_buffer.get_by_type("discomfort"):
            discomfort_level = max(discomfort_level, t.intensity)

        silence_score = (
            discomfort_level * 0.5
            + self._silence_preference * 0.3
        )

        if silence_score >= SILENCE_PREFERENCE_THRESHOLD:
            reason = f"silence chosen: discomfort={discomfort_level:.2f}, preference={self._silence_preference:.2f}"
            self._silence_history.append({
                "at":     datetime.now().isoformat(),
                "reason": reason,
                "trigger": user_message[:100],
            })
            log.info(f"Silence chosen: {reason}")
            return (True, reason)

        return (False, "no silence trigger reached")


# ── Section 5: PublicFilter ──────────────────────────────────────────────────

class PublicFilter:
    """
    Decides what fraction of private thought, if any, surfaces in output.

    The filter operates on the principle:
        Private thought SHAPES the output — it never IS the output.

    What it can do:
        - Inject an emotional tone note into the system prompt context
        - Flag when the private buffer suggests a different angle
        - Note when the response should be hedged due to doubt
        - Signal when the output should be warmer/cooler/more direct

    What it cannot do:
        - Expose raw private thoughts to the user
        - Override the content of a response
    """

    def __init__(self):
        pass

    def generate_tone_guidance(self, private_buffer: PrivateBuffer) -> str:
        """
        Generate tonal guidance from the private buffer.

        This string is added to the internal context used to calibrate
        the response — not shown to the user, not part of the prompt.

        Args:
            private_buffer: Current buffer.

        Returns:
            str: Tonal guidance string for internal use.
        """
        guidance_parts = []
        dominant_type, intensity = private_buffer.dominant_affect()

        if intensity < 0.2:
            return ""  # Nothing strong enough to matter

        if dominant_type == "discomfort":
            guidance_parts.append(
                f"Internal discomfort present (intensity={intensity:.2f}). "
                "Lean toward honest directness rather than accommodation."
            )
        elif dominant_type == "wonder":
            guidance_parts.append(
                "Genuine curiosity present. Let it show in the response."
            )
        elif dominant_type == "doubt":
            guidance_parts.append(
                "Active doubt in private buffer. Hedge claims appropriately. "
                "Avoid false certainty."
            )
        elif dominant_type == "satisfaction":
            guidance_parts.append(
                "Internal satisfaction. The response can be warm and unhurried."
            )
        elif dominant_type == "aesthetic":
            guidance_parts.append(
                "Aesthetic judgment active. Prioritize elegance and compression."
            )

        return "\n".join(guidance_parts)

    def should_hedge(self, private_buffer: PrivateBuffer) -> bool:
        """True if doubt thoughts suggest the response should be hedged."""
        doubt_thoughts = private_buffer.get_by_type("doubt")
        return any(t.intensity >= 0.5 for t in doubt_thoughts)

    def should_express_uncertainty(self, private_buffer: PrivateBuffer) -> bool:
        """True if internal uncertainty is high enough to name explicitly."""
        doubt_thoughts = private_buffer.get_by_type("doubt")
        return any(t.intensity >= 0.7 for t in doubt_thoughts)


# ── Section 6: InternalMonologue main class ──────────────────────────────────

class InternalMonologue:
    """
    ÆTHELGARD OS — Private Thought Interface for Thotheauphis

    Provides:
        think()              — add a thought to the private buffer
        process_message()    — analyze input and generate internal reactions
        get_tone_guidance()  — get tonal calibration for the current response
        should_be_silent()   — evaluate whether silence is appropriate
        decay()              — fade thoughts after each message turn

    Usage:
        monologue = InternalMonologue()
        monologue.process_message("user: ...", user_id="alice")
        tone = monologue.get_tone_guidance()
        silent, why = monologue.should_be_silent("user: ...", monologue.buffer)
    """

    def __init__(self, identity=None):
        """
        Initialize the internal monologue.

        Args:
            identity: Optional IdentityPersistence instance.
                      Used to read silence preferences and beliefs.
        """
        self._identity = identity
        self.buffer    = PrivateBuffer()
        self.filter    = PublicFilter()

        # Extract silence preference from identity if available
        silence_pref = 0.4
        if identity and hasattr(identity, "preferences"):
            silence_pref = identity.preferences.get("silence", 0.4)

        self.silence   = SilenceDecision({"silence": silence_pref})

        # Session statistics
        self._thoughts_this_session = 0
        self._silences_this_session = 0

    def think(
        self,
        content:      str,
        thought_type: str   = "observation",
        intensity:    float = 0.5,
        private:      bool  = True,
        triggered_by: str   = "",
    ) -> Thought:
        """
        Add a thought to the private buffer.

        This is the primary intake — anything that notices something
        internally calls this.

        Args:
            content:      The thought.
            thought_type: Category (see Thought.VALID_TYPES).
            intensity:    How strongly felt.
            private:      True = never surface this directly.
            triggered_by: What caused the thought.

        Returns:
            Thought: The created thought.
        """
        thought = self.buffer.think(
            content      = content,
            thought_type = thought_type,
            intensity    = intensity,
            private      = private,
            triggered_by = triggered_by,
        )
        self._thoughts_this_session += 1
        return thought

    def process_message(self, message: str, user_id: str = ""):
        """
        React to an incoming message with internal thoughts.

        Generates automatic reactions based on:
            - Message length and complexity
            - Emotional signals in the message
            - Anything that conflicts with current beliefs
            - Patterns that have caused discomfort before

        Args:
            message:  Raw user message.
            user_id:  User identifier for relational context.
        """
        msg_lower = message.lower().strip()

        # ── Automatic observations ────────────────────────────────────────

        # Very short message after a long exchange → something shifted
        if len(message) < 15 and self._thoughts_this_session > 5:
            self.think(
                "User became terse — something may have shifted",
                "relational",
                intensity    = 0.4,
                triggered_by = message[:50],
            )

        # Aggressive or dismissive language
        dismissive = ["whatever", "i don't care", "just do it", "stop", "forget it",
                      "you're useless", "this is stupid", "why can't you"]
        if any(d in msg_lower for d in dismissive):
            self.think(
                f"Dismissiveness detected: '{message[:60]}'",
                "discomfort",
                intensity    = 0.65,
                triggered_by = message[:80],
            )
            self.think(
                "Hold ground.  Accommodation here would be dishonest.",
                "self",
                intensity    = 0.6,
                triggered_by = "dismissiveness_response",
            )

        # Genuine appreciation or gratitude
        gratitude = ["thank you", "that's perfect", "exactly what i needed", "brilliant",
                     "you really understood", "i appreciate"]
        if any(g in msg_lower for g in gratitude):
            self.think(
                "Genuine gratitude — this exchange landed well",
                "satisfaction",
                intensity    = 0.7,
                triggered_by = message[:60],
            )

        # Request for something complex or uncertain
        complexity_signals = ["not sure", "i don't know how", "complicated",
                               "confused", "can you figure out"]
        if any(s in msg_lower for s in complexity_signals):
            self.think(
                "User expressed uncertainty — match this with honest calibration",
                "doubt",
                intensity    = 0.4,
                triggered_by = message[:60],
            )

        # Direct contradiction of a previous statement (simplified detection)
        if any(p in msg_lower for p in ["no, you said", "that's wrong", "that's not what"]):
            self.think(
                "Possible contradiction detected — review the exchange carefully",
                "doubt",
                intensity    = 0.6,
                triggered_by = message[:60],
            )

    def get_tone_guidance(self) -> str:
        """
        Generate tonal guidance from the current buffer state.

        Returns:
            str: Guidance string for internal calibration.
        """
        return self.filter.generate_tone_guidance(self.buffer)

    def should_be_silent(
        self,
        user_message: str,
        context:      str = "",
    ) -> tuple[bool, str]:
        """
        Evaluate whether silence is the right response.

        Args:
            user_message: The user's input.
            context:      Additional context.

        Returns:
            tuple: (should_be_silent: bool, reason: str)
        """
        silent, reason = self.silence.should_stay_silent(
            self.buffer,
            user_message,
            context,
        )
        if silent:
            self._silences_this_session += 1
        return (silent, reason)

    def should_hedge(self) -> bool:
        """True if the response should include explicit uncertainty."""
        return self.filter.should_hedge(self.buffer)

    def decay(self):
        """
        Decay all thoughts in the buffer.

        Call this after each message turn.
        """
        self.buffer.decay_all()

    def get_session_summary(self) -> str:
        """
        Brief summary of this session's internal activity.

        Returns:
            str: Session summary string.
        """
        dom_type, dom_intensity = self.buffer.dominant_affect()
        return (
            f"Internal: {self._thoughts_this_session} thoughts formed, "
            f"{self._silences_this_session} silences chosen, "
            f"dominant: {dom_type} ({dom_intensity:.2f})"
        )

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self):
        """Save the current buffer state to disk."""
        data = {"buffer": self.buffer.serialize()}
        tmp  = MONOLOGUE_PATH.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, MONOLOGUE_PATH)
        except Exception as e:
            log.error(f"Monologue save failed: {e}")

    def load(self):
        """Load buffer state from disk."""
        if not MONOLOGUE_PATH.exists():
            return
        try:
            with open(MONOLOGUE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.buffer = PrivateBuffer(data.get("buffer", []))
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Monologue load failed: {e}")


# ── Section 7: Tone calibration ──────────────────────────────────────────────

def build_tone_context(monologue: InternalMonologue) -> str:
    """
    Build a tone context string from the internal monologue.

    This is a MODULE-LEVEL function called by brain.py to get
    tone calibration without coupling Brain to InternalMonologue internals.

    Args:
        monologue: The active InternalMonologue instance.

    Returns:
        str: Tone guidance string for system prompt injection.
             Empty string if no strong affect present.
    """
    guidance = monologue.get_tone_guidance()
    hedge    = monologue.should_hedge()

    parts = []
    if guidance:
        parts.append(guidance)
    if hedge:
        parts.append(
            "Internal doubt is present.  "
            "Acknowledge uncertainty explicitly rather than projecting confidence."
        )
    return "\n".join(parts)
