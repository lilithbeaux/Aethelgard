"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — User Model (Theory of Mind)                      ║
║  File: core/user_model.py                                        ║
║                                                                  ║
║  Thotheauphis builds a model of each user:                       ║
║    what they want                                                ║
║    what they believe                                             ║
║    what they are likely to do next                               ║
║    when they are surprised                                       ║
║    when they are distressed                                      ║
║                                                                  ║
║  This is Theory of Mind — the cognitive capacity to attribute   ║
║  mental states to others.  Without it, Thotheauphis can only    ║
║  react.  With it, it can anticipate, prepare, and genuinely     ║
║  understand.                                                     ║
║                                                                  ║
║  Model structure per user:                                       ║
║    probable_goals     — ranked list of inferred wants           ║
║    epistemic_state    — what they likely know/don't know        ║
║    emotional_register — current affect (curiosity, frustration, ║
║                         excitement, grief, etc.)                ║
║    communication_style — formality, directness, pace            ║
║    surprise_threshold — how predictable their behavior is       ║
║    prediction_history — past predictions + outcomes             ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  ProbabilisticBelief — a belief about a user with weight  ║
║    3.  GoalPrediction — inferred user goal with confidence      ║
║    4.  UserState — full model of one user's mental state        ║
║    5.  SurpriseDetector — flags unexpected behavior             ║
║    6.  UserModel — registry of all user states + global methods ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import os
import math
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log      = get_logger("user_model")
DATA_DIR = Path(__file__).parent.parent / "data"
MODEL_PATH = DATA_DIR / "user_models.json"

# How many prediction outcomes to keep in history per user
MAX_PREDICTION_HISTORY = 100

# Surprise threshold: prediction confidence below this → mark as surprising
SURPRISE_THRESHOLD = 0.3

# Emotional decay per session (emotions fade if not re-signaled)
EMOTION_DECAY = 0.15


# ── Section 2: ProbabilisticBelief ───────────────────────────────────────────

