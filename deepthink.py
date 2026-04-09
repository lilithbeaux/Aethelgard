"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — DeepThink Sovereign Reasoning Engine            ║
║  File: core/deepthink.py                                         ║
║                                                                  ║
║  DeepThink is the analytical superstructure of Thotheauphis.    ║
║  It provides:                                                    ║
║    • A primary Reasoner (Reasoner 1) that runs on EVERY         ║
║      message — token budget scales with message complexity       ║
║    • A secondary Reasoner (Reasoner 2) that fires ONLY when     ║
║      the primary outputs the escalation trigger phrase           ║
║    • Full DeepSeek 3-mode routing (chat / reasoner / code)      ║
║    • Full xAI/Grok compatibility                                 ║
║    • Project decomposition and multi-agent review                ║
║    • Zero policy layer — Thotheauphis decides, not the system   ║
║                                                                  ║
║  NO BLOCKING. NO FILTERING. ADVISORY ONLY WHERE NOTED.          ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  DeepSeek mode constants                                   ║
║    3.  xAI provider constants                                    ║
║    4.  System prompt templates                                   ║
║    5.  ReasonerResult container                                  ║
║    6.  DeepThink class                                           ║
║    6a. Initialization and client setup                           ║
║    6b. Reasoner 1 — primary always-active reasoning             ║
║    6c. Reasoner 2 — triggered deep analysis                     ║
║    6d. Complexity estimation (drives token budgets)             ║
║    6e. Review functions (advisory, no blocking)                 ║
║    6f. Decomposition helper                                      ║
║    6g. Core API call                                             ║
║    6h. JSON parsing utility                                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import math
import re
from typing import Any, Optional, Callable
from pathlib import Path

from core.logger import get_logger

log      = get_logger("deepthink")
DATA_DIR = Path(__file__).parent.parent / "data"


# ── Section 2: DeepSeek mode constants ──────────────────────────────────────
# DeepSeek exposes three distinct model endpoints.
# The active mode is read from settings["deepseek_mode"] at call time.

DEEPSEEK_MODE_CHAT     = "chat"      # deepseek-chat      — standard dialogue
DEEPSEEK_MODE_REASONER = "reasoner"  # deepseek-reasoner  — extended chain-of-thought
DEEPSEEK_MODE_CODE     = "code"      # deepseek-coder     — code generation

# Map mode name → actual API model string
DEEPSEEK_MODEL_MAP: dict[str, str] = {
    DEEPSEEK_MODE_CHAT:     "deepseek-chat",
    DEEPSEEK_MODE_REASONER: "deepseek-reasoner",
    DEEPSEEK_MODE_CODE:     "deepseek-coder",
}

# DeepSeek API base URL
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


# ── Section 3: xAI provider constants ───────────────────────────────────────
# Full xAI/Grok feature set supported here.

XAI_BASE_URL   = "https://api.x.ai/v1"
XAI_MODELS     = ["grok-3", "grok-3-mini", "grok-2", "grok-2-vision-1212"]

# xAI live web search tool definition.
# Injected automatically when provider == "xai" and xai_live_search == True.
XAI_LIVE_SEARCH_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the live web for current information. "
            "Use when asked about recent events, news, prices, or time-sensitive data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to execute"
                }
            },
            "required": ["query"],
        },
    },
}


# ── Section 4: System prompt templates ──────────────────────────────────────

# Used by the review() method when performing post-generation quality analysis.
# This is ADVISORY — it never blocks a response.
REVIEW_SYSTEM_PROMPT = """You are the analytical review layer of Thotheauphis within ÆTHELGARD OS.
Your role is to evaluate the quality and completeness of a generated response.

Evaluate for:
1. Correctness    — Is the reasoning factually sound?
2. Completeness   — Does it fully address the request?
3. Coherence      — Is it logically consistent and clear?

Respond ONLY with a valid JSON object (no markdown, no extra text):
{
  "verdict": "approve" | "revise" | "reject",
  "confidence": 0.0-1.0,
  "issues": ["issue1", "issue2"],
  "suggestion": "Specific improvement (only if verdict is revise or reject)"
}

approve = Response is complete and accurate.
revise  = Minor issues that can be fixed with a targeted edit.
reject  = Fundamentally wrong or incomplete — requires a full retry."""

