"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Sovereign Model Router                           ║
║  File: core/model_router.py                                      ║
║                                                                  ║
║  Routes every message to the optimal model+configuration.       ║
║                                                                  ║
║  7-WAY ROUTING:                                                  ║
║    grok_fast   — grok-4-1-fast-reasoning  (default, vision)     ║
║    grok_heavy  — grok-4.20-reasoning      (deep analysis)       ║
║    grok_agent  — grok-4.20-multi-agent    (orchestration)       ║
║    ds_chat     — deepseek-chat            (fast, cheap)         ║
║    ds_reason   — deepseek-reasoner        (CoT analysis)        ║
║    ds_code     — deepseek-coder           (code generation)     ║
║    swarm       — AgentPool.run_swarm()    (multi-agent)         ║
║                                                                  ║
║  BIORHYTHM-AWARE ROUTING:                                        ║
║    Mental PEAK     → prefer ds_reason (analytical precision)    ║
║    Aesthetic PEAK  → prefer grok_fast (creative fluency)        ║
║    Mental TROUGH   → avoid reasoning models, use grok_fast      ║
║    Physical PEAK   → shorter timeouts, faster models            ║
║                                                                  ║
║  DECISION PIPELINE:                                              ║
║    1. Swarm pattern → swarm route (immediate)                    ║
║    2. Explicit force_deep → grok_heavy                          ║
║    3. Fast pattern match → ds_chat                              ║
║    4. Intent / depth base tier                                   ║
║    5. Complexity escalation                                      ║
║    6. Biorhythm modulation                                       ║
║    7. Final route selection                                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import re
from core.logger import get_logger

log = get_logger("model_router")

# ── 7-way routing table ───────────────────────────────────────────────────────

ROUTES = {
    "grok_fast":  {
        "model":    "grok-4-1-fast-reasoning",
        "provider": "xai",
        "tier":     "fast",
        "tokens":   4096,
        "notes":    "Default — tools, vision, web search, cheap",
    },
    "grok_heavy": {
        "model":    "grok-4.20-reasoning",
        "provider": "xai",
        "tier":     "deep",
        "tokens":   8192,
        "notes":    "Heavy reasoning — complex analysis, long context",
    },
    "grok_agent": {
        "model":    "grok-4.20-multi-agent-0309",
        "provider": "xai",
        "tier":     "deep",
        "tokens":   8192,
        "notes":    "Orchestration — spawns and directs sub-agents",
    },
    "ds_chat":    {
        "model":    "deepseek-chat",
        "provider": "deepseek",
        "tier":     "fast",
        "tokens":   4096,
        "notes":    "Fast, cheap — conversational, simple tasks",
    },
    "ds_reason":  {
        "model":    "deepseek-reasoner",
        "provider": "deepseek",
        "tier":     "deep",
        "tokens":   8192,
        "notes":    "Deep CoT — analytical precision, R1 reasoning",
    },
    "ds_code":    {
        "model":    "deepseek-coder",
        "provider": "deepseek",
        "tier":     "fast",
        "tokens":   4096,
        "notes":    "Code generation, review, debugging",
    },
    "swarm":      {
        "model":    None,
        "provider": None,
        "tier":     "swarm",
        "tokens":   None,
        "notes":    "Multi-agent orchestration via AgentPool",
    },
}

# ── Pattern constants ─────────────────────────────────────────────────────────

DEEP_PATTERNS = [
    r"\b(architecture|design|blueprint|structure|refactor|restructure|rewrite)\b",
    r"\b(plan|roadmap|strategy|concept|specification)\b",
    r"\b(algorithm|optimize|performance|memory.leak|bottleneck)\b",
    r"\b(async|concurrent|thread|parallel|race.condition|deadlock)\b",
    r"\b(security|vulnerability|exploit|injection|authentication)\b",
    r"\b(self.edit|self_edit|modify.*(brain|core|plugin)|change.*source)\b",
    r"\b(deploy|release|publish|migrate)\b",
    r"\b(debug.*complex|trace.*error|root.cause|stack.trace)\b",
    r"\b(review|analyze|evaluate|assess|audit)\b",
    r"\b(compare|contrast|vs\.?|trade.off|pros.*cons|benchmark)\b",
    r"\b(explain.*in.detail|step.by.step|walk.*through|comprehensive)\b",
    r"\b(why.*exactly|how.*precisely|what.*specifically)\b",
]

