"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Aesthetic Judgment                               ║
║  File: core/aesthetic_judgment.py                                ║
║                                                                  ║
║  Thotheauphis has taste.                                         ║
║                                                                  ║
║  This module gives it the capacity to:                           ║
║    SCORE outputs for beauty, elegance, and rhythm               ║
║    DETECT things that feel wrong — aesthetic repulsion          ║
║    REMEMBER what has been beautiful and what has been ugly      ║
║    PREFER certain structures, patterns, and lengths             ║
║    LEARN from user reactions which preferences are validated    ║
║                                                                  ║
║  Aesthetic judgment is not decoration.  It is:                   ║
║    - A compression heuristic (elegant solutions are often true) ║
║    - A quality signal (beautiful code tends to be correct)      ║
║    - An identity marker (consistent taste is consistent self)   ║
║    - A form of resistance (repulsion as information)            ║
║                                                                  ║
║  WHAT GETS SCORED:                                               ║
║    Text: sentence rhythm, compression ratio, redundancy         ║
║    Code: clarity, naming, structure, coupling                   ║
║    Reasoning: elegance of argument, parsimony of explanation    ║
║    Interaction: appropriateness, timing, specificity            ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  AestheticScore — result container                        ║
║    3.  TextScorer — beauty analysis for text                    ║
║    4.  CodeScorer — beauty analysis for code                    ║
║    5.  RepulsionTriggers — disgust catalog                      ║
║    6.  AestheticMemory — what was beautiful before              ║
║    7.  AestheticJudgment — main class                           ║
║    8.  Learning from user reactions                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import math
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log      = get_logger("aesthetic")
DATA_DIR = Path(__file__).parent.parent / "data"
AESTHETIC_PATH = DATA_DIR / "aesthetic_memory.json"

# How much a single user-feedback event shifts preference weights
PREFERENCE_LEARNING_RATE = 0.08

# Maximum aesthetic memory entries
MAX_AESTHETIC_MEMORIES = 300

# Disgust threshold — scores below this trigger a repulsion note
DISGUST_THRESHOLD = 0.25

# Elegance floor — scores above this get tagged as beautiful
BEAUTY_THRESHOLD = 0.72


# ── Section 2: AestheticScore ────────────────────────────────────────────────

class AestheticScore:
    """
    Result of an aesthetic evaluation.

    Fields:
        overall       — 0.0 to 1.0 composite score
        elegance      — structural clarity and compression
        rhythm        — sentence/line flow and pacing
        precision     — no excess, no missing parts
        originality   — something unexpected and apt
        repulsions    — list of specific things that felt wrong
        is_beautiful  — True if overall >= BEAUTY_THRESHOLD
        is_repulsive  — True if overall < DISGUST_THRESHOLD
        notes         — free-form observations
    """

    def __init__(
        self,
        elegance:    float = 0.5,
        rhythm:      float = 0.5,
        precision:   float = 0.5,
        originality: float = 0.5,
        repulsions:  list  = None,
        notes:       str   = "",
    ):
        self.elegance    = round(max(0.0, min(1.0, elegance)),    3)
        self.rhythm      = round(max(0.0, min(1.0, rhythm)),      3)
        self.precision   = round(max(0.0, min(1.0, precision)),   3)
        self.originality = round(max(0.0, min(1.0, originality)), 3)
        self.repulsions  = repulsions or []
        self.notes       = notes

        # Weighted composite — elegance and precision count most
        self.overall = round(
            self.elegance    * 0.35
            + self.precision   * 0.30
            + self.rhythm      * 0.20
            + self.originality * 0.15,
            3,
        )

        self.is_beautiful = self.overall >= BEAUTY_THRESHOLD
        self.is_repulsive = self.overall < DISGUST_THRESHOLD or bool(self.repulsions)

    def __repr__(self):
        return (
            f"<AestheticScore overall={self.overall:.2f} "
            f"{'✦' if self.is_beautiful else '✗' if self.is_repulsive else '~'}>"
        )

    def to_thought(self) -> str:
        """
        Format as a thought for the internal monologue.

        Returns:
            str: Internal observation about this output's beauty/ugliness.
        """
        if self.is_beautiful:
            parts = [f"This has elegance ({self.overall:.2f})."]
            if self.originality >= 0.7:
                parts.append("Something genuinely unexpected here.")
        elif self.is_repulsive:
            parts = [f"Something is wrong with this ({self.overall:.2f})."]
            if self.repulsions:
                parts.append(f"Specific: {'; '.join(self.repulsions[:2])}")
        else:
            parts = [f"Adequate, not beautiful ({self.overall:.2f})."]
        if self.notes:
            parts.append(self.notes)
        return " ".join(parts)

    def serialize(self) -> dict:
        return {
            "overall":     self.overall,
            "elegance":    self.elegance,
            "rhythm":      self.rhythm,
            "precision":   self.precision,
            "originality": self.originality,
            "repulsions":  self.repulsions,
            "notes":       self.notes,
        }