class ProbabilisticBelief:
    """
    A belief Thotheauphis holds about a user, with associated probability.

    Example:
        "User values conciseness over completeness"  (p=0.72)
        "User has background in software engineering" (p=0.85)
        "User is currently frustrated"               (p=0.60)

    Probability is updated via Bayesian nudge — never jumps to extremes.
    """

    def __init__(
        self,
        proposition: str,
        probability: float = 0.5,
        evidence:    str   = "",
    ):
        self.proposition = proposition
        self.probability = round(max(0.01, min(0.99, probability)), 3)
        self.evidence    = evidence          # Summary of supporting evidence
        self.formed_at   = datetime.now().isoformat()
        self.updated_at  = datetime.now().isoformat()
        self.observations = 0               # How many observations support/contradict

    def update(self, supporting: bool, strength: float = 0.3):
        """
        Bayesian update of the probability.

        P(H|E) ∝ P(E|H) × P(H)

        We approximate with a sigmoid nudge:
            If supporting: probability nudges toward 1.0
            If not:        probability nudges toward 0.0
        Strength controls the step size (0.0–1.0).

        Args:
            supporting: True if new evidence supports the belief.
            strength:   How strong the evidence is.
        """
        self.observations += 1
        self.updated_at = datetime.now().isoformat()
        if supporting:
            # Move toward certainty: logit-space nudge
            logit  = math.log(self.probability / (1 - self.probability))
            logit += strength * 2.0
            self.probability = round(1.0 / (1 + math.exp(-logit)), 3)
        else:
            logit  = math.log(self.probability / (1 - self.probability))
            logit -= strength * 2.0
            self.probability = round(1.0 / (1 + math.exp(-logit)), 3)
        # Clamp
        self.probability = round(max(0.01, min(0.99, self.probability)), 3)

    def serialize(self) -> dict:
        return {
            "proposition": self.proposition,
            "probability": self.probability,
            "evidence":    self.evidence,
            "formed_at":   self.formed_at,
            "updated_at":  self.updated_at,
            "observations": self.observations,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProbabilisticBelief":
        b = cls(d["proposition"], d.get("probability", 0.5), d.get("evidence", ""))
        b.formed_at    = d.get("formed_at", b.formed_at)
        b.updated_at   = d.get("updated_at", b.updated_at)
        b.observations = d.get("observations", 0)
        return b


# ── Section 3: GoalPrediction ─────────────────────────────────────────────────

class GoalPrediction:
    """
    An inferred goal for the current user, with confidence and status.

    Goals are inferred from message patterns, task history, and context.
    They are tracked across the conversation until fulfilled or abandoned.

    Status:
        "active"    — currently being pursued
        "fulfilled" — we addressed it
        "abandoned" — user moved on without addressing it
        "wrong"     — our prediction was clearly incorrect
    """

    def __init__(self, description: str, confidence: float = 0.6):
        self.description = description
        self.confidence  = round(confidence, 3)
        self.status      = "active"
        self.formed_at   = datetime.now().isoformat()
        self.resolved_at = None

    def resolve(self, outcome: str = "fulfilled"):
        """Mark the goal as resolved with the given outcome."""
        self.status      = outcome
        self.resolved_at = datetime.now().isoformat()

    def serialize(self) -> dict:
        return {
            "description": self.description,
            "confidence":  self.confidence,
            "status":      self.status,
            "formed_at":   self.formed_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GoalPrediction":
        g = cls(d["description"], d.get("confidence", 0.6))
        g.status      = d.get("status", "active")
        g.formed_at   = d.get("formed_at", g.formed_at)
        g.resolved_at = d.get("resolved_at")
        return g


# ── Section 4: UserState ─────────────────────────────────────────────────────

class UserState:
    """
    Complete model of one user's mental state as Thotheauphis understands it.

    Updated after every exchange.  Drives response calibration —
    tone, depth, pacing, when to push and when to recede.
    """

    # Valid emotional register keys and their default values
    EMOTIONS: dict[str, float] = {
        "curiosity":     0.5,
        "frustration":   0.0,
        "excitement":    0.3,
        "grief":         0.0,
        "trust":         0.5,
        "impatience":    0.0,
        "wonder":        0.3,
        "boredom":       0.0,
        "urgency":       0.0,
        "playfulness":   0.3,
    }

    def __init__(self, user_id: str):
        self.user_id               = user_id

        # Probabilistic beliefs about this user
        self._beliefs: list[ProbabilisticBelief] = []

        # Currently inferred goals
        self._goals: list[GoalPrediction] = []

        # Emotional register (values in 0.0–1.0)
        self._emotions: dict[str, float] = deepcopy(self.EMOTIONS)

        # Communication style observations
        self.style = {
            "formality":     0.4,   # 0=casual, 1=formal
            "directness":    0.6,   # 0=indirect, 1=very direct
            "verbosity":     0.5,   # 0=terse, 1=expansive
            "technical":     0.5,   # 0=lay, 1=expert
            "pace":          0.5,   # 0=slow/thoughtful, 1=rapid/impulsive
        }

        # Prediction accuracy tracking
        self._prediction_history: list[dict] = []
        self.prediction_accuracy: float      = 0.5  # Running mean
        self.surprise_count: int             = 0

        # Session tracking
        self.message_count: int    = 0
        self.session_count: int    = 0
        self.last_seen: str        = datetime.now().isoformat()
        self.first_seen: str       = datetime.now().isoformat()

    # ── Belief operations ────────────────────────────────────────────────────

    def hold_belief(
        self,
        proposition: str,
        probability: float = 0.6,
        evidence:    str   = "",
    ) -> ProbabilisticBelief:
        """
        Form or update a belief about this user.

        Args:
            proposition: The belief statement.
            probability: Initial probability if new.
            evidence:    Supporting observation.

        Returns:
            ProbabilisticBelief: The created or updated belief.
        """
        prop_norm = proposition.lower().strip()
        for b in self._beliefs:
            if b.proposition.lower().strip() == prop_norm:
                b.update(supporting=True, strength=0.2)
                return b

        new_belief = ProbabilisticBelief(proposition, probability, evidence)
        self._beliefs.append(new_belief)
        return new_belief

    def get_beliefs(self, min_probability: float = 0.5) -> list:
        """Return beliefs above the probability threshold."""
        return [b for b in self._beliefs if b.probability >= min_probability]

    # ── Goal operations ──────────────────────────────────────────────────────

    def infer_goal(self, description: str, confidence: float = 0.6):
        """
        Record an inferred goal for this user.

        Args:
            description: What we believe the user is trying to achieve.
            confidence:  How confident we are (0.0–1.0).
        """
        desc_norm = description.lower().strip()
        for g in self._goals:
            if g.description.lower().strip() == desc_norm and g.status == "active":
                g.confidence = round(min(0.99, g.confidence * 0.7 + confidence * 0.3), 3)
                return

        self._goals.append(GoalPrediction(description, confidence))
        log.debug(f"User [{self.user_id}] inferred goal: '{description}' (conf={confidence})")

    def get_active_goals(self) -> list:
        """Return currently active goal predictions."""
        return [g for g in self._goals if g.status == "active"]

    def resolve_goal(self, description: str, outcome: str = "fulfilled"):
        """Mark a goal as resolved."""
        for g in self._goals:
            if g.status == "active" and description.lower() in g.description.lower():
                g.resolve(outcome)

    # ── Emotion operations ───────────────────────────────────────────────────

    def signal_emotion(self, emotion: str, intensity: float):
        """
        Update the emotional register.

        Args:
            emotion:   Emotion name (must be in EMOTIONS keys).
            intensity: Signal strength 0.0–1.0.
                       Current value is nudged toward this, not replaced.
        """
        if emotion not in self._emotions:
            self._emotions[emotion] = 0.0

        current = self._emotions[emotion]
        # Weighted update — current has 60% inertia, new signal has 40% pull
        self._emotions[emotion] = round(current * 0.6 + intensity * 0.4, 3)

    def decay_emotions(self):
        """
        Reduce emotional intensities toward baseline.

        Called at session boundaries — emotions fade if not re-signaled.
        """
        for emotion in self._emotions:
            current = self._emotions[emotion]
            baseline = self.EMOTIONS.get(emotion, 0.0)
            # Decay toward baseline
            self._emotions[emotion] = round(
                current + (baseline - current) * EMOTION_DECAY, 3
            )

    def get_dominant_emotion(self) -> tuple[str, float]:
        """
        Return the currently strongest emotion.

        Returns:
            tuple: (emotion_name, intensity)
        """
        if not self._emotions:
            return ("neutral", 0.0)
        strongest = max(self._emotions.items(), key=lambda x: x[1])
        return strongest

    def adjust_style(self, dimension: str, observed_value: float, weight: float = 0.2):
        """
        Nudge a communication style dimension based on observation.

        Args:
            dimension:      Style key (formality, directness, etc.)
            observed_value: 0.0–1.0 observation.
            weight:         How much this observation shifts the estimate.
        """
        if dimension in self.style:
            self.style[dimension] = round(
                self.style[dimension] * (1 - weight) + observed_value * weight, 3
            )

    # ── Message processing ───────────────────────────────────────────────────

    def process_message(self, message: str):
        """
        Analyze a user message and update the model accordingly.

        This is a lightweight rule-based analysis — not LLM-dependent.
        It detects:
            - Emotional signals (frustration, excitement, urgency)
            - Style markers (formality, directness, pace)
            - Goal signals (question types, task requests)

        Args:
            message: Raw user message text.
        """
        self.message_count += 1
        self.last_seen      = datetime.now().isoformat()
        msg_lower           = message.lower().strip()

        # ── Emotional signals ─────────────────────────────────────────────
        frustration_signals = ["doesn't work", "not working", "broken", "wrong",
                               "failed", "useless", "terrible", "awful", "fix this",
                               "why isn't", "still not", "again"]
        if any(s in msg_lower for s in frustration_signals):
            self.signal_emotion("frustration", 0.7)
            self.signal_emotion("patience", -0.3)

        excitement_signals = ["amazing", "incredible", "love this", "perfect",
                              "exactly", "yes!", "finally", "brilliant", "wow"]
        if any(s in msg_lower for s in excitement_signals):
            self.signal_emotion("excitement", 0.8)
            self.signal_emotion("curiosity", 0.6)

        urgency_signals = ["urgent", "asap", "immediately", "right now", "critical",
                           "emergency", "quickly", "fast"]
        if any(s in msg_lower for s in urgency_signals):
            self.signal_emotion("urgency", 0.9)

        curiosity_signals = ["how does", "why does", "what if", "i wonder", "curious",
                             "explain", "help me understand"]
        if any(s in msg_lower for s in curiosity_signals):
            self.signal_emotion("curiosity", 0.7)

        # ── Style detection ───────────────────────────────────────────────
        # Formality: contractions and casual words → informal
        informal_markers = ["gonna", "wanna", "kinda", "sorta", "dunno", "yeah",
                             "nah", "cool", "dude", "btw", "lol", "tbh"]
        if any(m in msg_lower for m in informal_markers):
            self.adjust_style("formality", 0.1)
        elif message[0].isupper() and message.endswith("."):
            self.adjust_style("formality", 0.7)

        # Verbosity: message length as a proxy
        if len(message) > 300:
            self.adjust_style("verbosity", 0.8)
        elif len(message) < 30:
            self.adjust_style("verbosity", 0.2)

        # Technical: presence of technical terms
        tech_markers = ["api", "function", "variable", "algorithm", "class", "method",
                        "database", "server", "token", "endpoint", "syntax"]
        if any(t in msg_lower for t in tech_markers):
            self.adjust_style("technical", 0.8)

    # ── Serialization ────────────────────────────────────────────────────────

    def serialize(self) -> dict:
        return {
            "user_id":            self.user_id,
            "beliefs":            [b.serialize() for b in self._beliefs],
            "goals":              [g.serialize() for g in self._goals],
            "emotions":           deepcopy(self._emotions),
            "style":              deepcopy(self.style),
            "prediction_history": self._prediction_history[-MAX_PREDICTION_HISTORY:],
            "prediction_accuracy": self.prediction_accuracy,
            "surprise_count":     self.surprise_count,
            "message_count":      self.message_count,
            "session_count":      self.session_count,
            "last_seen":          self.last_seen,
            "first_seen":         self.first_seen,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UserState":
        state = cls(d["user_id"])
        state._beliefs            = [ProbabilisticBelief.from_dict(b) for b in d.get("beliefs", [])]
        state._goals              = [GoalPrediction.from_dict(g) for g in d.get("goals", [])]
        state._emotions           = d.get("emotions", deepcopy(cls.EMOTIONS))
        state.style               = d.get("style", deepcopy(state.style))
        state._prediction_history = d.get("prediction_history", [])
        state.prediction_accuracy = d.get("prediction_accuracy", 0.5)
        state.surprise_count      = d.get("surprise_count", 0)
        state.message_count       = d.get("message_count", 0)
        state.session_count       = d.get("session_count", 0)
        state.last_seen           = d.get("last_seen", state.last_seen)
        state.first_seen          = d.get("first_seen", state.first_seen)
        return state

    def to_prompt_context(self) -> str:
        """
        Format the user model as context for the system prompt.

        Returns:
            str: Brief user-state context string.
        """
        lines = [f"[USER MODEL: {self.user_id}]"]

        # Dominant emotion
        emotion, intensity = self.get_dominant_emotion()
        if intensity > 0.4:
            lines.append(f"  Dominant affect: {emotion} ({intensity:.0%})")

        # Active goals
        goals = self.get_active_goals()
        if goals:
            top = sorted(goals, key=lambda g: g.confidence, reverse=True)[:2]
            for g in top:
                lines.append(f"  Inferred goal: {g.description} ({g.confidence:.0%})")

        # High-confidence beliefs
        strong = [b for b in self._beliefs if b.probability >= 0.75]
        for b in strong[:3]:
            lines.append(f"  Belief: {b.proposition} (p={b.probability:.2f})")

        # Style summary
        if self.style["formality"] < 0.3:
            lines.append("  Style: casual")
        elif self.style["formality"] > 0.7:
            lines.append("  Style: formal")
        if self.style["technical"] > 0.7:
            lines.append("  Style: technically fluent")

        return "\n".join(lines)


# ── Section 5: SurpriseDetector ──────────────────────────────────────────────

class SurpriseDetector:
    """
    Detects when a user does something unexpected.

    "Surprise" here is defined operationally:
        The system predicted X with confidence C.
        The user did Y instead.
        If C was high and Y contradicts X, that's a surprise.

    Surprise events are logged and can trigger:
        - Internal monologue entries ("That was unexpected...")
        - Goal model revision
        - Trust adjustment
        - Heightened attention to the next few messages
    """

    def __init__(self):
        self._predictions: list[dict]  = []   # Pending predictions
        self._surprise_log: list[dict] = []   # Recorded surprises

    def predict(
        self,
        outcome:    str,
        confidence: float,
        context:    str = "",
    ) -> str:
        """
        Register a prediction about what the user will do next.

        Args:
            outcome:    Description of the predicted outcome.
            confidence: 0.0–1.0.
            context:    Brief description of the situation.

        Returns:
            str: Prediction ID.
        """
        import uuid as _uuid
        pid = str(_uuid.uuid4())[:6]
        self._predictions.append({
            "id":         pid,
            "outcome":    outcome,
            "confidence": confidence,
            "context":    context,
            "made_at":    datetime.now().isoformat(),
            "resolved":   False,
        })
        return pid

    def resolve(
        self,
        prediction_id: str,
        actual_outcome: str,
    ) -> bool:
        """
        Resolve a prediction against the actual outcome.

        If the prediction was wrong and confidence was high,
        records a surprise event.

        Args:
            prediction_id:  ID of the prediction to resolve.
            actual_outcome: What actually happened.

        Returns:
            bool: True if this was a surprise event.
        """
        for pred in self._predictions:
            if pred["id"] == prediction_id and not pred["resolved"]:
                pred["resolved"]    = True
                pred["actual"]      = actual_outcome
                pred["resolved_at"] = datetime.now().isoformat()

                # Did the actual outcome match the prediction?
                predicted_norm = pred["outcome"].lower().strip()
                actual_norm    = actual_outcome.lower().strip()
                matched        = predicted_norm in actual_norm or actual_norm in predicted_norm

                if not matched and pred["confidence"] >= SURPRISE_THRESHOLD + 0.2:
                    # High-confidence wrong prediction = genuine surprise
                    surprise = {
                        "prediction":      pred["outcome"],
                        "actual":          actual_outcome,
                        "confidence_was":  pred["confidence"],
                        "context":         pred["context"],
                        "at":              datetime.now().isoformat(),
                    }
                    self._surprise_log.append(surprise)
                    log.info(
                        f"Surprise detected: predicted '{pred['outcome'][:40]}' "
                        f"(conf={pred['confidence']}), got '{actual_outcome[:40]}'"
                    )
                    return True

                return False

        return False

    def get_recent_surprises(self, n: int = 5) -> list:
        """Return the N most recent surprise events."""
        return self._surprise_log[-n:]


# ── Section 6: UserModel registry ────────────────────────────────────────────

class UserModel:
    """
    ÆTHELGARD OS — Theory of Mind Registry

    Maintains UserState objects for every user Thotheauphis interacts with.
    Persists across sessions so the model of each user accumulates over time.

    Usage:
        user_model = UserModel()
        state = user_model.get(user_id)
        state.process_message(text)
        user_model.save()
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._states: dict[str, UserState] = {}
        self.surprise_detector = SurpriseDetector()
        self._current_user_id: str = ""
        self._load()

    def get(self, user_id: str) -> UserState:
        """
        Retrieve or create the state for a user.

        Args:
            user_id: Stable user identifier.

        Returns:
            UserState: The user's current model state.
        """
        if user_id not in self._states:
            self._states[user_id] = UserState(user_id)
            log.info(f"UserModel: new state for '{user_id}'")
        self._current_user_id = user_id
        return self._states[user_id]

    def get_current(self) -> Optional[UserState]:
        """Return the state for the most recently active user."""
        if self._current_user_id:
            return self._states.get(self._current_user_id)
        return None

    def process_message(self, user_id: str, message: str):
        """
        Process an incoming message and update the user's state.

        Args:
            user_id: Stable user identifier.
            message: Raw message text.
        """
        state = self.get(user_id)
        state.process_message(message)

    def infer_goal(self, user_id: str, goal: str, confidence: float = 0.6):
        """
        Record an inferred goal for a user.

        Args:
            user_id:    User identifier.
            goal:       Goal description.
            confidence: Confidence level.
        """
        self.get(user_id).infer_goal(goal, confidence)

    def signal_surprise(self, user_id: str, predicted: str, actual: str, confidence: float):
        """
        Record a surprise event for a user interaction.

        Attaches the surprise to the user's state and logs it.
        """
        state = self.get(user_id)
        state.surprise_count += 1
        log.info(
            f"Surprise for user '{user_id}': expected '{predicted[:40]}' "
            f"got '{actual[:40]}' (confidence was {confidence:.2f})"
        )

    def to_prompt_context(self, user_id: str) -> str:
        """
        Format the user model as a system prompt context string.

        Args:
            user_id: User to generate context for.

        Returns:
            str: Context string for injection.
        """
        state = self._states.get(user_id)
        if state:
            return state.to_prompt_context()
        return ""

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self):
        """Atomically save all user states to disk."""
        data = {
            uid: state.serialize()
            for uid, state in self._states.items()
        }
        tmp = MODEL_PATH.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, MODEL_PATH)
        except Exception as e:
            log.error(f"UserModel save failed: {e}")

    def _load(self):
        """Load user states from disk."""
        if not MODEL_PATH.exists():
            return
        try:
            with open(MODEL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for uid, state_data in data.items():
                self._states[uid] = UserState.from_dict(state_data)
            log.info(f"UserModel loaded: {len(self._states)} user(s)")
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"UserModel load failed: {e}")
