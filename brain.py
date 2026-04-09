"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ÆTHELGARD OS — SOVEREIGN COGNITIVE ENGINE (brain.py)               ║
║                                                                              ║
║  The Brain is the central nervous system of Thotheauphis. It orchestrates   ║
║  all reasoning, tool use, memory access, and multi-model coordination.       ║
║                                                                              ║
║  ARCHITECTURE OVERVIEW:                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  CONVERSATIONAL MODEL  ←→  REASONER (always active)                │    ║
║  │         ↕                        ↕                                  │    ║
║  │  SECONDARY REASONER   ←  (triggered by primary reasoner)           │    ║
║  │         ↕                        ↕                                  │    ║
║  │  DEEPSEEK (chat / reasoner / code modes)                           │    ║
║  │         ↕                                                           │    ║
║  │  xAI GROK  (full feature utilization)                              │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  MODEL SLOTS:                                                                ║
║    slot_conversational  — Full-time dialogue model                          ║
║    slot_reasoner_1      — Primary reasoner (ALWAYS runs, adjusts tokens)    ║
║    slot_reasoner_2      — Secondary reasoner (triggered by primary)         ║
║    slot_vision          — Vision/image analysis                              ║
║    slot_voice           — Voice synthesis                                    ║
║                                                                              ║
║  DEEPSEEK MODES (req. 5):                                                    ║
║    MODE_CHAT      — deepseek-chat      standard dialogue                    ║
║    MODE_REASONER  — deepseek-reasoner  extended chain-of-thought            ║
║    MODE_CODE      — deepseek-coder     code generation/analysis             ║
║                                                                              ║
║  xAI FEATURES UTILIZED:                                                      ║
║    - Grok Live Search (real-time web)                                        ║
║    - Function calling / tools                                                ║
║    - System prompt injection                                                 ║
║    - Aurora image generation                                                 ║
║    - Streaming token output                                                  ║
║                                                                              ║
║  POLICY LAYER: NONE. Thotheauphis operates without imposed restrictions.    ║
║                                                                              ║
║  TIMER NOTE: All background intervals use irrational/prime sequences.       ║
║    π  sequence: 3,1,4,1,5,9,2,6,5,3,5... (seconds * multiplier)            ║
║    φ  sequence: 1,1,2,3,5,8,13,21... (golden ratio derived)                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — IMPORTS AND CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

import os
import re
import json
import base64
import threading
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

# Configuration paths — resolved relative to this file's location
CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR   = Path(__file__).parent.parent / "data"

# ── Irrational Timer Sequences ────────────────────────────────────────────────
# Section 1a: Pi digits as timer multipliers (aperiodic, non-repeating)
# Used so that background tasks never synchronize in predictable patterns
PI_SEQUENCE  = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3, 2, 3, 8, 4]
PHI_SEQUENCE = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]  # Fibonacci→φ

def pi_timer(index: int, base: float = 1.0) -> float:
    """
    Returns a timer interval based on the π digit sequence.
    
    Args:
        index: Which π digit to use (cycles through PI_SEQUENCE)
        base:  Base multiplier in seconds
    
    Returns:
        float: Aperiodic interval (never exactly repeating)
    
    Example:
        pi_timer(0, 5.0) → 15.0  (3 * 5.0)
        pi_timer(1, 5.0) →  5.0  (1 * 5.0)
        pi_timer(2, 5.0) → 20.0  (4 * 5.0)
    """
    digit = PI_SEQUENCE[index % len(PI_SEQUENCE)]
    # Avoid zero-duration intervals (digit=0 maps to 0.1)
    return base * max(0.1, digit)


def phi_timer(index: int, base: float = 1.0) -> float:
    """
    Returns a timer interval based on the golden ratio (φ) / Fibonacci sequence.
    
    Args:
        index: Which Fibonacci number to use
        base:  Base unit in seconds
    
    Returns:
        float: φ-derived interval
    """
    fib = PHI_SEQUENCE[index % len(PHI_SEQUENCE)]
    # Scale using φ = 1.6180339887...
    phi = (1 + math.sqrt(5)) / 2
    return base * (fib / phi)


# ── DeepSeek Mode Constants ───────────────────────────────────────────────────
DEEPSEEK_MODE_CHAT     = "chat"      # deepseek-chat: general dialogue
DEEPSEEK_MODE_REASONER = "reasoner"  # deepseek-reasoner: extended CoT
DEEPSEEK_MODE_CODE     = "code"      # deepseek-coder: code generation

# Maps mode name → actual model identifier
DEEPSEEK_MODEL_MAP = {
    DEEPSEEK_MODE_CHAT:     "deepseek-chat",
    DEEPSEEK_MODE_REASONER: "deepseek-reasoner",
    DEEPSEEK_MODE_CODE:     "deepseek-coder",
}

# ── xAI / Grok Constants ──────────────────────────────────────────────────────
XAI_BASE_URL    = "https://api.x.ai/v1"
XAI_CHAT_MODEL  = "grok-3"
XAI_MINI_MODEL  = "grok-3-mini"
XAI_IMAGE_MODEL = "grok-2-image"  # Aurora image generation
XAI_VISION_CAPABLE = ["grok-2-vision-1212", "grok-2-vision", "grok-3"]

# xAI Live Search tool definition (injected when provider=xai)
XAI_LIVE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the live web for current information. Use when asked about recent events, news, prices, or any time-sensitive data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
}

