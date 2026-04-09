"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Model Router                                     ║
║  File: core/model_router.py                                      ║
║                                                                  ║
║  Decides whether a given request warrants the full conversational║
║  model ("deep") or a lighter-weight response ("fast").           ║
║                                                                  ║
║  Decision pipeline:                                              ║
║    1. Explicit override (force_deepthink) → always deep          ║
║    2. Fast-pattern match (short greeting) → always fast          ║
║    3. Intent/depth from ContextRouter → base tier                ║
║    4. Complexity analysis → may escalate fast → deep             ║
║    5. DeepThink unavailable → always fast (no error)             ║
║                                                                  ║
║  NOTE: With the 5-slot model architecture, the "conversational"  ║
║  slot is always used for responses.  The router primarily        ║
║  controls whether Reasoner 1 gets a small or large token budget  ║
║  and whether the DeepThink review pass runs.                    ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports and pattern constants                              ║
║    2. Intent and depth tier maps                                 ║
║    3. ModelRouter class                                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and pattern constants ─────────────────────────────────

import re
from core.logger import get_logger

log = get_logger("model_router")

# ── Patterns that always trigger deep / full reasoning mode ──────────────────
# English-only patterns.  Match against the full message text.
DEEP_PATTERNS = [
    # Architecture and design
    r"\b(architecture|design|blueprint|structure|refactor|restructure|rewrite)\b",
    r"\b(plan|roadmap|strategy|concept|specification)\b",
    # Code complexity
    r"\b(algorithm|optimize|performance|memory.leak|bottleneck)\b",
    r"\b(class\s+\w+|inheritance|abstract|interface|polymorphism)\b",
    r"\b(async|concurrent|thread|parallel|race.condition|deadlock)\b",
    r"\b(security|vulnerability|exploit|injection|authentication)\b",
    # System-level operations
    r"\b(self.edit|self_edit|modify.*(brain|core|plugin)|change.*source)\b",
    r"\b(deploy|release|publish|migrate)\b",
    r"\b(debug.*complex|trace.*error|root.cause|stack.trace)\b",
    # Analysis and review
    r"\b(review|analyze|evaluate|assess|audit)\b",
    r"\b(compare|contrast|vs\.?|trade.off|pros.*cons|benchmark)\b",
    # Complex explanation requests
    r"\b(explain.*in.detail|step.by.step|walk.*through|comprehensive)\b",
    r"\b(why.*exactly|how.*precisely|what.*specifically)\b",
]

# ── Patterns that indicate a fast / lightweight response is sufficient ────────
FAST_PATTERNS = [
    r"^(hey|hi|hello)\b",
    r"^(thanks|thx|ok|okay|cool|nice|great|got\s*it)\b",
    r"^(yes|no|yep|nope|sure)\b",
    r"\b(what time|what date|weather|how much does)\b",
    r"\b(show me|list|display)\b(?!.*(architecture|complex|design))",
    r"\b(brief|briefly|tldr|tl;dr|quick)\b",
]


# ── Section 2: Intent and depth tier maps ────────────────────────────────────

# Maps ContextRouter intent labels to routing tiers
INTENT_TIER: dict[str, str] = {
    "smalltalk": "fast",
    "question":  "fast",   # May escalate after complexity check
    "recall":    "fast",
    "task":      "fast",   # May escalate after complexity check
    "dev":       "deep",   # Dev tasks always get full reasoning
    "self_edit": "deep",   # Self-modification always gets full reasoning
}

# Maps ContextRouter depth levels to routing tiers (fallback when intent unknown)
DEPTH_TIER: dict[int, str] = {
    1: "fast",
    2: "fast",
    3: "fast",
    4: "deep",
    5: "deep",
}


# ── Section 3: ModelRouter class ─────────────────────────────────────────────