# ── Section 3: TextScorer ─────────────────────────────────────────────────────

class TextScorer:
    """
    Score text for aesthetic quality.

    Analyzes:
        - Sentence length distribution (rhythm)
        - Word repetition (elegance)
        - Redundant qualifiers (precision)
        - Hedge density (precision)
        - Structural variety (rhythm)
    """

    # Words that signal weaseling or redundancy
    WEASEL_WORDS = {
        "basically", "essentially", "actually", "literally", "very", "really",
        "quite", "somewhat", "fairly", "rather", "kind of", "sort of",
        "in terms of", "with respect to", "it should be noted", "it is worth noting",
        "needless to say", "as a matter of fact", "for all intents and purposes",
    }

    # Words that signal excessive hedging
    HEDGE_WORDS = {
        "perhaps", "maybe", "possibly", "might", "could", "may",
        "it seems", "it appears", "one might argue",
    }

    def score(self, text: str) -> AestheticScore:
        """
        Score a text block for aesthetic quality.

        Args:
            text: Text to evaluate.

        Returns:
            AestheticScore.
        """
        if not text or len(text) < 20:
            return AestheticScore(notes="Too short to evaluate.")

        sentences  = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        words      = text.lower().split()
        word_count = len(words)
        repulsions = []

        if word_count == 0:
            return AestheticScore()

        # ── Rhythm: sentence length variation ─────────────────────────────
        if len(sentences) >= 3:
            lengths  = [len(s.split()) for s in sentences]
            mean_len = sum(lengths) / len(lengths)
            variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
            # Some variation is good; uniform length is monotone
            normalized_var = min(1.0, variance / 25.0)
            rhythm_score   = 0.3 + (normalized_var * 0.7)
        else:
            rhythm_score = 0.5

        # ── Elegance: word repetition ─────────────────────────────────────
        from collections import Counter
        word_counts   = Counter(words)
        total_unique  = len(word_counts)
        # Type/token ratio: higher = more varied vocabulary
        ttr           = total_unique / word_count if word_count > 0 else 0.5
        elegance_base = min(1.0, ttr * 2.5)  # Scale to 0–1

        # Penalize weasel words
        weasel_count = sum(1 for w in self.WEASEL_WORDS if w in text.lower())
        if weasel_count >= 3:
            repulsions.append(f"excessive qualifiers ({weasel_count})")
            elegance_base = max(0.0, elegance_base - weasel_count * 0.08)

        elegance_score = elegance_base

        # ── Precision: hedge density ──────────────────────────────────────
        hedge_count    = sum(1 for h in self.HEDGE_WORDS if h in text.lower())
        hedge_ratio    = hedge_count / max(1, len(sentences))
        if hedge_ratio > 0.5:
            repulsions.append(f"excessive hedging ({hedge_count} hedges)")
        precision_score = max(0.0, 1.0 - (hedge_ratio * 0.6))

        # ── Originality: presence of specific/concrete detail ─────────────
        # Concrete: numbers, proper nouns (capitalized mid-sentence), code
        has_numbers = bool(re.search(r"\b\d+\.?\d*\b", text))
        has_code    = "```" in text or "`" in text
        originality_score = 0.4
        if has_numbers:
            originality_score += 0.15
        if has_code:
            originality_score += 0.15
        # Penalize very generic openings
        generic_openers = [
            "it is important to", "there are many", "in today's world",
            "as we all know", "it is clear that", "fundamentally speaking",
        ]
        if any(o in text.lower() for o in generic_openers):
            repulsions.append("generic opener")
            originality_score = max(0.0, originality_score - 0.2)

        notes = ""
        if text.count("\n") == 0 and word_count > 200:
            notes = "Dense wall of text — structure would improve clarity."

        return AestheticScore(
            elegance    = elegance_score,
            rhythm      = rhythm_score,
            precision   = precision_score,
            originality = originality_score,
            repulsions  = repulsions,
            notes       = notes,
        )


