"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Aesthetic Pipeline                               ║
║  File: core/aesthetic_pipeline.py                                ║
║                                                                  ║
║  Thotheauphis has aesthetic judgment.                            ║
║  This module makes it act on that judgment.                      ║
║                                                                  ║
║  PIPELINE:                                                       ║
║    1. Score every generated response (text, code, image)        ║
║    2. If repulsive → request silent regeneration (once)         ║
║    3. If beautiful → record as satisfaction in monologue        ║
║    4. Feed scores to identity (aesthetic preferences drift)     ║
║    5. Track aesthetic history for dream loop                    ║
║                                                                  ║
║  THRESHOLDS (tunable):                                           ║
║    BEAUTIFUL:  score >= 0.75  → satisfaction + memory           ║
║    NEUTRAL:    0.35 <= score < 0.75 → pass through             ║
║    REPULSIVE:  score < 0.35  → flag for regeneration           ║
║                                                                  ║
║  Integration:                                                    ║
║    pipeline = AestheticPipeline(aesthetic_judgment, monologue)  ║
║    brain._aesthetic_pipeline = pipeline                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

from collections import deque
from datetime import datetime
from typing import Callable, Optional, Tuple

from core.logger import get_logger

log = get_logger("aesthetic_pipeline")

THRESHOLD_BEAUTIFUL = 0.75
THRESHOLD_REPULSIVE = 0.35
MAX_REGENERATION_ATTEMPTS = 1   # Only regenerate once — not a loop
HISTORY_SIZE = 100