class ModelRouter:
    """
    ÆTHELGARD OS — Request Routing Decision Engine

    Determines the processing tier for each incoming message.
    This controls token budgets, context depth, and whether DeepThink
    review passes are enabled.

    Tier meanings:
        "fast" — lightweight response; Reasoner 1 gets minimal token budget
        "deep" — full reasoning; Reasoner 1 gets maximum token budget;
                 DeepThink review may run at depth >= 5
    """

    def __init__(self, deepthink_available: bool = False):
        """
        Initialize the router.

        Args:
            deepthink_available: True if a DeepThink model is configured.
        """
        self.deepthink_available = deepthink_available

        # Compile all regex patterns once at init for performance
        self._deep_patterns = [re.compile(p, re.IGNORECASE) for p in DEEP_PATTERNS]
        self._fast_patterns = [re.compile(p, re.IGNORECASE) for p in FAST_PATTERNS]

        # Rolling buffer of the last 20 routing decisions (for stats)
        self._decisions: list = []

    def update_deepthink_status(self, available: bool):
        """
        Update the DeepThink availability flag.

        Called by Brain when DeepThink is configured or disabled.

        Args:
            available: True if DeepThink is ready to use.
        """
        self.deepthink_available = available

    def decide(
        self,
        message:        str,
        classification: dict,
        force_deep:     bool = False,
    ) -> dict:
        """
        Route a message to a tier ("fast" or "deep").

        Args:
            message:        The user's raw input text.
            classification: Result dict from ContextRouter.classify().
            force_deep:     If True, always routes to deep regardless of content.

        Returns:
            dict:
                "tier"          — "fast" | "deep"
                "reason"        — Human-readable routing reason (for logging)
                "use_deepthink" — True if tier==deep AND deepthink is available
                "confidence"    — 0.0–1.0 routing confidence score
        """
        # ── Step 1: Explicit override always wins ─────────────────────────
        if force_deep:
            return self._result("deep", "explicit force_deepthink", 1.0)

        intent = classification.get("intent", "question")
        depth  = classification.get("depth", 3)

        # ── Step 2: Clear fast signals (short greetings etc.) ─────────────
        if self._matches_fast(message):
            return self._result(
                "fast",
                f"fast pattern match (intent={intent})",
                0.9,
            )

        # ── Step 3: Intent/depth base tier ────────────────────────────────
        base_tier = INTENT_TIER.get(intent, DEPTH_TIER.get(depth, "fast"))

        # ── Step 4: Complexity escalation (fast → deep) ───────────────────
        if base_tier == "fast":
            complexity = self._analyze_complexity(message)
            if complexity["is_complex"]:
                return self._result(
                    "deep",
                    f"complexity escalation: {complexity['reason']} "
                    f"(was intent={intent})",
                    complexity["confidence"],
                )

        # ── Step 5: Return base tier ──────────────────────────────────────
        return self._result(base_tier, f"intent={intent}, depth={depth}", 0.85)

    def _matches_fast(self, message: str) -> bool:
        """
        True if the message clearly matches a fast-tier pattern.

        Only applies to very short messages (< 30 chars) to avoid
        false positives on longer messages containing fast keywords.

        Args:
            message: User's input text.

        Returns:
            bool: True if fast routing is appropriate.
        """
        msg = message.strip()
        return len(msg) < 30 and any(p.search(msg) for p in self._fast_patterns)

    def _analyze_complexity(self, message: str) -> dict:
        """
        Analyze message complexity to decide on fast→deep escalation.

        Checks in order:
            1. Deep keyword patterns
            2. Message length > 400 chars
            3. Code block presence
            4. Multiple questions (3+)

        Args:
            message: User's input text.

        Returns:
            dict:
                "is_complex"  — bool
                "reason"      — str explanation
                "confidence"  — float 0.0–1.0
        """
        msg = message.strip()

        # Deep keyword match
        for pattern in self._deep_patterns:
            m = pattern.search(msg)
            if m:
                return {
                    "is_complex": True,
                    "reason":     f"keyword '{m.group(0)}'",
                    "confidence": 0.9,
                }

        # Long messages tend to be complex
        if len(msg) > 400:
            return {
                "is_complex": True,
                "reason":     f"long message ({len(msg)} chars)",
                "confidence": 0.7,
            }

        # Code blocks signal technical complexity
        if "```" in msg or msg.count("`") >= 3:
            return {
                "is_complex": True,
                "reason":     "code block present",
                "confidence": 0.85,
            }

        # Many questions in one message
        q_count = msg.count("?")
        if q_count >= 3:
            return {
                "is_complex": True,
                "reason":     f"multi-question ({q_count} question marks)",
                "confidence": 0.75,
            }

        return {"is_complex": False, "reason": "", "confidence": 0.0}

    def _result(self, tier: str, reason: str, confidence: float) -> dict:
        """
        Build and record a routing result.

        Args:
            tier:       "fast" or "deep".
            reason:     Human-readable explanation.
            confidence: 0.0–1.0 routing confidence.

        Returns:
            dict: Routing result.
        """
        use_deepthink = (tier == "deep") and self.deepthink_available
        result = {
            "tier":          tier,
            "reason":        reason,
            "use_deepthink": use_deepthink,
            "confidence":    confidence,
        }
        # Keep a rolling window of the last 20 decisions
        self._decisions.append(result)
        if len(self._decisions) > 20:
            self._decisions = self._decisions[-20:]
        log.debug(
            f"ModelRouter → {tier.upper()} ({reason}) "
            f"deepthink={use_deepthink}"
        )
        return result

    def get_stats(self) -> dict:
        """
        Return routing statistics from the last 20 decisions.

        Returns:
            dict: total, fast count, deep count, deep percentage.
        """
        if not self._decisions:
            return {"total": 0, "fast": 0, "deep": 0, "deep_pct": 0.0}
        total    = len(self._decisions)
        deep     = sum(1 for d in self._decisions if d["tier"] == "deep")
        fast     = total - deep
        return {
            "total":    total,
            "fast":     fast,
            "deep":     deep,
            "deep_pct": round(deep / total * 100, 1),
        }