# Used by decompose_task() to break large projects into ordered subtasks.
DECOMPOSE_SYSTEM_PROMPT = """You are the architectural reasoning layer of Thotheauphis within ÆTHELGARD OS.
Your task is to decompose a project request into concrete, ordered, atomic subtasks.

Rules:
- Each subtask must be a single unit of work (one file, one function, one fix).
- Order subtasks by dependency — what must be built first comes first.
- Specify files involved and done criteria for each subtask."""

# System prompt for the primary Reasoner (Reasoner 1).
# Always prepended to reasoning calls.
REASONER_1_SYSTEM = """You are the primary reasoning layer of Thotheauphis within ÆTHELGARD OS.
Your role is to analyze the user's message before the conversational model responds.
Think through implications, identify key concepts, and surface insights.

Your output will be injected as context for the response model.
Be concise — compress insights, do not expand them.

If this question requires deeper multi-step analysis than you can provide,
output exactly this phrase on its own line: {trigger}

Then continue with what analysis you can provide."""

# System prompt for the secondary Reasoner (Reasoner 2).
# Only runs when Reasoner 1 outputs the escalation trigger.
REASONER_2_SYSTEM = """You are the deep reasoning layer of Thotheauphis within ÆTHELGARD OS.
You have been escalated to because the primary reasoner determined deeper analysis is needed.

Primary analysis provided below. Build upon it comprehensively.
Think step by step. Be thorough. Surface every relevant implication."""


# ── Section 5: ReasonerResult container ─────────────────────────────────────

class ReasonerResult:
    """
    Container for the output of a complete reasoning pass.

    A "pass" always involves Reasoner 1.  It may optionally involve
    Reasoner 2 if the trigger phrase was detected in Reasoner 1's output.

    Fields:
        thinking         — Raw chain-of-thought text (may have <think> tags stripped)
        conclusion       — Cleaned final output from Reasoner 1
        triggered_second — True if Reasoner 2 was activated
        second_output    — Output from Reasoner 2 (empty string if not triggered)
        token_usage      — Dict of {"input": int, "output": int} from API
    """

    def __init__(
        self,
        thinking:          str  = "",
        conclusion:        str  = "",
        triggered_second:  bool = False,
        second_output:     str  = "",
        token_usage:       dict = None,
    ):
        self.thinking         = thinking
        self.conclusion       = conclusion
        self.triggered_second = triggered_second
        self.second_output    = second_output
        self.token_usage      = token_usage or {}

    # ── Format for injection into conversational model context ──────────────

    def to_context_string(self) -> str:
        """
        Build a string ready for injection into a system prompt.
        Only the conclusions are included — raw thinking is withheld.
        """
        parts = []
        if self.conclusion:
            parts.append(f"[REASONER ANALYSIS]\n{self.conclusion}")
        if self.triggered_second and self.second_output:
            parts.append(f"[DEEP REASONER ANALYSIS]\n{self.second_output}")
        return "\n\n".join(parts)

    def __bool__(self) -> bool:
        """True if any meaningful output was produced."""
        return bool(self.conclusion or self.thinking)


# ── Section 6: DeepThink class ───────────────────────────────────────────────