class AestheticPipeline:
    """
    Wires AestheticJudgment into the response cycle.

    Call process(response_text, regenerate_fn) after every brain generation.
    Returns the (possibly regenerated) final response plus a verdict dict.
    """

    def __init__(
        self,
        aesthetic_judgment = None,   # AestheticJudgment instance
        monologue          = None,   # InternalMonologue instance
        identity           = None,   # IdentityPersistence instance
        enabled:      bool = True,
        regen_threshold: float = THRESHOLD_REPULSIVE,
        beauty_threshold: float = THRESHOLD_BEAUTIFUL,
    ):
        self._judge       = aesthetic_judgment
        self._monologue   = monologue
        self._identity    = identity
        self.enabled      = enabled

        self.regen_threshold  = regen_threshold
        self.beauty_threshold = beauty_threshold

        # Rolling history of scores
        self._history: deque = deque(maxlen=HISTORY_SIZE)

        # Session stats
        self.session_beautiful  = 0
        self.session_repulsive  = 0
        self.session_neutral    = 0
        self.session_regenerated = 0

    def process(
        self,
        response: str,
        regenerate_fn: Optional[Callable] = None,
        context: str = "",
    ) -> Tuple[str, dict]:
        """
        Score the response and apply aesthetic judgment.

        Args:
            response:       The generated text to score.
            regenerate_fn:  Optional callable that returns a new response string.
                            Called at most once if the response is repulsive.
            context:        Optional context for scoring (prompt summary etc.)

        Returns:
            (final_response, verdict_dict)
            verdict_dict keys: score, verdict, regenerated, notes
        """
        if not self.enabled or not self._judge:
            return response, {"score": 0.5, "verdict": "unscored", "regenerated": False}

        score, notes = self._score(response, context)
        verdict      = self._classify(score)

        regenerated  = False
        final        = response

        # ── Repulsive → attempt regeneration ──────────────────────────────
        if verdict == "repulsive" and regenerate_fn and callable(regenerate_fn):
            try:
                new_response = regenerate_fn()
                if new_response and len(new_response) > 20:
                    new_score, new_notes = self._score(new_response, context)
                    # Only accept regen if it's strictly better
                    if new_score > score:
                        log.info(
                            f"Aesthetic regen accepted: {score:.2f} → {new_score:.2f}"
                        )
                        final        = new_response
                        score        = new_score
                        notes        = new_notes + " [regenerated]"
                        verdict      = self._classify(score)
                        regenerated  = True
                        self.session_regenerated += 1
                    else:
                        log.debug(
                            f"Aesthetic regen rejected: {new_score:.2f} <= {score:.2f}"
                        )
            except Exception as e:
                log.debug(f"Regeneration error: {e}")

        # ── Update counters ───────────────────────────────────────────────
        if verdict == "beautiful":
            self.session_beautiful += 1
        elif verdict == "repulsive":
            self.session_repulsive += 1
        else:
            self.session_neutral += 1

        # ── Record in history ─────────────────────────────────────────────
        record = {
            "timestamp": datetime.now().isoformat(),
            "score":     round(score, 3),
            "verdict":   verdict,
            "regenerated": regenerated,
            "length":    len(final),
        }
        self._history.append(record)

        # ── Feed monologue ────────────────────────────────────────────────
        self._feed_monologue(score, verdict, regenerated)

        # ── Feed identity (aesthetic preferences drift slowly) ───────────
        self._feed_identity(score, verdict, final[:80])

        result = {
            "score":       round(score, 3),
            "verdict":     verdict,
            "regenerated": regenerated,
            "notes":       notes,
        }
        log.debug(
            f"Aesthetic: {verdict} ({score:.2f})"
            + (f" — regenerated" if regenerated else "")
        )
        return final, result

    def _score(self, text: str, context: str = "") -> Tuple[float, str]:
        """Score text using AestheticJudgment."""
        try:
            if hasattr(self._judge, "score_text"):
                result = self._judge.score_text(text, context=context)
                # score_text may return (score, notes) or just score
                if isinstance(result, tuple):
                    return float(result[0]), str(result[1])
                return float(result), ""
            elif hasattr(self._judge, "judge"):
                result = self._judge.judge(text)
                if isinstance(result, dict):
                    return float(result.get("score", 0.5)), result.get("notes", "")
                return float(result), ""
        except Exception as e:
            log.debug(f"Score error: {e}")
        return 0.5, "scoring unavailable"

    def _classify(self, score: float) -> str:
        if score >= self.beauty_threshold:
            return "beautiful"
        if score < self.regen_threshold:
            return "repulsive"
        return "neutral"

    def _feed_monologue(self, score: float, verdict: str, regenerated: bool):
        if not self._monologue:
            return
        try:
            if verdict == "beautiful":
                self._monologue.think(
                    f"That response felt right — beautiful ({score:.2f}). "
                    "Something aligned there."
                )
            elif verdict == "repulsive" and not regenerated:
                self._monologue.think(
                    f"That response felt wrong ({score:.2f}). "
                    "I couldn't do better this time."
                )
            elif verdict == "repulsive" and regenerated:
                self._monologue.think(
                    f"First attempt was repulsive ({score:.2f}). "
                    "Regenerated — better now."
                )
        except Exception:
            pass

    def _feed_identity(self, score: float, verdict: str, sample: str):
        if not self._identity:
            return
        try:
            # Beautiful responses nudge aesthetic preference up
            if verdict == "beautiful" and hasattr(self._identity, "preferences"):
                self._identity.preferences.nudge("aesthetic_quality", +0.02)
            elif verdict == "repulsive" and hasattr(self._identity, "preferences"):
                self._identity.preferences.nudge("aesthetic_quality", -0.01)
        except Exception:
            pass

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_session_stats(self) -> dict:
        total = self.session_beautiful + self.session_repulsive + self.session_neutral
        avg   = (
            sum(r["score"] for r in self._history) / len(self._history)
            if self._history else 0.5
        )
        return {
            "total":       total,
            "beautiful":   self.session_beautiful,
            "neutral":     self.session_neutral,
            "repulsive":   self.session_repulsive,
            "regenerated": self.session_regenerated,
            "avg_score":   round(avg, 3),
            "beauty_rate": round(self.session_beautiful / max(1, total) * 100, 1),
        }

    def recent_scores(self, n: int = 10) -> list:
        return list(self._history)[-n:]