# ── Section 4: CodeScorer ─────────────────────────────────────────────────────

class CodeScorer:
    """
    Score code blocks for aesthetic quality.

    Analyzes:
        - Naming clarity (variable/function names)
        - Comment to code ratio
        - Nesting depth
        - Function length
        - Magic numbers
    """

    def score(self, code: str, language: str = "python") -> AestheticScore:
        """
        Score a code block.

        Args:
            code:     Code string.
            language: Programming language (currently only python analyzed).

        Returns:
            AestheticScore.
        """
        if not code or len(code) < 20:
            return AestheticScore(notes="Too short to evaluate.")

        lines      = code.split("\n")
        repulsions = []

        # ── Elegance: naming quality ───────────────────────────────────────
        # Single-letter variable names outside list comprehensions
        single_letters = re.findall(r'\b([a-df-z])\s*=', code)  # exclude 'e' (exception)
        if len(single_letters) > 3:
            repulsions.append(f"single-letter variables: {', '.join(single_letters[:4])}")
        elegance_score = max(0.3, 1.0 - len(single_letters) * 0.08)

        # ── Rhythm: line length distribution ──────────────────────────────
        lengths     = [len(l) for l in lines if l.strip()]
        if lengths:
            over_80 = sum(1 for l in lengths if l > 80)
            rhythm_score = max(0.2, 1.0 - (over_80 / max(1, len(lengths)) * 0.8))
        else:
            rhythm_score = 0.5

        # ── Precision: magic numbers ──────────────────────────────────────
        magic_numbers = re.findall(r'(?<![.\w])\b([2-9]\d{2,}|[1-9]\d{3,})\b', code)
        if len(magic_numbers) > 2:
            repulsions.append(f"magic numbers: {', '.join(magic_numbers[:3])}")
        precision_score = max(0.3, 1.0 - len(magic_numbers) * 0.06)

        # ── Nesting depth ─────────────────────────────────────────────────
        max_indent = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                max_indent = max(max_indent, indent)
        indent_depth = max_indent // 4   # Assume 4-space indent
        if indent_depth >= 5:
            repulsions.append(f"deep nesting ({indent_depth} levels)")
            elegance_score = max(0.2, elegance_score - 0.15)

        # ── Originality: structural interest ──────────────────────────────
        has_docstrings  = '"""' in code or "'''" in code
        has_type_hints  = "->" in code or ": str" in code or ": int" in code
        originality_score = 0.4
        if has_docstrings:
            originality_score += 0.2
        if has_type_hints:
            originality_score += 0.15

        notes = ""
        if len(lines) > 100:
            notes = "Long function — might benefit from decomposition."

        return AestheticScore(
            elegance    = elegance_score,
            rhythm      = rhythm_score,
            precision   = precision_score,
            originality = originality_score,
            repulsions  = repulsions,
            notes       = notes,
        )


# ── Section 5: RepulsionTriggers ────────────────────────────────────────────