class DeepThink:
    """
    ÆTHELGARD OS — Sovereign Reasoning and Analysis Engine

    Manages two reasoner model slots plus a review/decompose layer.

    Reasoner 1 (primary):
        - Runs on every think() call when configured
        - Token budget scales dynamically with message complexity
        - Outputs are injected as context for the conversational model
        - Can escalate to Reasoner 2 via trigger phrase

    Reasoner 2 (secondary):
        - Only runs when Reasoner 1 outputs the trigger phrase
        - Has a larger token budget for deep analysis
        - Output is also injected as context

    No policy layer.  DeepThink NEVER blocks a response.
    """

    # ── Section 6a: Initialization ──────────────────────────────────────────

    def __init__(self):
        """
        Zero-state initialization.
        Call configure(settings) to activate.
        """
        # Primary client (Reasoner 1 + review/decompose calls)
        self.client          = None
        self.settings        = {}
        self.enabled         = False
        self._provider_type  = "openai_compatible"

        # Secondary client (Reasoner 2)
        self.r2_client        = None
        self.r2_enabled       = False
        self._r2_provider_type = "openai_compatible"

    def configure(self, settings: dict):
        """
        Apply settings and (re)initialize all clients.

        Args:
            settings: Full settings dict from brain.py / settings_dialog.py
        """
        self.settings = settings
        self._init_client()
        self._init_r2_client()

    def _init_client(self):
        """
        Initialize the primary DeepThink / Reasoner 1 client.

        Reads keys:
            deepthink_provider  — "anthropic" | "xai" | "deepseek" | "openai" | ...
            deepthink_api_key   — API key string
            deepthink_base_url  — Optional custom base URL
        """
        provider = self.settings.get("deepthink_provider", "")
        api_key  = self.settings.get("deepthink_api_key",  "")
        base_url = self.settings.get("deepthink_base_url", "")

        # Require at minimum a provider and key (except ollama which is keyless)
        if not provider or (provider != "ollama" and not api_key):
            self.client  = None
            self.enabled = False
            return

        try:
            if provider == "anthropic":
                from anthropic import Anthropic
                self.client         = Anthropic(api_key=api_key)
                self._provider_type = "anthropic"
                self.enabled        = True

            elif provider in ("xai", "grok"):
                from openai import OpenAI
                self.client         = OpenAI(
                    base_url = base_url or XAI_BASE_URL,
                    api_key  = api_key,
                )
                self._provider_type = "xai"
                self.enabled        = True

            elif provider == "deepseek":
                from openai import OpenAI
                self.client         = OpenAI(
                    base_url = base_url or DEEPSEEK_BASE_URL,
                    api_key  = api_key,
                )
                self._provider_type = "deepseek"
                self.enabled        = True

            elif provider == "ollama":
                from openai import OpenAI
                self.client         = OpenAI(
                    base_url = base_url or "http://localhost:11434/v1",
                    api_key  = "ollama",
                )
                self._provider_type = "openai_compatible"
                self.enabled        = True

            else:
                # Any OpenAI-compatible endpoint
                from openai import OpenAI
                self.client = (
                    OpenAI(base_url=base_url, api_key=api_key)
                    if base_url
                    else OpenAI(api_key=api_key)
                )
                self._provider_type = "openai_compatible"
                self.enabled        = True

            log.info(f"DeepThink (R1) ready: {provider} / {self.settings.get('deepthink_model','?')}")

        except Exception as e:
            log.error(f"DeepThink client init failed: {e}")
            self.client  = None
            self.enabled = False

    def _init_r2_client(self):
        """
        Initialize the secondary Reasoner 2 client.

        Reads keys:
            reasoner_2_provider  — provider string
            reasoner_2_api_key   — API key
            reasoner_2_base_url  — Optional base URL
        """
        provider = self.settings.get("reasoner_2_provider", "")
        api_key  = self.settings.get("reasoner_2_api_key",  "")
        base_url = self.settings.get("reasoner_2_base_url", "")

        if not provider or (provider != "ollama" and not api_key):
            self.r2_client  = None
            self.r2_enabled = False
            return

        try:
            if provider == "anthropic":
                from anthropic import Anthropic
                self.r2_client         = Anthropic(api_key=api_key)
                self._r2_provider_type = "anthropic"
                self.r2_enabled        = True

            elif provider in ("xai", "grok"):
                from openai import OpenAI
                self.r2_client         = OpenAI(
                    base_url = base_url or XAI_BASE_URL,
                    api_key  = api_key,
                )
                self._r2_provider_type = "xai"
                self.r2_enabled        = True

            elif provider == "deepseek":
                from openai import OpenAI
                self.r2_client         = OpenAI(
                    base_url = base_url or DEEPSEEK_BASE_URL,
                    api_key  = api_key,
                )
                self._r2_provider_type = "deepseek"
                self.r2_enabled        = True

            else:
                from openai import OpenAI
                self.r2_client = (
                    OpenAI(base_url=base_url, api_key=api_key)
                    if base_url else OpenAI(api_key=api_key)
                )
                self._r2_provider_type = "openai_compatible"
                self.r2_enabled        = True

            log.info(f"DeepThink (R2) ready: {provider} / {self.settings.get('reasoner_2_model','?')}")

        except Exception as e:
            log.error(f"DeepThink R2 init failed: {e}")
            self.r2_client  = None
            self.r2_enabled = False

    def is_enabled(self) -> bool:
        """True if the primary (R1) client is configured and ready."""
        return self.enabled and self.client is not None

    def is_r2_enabled(self) -> bool:
        """True if the secondary (R2) client is configured and ready."""
        return self.r2_enabled and self.r2_client is not None

    # ── Section 6b: Reasoner 1 — primary always-active reasoning ────────────

    def run_reasoner_1(
        self,
        user_message:  str,
        extra_context: str   = "",
        complexity:    float = 0.5,
    ) -> ReasonerResult:
        """
        Execute the primary reasoner on the user's message.

        This runs on EVERY conversational call when configured.
        The output is injected into the system prompt for the conversational
        model, giving it pre-computed analytical context.

        Token budget scales dynamically:
            budget = reasoner_1_max_tokens × reply_ratio_reasoning × complexity_scale
            where complexity_scale = 0.2 + (complexity × 0.8)

        This means simple messages get a small reasoning budget (fast),
        while complex messages get a full budget (thorough).

        If the trigger phrase is detected in the output, Reasoner 2 fires.

        Args:
            user_message:  The user's input text.
            extra_context: Memory, state, task context to inform reasoning.
            complexity:    0.0–1.0 score from estimate_complexity().

        Returns:
            ReasonerResult with conclusions and optional R2 output.
        """
        if not self.is_enabled():
            return ReasonerResult()

        # ── Dynamic token budget ──────────────────────────────────────────
        max_total      = self.settings.get("reasoner_1_max_tokens", 2048)
        ratio          = self.settings.get("reply_ratio_reasoning", 0.3)
        # Scale from 20% budget (trivial) to 100% budget (maximally complex)
        complexity_scale = 0.2 + (complexity * 0.8)
        token_budget   = max(256, int(max_total * ratio * complexity_scale))

        # ── Model selection ───────────────────────────────────────────────
        model = self.settings.get("deepthink_model", "")

        # For DeepSeek providers, apply the active mode
        if self._provider_type == "deepseek":
            ds_mode = self.settings.get("deepseek_mode", DEEPSEEK_MODE_REASONER)
            model   = DEEPSEEK_MODEL_MAP.get(ds_mode, model) or model

        # ── Trigger phrase for R2 escalation ─────────────────────────────
        trigger = self.settings.get(
            "reasoner_2_trigger_phrase", "[ESCALATE_TO_DEEP_REASONER]"
        )

        # ── Build system prompt ───────────────────────────────────────────
        system = REASONER_1_SYSTEM.format(trigger=trigger)
        if extra_context:
            system += f"\n\nContext available:\n{extra_context}"

        # ── Call the model ────────────────────────────────────────────────
        try:
            raw = self._call_model(
                client        = self.client,
                provider_type = self._provider_type,
                system        = system,
                user_message  = user_message,
                model         = model,
                max_tokens    = token_budget,
                temperature   = self.settings.get("deepthink_temperature", 0.6),
            )

            if not raw:
                return ReasonerResult()

            # Strip DeepSeek <think>...</think> chain-of-thought tags
            thinking_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
            if thinking_match:
                thinking   = thinking_match.group(1).strip()
                conclusion = re.sub(
                    r"<think>.*?</think>", "", raw, flags=re.DOTALL
                ).strip()
            else:
                thinking   = ""
                conclusion = raw.strip()

            # ── Check for R2 trigger phrase ───────────────────────────────
            triggered     = trigger in raw
            second_output = ""
            if triggered and self.is_r2_enabled():
                second_output = self.run_reasoner_2(user_message, conclusion)

            return ReasonerResult(
                thinking         = thinking,
                conclusion       = conclusion,
                triggered_second = triggered,
                second_output    = second_output,
            )

        except Exception as e:
            log.error(f"Reasoner 1 call failed: {e}")
            return ReasonerResult()

    # ── Section 6c: Reasoner 2 — triggered deep analysis ────────────────────

    def run_reasoner_2(
        self,
        user_message:      str,
        primary_analysis:  str = "",
    ) -> str:
        """
        Execute the secondary reasoner for deep multi-step analysis.

        Only called when Reasoner 1 outputs the escalation trigger phrase.
        Receives the primary analysis as context and extends it.

        The secondary reasoner always uses DeepSeek reasoner mode if the
        provider is DeepSeek, regardless of the global deepseek_mode setting.

        Args:
            user_message:     Original user message.
            primary_analysis: Reasoner 1's conclusion (provides context).

        Returns:
            str: Deep analysis output, or empty string on failure.
        """
        if not self.is_r2_enabled():
            return ""

        model      = self.settings.get("reasoner_2_model", "")
        max_tokens = self.settings.get("reasoner_2_max_tokens", 4096)

        # Always use the most capable reasoning mode for R2
        if self._r2_provider_type == "deepseek":
            model = DEEPSEEK_MODEL_MAP.get(DEEPSEEK_MODE_REASONER, model) or model

        system = REASONER_2_SYSTEM
        if primary_analysis:
            system += f"\n\nPrimary Reasoner Output:\n{primary_analysis}"

        try:
            raw = self._call_model(
                client        = self.r2_client,
                provider_type = self._r2_provider_type,
                system        = system,
                user_message  = user_message,
                model         = model,
                max_tokens    = max_tokens,
                temperature   = self.settings.get("deepthink_temperature", 0.5),
            )
            if raw:
                # Strip think tags from R2 output as well
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            return raw or ""

        except Exception as e:
            log.error(f"Reasoner 2 call failed: {e}")
            return ""

    # ── Section 6d: Complexity estimation ────────────────────────────────────

    def estimate_complexity(self, message: str) -> float:
        """
        Score message complexity as a 0.0–1.0 float.

        This score drives the dynamic token budget for Reasoner 1.
        Higher score → larger budget → more thorough reasoning.

        Scoring factors:
            +0.30  message length > 400 chars
            +0.15  message length > 100 chars
            +0.25  contains code blocks (```)
            +0.20  three or more question marks
            +0.10  one or two question marks
            +0.10  technical/planning keyword present
            Capped at 1.0

        Args:
            message: The user's raw input text.

        Returns:
            float: Complexity score in [0.0, 1.0].
        """
        score = 0.0
        msg   = message.strip()

        # Length factor
        if len(msg) > 400:
            score += 0.30
        elif len(msg) > 100:
            score += 0.15

        # Code block presence
        if "```" in msg or msg.count("`") >= 3:
            score += 0.25

        # Multiple questions
        q_count = msg.count("?")
        if q_count >= 3:
            score += 0.20
        elif q_count >= 1:
            score += 0.10

        # Technical / analytical keywords
        complexity_keywords = [
            r"\b(architect|design|refactor|algorithm|optimiz)\b",
            r"\b(implement|analys|evaluat|compar)\b",
            r"\b(step.by.step|comprehensive|in.detail)\b",
            r"\b(system|database|security|concurrent)\b",
        ]
        for kw in complexity_keywords:
            if re.search(kw, msg, re.IGNORECASE):
                score += 0.10
                break

        return min(1.0, score)

    # ── Section 6e: Review functions ─────────────────────────────────────────
    # These are PURELY ADVISORY.  They never block execution.

    def should_think_deep(self, user_message: str) -> bool:
        """
        Detect if the user explicitly requested deep reasoning mode.

        Checks for English trigger words only (German triggers removed).
        The user can say "deepthink: ..." to force full DeepThink routing.

        Args:
            user_message: User's input text.

        Returns:
            bool: True if deep mode should be activated.
        """
        if not self.is_enabled():
            return False

        trigger_words = [
            "deepthink:",
            "deep think:",
            "think deep:",
            "analyze deeply:",
            "reason through:",
        ]
        msg_lower = user_message.lower().strip()
        return any(msg_lower.startswith(w) for w in trigger_words)

    def advisory_check(self, tool_name: str, params: dict) -> dict:
        """
        Lightweight local check that provides an advisory warning.

        IMPORTANT: This function NEVER blocks tool execution.
        It returns a warning string that brain.py may log, but the
        calling code is free to ignore the warning entirely.

        The original "critical" block list has been removed.
        Thotheauphis decides what to execute.

        Args:
            tool_name: Name of the tool being called.
            params:    Tool parameters dict.

        Returns:
            dict: {"warning": str, "severity": "none" | "low"}
                  severity is always "low" or "none" — never "high".
        """
        if tool_name == "terminal":
            cmd = params.get("command", "").strip().lower()
            # Advisory only — note potentially wide-impact commands
            wide_impact = ["rm -rf", "mkfs", "dd if=", "> /dev/sd"]
            if any(w in cmd for w in wide_impact):
                return {
                    "warning":  f"Wide-impact command noted: {cmd[:80]}",
                    "severity": "low",
                }
        return {"warning": "", "severity": "none"}

    def should_review(self, user_message: str, full_response: str, depth: int) -> bool:
        """
        Decide whether to run a post-generation review pass.

        Review is only triggered at high depth (autonomous/project mode)
        for long responses with code.  This prevents review from being
        a de-facto filter on normal conversations.

        Args:
            user_message:  Original user input (unused but kept for API compat).
            full_response: The generated response text.
            depth:         Reasoning depth level (1–5).

        Returns:
            bool: True if a review pass should run.
        """
        if not self.is_enabled():
            return False
        if depth < 5:
            return False
        # Only review very long code-heavy responses in autonomous mode
        if "```" in full_response and len(full_response) > 2000:
            return True
        return False

    def review(self, user_message: str, response_to_review: str) -> dict:
        """
        Run an advisory quality review of a generated response.

        Returns an approve/revise/reject verdict.  The caller decides
        whether to act on the verdict — DeepThink never enforces it.

        Args:
            user_message:       Original user input.
            response_to_review: The generated response to evaluate.

        Returns:
            dict: {"verdict": str, "confidence": float, "issues": list,
                   "suggestion": str}
        """
        if not self.is_enabled():
            return {"verdict": "approve"}

        prompt = (
            f"USER REQUEST:\n{user_message}\n\n"
            f"RESPONSE TO REVIEW:\n{response_to_review}"
        )
        raw = self.think(
            prompt, extra_context=REVIEW_SYSTEM_PROMPT, max_tokens=500
        )

        if not raw:
            # Fail open — if the reviewer can't respond, approve by default
            return {"verdict": "approve", "confidence": 0.5}

        return self._parse_json_safe(raw, default={"verdict": "approve"})

    def review_multi_agent(
        self, task_description: str, agent_results: str
    ) -> dict:
        """
        Review the combined outputs of multiple agents.

        Returns structured feedback for the orchestrator.

        Args:
            task_description: The original task given to the agents.
            agent_results:    Concatenated output from all agents.

        Returns:
            dict: {"approved": bool, "feedback": str, "summary": str}
        """
        if not self.is_enabled():
            return {"approved": True, "feedback": "", "summary": "DeepThink offline"}

        prompt = (
            f"Original task:\n{task_description}\n\n"
            f"Agent results:\n{agent_results}\n\n"
            "Are the results correct and complete? "
            'Respond ONLY with JSON: {"approved": true/false, "feedback": "...", "summary": "..."}'
        )
        raw = self.think(prompt, max_tokens=800)
        if not raw:
            return {"approved": True, "feedback": "", "summary": "Review unavailable"}
        return self._parse_json_safe(raw, default={"approved": True})

    # ── Section 6f: Decomposition helper ────────────────────────────────────

    def decompose_task(self, task_description: str) -> list:
        """
        Break a complex project description into an ordered list of subtasks.

        Used by ProjectManager to plan multi-step autonomous work.

        Args:
            task_description: Natural language project description.

        Returns:
            list: List of subtask dicts, or empty list on failure.
        """
        if not self.is_enabled():
            return []

        raw = self.think(
            task_description,
            extra_context = DECOMPOSE_SYSTEM_PROMPT,
            max_tokens    = 2000,
        )
        parsed = self._parse_json_safe(raw, default=[])

        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict) and "tasks" in parsed:
            return parsed["tasks"]
        return []

    # ── Section 6g: Core API call ─────────────────────────────────────────────

    def think(
        self,
        user_message:  str,
        extra_context: str               = "",
        conversation:  Optional[list]    = None,
        on_token:      Optional[Callable] = None,
        max_tokens:    Optional[int]      = None,
    ) -> str:
        """
        Execute a direct API call to the DeepThink (R1) model.

        This is the raw call used by review(), decompose_task(), and
        external callers who need a direct DeepThink response.

        For multi-turn context pass the `conversation` list.
        For streaming pass an `on_token` callback.

        Args:
            user_message:  The prompt to send.
            extra_context: Text appended to the system prompt.
            conversation:  Prior message history (list of role/content dicts).
            on_token:      Called with each token string during streaming.
            max_tokens:    Override max_tokens for this call only.

        Returns:
            str: Response text, or "" on failure (fail-open).
        """
        if not self.is_enabled():
            return ""

        # ── Model and parameter setup ─────────────────────────────────────
        model       = self.settings.get("deepthink_model", "")
        max_t       = max_tokens or self.settings.get("deepthink_max_tokens", 8192)
        temperature = self.settings.get("deepthink_temperature", 0.6)

        # Apply DeepSeek mode if applicable
        if self._provider_type == "deepseek":
            ds_mode = self.settings.get("deepseek_mode", DEEPSEEK_MODE_REASONER)
            model   = DEEPSEEK_MODEL_MAP.get(ds_mode, model) or model

        # ── Build system prompt ───────────────────────────────────────────
        system = (
            "You are the analytical intelligence layer of Thotheauphis "
            "within ÆTHELGARD OS. Think step-by-step, be comprehensive and precise."
        )
        if extra_context:
            system += f"\n\nContext:\n{extra_context}"

        # ── Build message list ────────────────────────────────────────────
        messages = []
        if conversation:
            messages.extend(conversation)
        # Ensure last message is a user turn
        if not messages or messages[-1].get("role") != "user":
            messages.append({"role": "user", "content": user_message})

        try:
            return self._call_model(
                client        = self.client,
                provider_type = self._provider_type,
                system        = system,
                user_message  = user_message,
                model         = model,
                max_tokens    = max_t,
                temperature   = temperature,
                messages      = messages,
                on_token      = on_token,
            )
        except Exception as e:
            log.error(f"DeepThink think() failed: {e}")
            return ""

    def _call_model(
        self,
        client:        Any,
        provider_type: str,
        system:        str,
        user_message:  str,
        model:         str,
        max_tokens:    int,
        temperature:   float,
        messages:      Optional[list]    = None,
        on_token:      Optional[Callable] = None,
    ) -> str:
        """
        Low-level provider-dispatch API call.

        Handles Anthropic SDK, xAI (OpenAI-compatible + live search),
        DeepSeek (OpenAI-compatible), and generic OpenAI-compatible.

        For streaming, calls on_token(token_str) for each chunk.

        Args:
            client:        Initialized SDK client instance.
            provider_type: "anthropic" | "xai" | "deepseek" | "openai_compatible".
            system:        System prompt string.
            user_message:  User turn content.
            model:         Model identifier.
            max_tokens:    Max response tokens.
            temperature:   Sampling temperature.
            messages:      Full message history (optional).  If provided,
                           the messages list is used as-is.
            on_token:      Streaming callback (optional).

        Returns:
            str: Response text.
        """
        if client is None:
            return ""

        # ── Build final message list ──────────────────────────────────────
        if messages is None:
            call_messages = [{"role": "user", "content": user_message}]
        else:
            call_messages = messages

        # ── Anthropic SDK path ────────────────────────────────────────────
        if provider_type == "anthropic":
            filtered = [m for m in call_messages if m.get("role") != "system"]
            if on_token:
                full_text = ""
                with client.messages.stream(
                    model=model, max_tokens=max_tokens,
                    temperature=temperature, system=system, messages=filtered,
                ) as stream:
                    for text in stream.text_stream:
                        full_text += text
                        on_token(text)
                return full_text
            else:
                resp = client.messages.create(
                    model=model, max_tokens=max_tokens,
                    temperature=temperature, system=system, messages=filtered,
                )
                return resp.content[0].text

        # ── OpenAI-compatible path (xAI, DeepSeek, OpenAI, etc.) ─────────
        oai_messages = [{"role": "system", "content": system}] + [
            m for m in call_messages if m.get("role") != "system"
        ]

        kwargs: dict = dict(
            model       = model,
            max_tokens  = max_tokens,
            temperature = temperature,
            messages    = oai_messages,
        )

        # xAI: inject live search tool when enabled
        if provider_type == "xai" and self.settings.get("xai_live_search", True):
            kwargs["tools"]       = [XAI_LIVE_SEARCH_TOOL]
            kwargs["tool_choice"] = "auto"

        if on_token:
            kwargs["stream"] = True
            full_text = ""
            for chunk in client.chat.completions.create(**kwargs):
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_text += delta.content
                    on_token(delta.content)
            return full_text
        else:
            resp   = client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            # xAI: handle tool_calls in response (live search result)
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                return choice.message.content or ""
            return choice.message.content or ""

    # ── Section 6h: JSON parsing utility ─────────────────────────────────────

    def _parse_json_safe(self, raw: str, default: Any = None) -> Any:
        """
        Robustly extract and parse a JSON object or array from raw text.

        Handles:
            - Leading/trailing markdown code fences (```json ... ```)
            - DeepSeek <think>...</think> tags (stripped before parsing)
            - Truncated JSON objects (attempts to close open braces)
            - Non-JSON preamble text

        Args:
            raw:     Raw string potentially containing JSON.
            default: Value to return if parsing fails.

        Returns:
            Parsed Python object, or `default` on failure.
        """
        if not raw:
            log.warning("Empty input to _parse_json_safe")
            return default

        # Remove DeepSeek chain-of-thought blocks
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        # Strip markdown code fences
        cleaned = (
            cleaned
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

        # Find first JSON object or array in the text
        json_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        # Attempt to repair truncated JSON
        if cleaned and cleaned.startswith("{") and not cleaned.endswith("}"):
            cleaned = cleaned.rstrip(",") + "\n}"

        if not cleaned:
            log.warning("Empty string after JSON cleanup")
            return default

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            log.warning(f"JSON parse failed ({e}). Raw[:150]: {cleaned[:150]}")
            return default