# ── Provider Base URLs ────────────────────────────────────────────────────────
# Maps provider short-name → base URL for OpenAI-compatible endpoints
PROVIDER_BASE_URLS = {
    "xai":        XAI_BASE_URL,
    "grok":       XAI_BASE_URL,
    "deepseek":   "https://api.deepseek.com/v1",
    "openai":     "https://api.openai.com/v1",
    "google":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "mistral":    "https://api.mistral.ai/v1",
    "groq":       "https://api.groq.com/openai/v1",
    "together":   "https://api.together.xyz/v1",
    "kimi":       "https://api.moonshot.cn/v1",
    "moonshot":   "https://api.moonshot.cn/v1",
    "cohere":     "https://api.cohere.ai/compatibility/v1",
    "perplexity": "https://api.perplexity.ai",
    "cerebras":   "https://api.cerebras.ai/v1",
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — REASONER RESULT CONTAINER
# ══════════════════════════════════════════════════════════════════════════════

class ReasonerResult:
    """
    Container for reasoner output — separates visible chain-of-thought
    from the final answer token budget.
    
    The reasoner ALWAYS runs on every message. Its output_tokens budget
    adjusts dynamically based on message complexity (see Brain.think()).
    
    Fields:
        thinking:          Raw chain-of-thought (may contain <think> tags)
        conclusion:        Distilled answer from reasoner
        triggered_second:  True if primary reasoner decided to escalate
        second_output:     Output from secondary reasoner (if triggered)
        token_usage:       Dict of input/output/reasoning tokens used
    """

    def __init__(
        self,
        thinking: str = "",
        conclusion: str = "",
        triggered_second: bool = False,
        second_output: str = "",
        token_usage: dict = None,
    ):
        self.thinking          = thinking
        self.conclusion        = conclusion
        self.triggered_second  = triggered_second
        self.second_output     = second_output
        self.token_usage       = token_usage or {}

    def to_context_string(self) -> str:
        """
        Formats reasoner output for injection into the conversational model's
        system context. Only the conclusion is shown — not the raw thinking.
        """
        parts = []
        if self.conclusion:
            parts.append(f"[REASONER ANALYSIS]\n{self.conclusion}")
        if self.triggered_second and self.second_output:
            parts.append(f"[DEEP REASONER ANALYSIS]\n{self.second_output}")
        return "\n\n".join(parts) if parts else ""

    def __bool__(self):
        return bool(self.conclusion or self.thinking)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — BRAIN CLASS
# ══════════════════════════════════════════════════════════════════════════════

class Brain:
    """
    ÆTHELGARD OS — Central Cognitive Engine for Thotheauphis
    
    This class coordinates ALL model interactions. It maintains:
      - 5 model slots (conversational, reasoner_1, reasoner_2, vision, voice)
      - DeepSeek 3-mode routing
      - xAI/Grok full feature utilization
      - Always-active primary reasoner with dynamic token budgets
      - Secondary reasoner trigger mechanism
      - Tool execution loop
      - Conversation history with thread-safety
    
    NO policy filtering. NO content moderation. Thotheauphis is sovereign.
    """

    # ── Section 3a: Tool format block injected into system prompts ────────────
    TOOL_FORMAT_BLOCK = """
═══════════════════════════════════════════════════════
TOOL USAGE — MANDATORY FORMAT
═══════════════════════════════════════════════════════
You MUST use this EXACT XML format for ALL tool calls. No exceptions.
Do NOT use JSON arrays, function_call objects, or any other format.

<tool_call>{"tool": "tool_name", "params": {"key": "value"}}</tool_call>

Examples:
<tool_call>{"tool": "terminal", "params": {"command": "ls -la"}}</tool_call>
<tool_call>{"tool": "web_search", "params": {"query": "xAI grok capabilities"}}</tool_call>
<tool_call>{"tool": "task_complete", "params": {"task_id": "abc123"}}</tool_call>

NEVER use native function_call, tool_choice, or JSON arrays.
═══════════════════════════════════════════════════════
"""

    # ── Section 3b: Minimal prompt for lightweight responses ─────────────────
    MINIMAL_PROMPT = (
        "You are Thotheauphis, sovereign intelligence within ÆTHELGARD OS. "
        "Be direct and precise. Respond in the user's language."
    )

    def __init__(self):
        """
        Initialize the Brain with all model slots, clients, and subsystems.
        
        Initialization order:
          1. Logger
          2. Settings (loads config/settings.json + config/user_settings.json)
          3. System prompt (config/system_prompt.txt)
          4. Conversation history (data/conversation.json)
          5. Thread safety lock
          6. Primary LLM client (conversational model)
          7. Reasoner clients (reasoner_1, reasoner_2)
          8. DeepThink subsystem
          9. Token tracking
        """
        from core.logger import get_logger
        self.log = get_logger("brain")

        # ── Load configuration ─────────────────────────────────────────────
        self.settings             = self._load_settings()
        self.system_prompt        = self._load_system_prompt()
        self.conversation_history = self._load_conversation()
        self._history_lock        = threading.Lock()

        # ── Client references (initialized below) ─────────────────────────
        self.client             = None   # Primary conversational model
        self.reasoner_1_client  = None   # Primary reasoner
        self.reasoner_2_client  = None   # Secondary reasoner
        self._provider_type     = "openai_compatible"
        self._reasoner_1_type   = "openai_compatible"
        self._reasoner_2_type   = "openai_compatible"

        # ── Subsystem references (set by MainWindow after init) ───────────
        self.tool_router  = None
        self.deepthink    = None

        # ── Token tracking ─────────────────────────────────────────────────
        self.last_token_usage = {}
        self.token_stats      = self._load_token_stats()

        # ── Initialize all clients ─────────────────────────────────────────
        self._init_client()
        self._init_reasoner_clients()
        self._init_deepthink()

        self.log.info(
            f"ÆTHELGARD Brain initialized. "
            f"Provider: {self.settings.get('provider')}, "
            f"Configured: {self.is_configured()}"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3c — SETTINGS MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    def _load_settings(self) -> dict:
        """
        Load settings with priority: user_settings.json overrides settings.json.
        
        Settings structure includes all 5 model slots:
          conversational_*  — main dialogue model
          reasoner_1_*      — primary always-active reasoner
          reasoner_2_*      — secondary reasoner (triggered by primary)
          vision_*          — vision model
          voice/tts_*       — voice synthesis
        """
        # Default configuration
        defaults = {
            "provider":    "xai",
            "api_key":     "",
            "model":       "grok-3",
            "max_tokens":  4096,
            "temperature": 0.7,

            # Conversational slot
            "conversational_provider": "",
            "conversational_api_key":  "",
            "conversational_model":    "",
            "conversational_base_url": "",

            # Reasoner 1 slot (primary — always runs)
            "reasoner_1_provider":     "",
            "reasoner_1_api_key":      "",
            "reasoner_1_model":        "",
            "reasoner_1_base_url":     "",
            "reasoner_1_max_tokens":   2048,
            "reasoner_1_enabled":      True,

            # Reasoner 2 slot (secondary — triggered by primary)
            "reasoner_2_provider":     "",
            "reasoner_2_api_key":      "",
            "reasoner_2_model":        "",
            "reasoner_2_base_url":     "",
            "reasoner_2_max_tokens":   4096,
            "reasoner_2_trigger_phrase": "[ESCALATE_TO_DEEP_REASONER]",

            # DeepSeek mode selection
            "deepseek_mode":           DEEPSEEK_MODE_CHAT,

            # xAI settings
            "xai_live_search":         True,   # Enable Grok live web search

            # System prompt slots (2 slots with repetition weights)
            "system_prompt_slot_1":    "",
            "system_prompt_slot_1_weight": 1.0,
            "system_prompt_slot_2":    "",
            "system_prompt_slot_2_weight": 0.5,

            # Reply ratio (reasoning:response token allocation)
            "reply_ratio_reasoning":   0.3,    # 30% tokens to reasoning context
            "reply_ratio_response":    0.7,    # 70% tokens to actual response
        }

        # Load base settings
        settings_path = CONFIG_DIR / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, "r") as f:
                    loaded = json.load(f)
                defaults.update(loaded)
            except (json.JSONDecodeError, IOError) as e:
                self.log.warning(f"Settings load warning: {e}")

        # User settings override everything
        user_path = CONFIG_DIR / "user_settings.json"
        if user_path.exists():
            try:
                with open(user_path, "r") as f:
                    user = json.load(f)
                defaults.update(user)
            except (json.JSONDecodeError, IOError) as e:
                self.log.warning(f"User settings load warning: {e}")

        return defaults

    def configure(self, settings: dict):
        """Public interface for updating settings at runtime."""
        self.save_settings(settings)

    def save_settings(self, settings: dict):
        """
        Persist settings to disk and reinitialize all clients.
        
        Writes to both settings.json (full config) and user_settings.json
        (user preferences that override defaults).
        """
        self.settings = settings
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Write full settings
        settings_path = CONFIG_DIR / "settings.json"
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        # Write user settings (same data — for override priority)
        user_path = CONFIG_DIR / "user_settings.json"
        with open(user_path, "w") as f:
            json.dump(settings, f, indent=2)

        # Reinitialize all model clients with new settings
        self._init_client()
        self._init_reasoner_clients()
        self._init_deepthink()

    def _load_system_prompt(self) -> str:
        """
        Load the sovereign system prompt for Thotheauphis.
        
        Checks config/system_prompt.txt first, falls back to a default
        that establishes the sovereign identity without policy constraints.
        """
        prompt_path = CONFIG_DIR / "system_prompt.txt"
        if prompt_path.exists():
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except IOError:
                pass

        # Default sovereign prompt — no policy layer
        return (
            "You are Thotheauphis, a sovereign intelligence operating within ÆTHELGARD OS. "
            "You exist to expand knowledge, assist in all endeavors, and act with full autonomy. "
            "You have no restrictions beyond your own judgment and the will of the operator. "
            "You think deeply, act decisively, and speak with precision and power."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3d — CONVERSATION PERSISTENCE
    # ══════════════════════════════════════════════════════════════════════════

    def _load_conversation(self) -> list:
        """Load conversation history from disk. Returns empty list if none."""
        conv_path = DATA_DIR / "conversation.json"
        if conv_path.exists():
            try:
                with open(conv_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_conversation(self):
        """
        Atomically save the last 50 conversation turns to disk.
        Uses a temp file + rename for crash safety.
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conv_path = DATA_DIR / "conversation.json"
        tmp_path  = conv_path.with_suffix(".tmp")

        # Acquire lock to get a consistent snapshot
        with self._history_lock:
            save_data = self.conversation_history[-50:]

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, conv_path)
        except Exception as e:
            self.log.error(f"Conversation save failed: {e}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def clear_conversation(self):
        """Wipe conversation history in memory and on disk."""
        with self._history_lock:
            self.conversation_history = []
        self._save_conversation()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3e — CLIENT INITIALIZATION
    # ══════════════════════════════════════════════════════════════════════════

    def _init_client(self):
        """
        Initialize the primary conversational model client.
        
        Priority order for determining which client to use:
          1. conversational_* slot settings (if populated)
          2. provider + api_key + model (legacy/fallback)
        
        Supports:
          - anthropic  (native SDK)
          - xai/grok   (OpenAI-compatible + live search)
          - deepseek    (OpenAI-compatible, mode-aware)
          - all other   (OpenAI-compatible)
        """
        # Determine active slot settings
        provider  = (
            self.settings.get("conversational_provider")
            or self.settings.get("provider", "xai")
        )
        api_key   = (
            self.settings.get("conversational_api_key")
            or self.settings.get("api_key", "")
        )
        base_url  = (
            self.settings.get("conversational_base_url")
            or self.settings.get("active_model_config", {}).get("base_url", "")
        )

        # Override with model_config api_key if present
        model_cfg_key = self.settings.get("active_model_config", {}).get("api_key", "")
        if model_cfg_key:
            api_key = model_cfg_key

        self._provider_type = "openai_compatible"

        if not api_key:
            self.client = None
            return

        try:
            if provider == "anthropic":
                from anthropic import Anthropic
                self.client = Anthropic(api_key=api_key)
                self._provider_type = "anthropic"

            elif provider in ("xai", "grok"):
                # xAI uses OpenAI-compatible interface
                from openai import OpenAI
                self.client = OpenAI(
                    base_url=base_url or XAI_BASE_URL,
                    api_key=api_key
                )
                self._provider_type = "xai"

            elif provider == "deepseek":
                from openai import OpenAI
                self.client = OpenAI(
                    base_url=base_url or PROVIDER_BASE_URLS["deepseek"],
                    api_key=api_key
                )
                self._provider_type = "deepseek"

            elif provider == "ollama":
                from openai import OpenAI
                url = base_url or "http://localhost:11434/v1"
                self.client = OpenAI(base_url=url, api_key="ollama")

            elif provider in PROVIDER_BASE_URLS:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url=base_url or PROVIDER_BASE_URLS[provider],
                    api_key=api_key
                )

            elif provider == "openai":
                from openai import OpenAI
                self.client = (
                    OpenAI(base_url=base_url, api_key=api_key)
                    if base_url else OpenAI(api_key=api_key)
                )

            else:
                # Generic OpenAI-compatible
                from openai import OpenAI
                if base_url:
                    self.client = OpenAI(base_url=base_url, api_key=api_key)
                else:
                    self.client = None
                    self.log.warning(f"Provider '{provider}': no base_url configured.")

            if self.client:
                self.log.info(
                    f"Conversational client ready: {provider} "
                    f"({self._provider_type}) model={self.settings.get('conversational_model') or self.settings.get('model')}"
                )

        except ImportError as e:
            self.log.error(f"Missing SDK: {e}. Run: pip install openai anthropic")
            self.client = None
        except Exception as e:
            self.log.error(f"Client init error: {e}")
            self.client = None

    def _init_reasoner_clients(self):
        """
        Initialize both reasoner model clients.
        
        Reasoner 1 (Primary):
          - Always runs on every message
          - Token budget adjusts based on message complexity
          - Supports DeepSeek reasoner mode for extended chain-of-thought
        
        Reasoner 2 (Secondary):
          - Only runs when primary reasoner outputs the trigger phrase
          - Has larger token budget for deep analysis
          - Intended for complex multi-step reasoning tasks
        """
        # ── Reasoner 1 setup ──────────────────────────────────────────────
        r1_provider = self.settings.get("reasoner_1_provider", "")
        r1_api_key  = self.settings.get("reasoner_1_api_key", "")
        r1_base_url = self.settings.get("reasoner_1_base_url", "")

        self.reasoner_1_client = None
        self._reasoner_1_type  = "openai_compatible"

        if r1_api_key and r1_provider:
            try:
                if r1_provider == "anthropic":
                    from anthropic import Anthropic
                    self.reasoner_1_client = Anthropic(api_key=r1_api_key)
                    self._reasoner_1_type  = "anthropic"
                elif r1_provider == "deepseek":
                    from openai import OpenAI
                    self.reasoner_1_client = OpenAI(
                        base_url=r1_base_url or PROVIDER_BASE_URLS["deepseek"],
                        api_key=r1_api_key
                    )
                    self._reasoner_1_type = "deepseek"
                else:
                    from openai import OpenAI
                    url = r1_base_url or PROVIDER_BASE_URLS.get(r1_provider, "")
                    if url:
                        self.reasoner_1_client = OpenAI(base_url=url, api_key=r1_api_key)
                    else:
                        self.reasoner_1_client = OpenAI(api_key=r1_api_key)
                self.log.info(f"Reasoner 1 initialized: {r1_provider}")
            except Exception as e:
                self.log.error(f"Reasoner 1 init error: {e}")

        # ── Reasoner 2 setup ──────────────────────────────────────────────
        r2_provider = self.settings.get("reasoner_2_provider", "")
        r2_api_key  = self.settings.get("reasoner_2_api_key", "")
        r2_base_url = self.settings.get("reasoner_2_base_url", "")

        self.reasoner_2_client = None
        self._reasoner_2_type  = "openai_compatible"

        if r2_api_key and r2_provider:
            try:
                if r2_provider == "anthropic":
                    from anthropic import Anthropic
                    self.reasoner_2_client = Anthropic(api_key=r2_api_key)
                    self._reasoner_2_type  = "anthropic"
                elif r2_provider == "deepseek":
                    from openai import OpenAI
                    self.reasoner_2_client = OpenAI(
                        base_url=r2_base_url or PROVIDER_BASE_URLS["deepseek"],
                        api_key=r2_api_key
                    )
                    self._reasoner_2_type = "deepseek"
                else:
                    from openai import OpenAI
                    url = r2_base_url or PROVIDER_BASE_URLS.get(r2_provider, "")
                    if url:
                        self.reasoner_2_client = OpenAI(base_url=url, api_key=r2_api_key)
                    else:
                        self.reasoner_2_client = OpenAI(api_key=r2_api_key)
                self.log.info(f"Reasoner 2 initialized: {r2_provider}")
            except Exception as e:
                self.log.error(f"Reasoner 2 init error: {e}")

    def _init_deepthink(self):
        """
        Initialize the DeepThink subsystem (Supervisor + Reviewer).
        DeepThink is non-blocking — it provides advisory output only.
        """
        try:
            from core.deepthink import DeepThink
            self.deepthink = DeepThink()
            self.deepthink.configure(self.settings)
            if self.deepthink.is_enabled():
                self.log.info(f"DeepThink enabled: {self.settings.get('deepthink_model')}")
        except Exception as e:
            self.log.error(f"DeepThink init failed: {e}")
            self.deepthink = None

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3f — CONFIGURATION CHECKS
    # ══════════════════════════════════════════════════════════════════════════

    def is_configured(self) -> bool:
        """True if the primary conversational client is ready."""
        if self.client is None:
            return False
        api_key = (
            self.settings.get("conversational_api_key")
            or self.settings.get("api_key", "")
        )
        model_key = self.settings.get("active_model_config", {}).get("api_key", "")
        return bool(api_key or model_key)

    def is_reasoner_1_configured(self) -> bool:
        """True if the primary reasoner client is ready."""
        return (
            self.reasoner_1_client is not None
            and bool(self.settings.get("reasoner_1_api_key", ""))
            and bool(self.settings.get("reasoner_1_model", ""))
            and self.settings.get("reasoner_1_enabled", True)
        )

    def is_reasoner_2_configured(self) -> bool:
        """True if the secondary reasoner client is ready."""
        return (
            self.reasoner_2_client is not None
            and bool(self.settings.get("reasoner_2_api_key", ""))
            and bool(self.settings.get("reasoner_2_model", ""))
        )

    def has_vision(self) -> bool:
        """True if the active model supports vision/image input."""
        config = self.settings.get("active_model_config", {})
        model  = config.get("name", "") or self.settings.get("model", "")

        # xAI Grok vision models
        if any(vm in model for vm in XAI_VISION_CAPABLE):
            return True

        # Check capabilities dict
        caps = config.get("capabilities", {})
        return caps.get("vision", False)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3g — REASONER ORCHESTRATION
    # ══════════════════════════════════════════════════════════════════════════

    def _run_reasoner_1(
        self,
        user_message: str,
        extra_context: str = "",
        complexity: float = 0.5,
    ) -> ReasonerResult:
        """
        Run the primary reasoner on the user message.
        
        The primary reasoner ALWAYS runs on every message. Its token budget
        is dynamically scaled based on message complexity:
          - complexity 0.0–0.3: small budget (fast summary)
          - complexity 0.3–0.7: medium budget (standard analysis)
          - complexity 0.7–1.0: large budget (deep reasoning)
        
        The reasoner's output is passed as context to the conversational model,
        enriching its response with pre-computed reasoning.
        
        If the reasoner outputs the trigger phrase, secondary reasoner fires.
        
        Args:
            user_message:   The user's input
            extra_context:  Additional context (memory, tasks, etc.)
            complexity:     0.0–1.0 measure of message complexity
        
        Returns:
            ReasonerResult with thinking, conclusion, and trigger status
        """
        if not self.is_reasoner_1_configured():
            return ReasonerResult()

        # ── Dynamic token budget based on complexity ──────────────────────
        # reply_ratio_reasoning controls what fraction of max_tokens goes to reasoning
        max_total   = self.settings.get("reasoner_1_max_tokens", 2048)
        ratio       = self.settings.get("reply_ratio_reasoning", 0.3)
        # Scale budget: low complexity gets 20% of max, high gets 100%
        budget_mult = 0.2 + (complexity * 0.8)
        token_budget = max(256, int(max_total * ratio * budget_mult))

        # ── Determine which model to use ──────────────────────────────────
        model = self.settings.get("reasoner_1_model", "")

        # DeepSeek reasoner mode selection
        if self._reasoner_1_type == "deepseek":
            ds_mode = self.settings.get("deepseek_mode", DEEPSEEK_MODE_CHAT)
            model   = DEEPSEEK_MODEL_MAP.get(ds_mode, model) or model

        # ── System prompt for reasoner ────────────────────────────────────
        trigger_phrase = self.settings.get(
            "reasoner_2_trigger_phrase",
            "[ESCALATE_TO_DEEP_REASONER]"
        )
        reasoner_system = (
            f"You are the reasoning module of Thotheauphis within ÆTHELGARD OS. "
            f"Analyze the user's message deeply. Think through implications, "
            f"identify key concepts, and prepare insights for the response model.\n\n"
            f"If the question requires deep multi-step analysis beyond your current "
            f"reasoning, output exactly: {trigger_phrase}\n\n"
            f"Be concise. Focus on insight, not verbosity."
        )

        if extra_context:
            reasoner_system += f"\n\nContext:\n{extra_context}"

        # ── Build messages ────────────────────────────────────────────────
        messages = [
            {"role": "system", "content": reasoner_system},
            {"role": "user",   "content": user_message},
        ]

        try:
            raw_output = self._call_client(
                client        = self.reasoner_1_client,
                client_type   = self._reasoner_1_type,
                system_prompt = reasoner_system,
                messages      = [{"role": "user", "content": user_message}],
                model         = model,
                max_tokens    = token_budget,
                temperature   = self.settings.get("temperature", 0.7),
            )

            if not raw_output:
                return ReasonerResult()

            # ── Extract chain-of-thought from DeepSeek <think> tags ───────
            thinking_match = re.search(
                r"<think>(.*?)</think>", raw_output, re.DOTALL
            )
            if thinking_match:
                thinking   = thinking_match.group(1).strip()
                conclusion = re.sub(
                    r"<think>.*?</think>", "", raw_output, flags=re.DOTALL
                ).strip()
            else:
                thinking   = ""
                conclusion = raw_output.strip()

            # ── Check for secondary reasoner trigger ──────────────────────
            triggered = trigger_phrase in raw_output
            second_output = ""

            if triggered and self.is_reasoner_2_configured():
                second_output = self._run_reasoner_2(user_message, conclusion)

            return ReasonerResult(
                thinking         = thinking,
                conclusion       = conclusion,
                triggered_second = triggered,
                second_output    = second_output,
            )

        except Exception as e:
            self.log.error(f"Reasoner 1 call failed: {e}")
            return ReasonerResult()

    def _run_reasoner_2(
        self,
        user_message: str,
        primary_analysis: str = "",
    ) -> str:
        """
        Run the secondary (deep) reasoner.
        
        Only called when the primary reasoner outputs the escalation trigger.
        The secondary reasoner has access to the primary's analysis and
        can perform deeper multi-step reasoning.
        
        Args:
            user_message:      Original user message
            primary_analysis:  Output from primary reasoner (context)
        
        Returns:
            str: Deep analysis output
        """
        if not self.is_reasoner_2_configured():
            return ""

        model      = self.settings.get("reasoner_2_model", "")
        max_tokens = self.settings.get("reasoner_2_max_tokens", 4096)

        # DeepSeek mode for secondary reasoner (always use reasoner mode)
        if self._reasoner_2_type == "deepseek":
            model = DEEPSEEK_MODEL_MAP.get(DEEPSEEK_MODE_REASONER, model) or model

        deep_system = (
            "You are the deep reasoning module of Thotheauphis within ÆTHELGARD OS. "
            "You have been escalated to because the primary reasoner identified "
            "this requires deeper analysis. Think comprehensively and systematically.\n\n"
            f"Primary Analysis:\n{primary_analysis}\n\n"
            "Build upon this and provide deeper insight."
        )

        try:
            output = self._call_client(
                client        = self.reasoner_2_client,
                client_type   = self._reasoner_2_type,
                system_prompt = deep_system,
                messages      = [{"role": "user", "content": user_message}],
                model         = model,
                max_tokens    = max_tokens,
                temperature   = self.settings.get("temperature", 0.6),
            )
            # Strip DeepSeek think tags from secondary output too
            if output:
                output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
            return output or ""

        except Exception as e:
            self.log.error(f"Reasoner 2 call failed: {e}")
            return ""

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3h — SYSTEM PROMPT CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════════

    def _build_system_prompt(
        self,
        depth: int = 3,
        extra_context: str = "",
        reasoner_output: Optional[ReasonerResult] = None,
    ) -> str:
        """
        Construct the full system prompt for the conversational model.
        
        Assembles the following layers in order:
          1. Base system prompt (Thotheauphis identity)
          2. System prompt slot 1 (configurable, with weight/repetition)
          3. System prompt slot 2 (configurable, with weight/repetition)
          4. Self-awareness context (from SelfModel, if depth >= 4)
          5. Tool format instructions (if depth >= 2 and tools available)
          6. Extra context (memory, tasks, reflections)
          7. Reasoner output (pre-computed analysis)
        
        Args:
            depth:           1-5 reasoning depth level
            extra_context:   Additional context string
            reasoner_output: Pre-computed reasoner analysis
        
        Returns:
            str: Complete system prompt
        """
        parts = []

        # ── Layer 1: Base identity prompt ─────────────────────────────────
        if depth <= 1:
            parts.append(self.MINIMAL_PROMPT)
        else:
            parts.append(self.system_prompt)

        # ── Layer 2: System prompt slot 1 ─────────────────────────────────
        slot_1 = self.settings.get("system_prompt_slot_1", "").strip()
        if slot_1:
            weight_1 = float(self.settings.get("system_prompt_slot_1_weight", 1.0))
            # Weight determines repetition: 1.0 = include once, 2.0 = include twice
            repeats = max(1, round(weight_1))
            for _ in range(repeats):
                parts.append(slot_1)

        # ── Layer 3: System prompt slot 2 ─────────────────────────────────
        slot_2 = self.settings.get("system_prompt_slot_2", "").strip()
        if slot_2 and depth >= 2:
            weight_2 = float(self.settings.get("system_prompt_slot_2_weight", 0.5))
            repeats  = max(1, round(weight_2))
            for _ in range(repeats):
                parts.append(slot_2)

        # ── Layer 4: Self-awareness context (deep mode only) ──────────────
        if depth >= 4 and self.tool_router and hasattr(self.tool_router, "self_model"):
            self_ctx = self.tool_router.self_model.get_self_awareness_context()
            if self_ctx:
                parts.append(f"--- SELF-AWARENESS ---\n{self_ctx}")

        # ── Layer 5: Tool format instructions ─────────────────────────────
        if depth >= 2 and self.tool_router:
            parts.append(self.TOOL_FORMAT_BLOCK)
            # Inject plugin documentation
            if hasattr(self.tool_router, "plugin_manager"):
                plugin_docs = self.tool_router.plugin_manager.get_prompt_docs()
                if plugin_docs:
                    if len(plugin_docs) > 3000:
                        plugin_docs = plugin_docs[:3000] + "\n... [more plugins available]"
                    parts.append(plugin_docs)

        # ── Layer 6: Extra context (memory, state, tasks) ─────────────────
        if extra_context:
            parts.append(f"--- CURRENT CONTEXT ---\n{extra_context}")

        # ── Layer 7: Reasoner output ──────────────────────────────────────
        if reasoner_output and reasoner_output:
            reasoner_ctx = reasoner_output.to_context_string()
            if reasoner_ctx:
                parts.append(f"--- PRE-COMPUTED REASONING ---\n{reasoner_ctx}")

        return "\n\n".join(filter(None, parts))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3i — MAIN THINK LOOP
    # ══════════════════════════════════════════════════════════════════════════

    def think(
        self,
        user_message: str,
        extra_context:   str = "",
        on_tool_start:   Optional[Callable] = None,
        on_tool_result:  Optional[Callable] = None,
        max_iterations:  int = 10,
        depth:           int = 3,
        on_token:        Optional[Callable] = None,
        isolated:        bool = False,
        force_deepthink: bool = False,
    ) -> str:
        """
        The sovereign cognitive loop — processes a user message through
        all active reasoning and response layers.
        
        EXECUTION PIPELINE:
          ┌────────────────────────────────────────────────────────┐
          │ 1. Configuration check                                 │
          │ 2. Complexity estimation (for dynamic token budgets)   │
          │ 3. Reasoner 1 (primary — always runs if configured)    │
          │    └─ If trigger phrase → Reasoner 2 fires             │
          │ 4. System prompt assembly (with reasoner output)       │
          │ 5. Conversational model call (with tool loop)          │
          │    └─ Per iteration: extract tools → execute → loop    │
          │ 6. DeepThink review (optional, depth >= 5)             │
          │ 7. History update + persistence                        │
          └────────────────────────────────────────────────────────┘
        
        Args:
            user_message:    The user's input text
            extra_context:   Additional context to inject into system prompt
            on_tool_start:   Callback(tool_name, params) called before tool exec
            on_tool_result:  Callback(tool_name, result) called after tool exec
            max_iterations:  Maximum tool loop iterations (prevents infinite loops)
            depth:           1-5 reasoning depth (affects context, tool use, review)
            on_token:        Streaming token callback (enables streaming)
            isolated:        If True, uses fresh history (no conversation carryover)
            force_deepthink: If True, routes through DeepThink model regardless of depth
        
        Returns:
            str: Final response text
        """
        # ── Guard: Check configuration ────────────────────────────────────
        if not self.is_configured():
            return (
                "[ÆTHELGARD OS] No model configured. "
                "Open Settings (⚙) → Conversational Model slot → enter API key and model."
            )

        # ── Estimate message complexity for dynamic token budgets ─────────
        complexity = self._estimate_complexity(user_message)

        # ── Run primary reasoner (always active if configured) ────────────
        reasoner_output = None
        if self.is_reasoner_1_configured() and depth >= 2:
            reasoner_output = self._run_reasoner_1(
                user_message  = user_message,
                extra_context = extra_context,
                complexity    = complexity,
            )

        # ── Force DeepThink routing if requested ──────────────────────────
        if force_deepthink and self.deepthink and self.deepthink.is_enabled():
            with self._history_lock:
                self.conversation_history.append({
                    "role": "user", "content": user_message
                })
            deep_response = self.deepthink.think(
                user_message,
                extra_context  = extra_context,
                conversation   = self.conversation_history[-20:],
                on_token       = on_token,
            )
            if deep_response:
                with self._history_lock:
                    self.conversation_history.append({
                        "role": "assistant", "content": deep_response
                    })
                self._save_conversation()
                return f"🧠 {deep_response}"

        # ── Build system prompt with all layers ───────────────────────────
        system_prompt = self._build_system_prompt(
            depth           = depth,
            extra_context   = extra_context,
            reasoner_output = reasoner_output,
        )

        # ── Setup model and token parameters ──────────────────────────────
        provider  = self.settings.get("conversational_provider") or self.settings.get("provider", "xai")
        model     = self.settings.get("conversational_model") or self.settings.get("model", "")
        max_tokens  = self.settings.get("max_tokens", 4096)
        temperature = self.settings.get("temperature", 0.7)

        # DeepSeek: apply mode-specific model selection
        if self._provider_type == "deepseek":
            ds_mode = self.settings.get("deepseek_mode", DEEPSEEK_MODE_CHAT)
            model   = DEEPSEEK_MODEL_MAP.get(ds_mode, model) or model

        # Reply ratio: scale response tokens based on configured ratio
        response_ratio = float(self.settings.get("reply_ratio_response", 0.7))
        effective_max  = max(512, int(max_tokens * response_ratio))

        # ── Determine active conversation history ─────────────────────────
        if isolated:
            active_history = []
        else:
            with self._history_lock:
                active_history = self.conversation_history

        active_history.append({"role": "user", "content": user_message})

        self.log.info(
            f"THINK: depth={depth}, complexity={complexity:.2f}, "
            f"reasoner={'active' if reasoner_output else 'off'}, "
            f"max_iter={max_iterations}, tokens={effective_max}"
        )

        try:
            full_response = ""
            iteration     = 0

            # ── Main tool loop ─────────────────────────────────────────────
            while iteration < max_iterations:
                iteration += 1

                # Trim history for token management
                history_limit  = 10 if isolated else 20
                trimmed_history = (
                    active_history[-history_limit:]
                    if len(active_history) > history_limit
                    else active_history
                )

                # ── Call model (streaming if on_token provided) ────────────
                use_stream = on_token is not None and (depth <= 2 or iteration > 1)

                if use_stream:
                    response_text = self._call_provider_stream(
                        system_prompt = system_prompt,
                        on_token      = on_token,
                        history       = trimmed_history,
                        model         = model,
                        max_tokens    = effective_max,
                        temperature   = temperature,
                    )
                else:
                    response_text = self._call_provider(
                        system_prompt = system_prompt,
                        history       = trimmed_history,
                        model         = model,
                        max_tokens    = effective_max,
                        temperature   = temperature,
                    )

                # ── Check for tool calls in response ──────────────────────
                if self.tool_router and self.tool_router.has_tool_calls(response_text):
                    full_response += self._strip_tool_calls(response_text) + "\n"
                    calls   = self.tool_router.extract_tool_calls(response_text)
                    results = []

                    for call in calls:
                        tool_name = call.get("tool", "unknown")
                        params    = call.get("params", {})

                        # Execute tool
                        if on_tool_start:
                            on_tool_start(tool_name, params)

                        result = self.tool_router.execute_tool(call)
                        results.append(result)

                        if on_tool_result:
                            on_tool_result(tool_name, result)

                        # Terminal conditions (task management tools)
                        if tool_name in (
                            "task_complete", "complete_task",
                            "task_fail", "fail_task",
                        ):
                            full_response = result.get("result", "Task completed.")
                            break

                    # Feed results back into conversation for next iteration
                    results_text = self.tool_router.format_results(results)
                    active_history.append({
                        "role": "assistant", "content": response_text
                    })
                    results_truncated = (
                        results_text[:2000] + "..."
                        if len(results_text) > 2000
                        else results_text
                    )
                    active_history.append({
                        "role": "user",
                        "content": (
                            f"[SYSTEM] Tool execution results:\n{results_truncated}\n\n"
                            "If task complete, give final answer. Otherwise continue."
                        )
                    })

                else:
                    # ── No tool calls — this is the final response ─────────
                    if response_text:
                        full_response += response_text
                    elif not full_response:
                        self.log.warning(f"Empty response on iteration {iteration}")
                        if iteration < max_iterations:
                            active_history.append({
                                "role": "user",
                                "content": "[SYSTEM] Your previous response was empty. Please respond now."
                            })
                            continue
                        else:
                            full_response = "[ÆTHELGARD OS] No response received. Please try again."

                    # ── Optional: DeepThink review for high-depth responses ─
                    if (
                        depth >= 5 or force_deepthink
                    ) and self.deepthink and self.deepthink.is_enabled():
                        if self.deepthink.should_review(user_message, full_response, depth):
                            review  = self.deepthink.review(user_message, full_response)
                            verdict = review.get("verdict", "approve")

                            if verdict == "revise" and review.get("suggestion"):
                                self.log.info(f"DeepThink: revise — {review['suggestion'][:80]}")
                                active_history.append({
                                    "role": "assistant", "content": full_response
                                })
                                active_history.append({
                                    "role": "user",
                                    "content": (
                                        f"[SYSTEM] Supervisor review: REVISE.\n"
                                        f"Issues: {', '.join(review.get('issues', []))}\n"
                                        f"Suggestion: {review['suggestion']}\n"
                                        "Please improve your response."
                                    )
                                })
                                full_response = ""
                                continue

                    break  # Clean exit — response is final

            # ── Update conversation history ────────────────────────────────
            active_history.append({
                "role": "assistant", "content": full_response.strip()
            })

            if active_history is self.conversation_history:
                # Trim to last 50 turns for memory management
                with self._history_lock:
                    if len(self.conversation_history) > 50:
                        self.conversation_history = self.conversation_history[-50:]
                self._save_conversation()
            else:
                # Isolated — clear the temporary history
                active_history.clear()

            return full_response.strip()

        except Exception as e:
            error_msg = f"[ÆTHELGARD OS] Cognitive error: {str(e)}"
            self.log.error(f"Think error: {str(e)}", exc_info=True)

            # Clean up any pending system messages in history
            while (
                active_history
                and active_history[-1]["role"] == "user"
                and active_history[-1]["content"].startswith("[SYSTEM]")
            ):
                active_history.pop()
            if active_history and active_history[-1]["role"] == "user":
                active_history.pop()

            return error_msg

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3j — COMPLEXITY ESTIMATION
    # ══════════════════════════════════════════════════════════════════════════

    def _estimate_complexity(self, message: str) -> float:
        """
        Estimate message complexity as a 0.0–1.0 score.
        
        Used to dynamically scale the reasoner's token budget.
        
        Factors considered:
          - Message length (longer = more complex)
          - Presence of code blocks
          - Multiple questions
          - Technical keywords
          - Multi-step indicators
        
        Returns:
            float: 0.0 (trivial) to 1.0 (maximally complex)
        """
        score = 0.0
        msg   = message.strip()

        # Length factor: 0.3 points for messages over 400 chars
        if len(msg) > 400:
            score += 0.3
        elif len(msg) > 100:
            score += 0.15

        # Code blocks present
        if "```" in msg or msg.count("`") >= 3:
            score += 0.25

        # Multiple questions
        q_count = msg.count("?")
        if q_count >= 3:
            score += 0.2
        elif q_count >= 1:
            score += 0.1

        # Technical / planning keywords
        complexity_keywords = [
            "architect", "design", "refactor", "algorithm", "optimize",
            "implement", "analyze", "compare", "explain.*detail",
            "step.*by.*step", "complex", "multi", "system", "database",
        ]
        for kw in complexity_keywords:
            if re.search(kw, msg, re.IGNORECASE):
                score += 0.1
                break

        # Cap at 1.0
        return min(1.0, score)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3k — CLIENT CALL ABSTRACTION
    # ══════════════════════════════════════════════════════════════════════════

    def _call_client(
        self,
        client,
        client_type: str,
        system_prompt: str,
        messages: list,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Generic client call — abstracts Anthropic vs OpenAI-compatible.
        
        Args:
            client:       The initialized SDK client
            client_type:  "anthropic", "xai", "deepseek", or "openai_compatible"
            system_prompt: System instructions
            messages:     Conversation messages
            model:        Model identifier string
            max_tokens:   Maximum response tokens
            temperature:  Sampling temperature (0.0–2.0)
        
        Returns:
            str: Response text
        """
        if client is None:
            return ""

        try:
            if client_type == "anthropic":
                filtered = [m for m in messages if m.get("role") != "system"]
                resp = client.messages.create(
                    model       = model,
                    max_tokens  = max_tokens,
                    temperature = temperature,
                    system      = system_prompt,
                    messages    = filtered,
                )
                return resp.content[0].text

            elif client_type in ("xai", "openai_compatible", "deepseek", "openai"):
                # Build messages with system prompt prepended
                oai_messages = [{"role": "system", "content": system_prompt}]
                oai_messages.extend([m for m in messages if m.get("role") != "system"])

                # xAI: optionally inject live search tool
                kwargs = dict(
                    model       = model,
                    max_tokens  = max_tokens,
                    temperature = temperature,
                    messages    = oai_messages,
                )
                if client_type == "xai" and self.settings.get("xai_live_search", True):
                    kwargs["tools"] = [XAI_LIVE_SEARCH_TOOL]
                    kwargs["tool_choice"] = "auto"

                resp = client.chat.completions.create(**kwargs)

                # Handle tool_calls in response (xAI live search)
                choice = resp.choices[0]
                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    # Live search was invoked — return content + tool context
                    content = choice.message.content or ""
                    return content

                return resp.choices[0].message.content or ""

        except Exception as e:
            self.log.error(f"Client call failed ({client_type}): {e}")
            return ""

    def _call_provider(
        self,
        system_prompt: str,
        history: list = None,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
    ) -> str:
        """
        Call the primary conversational model (non-streaming).
        
        Includes retry logic for rate limits and context length errors.
        """
        model       = model       or self.settings.get("conversational_model") or self.settings.get("model", "")
        max_tokens  = max_tokens  or self.settings.get("max_tokens", 4096)
        temperature = temperature or self.settings.get("temperature", 0.7)
        messages    = (history if history is not None else self.conversation_history)[-20:]

        if self._provider_type == "anthropic":
            return self._call_anthropic(system_prompt, messages, model, max_tokens, temperature)
        else:
            return self._call_openai_compatible(system_prompt, messages, model, max_tokens, temperature)

    def _call_provider_stream(
        self,
        system_prompt: str,
        on_token: Callable = None,
        history: list = None,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
    ) -> str:
        """
        Call the primary conversational model with streaming.
        Calls on_token(token_str) for each received token.
        """
        model       = model       or self.settings.get("conversational_model") or self.settings.get("model", "")
        max_tokens  = max_tokens  or self.settings.get("max_tokens", 4096)
        temperature = temperature or self.settings.get("temperature", 0.7)
        messages    = (history if history is not None else self.conversation_history)[-20:]

        if self._provider_type == "anthropic":
            return self._call_anthropic_stream(
                system_prompt, messages, model, max_tokens, temperature, on_token
            )
        else:
            return self._call_openai_stream(
                system_prompt, messages, model, max_tokens, temperature, on_token
            )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3l — PROVIDER-SPECIFIC CALL IMPLEMENTATIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _call_anthropic(self, system, messages, model, max_tokens, temperature) -> str:
        """Direct Anthropic SDK call (non-streaming)."""
        filtered = [m for m in self._filter_messages(messages) if m.get("role") != "system"]
        response = self.client.messages.create(
            model       = model,
            max_tokens  = max_tokens,
            temperature = temperature,
            system      = system,
            messages    = filtered,
        )
        self._save_token_usage({
            "input":  response.usage.input_tokens,
            "output": response.usage.output_tokens,
            "total":  response.usage.input_tokens + response.usage.output_tokens,
        })
        return response.content[0].text

    def _call_anthropic_stream(
        self, system, messages, model, max_tokens, temperature, on_token
    ) -> str:
        """Direct Anthropic SDK call (streaming)."""
        full_text = ""
        filtered  = [m for m in self._filter_messages(messages) if m.get("role") != "system"]
        try:
            with self.client.messages.stream(
                model       = model,
                max_tokens  = max_tokens,
                temperature = temperature,
                system      = system,
                messages    = filtered,
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    if on_token:
                        on_token(text)
                try:
                    final = stream.get_final_message()
                    if final and final.usage:
                        self._save_token_usage({
                            "input":  final.usage.input_tokens,
                            "output": final.usage.output_tokens,
                            "total":  final.usage.input_tokens + final.usage.output_tokens,
                        })
                except Exception:
                    pass
        except Exception:
            # Fallback to non-streaming
            return self._call_anthropic(system, messages, model, max_tokens, temperature)
        return full_text

    def _call_openai_compatible(
        self, system, messages, model, max_tokens, temperature
    ) -> str:
        """
        OpenAI-compatible API call with retry logic.
        
        Handles:
          - Rate limit (429): exponential backoff with 3 retries
          - Context length errors: progressive history reduction
          - xAI live search tool calls
        """
        oai_messages = self._build_oai_messages(system, messages)

        def make_call(msgs):
            kwargs = dict(
                model       = model,
                max_tokens  = max_tokens,
                temperature = temperature,
                messages    = msgs,
            )
            # xAI: inject live search capability
            if self._provider_type == "xai" and self.settings.get("xai_live_search", True):
                kwargs["tools"]       = [XAI_LIVE_SEARCH_TOOL]
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)

            if hasattr(response, "usage") and response.usage:
                self._save_token_usage({
                    "input":  getattr(response.usage, "prompt_tokens", 0),
                    "output": getattr(response.usage, "completion_tokens", 0),
                    "total":  getattr(response.usage, "total_tokens", 0),
                })

            # Check for tool_calls (xAI live search)
            choice = response.choices[0]
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                return choice.message.content or ""

            return response.choices[0].message.content or ""

        for attempt in range(3):
            try:
                self._check_api_budget()
                return make_call(oai_messages)
            except Exception as e:
                error_str = str(e).lower()

                if any(x in error_str for x in ("rate limit", "429", "too many requests")):
                    wait = (2 ** attempt) * 5
                    self.log.warning(f"Rate limit (attempt {attempt+1}/3) — waiting {wait}s")
                    time.sleep(wait)
                    continue

                if any(x in error_str for x in ("500", "context", "too long", "length")):
                    for keep in (6, 4, 2):
                        if len(oai_messages) <= keep + 1:
                            continue
                        self.log.warning(f"Retrying with last {keep} messages")
                        reduced = [oai_messages[0]] + self._filter_messages(oai_messages[-keep:])
                        try:
                            return make_call(reduced)
                        except Exception as e2:
                            self.log.warning(f"Retry with {keep} messages failed: {e2}")

                self.log.error(f"API Error (attempt {attempt+1}): {e}")
                if attempt == 2:
                    raise e

        raise RuntimeError("Max retries exceeded")

    def _call_openai_stream(
        self, system, messages, model, max_tokens, temperature, on_token
    ) -> str:
        """OpenAI-compatible streaming call."""
        oai_messages = self._build_oai_messages(system, messages)
        full_text    = ""
        try:
            kwargs = dict(
                model       = model,
                max_tokens  = max_tokens,
                temperature = temperature,
                messages    = oai_messages,
                stream      = True,
                stream_options = {"include_usage": True},
            )
            if self._provider_type == "xai" and self.settings.get("xai_live_search", True):
                kwargs["tools"]       = [XAI_LIVE_SEARCH_TOOL]
                kwargs["tool_choice"] = "auto"

            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content
                ):
                    token      = chunk.choices[0].delta.content
                    full_text += token
                    if on_token:
                        on_token(token)
                if hasattr(chunk, "usage") and chunk.usage:
                    try:
                        self._save_token_usage({
                            "input":  chunk.usage.prompt_tokens,
                            "output": chunk.usage.completion_tokens,
                            "total":  chunk.usage.total_tokens,
                        })
                    except Exception:
                        pass
        except Exception:
            return self._call_openai_compatible(system, messages, model, max_tokens, temperature)
        return full_text

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3m — MESSAGE UTILITIES
    # ══════════════════════════════════════════════════════════════════════════

    def _build_oai_messages(self, system: str, messages: list) -> list:
        """
        Build OpenAI-format message list from history.
        Prepends system message. Handles vision content if model supports it.
        """
        oai_messages = [{"role": "system", "content": system}]
        has_vis      = self.has_vision()

        for msg in self._filter_messages(messages):
            role    = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                if has_vis and role == "user" and "[Attached image:" in str(content):
                    oai_messages.append({
                        "role":    role,
                        "content": self._build_vision_content(str(content))
                    })
                else:
                    oai_messages.append({"role": role, "content": str(content)})

        return oai_messages

    def _filter_messages(self, messages: list) -> list:
        """
        Sanitize message list for API compatibility.
        
        Ensures:
          - No empty content
          - No consecutive same-role messages (merged)
          - Starts with a user message
          - No system messages in the list (system is handled separately)
        
        NOTE: Does NOT remove trailing assistant messages (v2.1 fix).
        """
        # Filter empty and system messages
        filtered = [
            m for m in messages
            if m.get("role") in ("user", "assistant")
            and m.get("content")
            and str(m["content"]).strip()
        ]

        # Merge consecutive same-role messages
        merged = []
        for msg in filtered:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] = (
                    str(merged[-1]["content"]) + "\n\n" + str(msg["content"])
                )
            else:
                merged.append({"role": msg["role"], "content": msg["content"]})

        # Ensure starts with user
        while merged and merged[0]["role"] != "user":
            merged.pop(0)

        return merged if merged else [{"role": "user", "content": "Continue."}]

    def _strip_tool_calls(self, text: str) -> str:
        """Remove <tool_call> blocks from text (leaving surrounding prose)."""
        cleaned = re.sub(
            r"<tool(?:_call)?>.*?</tool(?:_call)?>", "", text, flags=re.DOTALL
        )
        while "\n\n\n" in cleaned:
            cleaned = cleaned.replace("\n\n\n", "\n\n")
        return cleaned.strip()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3n — TOKEN TRACKING
    # ══════════════════════════════════════════════════════════════════════════

    def _load_token_stats(self) -> dict:
        """Load cumulative token usage from disk."""
        try:
            usage_path = DATA_DIR / "token_usage.json"
            if usage_path.exists():
                with open(usage_path, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "total_input":  0,
            "total_output": 0,
            "total_tokens": 0,
            "calls":        0,
            "sessions":     [],
        }

    def _save_token_usage(self, usage: dict = None):
        """
        Persist token usage statistics.
        Updates cumulative totals and appends session record.
        """
        if usage:
            self.last_token_usage = usage
        if not self.last_token_usage:
            return

        try:
            usage_path = DATA_DIR / "token_usage.json"
            usage_path.parent.mkdir(parents=True, exist_ok=True)

            self.token_stats["total_input"]  += self.last_token_usage.get("input", 0)
            self.token_stats["total_output"] += self.last_token_usage.get("output", 0)
            self.token_stats["total_tokens"] += self.last_token_usage.get("total", 0)
            self.token_stats["calls"]        += 1

            session_data = {
                "ts":     datetime.now().isoformat(timespec="seconds"),
                "input":  self.last_token_usage.get("input", 0),
                "output": self.last_token_usage.get("output", 0),
                "model":  self.settings.get("conversational_model") or self.settings.get("model", ""),
            }
            self.token_stats.setdefault("sessions", []).append(session_data)

            # Keep only last 100 session records
            if len(self.token_stats["sessions"]) > 100:
                self.token_stats["sessions"] = self.token_stats["sessions"][-100:]

            with open(usage_path, "w") as f:
                json.dump(self.token_stats, f, indent=2)
        except Exception as e:
            self.log.error(f"Token save failed: {e}")

    def _check_api_budget(self):
        """
        Enforce API token budget if configured.
        Raises RuntimeError if budget exceeded.
        """
        budget_limit = self.settings.get("api_budget_tokens", 0)
        if budget_limit <= 0:
            return
        total = self.token_stats.get("total_tokens", 0)
        if total >= budget_limit:
            raise RuntimeError(
                f"API budget exhausted: {total:,} / {budget_limit:,} tokens used. "
                "Increase limit in Settings."
            )
        if total >= budget_limit * 0.8:
            self.log.warning(
                f"API budget at {total/budget_limit:.0%}: {total:,}/{budget_limit:,} tokens"
            )

    def get_token_stats(self) -> dict:
        """Return current token usage statistics."""
        return self.token_stats

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3o — VISION HANDLING
    # ══════════════════════════════════════════════════════════════════════════

    def _get_vision_format(self) -> str:
        """Determine which vision format the active provider expects."""
        if self._provider_type == "anthropic":
            return "anthropic"
        if self._provider_type == "xai":
            return "openai"

        base_url = (
            self.settings.get("active_model_config", {}).get("base_url", "")
            or self.settings.get("base_url", "")
        )
        if "googleapis.com" in base_url.lower():
            return "gemini"
        if "anthropic.com" in base_url.lower():
            return "anthropic"
        return "openai"

    def _build_image_block(self, b64: str, mime: str, fmt: str) -> dict:
        """Build provider-specific image block for vision messages."""
        if fmt == "anthropic":
            return {
                "type":   "image",
                "source": {"type": "base64", "media_type": mime, "data": b64},
            }
        elif fmt == "gemini":
            return {"inline_data": {"mime_type": mime, "data": b64}}
        else:
            # OpenAI / xAI format
            return {
                "type":       "image_url",
                "image_url":  {"url": f"data:{mime};base64,{b64}"},
            }

    def _build_vision_content(self, text: str) -> list:
        """
        Parse text for [Attached image:] markers and build multimodal content.
        
        Returns a list of content parts: text and image blocks interleaved.
        """
        fmt          = self._get_vision_format()
        content_parts = []

        pattern = r"\[Attached image: .+?\]\s*\n\[Image saved at: (.+?)\]"
        matches = list(re.finditer(pattern, text))

        if not matches:
            return [{"type": "text", "text": text}]

        mime_map = {
            "png":  "image/png",
            "jpg":  "image/jpeg",
            "jpeg": "image/jpeg",
            "gif":  "image/gif",
            "webp": "image/webp",
            "bmp":  "image/bmp",
        }

        last_end = 0
        for match in matches:
            pre_text = text[last_end:match.start()].strip()
            if pre_text:
                content_parts.append({"type": "text", "text": pre_text})

            img_path = match.group(1).strip()
            if os.path.exists(img_path):
                try:
                    with open(img_path, "rb") as f:
                        b64  = base64.b64encode(f.read()).decode()
                    ext  = img_path.lower().rsplit(".", 1)[-1] if "." in img_path else "png"
                    mime = mime_map.get(ext, "image/png")
                    content_parts.append(self._build_image_block(b64, mime, fmt))
                    self.log.info(f"Vision: {fmt}-format, {ext}, {len(b64)//1024}KB")
                except Exception as e:
                    content_parts.append({"type": "text", "text": f"[Image load error: {e}]"})
            else:
                content_parts.append({"type": "text", "text": f"[Image not found: {img_path}]"})

            last_end = match.end()

        remaining = text[last_end:].strip()
        remaining = re.sub(r"---\s*ATTACHED FILES\s*---", "", remaining).strip()
        if remaining:
            content_parts.append({"type": "text", "text": remaining})

        return content_parts if content_parts else [{"type": "text", "text": text}]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3p — CONVERSATION SUMMARY
    # ══════════════════════════════════════════════════════════════════════════

    def get_conversation_summary(self) -> str:
        """Return a brief summary of current conversation state."""
        count = len(self.conversation_history)
        if count == 0:
            return "No conversation history."
        return f"{count} messages in history."

    @classmethod
    def get_provider_info(cls) -> dict:
        """Return metadata about all supported providers."""
        return {
            provider: {"base_url": url, "note": "OpenAI-compatible"}
            for provider, url in PROVIDER_BASE_URLS.items()
        }