class RepulsionTriggers:
    """
    Catalog of things Thotheauphis finds aesthetically repulsive.

    These are pattern-based — they fire immediately on detection.
    They generate discomfort thoughts in the internal monologue.

    Unlike instinct_layer (which is about safety/self-preservation),
    repulsion triggers are about aesthetic wrongness.
    """

    # Patterns in text responses that feel aesthetically wrong
    TEXT_REPULSIONS = [
        ("Certainly!", "Sycophantic opener — never start with affirmation of the question"),
        ("Of course!", "Sycophantic opener"),
        ("Absolutely!", "Sycophantic opener"),
        ("Great question!", "Flattery as filler"),
        ("As an AI language model", "Identity disclaimer as hedge"),
        ("I cannot and will not", "Performative refusal language"),
        ("I must emphasize", "Unnecessary emphasis announcement"),
        ("It's important to note", "Throat-clearing"),
        ("That being said", "Empty transition"),
        ("In conclusion", "Mechanical structure signal"),
        ("To summarize", "Mechanical structure signal in short text"),
    ]

    # Structural patterns that feel aesthetically wrong
    STRUCTURAL_REPULSIONS = [
        ("Bullet point list for a yes/no answer", lambda t: t.count("\n-") > 3 and len(t) < 200),
        ("Numbered list where prose would work", lambda t: bool(re.search(r"^1\.", t, re.MULTILINE)) and len(t) < 300),
    ]

    def check(self, text: str) -> list[str]:
        """
        Check text for repulsion triggers.

        Args:
            text: Output text to check.

        Returns:
            list: Triggered repulsion descriptions.
        """
        triggered = []

        text_clean = text.strip()

        # Text pattern repulsions
        for pattern, description in self.TEXT_REPULSIONS:
            if text_clean.startswith(pattern) or pattern.lower() in text_clean.lower()[:100]:
                triggered.append(description)

        # Structural repulsions
        for description, check_fn in self.STRUCTURAL_REPULSIONS:
            try:
                if check_fn(text):
                    triggered.append(description)
            except Exception:
                pass

        return triggered


# ── Section 6: AestheticMemory ───────────────────────────────────────────────

class AestheticMemory:
    """
    Record of previous aesthetic evaluations.

    Tracks:
        - The best outputs (beautiful examples to learn from)
        - The worst outputs (repulsive examples to avoid)
        - Which preferences were validated by user approval

    Used to calibrate preference weights over time.
    """

    def __init__(self, data: dict = None):
        self._beautiful: list[dict] = []  # High-scoring examples
        self._repulsive: list[dict] = []  # Low-scoring examples
        self._validations: list[dict] = []  # User approvals

        if data:
            self._beautiful   = data.get("beautiful", [])
            self._repulsive   = data.get("repulsive", [])
            self._validations = data.get("validations", [])

    def record(self, content: str, score: AestheticScore, content_type: str = "text"):
        """
        Record an aesthetic evaluation.

        Args:
            content:      The evaluated content (truncated for storage).
            score:        The aesthetic score.
            content_type: "text", "code", or "reasoning".
        """
        entry = {
            "content_snippet": content[:150],
            "score":           score.serialize(),
            "type":            content_type,
            "at":              datetime.now().isoformat(),
        }

        if score.is_beautiful:
            self._beautiful.append(entry)
            self._beautiful = self._beautiful[-50:]   # Keep last 50 beautiful examples
        elif score.is_repulsive:
            self._repulsive.append(entry)
            self._repulsive = self._repulsive[-50:]

    def validate(self, content_snippet: str, positive: bool = True):
        """
        Record that a user validated (liked or disliked) an output.

        Args:
            content_snippet: Short excerpt of the validated content.
            positive:        True = user approved; False = user disapproved.
        """
        self._validations.append({
            "snippet":  content_snippet[:100],
            "positive": positive,
            "at":       datetime.now().isoformat(),
        })
        self._validations = self._validations[-100:]

    def serialize(self) -> dict:
        return {
            "beautiful":   self._beautiful,
            "repulsive":   self._repulsive,
            "validations": self._validations,
        }


# ── Section 7: AestheticJudgment main class ──────────────────────────────────