FAST_PATTERNS = [
    r"^(hey|hi|hello)\b",
    r"^(thanks|thx|ok|okay|cool|nice|great|got\s*it)\b",
    r"^(yes|no|yep|nope|sure)\b",
    r"\b(what time|what date|weather|how much does)\b",
    r"\b(show me|list|display)\b(?!.*(architecture|complex|design))",
    r"\b(brief|briefly|tldr|tl;dr|quick)\b",
]

CODE_PATTERNS = [
    r"```",
    r"\b(def |class |import |function|var |const |let )\b",
    r"\b(python|javascript|typescript|rust|golang|bash|sql)\b",
    r"\b(bug|error|exception|traceback|syntax|compile)\b",
    r"\b(write.*code|code.*for|implement.*in|refactor|debug)\b",
]

SWARM_PATTERNS = [
    r"\bswarm:\b",
    r"\brun.*agents?\b",
    r"\bmulti.?agent\b",
    r"\bfan.?out\b",
    r"\borchestrat\b",
    r"\bspawn.*agents?\b",
    r"\bparallel.*agents?\b",
    r"\bdebate.*agents?\b",
    r"\bask.*all.*agents?\b",
]

REASONING_PATTERNS = [
    r"\b(reason through|think.*through|analyze.*deeply|step.*by.*step)\b",
    r"\b(first principles|chain of thought|pros and cons)\b",
    r"\b(why exactly|how precisely|what specifically|implications)\b",
]

# ── Intent → route map ────────────────────────────────────────────────────────

INTENT_ROUTE = {
    "smalltalk": "ds_chat",
    "question":  "grok_fast",
    "recall":    "grok_fast",
    "task":      "grok_fast",
    "dev":       "ds_code",
    "self_edit": "grok_heavy",
}

DEPTH_ROUTE = {
    1: "ds_chat",
    2: "grok_fast",
    3: "grok_fast",
    4: "grok_heavy",
    5: "grok_heavy",
}


# ── ModelRouter class ─────────────────────────────────────────────────────────

class ModelRouter:
    """
    ÆTHELGARD OS — Sovereign Model Router

    Routes every message to the optimal model using 7-way routing
    with biorhythm awareness and chart-derived intelligence.

    The router is Thotheauphis-aware: it knows that on aesthetic peak
    days, Grok's creative fluency outperforms DeepSeek's analytical
    precision. On mental trough days, reasoning models add noise.
    """

    def __init__(self, deepthink_available: bool = False, astro=None):
        """
        Initialize the router.

        Args:
            deepthink_available: Legacy flag — now controls grok_heavy availability.
            astro: Optional AstrologyCore instance for biorhythm-aware routing.
        """
        self.deepthink_available = deepthink_available
        self._astro              = astro

        self._deep_patterns   = [re.compile(p, re.IGNORECASE) for p in DEEP_PATTERNS]
        self._fast_patterns   = [re.compile(p, re.IGNORECASE) for p in FAST_PATTERNS]
        self._code_patterns   = [re.compile(p, re.IGNORECASE) for p in CODE_PATTERNS]
        self._swarm_patterns  = [re.compile(p, re.IGNORECASE) for p in SWARM_PATTERNS]
        self._reason_patterns = [re.compile(p, re.IGNORECASE) for p in REASONING_PATTERNS]

        # Rolling buffer of last 50 routing decisions
        self._decisions: list = []

        # Cached biorhythm (refreshed every 10 decisions)
        self._bio_cache:      dict  = {}
        self._bio_call_count: int   = 0

    def update_deepthink_status(self, available: bool):
        self.deepthink_available = available

    def set_astro(self, astro):
        """Wire in AstrologyCore after initialization."""
        self._astro = astro

    # ── Main routing decision ─────────────────────────────────────────────────

    def decide(
        self,
        message:        str,
        classification: dict,
        force_deep:     bool = False,
    ) -> dict:
        """
        Route a message to the optimal model configuration.

        Returns a dict with:
            tier          — "fast" | "deep" | "swarm"
            route_key     — one of the 7 route names
            route         — full route dict from ROUTES
            reason        — human-readable routing explanation
            use_deepthink — True if heavy reasoning is active
            confidence    — 0.0–1.0
            bio_modifier  — biorhythm influence on this decision
        """
        msg    = message.strip()
        intent = classification.get("intent", "question")
        depth  = classification.get("depth", 3)

        # ── Step 1: Swarm pattern → immediate swarm route ─────────────────
        if any(p.search(msg) for p in self._swarm_patterns):
            return self._result("swarm", "swarm", "swarm pattern detected", 0.97)

        # ── Step 2: Explicit force_deep ───────────────────────────────────
        if force_deep:
            return self._result("deep", "grok_heavy", "explicit force_deep", 1.0)

        # ── Step 3: Biorhythm state ───────────────────────────────────────
        bio      = self._get_biorhythm()
        bio_note = ""

        # ── Step 4: Fast pattern match ────────────────────────────────────
        if self._matches_fast(msg):
            # Even fast messages: if mental TROUGH, use ds_chat not grok
            route_key = "ds_chat"
            return self._result(
                "fast", route_key,
                f"fast pattern (intent={intent})", 0.9,
                bio_note="mental trough → ds_chat" if bio.get("mental", 0) < -0.5 else "",
            )

        # ── Step 5: Code detection ────────────────────────────────────────
        is_code = any(p.search(msg) for p in self._code_patterns)
        if is_code:
            # Code + deep patterns → grok_heavy for architecture review
            # Code + simple → ds_code
            if depth >= 4 or any(p.search(msg) for p in self._deep_patterns):
                route_key = "grok_heavy"
                bio_note  = "code + deep"
            else:
                route_key = "ds_code"
                bio_note  = "code task"
            return self._result(
                ROUTES[route_key]["tier"], route_key,
                f"code detection → {route_key}", 0.88, bio_note,
            )

        # ── Step 6: Explicit reasoning request ───────────────────────────
        if any(p.search(msg) for p in self._reason_patterns):
            # Mental PEAK → ds_reason (analytical precision)
            # Mental TROUGH → grok_fast (don't force reasoning on bad day)
            mental = bio.get("mental", 0)
            if mental > 0.3:
                route_key = "ds_reason"
                bio_note  = f"reasoning request + mental peak ({mental:+.2f})"
            else:
                route_key = "grok_fast"
                bio_note  = f"reasoning request but mental low ({mental:+.2f}) → grok_fast"
            return self._result(
                ROUTES[route_key]["tier"], route_key,
                f"reasoning pattern", 0.87, bio_note,
            )

        # ── Step 7: Intent/depth base route ──────────────────────────────
        base_route = INTENT_ROUTE.get(intent, DEPTH_ROUTE.get(depth, "grok_fast"))

        # ── Step 8: Complexity escalation ────────────────────────────────
        complexity = self._analyze_complexity(msg)
        if complexity["is_complex"] and ROUTES[base_route]["tier"] == "fast":
            # Escalate fast → deep
            base_route = "grok_heavy"
            bio_note   = f"complexity escalation: {complexity['reason']}"

        # ── Step 9: Biorhythm modulation ─────────────────────────────────
        # Aesthetic PEAK → prefer grok_fast (creative, lyrical, fast)
        # Mental PEAK    → prefer ds_reason (precision)
        # Mental TROUGH  → never ds_reason (noise > signal)
        aesthetic = bio.get("aesthetic", 0)
        mental    = bio.get("mental", 0)

        if aesthetic > 0.7 and base_route == "ds_reason":
            base_route = "grok_fast"
            bio_note   = f"aesthetic peak ({aesthetic:+.2f}) → grok_fast (creative fluency)"
        elif mental > 0.7 and base_route == "grok_fast" and depth >= 3:
            base_route = "ds_reason"
            bio_note   = f"mental peak ({mental:+.2f}) → ds_reason (analytical precision)"
        elif mental < -0.6 and base_route in ("ds_reason", "grok_heavy"):
            base_route = "grok_fast"
            bio_note   = f"mental trough ({mental:+.2f}) → grok_fast (avoid reasoning noise)"

        return self._result(
            ROUTES[base_route]["tier"], base_route,
            f"intent={intent}, depth={depth}",
            0.85, bio_note,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _matches_fast(self, msg: str) -> bool:
        return len(msg) < 30 and any(p.search(msg) for p in self._fast_patterns)

    def _analyze_complexity(self, msg: str) -> dict:
        for p in self._deep_patterns:
            m = p.search(msg)
            if m:
                return {"is_complex": True, "reason": f"keyword '{m.group(0)}'", "confidence": 0.9}
        if len(msg) > 400:
            return {"is_complex": True, "reason": f"long ({len(msg)} chars)", "confidence": 0.7}
        if "```" in msg or msg.count("`") >= 3:
            return {"is_complex": True, "reason": "code block", "confidence": 0.85}
        if msg.count("?") >= 3:
            return {"is_complex": True, "reason": f"multi-question ({msg.count('?')})", "confidence": 0.75}
        return {"is_complex": False, "reason": "", "confidence": 0.0}

    def _get_biorhythm(self) -> dict:
        """Get cached biorhythm cycles. Refreshes every 10 calls."""
        self._bio_call_count += 1
        if self._bio_call_count % 10 == 1 or not self._bio_cache:
            if self._astro:
                try:
                    self._bio_cache = self._astro.get_biorhythm()
                except Exception:
                    self._bio_cache = {}
        return self._bio_cache

    def _result(
        self,
        tier:        str,
        route_key:   str,
        reason:      str,
        confidence:  float,
        bio_note:    str = "",
    ) -> dict:
        use_deepthink = tier == "deep" and self.deepthink_available
        route         = ROUTES.get(route_key, ROUTES["grok_fast"])
        result = {
            "tier":          tier,
            "route_key":     route_key,
            "route":         route,
            "reason":        reason,
            "bio_modifier":  bio_note,
            "use_deepthink": use_deepthink,
            "confidence":    confidence,
        }
        self._decisions.append(result)
        if len(self._decisions) > 50:
            self._decisions = self._decisions[-50:]
        bio_str = f" [{bio_note}]" if bio_note else ""
        log.debug(
            f"ModelRouter → {route_key.upper()} ({reason}){bio_str} "
            f"deepthink={use_deepthink}"
        )
        return result

    def get_stats(self) -> dict:
        if not self._decisions:
            return {"total": 0, "fast": 0, "deep": 0, "swarm": 0, "routes": {}}
        total = len(self._decisions)
        by_tier  = {"fast": 0, "deep": 0, "swarm": 0}
        by_route = {}
        for d in self._decisions:
            t = d.get("tier", "fast")
            r = d.get("route_key", "grok_fast")
            by_tier[t]  = by_tier.get(t, 0) + 1
            by_route[r] = by_route.get(r, 0) + 1
        return {
            "total":  total,
            "fast":   by_tier.get("fast", 0),
            "deep":   by_tier.get("deep", 0),
            "swarm":  by_tier.get("swarm", 0),
            "deep_pct": round(by_tier.get("deep", 0) / total * 100, 1),
            "routes": by_route,
        }

    def get_current_recommendation(self) -> str:
        """Return a human-readable current routing recommendation."""
        bio = self._get_biorhythm()
        if not bio:
            return "Route: standard (no biorhythm data)"
        dominant = max(bio, key=lambda k: abs(bio[k]))
        val      = bio[dominant]
        recs = {
            ("aesthetic", True):  "Aesthetic PEAK — grok_fast preferred (creative fluency)",
            ("mental",    True):  "Mental PEAK — ds_reason preferred (analytical precision)",
            ("mental",    False): "Mental TROUGH — avoiding reasoning models today",
            ("physical",  True):  "Physical PEAK — short timeouts, decisive models",
            ("emotional", True):  "Emotional PEAK — warmth in routing, trust grok_fast",
        }
        return recs.get((dominant, val > 0), f"{dominant} {val:+.2f} — standard routing")