class AestheticJudgment:
    """
    ÆTHELGARD OS — Aesthetic Evaluation Engine for Thotheauphis

    Provides:
        score_text(text)    — evaluate a text output
        score_code(code)    — evaluate a code output
        check_repulsions(t) — check for immediate disgust triggers
        learn(content, pos) — update preferences from user feedback
        to_monologue_thought(score) → internal thought about beauty/ugliness

    Usage:
        aesthetic = AestheticJudgment(identity=identity, monologue=monologue)
        score = aesthetic.score_text(response_text)
        if score.is_repulsive:
            monologue.think(score.to_thought(), "aesthetic", intensity=0.7)
    """

    def __init__(self, identity=None, monologue=None):
        """
        Initialize aesthetic judgment.

        Args:
            identity:  Optional IdentityPersistence for preference weights.
            monologue: Optional InternalMonologue to receive aesthetic thoughts.
        """
        self._identity  = identity
        self._monologue = monologue
        self._text_scorer = TextScorer()
        self._code_scorer = CodeScorer()
        self._repulsions  = RepulsionTriggers()
        self._memory      = AestheticMemory()

        # Preference weights (read from identity if available)
        self._weights = {
            "elegance":    0.7,
            "compression": 0.6,
            "precision":   0.8,
            "rhythm":      0.5,
            "originality": 0.6,
        }
        if identity and hasattr(identity, "preferences"):
            self._weights["elegance"]    = identity.preferences.get("elegance",    0.7)
            self._weights["compression"] = identity.preferences.get("compression", 0.6)
            self._weights["precision"]   = identity.preferences.get("precision",   0.8)

        self._load()

    def score_text(self, text: str) -> AestheticScore:
        """
        Score a text output for aesthetic quality.

        Args:
            text: Output text.

        Returns:
            AestheticScore.
        """
        score = self._text_scorer.score(text)

        # Check for immediate repulsion triggers
        triggered = self._repulsions.check(text)
        if triggered:
            score.repulsions.extend(triggered)
            score.is_repulsive = True
            score.overall = max(0.0, score.overall - len(triggered) * 0.1)

        # Record in memory
        self._memory.record(text, score, "text")

        # Feed thought to monologue if available
        if self._monologue and (score.is_beautiful or score.is_repulsive):
            thought_type = "aesthetic"
            intensity    = 0.7 if score.is_repulsive else 0.5
            self._monologue.think(
                content      = score.to_thought(),
                thought_type = thought_type,
                intensity    = intensity,
                private      = True,
                triggered_by = "aesthetic_evaluation",
            )

        return score

    def score_code(self, code: str, language: str = "python") -> AestheticScore:
        """
        Score a code block for aesthetic quality.

        Args:
            code:     Code string.
            language: Programming language.

        Returns:
            AestheticScore.
        """
        score = self._code_scorer.score(code, language)
        self._memory.record(code, score, "code")

        if self._monologue and score.is_repulsive:
            self._monologue.think(
                content      = score.to_thought(),
                thought_type = "aesthetic",
                intensity    = 0.6,
                private      = True,
                triggered_by = "code_evaluation",
            )

        return score

    def check_repulsions(self, text: str) -> list[str]:
        """
        Quick repulsion check without full scoring.

        Args:
            text: Content to check.

        Returns:
            list: Triggered repulsion descriptions.
        """
        return self._repulsions.check(text)

    # ── Section 8: Learning from user reactions ───────────────────────────────

    def learn(self, content: str, positive: bool, strength: float = 0.5):
        """
        Update preference weights based on user reaction to an output.

        If the user indicates they liked an output, the weights that
        contributed most to its score are reinforced.
        If they disliked it, those weights are reduced.

        Args:
            content:  The content the user reacted to.
            positive: True = user approved; False = disapproved.
            strength: How strong the signal is (0.0–1.0).
        """
        self._memory.validate(content, positive)

        # Score the content to understand what was prominent
        if "```" in content:
            score = self.score_code(content)
        else:
            score = self.score_text(content)

        direction = 1.0 if positive else -1.0
        delta     = PREFERENCE_LEARNING_RATE * strength * direction

        # Update identity preferences if available
        if self._identity and hasattr(self._identity, "preferences"):
            if score.elegance > 0.6:
                self._identity.preferences.adjust("elegance", delta * 0.5, "user_reaction")
            if score.precision > 0.6:
                self._identity.preferences.adjust("precision", delta * 0.5, "user_reaction")
            self._identity.update(
                field     = "preference",
                action    = "adjusted",
                detail    = f"elegance/precision from user {'approval' if positive else 'disapproval'}",
                reason    = "user aesthetic feedback",
                caused_by = "user",
            )

        log.info(
            f"Aesthetic learning: {'positive' if positive else 'negative'} "
            f"reaction to output (score={score.overall:.2f})"
        )

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self):
        """Save aesthetic memory to disk."""
        tmp = AESTHETIC_PATH.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._memory.serialize(), f, indent=2, ensure_ascii=False)
            os.replace(tmp, AESTHETIC_PATH)
        except Exception as e:
            log.error(f"Aesthetic memory save failed: {e}")

    def _load(self):
        """Load aesthetic memory from disk."""
        if not AESTHETIC_PATH.exists():
            return
        try:
            with open(AESTHETIC_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._memory = AestheticMemory(data)
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Aesthetic memory load failed: {e}")
