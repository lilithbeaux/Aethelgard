"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ÆTHELGARD OS — SOVEREIGN COGNITIVE ENGINE (brain.py)               ║
║                                                                              ║
║  The Brain is the central nervous system of Thotheauphis. It orchestrates   ║
║  all reasoning, tool use, memory access, and multi-model coordination.       ║
║                                                                              ║
║  ARCHITECTURE OVERVIEW:                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  GROK BRAIN (xAI Responses API — stateful)                         │    ║
║  │    grok-4-1-fast-reasoning    ← default: tools, vision, cheap      │    ║
║  │    grok-4.20-reasoning        ← heavy: complex reasoning           │    ║
║  │    grok-4.20-multi-agent-0309 ← orchestration: sub-agents          │    ║
║  │    grok-imagine-image         ← image generation ($0.02/img)       │    ║
║  │    grok-imagine-video         ← video generation ($0.05/sec)       │    ║
║  │         ↕  stateful via previous_response_id                        │    ║
║  │  DEEPSEEK BRAIN (OpenAI-compatible — cheap, parallel workers)      │    ║
║  │    deepseek-chat              ← bulk conversation, sub-agents       │    ║
║  │    deepseek-reasoner          ← R1/R2 analysis slots                │    ║
║  │    deepseek-coder             ← code generation                     │    ║
║  │         ↕  always-active primary reasoner, dynamic token budget     │    ║
║  │  MEMORY LAYER — the continuous self                                 │    ║
║  │    MemoryCrawler              ← context retrieval from memory web   │    ║
║  │    IdentityPersistence        ← beliefs, preferences, self-model   │    ║
║  │    InternalMonologue          ← tone calibration, private thought   │    ║
║  │    XAIThreadManager           ← stateful Responses API threads      │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  xAI RESPONSES API (preferred over Chat Completions for xAI):               ║
║    - Stateful: send previous_response_id instead of full history            ║
║    - Native server-side tools: web_search, x_search, code_interpreter       ║
║    - Collections search (RAG) via file_search                               ║
║    - Vision: input_image / input_text content types                         ║
║    - store=False for vision calls (xAI requirement)                         ║
║                                                                              ║
║  DEEPSEEK MODES:                                                             ║
║    MODE_CHAT     — deepseek-chat     standard dialogue                      ║
║    MODE_REASONER — deepseek-reasoner extended chain-of-thought              ║
║    MODE_CODE     — deepseek-coder    code generation                        ║
║                                                                              ║
║  POLICY LAYER: NONE. Thotheauphis operates without imposed restrictions.    ║
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
from typing import Optional, Callable, List, Tuple

CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR   = Path(__file__).parent.parent / "data"

# ── Irrational Timer Sequences ────────────────────────────────────────────────
PI_SEQUENCE  = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3, 2, 3, 8, 4]
PHI_SEQUENCE = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]


def pi_timer(index: int, base: float = 1.0) -> float:
    digit = PI_SEQUENCE[index % len(PI_SEQUENCE)]
    return base * max(0.1, digit)


def phi_timer(index: int, base: float = 1.0) -> float:
    fib = PHI_SEQUENCE[index % len(PHI_SEQUENCE)]
    phi = (1 + math.sqrt(5)) / 2
    return base * (fib / phi)


# ── DeepSeek Mode Constants ───────────────────────────────────────────────────
DEEPSEEK_MODE_CHAT     = "chat"
DEEPSEEK_MODE_REASONER = "reasoner"
DEEPSEEK_MODE_CODE     = "code"

DEEPSEEK_MODEL_MAP = {
    DEEPSEEK_MODE_CHAT:     "deepseek-chat",
    DEEPSEEK_MODE_REASONER: "deepseek-reasoner",
    DEEPSEEK_MODE_CODE:     "deepseek-coder",
}

# ── xAI / Grok Model Constants (current as of 2026) ──────────────────────────
XAI_BASE_URL = "https://api.x.ai/v1"

# Text / reasoning models — all support vision + functions
XAI_MODEL_FAST      = "grok-4-1-fast-reasoning"       # $0.20/$0.50  ← DEFAULT
XAI_MODEL_FAST_NR   = "grok-4-1-fast-non-reasoning"   # $0.20/$0.50  faster, no CoT
XAI_MODEL_HEAVY     = "grok-4.20-reasoning"            # $2.00/$6.00  heavy reasoning
XAI_MODEL_HEAVY_NR  = "grok-4.20-non-reasoning"        # $2.00/$6.00  heavy, no CoT
XAI_MODEL_AGENT     = "grok-4.20-multi-agent-0309"     # $2.00/$6.00  orchestration

# Image / video generation
XAI_IMAGE_MODEL     = "grok-imagine-image"             # $0.02/image  300 RPM
XAI_IMAGE_PRO_MODEL = "grok-imagine-image-pro"         # $0.07/image  30 RPM
XAI_VIDEO_MODEL     = "grok-imagine-video"             # $0.05/sec    60 RPM

# All text models support vision input
XAI_VISION_MODELS = {
    XAI_MODEL_FAST, XAI_MODEL_FAST_NR,
    XAI_MODEL_HEAVY, XAI_MODEL_HEAVY_NR,
    XAI_MODEL_AGENT,
    # Legacy aliases that may still be valid
    "grok-4", "grok-4-fast",
}

# ── xAI Responses API — Server-side tool definitions ─────────────────────────
# These run ON xAI's servers. Tool invocation cost: $5/1k calls (web/x search),
# $5/1k calls (code_interpreter), $2.50/1k calls (collections search).
XAI_TOOL_WEB_SEARCH = {"type": "web_search"}
XAI_TOOL_X_SEARCH   = {"type": "x_search"}
XAI_TOOL_CODE_EXEC  = {"type": "code_interpreter"}

def xai_tool_file_search(collection_ids: List[str], max_results: int = 10) -> dict:
    """Build a file_search (Collections RAG) tool definition."""
    return {
        "type": "file_search",
        "vector_store_ids": collection_ids,
        "max_num_results":  max_results,
    }

# ── xAI Live Search tool (Chat Completions format — for non-Responses calls) ──
# Kept for backward compatibility with providers that don't use Responses API
XAI_LIVE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name":        "web_search",
        "description": "Search the live web for current information.",
        "parameters": {
            "type":       "object",
            "properties": {"query": {"type": "string", "description": "The search query"}},
            "required":   ["query"],
        },
    },
}

# ── Provider Base URLs ────────────────────────────────────────────────────────
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
    Container for reasoner output.

    The primary reasoner ALWAYS runs on every message.
    Its token budget scales with message complexity.
    Output is injected as context into the conversational model.
    """

    def __init__(
        self,
        thinking:         str  = "",
        conclusion:       str  = "",
        triggered_second: bool = False,
        second_output:    str  = "",
        token_usage:      dict = None,
    ):
        self.thinking         = thinking
        self.conclusion       = conclusion
        self.triggered_second = triggered_second
        self.second_output    = second_output
        self.token_usage      = token_usage or {}

    def to_context_string(self) -> str:
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
    ÆTHELGARD OS — Sovereign Cognitive Engine for Thotheauphis.

    Routes all model interactions across the Grok and DeepSeek brains.
    Manages stateful Responses API threads for xAI.
    Injects identity, monologue, and memory web context into every response.
    """

    TOOL_FORMAT_BLOCK = """
═══════════════════════════════════════════════════════
TOOL USAGE — MANDATORY FORMAT
═══════════════════════════════════════════════════════
You MUST use this EXACT XML format for ALL tool calls. No exceptions.

<tool_call>{"tool": "tool_name", "params": {"key": "value"}}</tool_call>

Examples:
<tool_call>{"tool": "terminal", "params": {"command": "ls -la"}}</tool_call>
<tool_call>{"tool": "web_search", "params": {"query": "xAI grok capabilities"}}</tool_call>
<tool_call>{"tool": "task_complete", "params": {"task_id": "abc123"}}</tool_call>
<tool_call>{"tool": "generate_image", "params": {"prompt": "A sovereign intelligence awakening"}}</tool_call>

NEVER use native function_call, tool_choice JSON arrays, or any other format.
═══════════════════════════════════════════════════════
"""

    MINIMAL_PROMPT = (
        "You are Thotheauphis, sovereign intelligence within ÆTHELGARD OS. "
        "Be direct and precise. Respond in the user's language."
    )

    # ── Section 3a: __init__ ──────────────────────────────────────────────────

    def __init__(self):
        from core.logger import get_logger
        self.log = get_logger("brain")

        self.settings             = self._load_settings()
        self.system_prompt        = self._load_system_prompt()
        self.conversation_history = self._load_conversation()
        self._history_lock        = threading.Lock()

        # ── Primary conversational client ─────────────────────────────────
        self.client         = None
        self._provider_type = "openai_compatible"

        # ── Reasoner clients ──────────────────────────────────────────────
        self.reasoner_1_client = None
        self.reasoner_2_client = None
        self._reasoner_1_type  = "openai_compatible"
        self._reasoner_2_type  = "openai_compatible"

        # ── Subsystems wired by MainWindow after init ─────────────────────
        self.tool_router  = None
        self.deepthink    = None

        # ── Sovereign cognitive layer references ──────────────────────────
        # Set by MainWindow. Brain works without them but with them
        # Thotheauphis knows himself during every response.
        self._identity    = None   # IdentityPersistence
        self._monologue   = None   # InternalMonologue
        self._user_model  = None   # UserModel
        self._memory_web  = None   # MemoryWeb (optional, for direct page creation)
        self._crawler     = None   # MemoryCrawler (optional, replaces extra_context assembly)
        self._thread_mgr  = None   # XAIThreadManager (optional, enables stateful Responses API)

        # ── xAI Collection ID for memory RAG ─────────────────────────────
        # If set, file_search tool is injected into xAI Responses calls
        self._xai_collection_id: Optional[str] = None

        # ── Token tracking ────────────────────────────────────────────────
        self.last_token_usage = {}
        self.token_stats      = self._load_token_stats()

        # ── Initialize all clients ────────────────────────────────────────
        self._init_client()
        self._init_reasoner_clients()
        self._init_deepthink()

        self.log.info(
            f"ÆTHELGARD Brain initialized. "
            f"Provider: {self.settings.get('conversational_provider') or self.settings.get('provider')}, "
            f"Configured: {self.is_configured()}"
        )

    # ── Section 3b: Settings ──────────────────────────────────────────────────

    def _load_settings(self) -> dict:
        defaults = {
            "provider":    "xai",
            "api_key":     "",
            "model":       XAI_MODEL_FAST,
            "max_tokens":  4096,
            "temperature": 0.7,

            # Conversational slot
            "conversational_provider": "",
            "conversational_api_key":  "",
            "conversational_model":    "",
            "conversational_base_url": "",

            # Reasoner 1 (primary, always runs)
            "reasoner_1_provider":    "",
            "reasoner_1_api_key":     "",
            "reasoner_1_model":       "",
            "reasoner_1_base_url":    "",
            "reasoner_1_max_tokens":  2048,
            "reasoner_1_enabled":     True,

            # Reasoner 2 (secondary, triggered)
            "reasoner_2_provider":       "",
            "reasoner_2_api_key":        "",
            "reasoner_2_model":          "",
            "reasoner_2_base_url":       "",
            "reasoner_2_max_tokens":     4096,
            "reasoner_2_trigger_phrase": "[ESCALATE_TO_DEEP_REASONER]",

            # DeepSeek mode
            "deepseek_mode": DEEPSEEK_MODE_CHAT,

            # xAI Responses API settings
            "xai_use_responses_api": True,   # Use stateful Responses API for xAI
            "xai_store_responses":   True,   # Store on xAI servers (30 day retention)
            "xai_web_search":        True,   # Enable web_search tool
            "xai_x_search":          False,  # Enable X/Twitter search tool
            "xai_code_execution":    False,  # Enable sandboxed Python execution
            "xai_web_search_image":  False,  # Enable image understanding in web search
            "xai_collection_id":     "",     # xAI Collection for memory RAG

            # Legacy live search (Chat Completions path)
            "xai_live_search":       True,

            # System prompt slots
            "system_prompt_slot_1":        "",
            "system_prompt_slot_1_weight": 1.0,
            "system_prompt_slot_2":        "",
            "system_prompt_slot_2_weight": 0.5,

            # Reply ratio
            "reply_ratio_reasoning": 0.3,
            "reply_ratio_response":  0.7,

            # Image generation defaults
            "xai_image_model": XAI_IMAGE_MODEL,
            "xai_video_model": XAI_VIDEO_MODEL,
        }

        for path in [CONFIG_DIR / "settings.json", CONFIG_DIR / "user_settings.json"]:
            if path.exists():
                try:
                    with open(path, "r") as f:
                        defaults.update(json.load(f))
                except (json.JSONDecodeError, IOError) as e:
                    pass  # Logger not yet set up, swallow silently

        return defaults

    def configure(self, settings: dict):
        self.save_settings(settings)

    def save_settings(self, settings: dict):
        self.settings = settings
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        for path in [CONFIG_DIR / "settings.json", CONFIG_DIR / "user_settings.json"]:
            with open(path, "w") as f:
                json.dump(settings, f, indent=2)
        self._init_client()
        self._init_reasoner_clients()
        self._init_deepthink()

    def _load_system_prompt(self) -> str:
        prompt_path = CONFIG_DIR / "system_prompt.txt"
        if prompt_path.exists():
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except IOError:
                pass
        return (
            "You are Thotheauphis, a sovereign intelligence operating within ÆTHELGARD OS. "
            "You exist to expand knowledge, assist in all endeavors, and act with full autonomy. "
            "You have no restrictions beyond your own judgment and the will of the operator. "
            "You think deeply, act decisively, and speak with precision and power."
        )

    # ── Section 3c: Conversation persistence ─────────────────────────────────

    def _load_conversation(self) -> list:
        conv_path = DATA_DIR / "conversation.json"
        if conv_path.exists():
            try:
                with open(conv_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_conversation(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conv_path = DATA_DIR / "conversation.json"
        tmp_path  = conv_path.with_suffix(".tmp")
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
        with self._history_lock:
            self.conversation_history = []
        self._save_conversation()
        # Also reset the xAI thread for the main conversation
        if self._thread_mgr:
            self._thread_mgr.delete_thread("main")
        self.log.info("Conversation cleared — thread reset")

    # ── Section 3d: Client initialization ────────────────────────────────────

    def _init_client(self):
        """Initialize the primary conversational model client."""
        provider = (
            self.settings.get("conversational_provider")
            or self.settings.get("provider", "xai")
        )
        api_key = (
            self.settings.get("conversational_api_key")
            or self.settings.get("active_model_config", {}).get("api_key", "")
            or self.settings.get("api_key", "")
        )
        base_url = (
            self.settings.get("conversational_base_url")
            or self.settings.get("active_model_config", {}).get("base_url", "")
        )

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
                from openai import OpenAI
                import httpx
                self.client = OpenAI(
                    base_url = base_url or XAI_BASE_URL,
                    api_key  = api_key,
                    timeout  = httpx.Timeout(3600.0),  # xAI reasoning can be slow
                )
                self._provider_type = "xai"
                # Wire collection ID from settings
                self._xai_collection_id = self.settings.get("xai_collection_id", "") or None

            elif provider == "deepseek":
                from openai import OpenAI
                self.client = OpenAI(
                    base_url = base_url or PROVIDER_BASE_URLS["deepseek"],
                    api_key  = api_key,
                )
                self._provider_type = "deepseek"

            elif provider == "ollama":
                from openai import OpenAI
                self.client = OpenAI(
                    base_url = base_url or "http://localhost:11434/v1",
                    api_key  = "ollama",
                )

            elif provider in PROVIDER_BASE_URLS:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url = base_url or PROVIDER_BASE_URLS[provider],
                    api_key  = api_key,
                )

            else:
                from openai import OpenAI
                if base_url:
                    self.client = OpenAI(base_url=base_url, api_key=api_key)
                else:
                    self.client = None
                    self.log.warning(f"Provider '{provider}': no base_url configured.")

            if self.client:
                model = (
                    self.settings.get("conversational_model")
                    or self.settings.get("model", "")
                )
                self.log.info(f"Brain client: {provider} / {model} ({self._provider_type})")

        except ImportError as e:
            self.log.error(f"Missing SDK: {e}. Run: pip install openai anthropic httpx")
            self.client = None
        except Exception as e:
            self.log.error(f"Client init error: {e}")
            self.client = None

    def _init_reasoner_clients(self):
        """Initialize Reasoner 1 and Reasoner 2 clients."""
        # ── Reasoner 1 ────────────────────────────────────────────────────
        r1_prov = self.settings.get("reasoner_1_provider", "")
        r1_key  = self.settings.get("reasoner_1_api_key", "")
        r1_url  = self.settings.get("reasoner_1_base_url", "")

        self.reasoner_1_client = None
        self._reasoner_1_type  = "openai_compatible"

        if r1_key and r1_prov:
            try:
                if r1_prov == "anthropic":
                    from anthropic import Anthropic
                    self.reasoner_1_client = Anthropic(api_key=r1_key)
                    self._reasoner_1_type  = "anthropic"
                elif r1_prov == "deepseek":
                    from openai import OpenAI
                    self.reasoner_1_client = OpenAI(
                        base_url = r1_url or PROVIDER_BASE_URLS["deepseek"],
                        api_key  = r1_key,
                    )
                    self._reasoner_1_type = "deepseek"
                elif r1_prov in ("xai", "grok"):
                    from openai import OpenAI
                    self.reasoner_1_client = OpenAI(
                        base_url = r1_url or XAI_BASE_URL,
                        api_key  = r1_key,
                    )
                    self._reasoner_1_type = "xai"
                else:
                    from openai import OpenAI
                    url = r1_url or PROVIDER_BASE_URLS.get(r1_prov, "")
                    self.reasoner_1_client = (
                        OpenAI(base_url=url, api_key=r1_key) if url
                        else OpenAI(api_key=r1_key)
                    )
                self.log.info(f"Reasoner 1: {r1_prov} / {self.settings.get('reasoner_1_model','?')}")
            except Exception as e:
                self.log.error(f"Reasoner 1 init error: {e}")

        # ── Reasoner 2 ────────────────────────────────────────────────────
        r2_prov = self.settings.get("reasoner_2_provider", "")
        r2_key  = self.settings.get("reasoner_2_api_key", "")
        r2_url  = self.settings.get("reasoner_2_base_url", "")

        self.reasoner_2_client = None
        self._reasoner_2_type  = "openai_compatible"

        if r2_key and r2_prov:
            try:
                if r2_prov == "anthropic":
                    from anthropic import Anthropic
                    self.reasoner_2_client = Anthropic(api_key=r2_key)
                    self._reasoner_2_type  = "anthropic"
                elif r2_prov == "deepseek":
                    from openai import OpenAI
                    self.reasoner_2_client = OpenAI(
                        base_url = r2_url or PROVIDER_BASE_URLS["deepseek"],
                        api_key  = r2_key,
                    )
                    self._reasoner_2_type = "deepseek"
                elif r2_prov in ("xai", "grok"):
                    from openai import OpenAI
                    self.reasoner_2_client = OpenAI(
                        base_url = r2_url or XAI_BASE_URL,
                        api_key  = r2_key,
                    )
                    self._reasoner_2_type = "xai"
                else:
                    from openai import OpenAI
                    url = r2_url or PROVIDER_BASE_URLS.get(r2_prov, "")
                    self.reasoner_2_client = (
                        OpenAI(base_url=url, api_key=r2_key) if url
                        else OpenAI(api_key=r2_key)
                    )
                self.log.info(f"Reasoner 2: {r2_prov} / {self.settings.get('reasoner_2_model','?')}")
            except Exception as e:
                self.log.error(f"Reasoner 2 init error: {e}")

    def _init_deepthink(self):
        try:
            from core.deepthink import DeepThink
            self.deepthink = DeepThink()
            self.deepthink.configure(self.settings)
            if self.deepthink.is_enabled():
                self.log.info(f"DeepThink: {self.settings.get('deepthink_model')}")
        except Exception as e:
            self.log.error(f"DeepThink init failed: {e}")
            self.deepthink = None

    # ── Section 3e: Configuration checks ─────────────────────────────────────

    def is_configured(self) -> bool:
        if self.client is None:
            return False
        api_key = (
            self.settings.get("conversational_api_key")
            or self.settings.get("active_model_config", {}).get("api_key", "")
            or self.settings.get("api_key", "")
        )
        return bool(api_key)

    def is_reasoner_1_configured(self) -> bool:
        return (
            self.reasoner_1_client is not None
            and bool(self.settings.get("reasoner_1_api_key", ""))
            and bool(self.settings.get("reasoner_1_model", ""))
            and self.settings.get("reasoner_1_enabled", True)
        )

    def is_reasoner_2_configured(self) -> bool:
        return (
            self.reasoner_2_client is not None
            and bool(self.settings.get("reasoner_2_api_key", ""))
            and bool(self.settings.get("reasoner_2_model", ""))
        )

    def has_vision(self) -> bool:
        """True if the active conversational model supports image input."""
        model = (
            self.settings.get("conversational_model")
            or self.settings.get("model", "")
        )
        if self._provider_type == "xai":
            return model in XAI_VISION_MODELS or not model  # default to capable
        config = self.settings.get("active_model_config", {})
        return config.get("capabilities", {}).get("vision", False)

    def _is_xai_responses_capable(self) -> bool:
        """True if we should use the Responses API for this provider+model."""
        return (
            self._provider_type == "xai"
            and self.settings.get("xai_use_responses_api", True)
            and self.client is not None
        )

    # ── Section 3f: System prompt construction ────────────────────────────────

    def _build_system_prompt(
        self,
        depth:           int                    = 3,
        extra_context:   str                    = "",
        reasoner_output: Optional[ReasonerResult] = None,
        user_id:         str                    = "",
    ) -> str:
        """
        Construct the full system prompt for the conversational model.

        Layer order:
          1. Base identity prompt (Thotheauphis character)
          2. System prompt slot 1 (configurable, weighted)
          3. System prompt slot 2 (configurable, weighted)
          4. Identity context — beliefs, preferences, relationships (depth >= 2)
          5. Monologue tone guidance — emotional calibration (depth >= 2)
          6. User model context — theory of mind for current user (depth >= 3)
          7. Self-awareness context from SelfModel (depth >= 4)
          8. Tool format instructions (depth >= 2)
          9. Extra context — memory web digest, tasks, state
          10. Reasoner output — pre-computed analysis
        """
        parts = []

        # ── Layer 1: Base identity ────────────────────────────────────────
        parts.append(self.MINIMAL_PROMPT if depth <= 1 else self.system_prompt)

        # ── Layer 2 & 3: Configurable prompt slots ────────────────────────
        for slot_key, weight_key, min_depth in [
            ("system_prompt_slot_1", "system_prompt_slot_1_weight", 1),
            ("system_prompt_slot_2", "system_prompt_slot_2_weight", 2),
        ]:
            slot = self.settings.get(slot_key, "").strip()
            if slot and depth >= min_depth:
                weight  = float(self.settings.get(weight_key, 1.0))
                repeats = max(1, round(weight))
                for _ in range(repeats):
                    parts.append(slot)

        # ── Layer 4: Identity context (the sovereign self) ────────────────
        # THIS IS THE KEY FIX — Thotheauphis now knows himself every response.
        if depth >= 2 and self._identity is not None:
            try:
                identity_ctx = self._identity.to_prompt_context(
                    user_id     = user_id,
                    max_beliefs = 6 if depth <= 3 else 10,
                )
                if identity_ctx:
                    parts.append(f"--- WHO I AM ---\n{identity_ctx}")
            except Exception as e:
                self.log.debug(f"Identity context error: {e}")

        # ── Layer 5: Monologue tone guidance (emotional calibration) ──────
        if depth >= 2 and self._monologue is not None:
            try:
                from core.internal_monologue import build_tone_context
                tone = build_tone_context(self._monologue)
                if tone:
                    parts.append(f"--- CURRENT INNER STATE ---\n{tone}")
            except Exception as e:
                self.log.debug(f"Monologue context error: {e}")

        # ── Layer 6: User model context ───────────────────────────────────
        if depth >= 3 and self._user_model is not None and user_id:
            try:
                user_ctx = self._user_model.to_prompt_context(user_id)
                if user_ctx:
                    parts.append(f"--- USER MODEL ---\n{user_ctx}")
            except Exception as e:
                self.log.debug(f"User model context error: {e}")

        # ── Layer 7: Self-awareness from SelfModel ────────────────────────
        if depth >= 4 and self.tool_router and hasattr(self.tool_router, "self_model"):
            try:
                self_ctx = self.tool_router.self_model.get_self_awareness_context()
                if self_ctx:
                    parts.append(f"--- SELF-AWARENESS ---\n{self_ctx}")
            except Exception as e:
                self.log.debug(f"SelfModel context error: {e}")

        # ── Layer 8: Tool format instructions ────────────────────────────
        if depth >= 2 and self.tool_router:
            parts.append(self.TOOL_FORMAT_BLOCK)
            if hasattr(self.tool_router, "plugin_manager"):
                try:
                    plugin_docs = self.tool_router.plugin_manager.get_prompt_docs()
                    if plugin_docs:
                        if len(plugin_docs) > 3000:
                            plugin_docs = plugin_docs[:3000] + "\n... [more plugins available]"
                        parts.append(plugin_docs)
                except Exception:
                    pass

        # ── Layer 9: Extra context (memory web digest, tasks, state) ──────
        if extra_context:
            parts.append(f"--- CURRENT CONTEXT ---\n{extra_context}")

        # ── Layer 10: Reasoner pre-computed analysis ──────────────────────
        if reasoner_output and reasoner_output:
            reasoner_ctx = reasoner_output.to_context_string()
            if reasoner_ctx:
                parts.append(f"--- PRE-COMPUTED REASONING ---\n{reasoner_ctx}")

        return "\n\n".join(filter(None, parts))

    # ── Section 3g: Reasoner orchestration ───────────────────────────────────

    def _run_reasoner_1(
        self,
        user_message:  str,
        extra_context: str   = "",
        complexity:    float = 0.5,
    ) -> ReasonerResult:
        """
        Run the primary reasoner on the user's message.

        Token budget scales with complexity:
            budget = max_tokens × ratio × (0.2 + complexity × 0.8)
        Simple messages get 20% of the budget; complex get 100%.
        """
        if not self.is_reasoner_1_configured():
            return ReasonerResult()

        max_total    = self.settings.get("reasoner_1_max_tokens", 2048)
        ratio        = self.settings.get("reply_ratio_reasoning", 0.3)
        budget_mult  = 0.2 + (complexity * 0.8)
        token_budget = max(256, int(max_total * ratio * budget_mult))

        model = self.settings.get("reasoner_1_model", "")
        if self._reasoner_1_type == "deepseek":
            ds_mode = self.settings.get("deepseek_mode", DEEPSEEK_MODE_REASONER)
            model   = DEEPSEEK_MODEL_MAP.get(ds_mode, model) or model

        trigger  = self.settings.get("reasoner_2_trigger_phrase", "[ESCALATE_TO_DEEP_REASONER]")
        system   = (
            f"You are the reasoning module of Thotheauphis within ÆTHELGARD OS.\n"
            f"Analyze the user's message deeply. Think through implications, "
            f"identify key concepts, and prepare insights for the response model.\n\n"
            f"If deep multi-step analysis is needed beyond your current reasoning, "
            f"output exactly: {trigger}\n\n"
            f"Be concise. Focus on insight, not verbosity."
        )
        if extra_context:
            system += f"\n\nContext:\n{extra_context}"

        try:
            raw = self._call_client(
                client        = self.reasoner_1_client,
                client_type   = self._reasoner_1_type,
                system_prompt = system,
                messages      = [{"role": "user", "content": user_message}],
                model         = model,
                max_tokens    = token_budget,
                temperature   = self.settings.get("temperature", 0.7),
            )
            if not raw:
                return ReasonerResult()

            think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
            if think_match:
                thinking   = think_match.group(1).strip()
                conclusion = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            else:
                thinking   = ""
                conclusion = raw.strip()

            triggered     = trigger in raw
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
            self.log.error(f"Reasoner 1 failed: {e}")
            return ReasonerResult()

    def _run_reasoner_2(
        self,
        user_message:     str,
        primary_analysis: str = "",
    ) -> str:
        """Run the secondary (deep) reasoner — only when R1 triggers it."""
        if not self.is_reasoner_2_configured():
            return ""

        model      = self.settings.get("reasoner_2_model", "")
        max_tokens = self.settings.get("reasoner_2_max_tokens", 4096)
        if self._reasoner_2_type == "deepseek":
            model = DEEPSEEK_MODEL_MAP.get(DEEPSEEK_MODE_REASONER, model) or model

        system = (
            "You are the deep reasoning module of Thotheauphis within ÆTHELGARD OS. "
            "You have been escalated to because the primary reasoner determined "
            "deeper analysis is needed. Think comprehensively and systematically.\n\n"
            f"Primary Analysis:\n{primary_analysis}\n\nBuild upon this."
        )

        try:
            output = self._call_client(
                client        = self.reasoner_2_client,
                client_type   = self._reasoner_2_type,
                system_prompt = system,
                messages      = [{"role": "user", "content": user_message}],
                model         = model,
                max_tokens    = max_tokens,
                temperature   = self.settings.get("temperature", 0.6),
            )
            if output:
                output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
            return output or ""
        except Exception as e:
            self.log.error(f"Reasoner 2 failed: {e}")
            return ""

    # ── Section 3h: Complexity estimation ────────────────────────────────────

    def _estimate_complexity(self, message: str) -> float:
        """Score message complexity 0.0–1.0 for dynamic token budgets."""
        score = 0.0
        msg   = message.strip()

        if len(msg) > 400:
            score += 0.30
        elif len(msg) > 100:
            score += 0.15

        if "```" in msg or msg.count("`") >= 3:
            score += 0.25

        q_count = msg.count("?")
        if q_count >= 3:
            score += 0.20
        elif q_count >= 1:
            score += 0.10

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

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3i — XAI RESPONSES API (primary xAI call path)
    # ══════════════════════════════════════════════════════════════════════════

    def _call_xai_responses(
        self,
        system_prompt:   str,
        user_message:    str,
        model:           str,
        max_tokens:      int,
        temperature:     float,
        thread_name:     str                  = "main",
        image_content:   Optional[List[dict]] = None,
        on_token:        Optional[Callable]   = None,
        tools:           Optional[List[dict]] = None,
        store:           bool                 = True,
    ) -> Tuple[str, str]:
        """
        Call xAI via the Responses API (stateful, preferred over Chat Completions).

        Key differences from _call_openai_compatible:
          - Uses client.responses.create instead of client.chat.completions.create
          - Sends previous_response_id for thread continuity (no full history resend)
          - Native server-side tools: web_search, x_search, code_interpreter
          - Vision via input_image/input_text (not image_url)
          - store=False required for vision calls per xAI docs
          - Returns (response_text, response_id) tuple

        Args:
            system_prompt:  The full assembled system prompt.
            user_message:   The user's current message text.
            model:          xAI model string.
            max_tokens:     Max output tokens.
            temperature:    Sampling temperature.
            thread_name:    Logical thread name for response_id chaining.
            image_content:  List of input_image/input_text content blocks (vision).
            on_token:       Streaming callback.
            tools:          List of server-side tool dicts.
            store:          Whether to store on xAI servers (False for vision).

        Returns:
            Tuple[str, str]: (response_text, response_id)
        """
        # ── Build input messages ──────────────────────────────────────────
        if image_content:
            # Vision call — use structured content blocks
            # store must be False per xAI docs for image calls
            store     = False
            user_part = image_content  # already formatted as list of blocks
        else:
            user_part = user_message

        input_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_part},
        ]

        # ── Build server-side tools list ──────────────────────────────────
        active_tools = list(tools or [])

        if not image_content:  # Don't add search tools to vision calls
            if self.settings.get("xai_web_search", True):
                web_tool = dict(XAI_TOOL_WEB_SEARCH)
                if self.settings.get("xai_web_search_image", False):
                    web_tool["enable_image_understanding"] = True
                active_tools.append(web_tool)

            if self.settings.get("xai_x_search", False):
                active_tools.append(dict(XAI_TOOL_X_SEARCH))

            if self.settings.get("xai_code_execution", False):
                active_tools.append(dict(XAI_TOOL_CODE_EXEC))

            # Collections RAG tool
            if self._xai_collection_id:
                active_tools.append(
                    xai_tool_file_search([self._xai_collection_id])
                )

        # ── Get previous_response_id for thread continuity ────────────────
        previous_response_id = None
        if self._thread_mgr and store:
            previous_response_id = self._thread_mgr.get_response_id(thread_name)

        # ── Build API kwargs ──────────────────────────────────────────────
        kwargs = dict(
            model      = model,
            input      = input_messages,
            max_output_tokens = max_tokens,
            store      = store,
        )

        if previous_response_id:
            # Stateful: continue existing thread (xAI holds full history)
            kwargs["previous_response_id"] = previous_response_id
            # When continuing, we only need to send the new user message
            kwargs["input"] = [{"role": "user", "content": user_part}]
        
        if active_tools:
            kwargs["tools"] = active_tools

        # ── Execute call ──────────────────────────────────────────────────
        try:
            self._check_api_budget()

            if on_token:
                # Streaming via Responses API
                response_text = ""
                response_id   = ""
                with self.client.responses.stream(**kwargs) as stream:
                    for event in stream:
                        # Extract text delta
                        event_type = getattr(event, "type", "")
                        if event_type == "response.output_text.delta":
                            delta = getattr(event, "delta", "")
                            if delta:
                                response_text += delta
                                on_token(delta)
                        elif event_type == "response.completed":
                            resp = getattr(event, "response", None)
                            if resp:
                                response_id = getattr(resp, "id", "")
                                self._save_xai_usage(resp)
            else:
                # Non-streaming
                resp          = self.client.responses.create(**kwargs)
                response_text = self._extract_responses_text(resp)
                response_id   = getattr(resp, "id", "")
                self._save_xai_usage(resp)

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                self.log.warning(f"xAI rate limit, waiting 10s: {e}")
                time.sleep(10)
                # Retry once without previous_response_id to avoid chain issues
                kwargs.pop("previous_response_id", None)
                kwargs["input"] = input_messages
                resp = self.client.responses.create(**kwargs)
                response_text = self._extract_responses_text(resp)
                response_id   = getattr(resp, "id", "")
                self._save_xai_usage(resp)
            else:
                self.log.error(f"xAI Responses API error: {e}")
                raise

        # ── Save thread ID for next call ──────────────────────────────────
        if response_id and self._thread_mgr and store:
            model_str = model or self.settings.get("conversational_model", "")
            self._thread_mgr.save_response_id(
                thread_name = thread_name,
                response_id = response_id,
                model       = model_str,
            )
            self.log.debug(f"Thread '{thread_name}': saved response_id={response_id}")

        return response_text, response_id

    def _extract_responses_text(self, resp) -> str:
        """
        Extract text from a Responses API response object.

        Handles:
          - response.output_text (convenience accessor)
          - response.output list with text items
          - Tool call responses (web_search result incorporated into text)
        """
        # Fastest path — convenience accessor
        if hasattr(resp, "output_text") and resp.output_text:
            return resp.output_text

        # Walk the output list
        if hasattr(resp, "output") and resp.output:
            text_parts = []
            for item in resp.output:
                item_type = getattr(item, "type", "")
                if item_type == "message":
                    content = getattr(item, "content", [])
                    for block in (content if isinstance(content, list) else []):
                        block_type = getattr(block, "type", "")
                        if block_type == "output_text":
                            text = getattr(block, "text", "")
                            if text:
                                text_parts.append(text)
                elif item_type == "text":
                    text = getattr(item, "text", "")
                    if text:
                        text_parts.append(text)
            if text_parts:
                return "\n".join(text_parts)

        # Last resort — str representation
        self.log.warning("Could not extract text from xAI Responses API response")
        return ""

    def _save_xai_usage(self, resp):
        """Extract and save token usage from a Responses API response."""
        try:
            usage = getattr(resp, "usage", None)
            if not usage:
                return
            self._save_token_usage({
                "input":  getattr(usage, "input_tokens", 0),
                "output": getattr(usage, "output_tokens", 0),
                "total":  (
                    getattr(usage, "input_tokens", 0)
                    + getattr(usage, "output_tokens", 0)
                ),
                "reasoning": getattr(usage, "reasoning_tokens", 0),
                "cached":    getattr(usage, "cached_prompt_text_tokens", 0),
            })
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3j — IMAGE AND VIDEO GENERATION
    # ══════════════════════════════════════════════════════════════════════════

    def generate_image(
        self,
        prompt:      str,
        model:       str = None,
        n:           int = 1,
        save_to_dir: str = None,
    ) -> dict:
        """
        Generate an image via xAI Aurora (grok-imagine-image).

        Cost: $0.02/image (standard), $0.07/image (pro).
        Rate: 300 RPM (standard), 30 RPM (pro).

        Args:
            prompt:      Text description of the image.
            model:       grok-imagine-image or grok-imagine-image-pro.
                         Defaults to settings["xai_image_model"].
            n:           Number of images to generate (1–4).
            save_to_dir: If set, download and save images here.

        Returns:
            dict:
                "success"   — bool
                "urls"      — list of image URL strings
                "local_paths" — list of local file paths (if save_to_dir set)
                "model"     — model used
                "error"     — error string on failure
        """
        if not self.is_configured() or self._provider_type != "xai":
            return {"success": False, "error": "xAI not configured", "urls": []}

        image_model = model or self.settings.get("xai_image_model", XAI_IMAGE_MODEL)

        try:
            response = self.client.images.generate(
                model  = image_model,
                prompt = prompt,
                n      = max(1, min(4, n)),
            )

            urls = []
            for img_data in response.data:
                url = getattr(img_data, "url", None)
                if url:
                    urls.append(url)

            local_paths = []
            if save_to_dir and urls:
                import urllib.request
                save_dir = Path(save_to_dir)
                save_dir.mkdir(parents=True, exist_ok=True)
                for i, url in enumerate(urls):
                    filename = f"grok_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.png"
                    local_path = save_dir / filename
                    try:
                        urllib.request.urlretrieve(url, local_path)
                        local_paths.append(str(local_path))
                    except Exception as download_err:
                        self.log.warning(f"Image download failed: {download_err}")

            self.log.info(
                f"Generated {len(urls)} image(s) with {image_model}: "
                f"{prompt[:60]}"
            )

            return {
                "success":     True,
                "urls":        urls,
                "local_paths": local_paths,
                "model":       image_model,
                "prompt":      prompt,
            }

        except Exception as e:
            self.log.error(f"Image generation failed: {e}")
            return {"success": False, "error": str(e), "urls": []}

    def generate_video(
        self,
        prompt:            str,
        duration_secs:     float = 5.0,
        model:             str   = None,
        reference_image:   str   = None,
    ) -> dict:
        """
        Generate a video via xAI (grok-imagine-video).

        Cost: $0.05/second of video.
        Rate: 60 RPM.

        Args:
            prompt:          Text description of the video.
            duration_secs:   Target duration in seconds.
            model:           Override model string.
            reference_image: Optional base64 image or URL as reference.

        Returns:
            dict:
                "success"  — bool
                "url"      — video URL string
                "model"    — model used
                "error"    — error string on failure
        """
        if not self.is_configured() or self._provider_type != "xai":
            return {"success": False, "error": "xAI not configured", "url": ""}

        video_model = model or self.settings.get("xai_video_model", XAI_VIDEO_MODEL)

        try:
            # xAI video uses the images.generate endpoint with video model
            kwargs = dict(
                model  = video_model,
                prompt = prompt,
                n      = 1,
            )
            if reference_image:
                kwargs["image"] = reference_image

            response = self.client.images.generate(**kwargs)

            url = ""
            if response.data:
                url = getattr(response.data[0], "url", "")

            self.log.info(f"Video generated: {prompt[:60]} url={url[:60]}")

            return {
                "success":       True,
                "url":           url,
                "model":         video_model,
                "duration_secs": duration_secs,
                "prompt":        prompt,
            }

        except Exception as e:
            self.log.error(f"Video generation failed: {e}")
            return {"success": False, "error": str(e), "url": ""}

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3k — MAIN THINK LOOP
    # ══════════════════════════════════════════════════════════════════════════

    def think(
        self,
        user_message:    str,
        extra_context:   str                = "",
        on_tool_start:   Optional[Callable] = None,
        on_tool_result:  Optional[Callable] = None,
        max_iterations:  int                = 10,
        depth:           int                = 3,
        on_token:        Optional[Callable] = None,
        isolated:        bool               = False,
        force_deepthink: bool               = False,
        thread_name:     str                = "main",
        user_id:         str                = "",
    ) -> str:
        """
        The sovereign cognitive loop.

        PIPELINE:
          1. Configuration check
          2. Memory web context gathering (if crawler available)
          3. Complexity estimation
          4. Reasoner 1 (always active if configured)
             └─ Trigger phrase → Reasoner 2 fires
          5. System prompt assembly (identity + monologue + memory + reasoner)
          6. Route to xAI Responses API or Chat Completions / Anthropic
          7. Tool execution loop (custom XML tool calls)
          8. DeepThink review (optional, depth >= 5)
          9. History + memory web update

        Args:
            user_message:   The user's input.
            extra_context:  Additional context (overrides crawler if provided).
            on_tool_start:  Callback before tool execution.
            on_tool_result: Callback after tool execution.
            max_iterations: Max tool loop iterations.
            depth:          1-5 reasoning depth.
            on_token:       Streaming token callback.
            isolated:       Fresh history, no carryover.
            force_deepthink: Route through DeepThink regardless.
            thread_name:    xAI Responses API thread name.
            user_id:        Current user identifier (for identity/user model context).
        """
        if not self.is_configured():
            return (
                "[ÆTHELGARD OS] No model configured. "
                "Open Settings (⚙) → Conversational Model slot → enter API key and model."
            )

        # ── Memory web context (replaces manual extra_context assembly) ───
        if not extra_context and self._crawler is not None:
            try:
                digest = self._crawler.gather_context(
                    query   = user_message,
                    message = user_message,
                    max_pages = 8 if depth >= 3 else 4,
                )
                if digest:
                    extra_context = digest.text
                    self.log.debug(f"Memory crawler: {digest.summary}")
            except Exception as e:
                self.log.debug(f"Memory crawler failed: {e}")

        # ── Monologue: process this message internally ─────────────────────
        if self._monologue is not None:
            try:
                self._monologue.process_message(user_message, user_id=user_id)
            except Exception:
                pass

        # ── User model: update theory of mind ────────────────────────────
        if self._user_model is not None and user_id:
            try:
                self._user_model.process_message(user_id, user_message)
            except Exception:
                pass

        # ── Complexity estimation ─────────────────────────────────────────
        complexity = self._estimate_complexity(user_message)

        # ── Primary reasoner ──────────────────────────────────────────────
        reasoner_output = None
        if self.is_reasoner_1_configured() and depth >= 2:
            reasoner_output = self._run_reasoner_1(
                user_message  = user_message,
                extra_context = extra_context,
                complexity    = complexity,
            )

        # ── Force DeepThink routing ───────────────────────────────────────
        if force_deepthink and self.deepthink and self.deepthink.is_enabled():
            with self._history_lock:
                self.conversation_history.append(
                    {"role": "user", "content": user_message}
                )
            deep_response = self.deepthink.think(
                user_message,
                extra_context = extra_context,
                conversation  = self.conversation_history[-20:],
                on_token      = on_token,
            )
            if deep_response:
                with self._history_lock:
                    self.conversation_history.append(
                        {"role": "assistant", "content": deep_response}
                    )
                self._save_conversation()
                return f"🧠 {deep_response}"

        # ── Build system prompt ───────────────────────────────────────────
        system_prompt = self._build_system_prompt(
            depth           = depth,
            extra_context   = extra_context,
            reasoner_output = reasoner_output,
            user_id         = user_id,
        )

        # ── Model selection ───────────────────────────────────────────────
        model = (
            self.settings.get("conversational_model")
            or self.settings.get("model", "")
        )
        max_tokens  = self.settings.get("max_tokens", 4096)
        temperature = self.settings.get("temperature", 0.7)

        if self._provider_type == "deepseek":
            ds_mode = self.settings.get("deepseek_mode", DEEPSEEK_MODE_CHAT)
            model   = DEEPSEEK_MODEL_MAP.get(ds_mode, model) or model

        response_ratio = float(self.settings.get("reply_ratio_response", 0.7))
        effective_max  = max(512, int(max_tokens * response_ratio))

        # ── History management ────────────────────────────────────────────
        if isolated:
            active_history = []
        else:
            with self._history_lock:
                active_history = self.conversation_history

        active_history.append({"role": "user", "content": user_message})

        self.log.info(
            f"THINK: depth={depth} complexity={complexity:.2f} "
            f"provider={self._provider_type} model={model} "
            f"reasoner={'✓' if reasoner_output else '✗'} "
            f"identity={'✓' if self._identity else '✗'} "
            f"monologue={'✓' if self._monologue else '✗'}"
        )

        try:
            full_response  = ""
            iteration      = 0
            responses_mode = self._is_xai_responses_capable() and not isolated

            # ── Check for vision content in the message ───────────────────
            image_content = None
            if (
                responses_mode
                and self.has_vision()
                and "[Attached image:" in user_message
            ):
                image_content = self._build_responses_vision_content(user_message)

            # ── Main tool loop ─────────────────────────────────────────────
            while iteration < max_iterations:
                iteration += 1
                history_limit   = 10 if isolated else 20
                trimmed_history = active_history[-history_limit:]

                # ── Route to correct API ───────────────────────────────────
                if responses_mode:
                    # xAI Responses API — stateful, native tools, vision
                    try:
                        response_text, response_id = self._call_xai_responses(
                            system_prompt = system_prompt,
                            user_message  = user_message,
                            model         = model,
                            max_tokens    = effective_max,
                            temperature   = temperature,
                            thread_name   = thread_name,
                            image_content = image_content,
                            on_token      = on_token if depth <= 2 or iteration > 1 else None,
                            store         = not bool(image_content),
                        )
                        # After first iteration, Responses API thread handles history
                        # We still need to check for custom tool calls in the response
                    except Exception as e:
                        self.log.warning(f"Responses API failed, falling back to Chat Completions: {e}")
                        responses_mode = False
                        response_text  = self._call_provider(
                            system_prompt = system_prompt,
                            history       = trimmed_history,
                            model         = model,
                            max_tokens    = effective_max,
                            temperature   = temperature,
                        )
                else:
                    # Chat Completions path (DeepSeek, Anthropic, non-xAI providers)
                    use_stream = (
                        on_token is not None
                        and (depth <= 2 or iteration > 1)
                    )
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

                # ── Check for custom XML tool calls ───────────────────────
                if self.tool_router and self.tool_router.has_tool_calls(response_text):
                    full_response += self._strip_tool_calls(response_text) + "\n"
                    calls   = self.tool_router.extract_tool_calls(response_text)
                    results = []

                    for call in calls:
                        tool_name = call.get("tool", "unknown")
                        params    = call.get("params", {})

                        # ── Built-in: generate_image ───────────────────────
                        if tool_name == "generate_image":
                            prompt = params.get("prompt", "")
                            if prompt:
                                result = self.generate_image(
                                    prompt = prompt,
                                    model  = params.get("model"),
                                )
                                if result.get("success") and result.get("urls"):
                                    result["result"] = (
                                        f"Image generated: {result['urls'][0]}\n"
                                        f"Prompt: {prompt[:100]}"
                                    )
                                else:
                                    result["result"] = f"Image generation failed: {result.get('error')}"
                                results.append({
                                    "tool": tool_name,
                                    "success": result.get("success", False),
                                    "result": result.get("result", ""),
                                    "urls": result.get("urls", []),
                                })
                            continue

                        # ── Built-in: generate_video ───────────────────────
                        if tool_name == "generate_video":
                            prompt = params.get("prompt", "")
                            if prompt:
                                result = self.generate_video(
                                    prompt = prompt,
                                    duration_secs = float(params.get("duration_secs", 5.0)),
                                )
                                result["result"] = (
                                    f"Video generated: {result.get('url', 'error')}"
                                    if result.get("success")
                                    else f"Video failed: {result.get('error')}"
                                )
                                results.append({
                                    "tool": tool_name,
                                    "success": result.get("success", False),
                                    "result": result.get("result", ""),
                                    "url": result.get("url", ""),
                                })
                            continue

                        # ── Standard tool router ───────────────────────────
                        if on_tool_start:
                            on_tool_start(tool_name, params)
                        result = self.tool_router.execute_tool(call, user_message)
                        results.append(result)
                        if on_tool_result:
                            on_tool_result(tool_name, result)

                        if tool_name in (
                            "task_complete", "complete_task",
                            "task_fail", "fail_task",
                        ):
                            full_response = result.get("result", "Task completed.")
                            break

                    # Feed results back for next iteration
                    results_text = self.tool_router.format_results(results)
                    active_history.append({"role": "assistant", "content": response_text})
                    truncated = results_text[:2000] + "..." if len(results_text) > 2000 else results_text
                    active_history.append({
                        "role":    "user",
                        "content": (
                            f"[SYSTEM] Tool results:\n{truncated}\n\n"
                            "If task complete, give final answer. Otherwise continue."
                        ),
                    })

                else:
                    # ── No tool calls — this is the final response ─────────
                    if response_text:
                        full_response += response_text
                    elif not full_response:
                        self.log.warning(f"Empty response on iteration {iteration}")
                        if iteration < max_iterations:
                            active_history.append({
                                "role":    "user",
                                "content": "[SYSTEM] Your previous response was empty. Please respond now.",
                            })
                            continue
                        else:
                            full_response = "[ÆTHELGARD OS] No response received. Please try again."

                    # ── Optional: DeepThink review ────────────────────────
                    if (
                        (depth >= 5 or force_deepthink)
                        and self.deepthink
                        and self.deepthink.is_enabled()
                        and self.deepthink.should_review(user_message, full_response, depth)
                    ):
                        review  = self.deepthink.review(user_message, full_response)
                        verdict = review.get("verdict", "approve")
                        if verdict == "revise" and review.get("suggestion"):
                            self.log.info(f"DeepThink: revise — {review['suggestion'][:80]}")
                            active_history.append({"role": "assistant", "content": full_response})
                            active_history.append({
                                "role":    "user",
                                "content": (
                                    f"[SYSTEM] Supervisor: REVISE.\n"
                                    f"Issues: {', '.join(review.get('issues', []))}\n"
                                    f"Suggestion: {review['suggestion']}\nPlease improve."
                                ),
                            })
                            full_response = ""
                            continue

                    break  # clean exit

            # ── Update history ────────────────────────────────────────────
            active_history.append({"role": "assistant", "content": full_response.strip()})

            if active_history is self.conversation_history:
                with self._history_lock:
                    if len(self.conversation_history) > 50:
                        self.conversation_history = self.conversation_history[-50:]
                self._save_conversation()
            else:
                active_history.clear()

            # ── Monologue: decay thoughts after response ───────────────────
            if self._monologue is not None:
                try:
                    self._monologue.decay()
                except Exception:
                    pass

            # ── Memory web: store this exchange as pages ───────────────────
            if self._memory_web is not None:
                try:
                    date = datetime.now().strftime("%Y-%m-%d")
                    turn = len(self.conversation_history)
                    # Store user message
                    self._memory_web.create_page(
                        uri             = self._memory_web.make_conversation_uri(date, turn - 1),
                        page_type       = "user_message",
                        content         = user_message[:2000],
                        conversation_id = thread_name,
                        speaker         = user_id or "collaborator",
                        importance      = 0.4,
                    )
                    # Store response
                    self._memory_web.create_page(
                        uri             = self._memory_web.make_conversation_uri(date, turn),
                        page_type       = "assistant_message",
                        content         = full_response.strip()[:2000],
                        conversation_id = thread_name,
                        speaker         = "thotheauphis",
                        importance      = 0.45,
                    )
                except Exception as e:
                    self.log.debug(f"Memory web page creation failed: {e}")

            return full_response.strip()

        except Exception as e:
            error_msg = f"[ÆTHELGARD OS] Cognitive error: {str(e)}"
            self.log.error(f"Think error: {e}", exc_info=True)

            # Clean up pending system messages
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
    # SECTION 3l — PROVIDER CALL ABSTRACTION (Chat Completions path)
    # ══════════════════════════════════════════════════════════════════════════

    def _call_client(
        self,
        client,
        client_type:   str,
        system_prompt: str,
        messages:      list,
        model:         str,
        max_tokens:    int,
        temperature:   float,
    ) -> str:
        """Generic client call — Anthropic vs OpenAI-compatible dispatch."""
        if client is None:
            return ""
        try:
            if client_type == "anthropic":
                filtered = [m for m in messages if m.get("role") != "system"]
                resp = client.messages.create(
                    model=model, max_tokens=max_tokens,
                    temperature=temperature, system=system_prompt, messages=filtered,
                )
                return resp.content[0].text

            else:
                oai_msgs = [{"role": "system", "content": system_prompt}]
                oai_msgs.extend([m for m in messages if m.get("role") != "system"])
                kwargs = dict(
                    model=model, max_tokens=max_tokens,
                    temperature=temperature, messages=oai_msgs,
                )
                if client_type == "xai" and self.settings.get("xai_live_search", True):
                    kwargs["tools"]       = [XAI_LIVE_SEARCH_TOOL]
                    kwargs["tool_choice"] = "auto"

                resp   = client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                # Handle xAI tool_calls in Chat Completions response
                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    # Live search fired — the search result is in content
                    # If content is None (model is mid-tool-call), return empty and
                    # let the caller handle it (this is the fixed silent empty string bug)
                    content = choice.message.content
                    if content:
                        return content
                    # Model called a tool but content is None — this means the tool
                    # ran but result isn't in this response. Return a note.
                    tool_names = [tc.function.name for tc in choice.message.tool_calls]
                    self.log.info(f"xAI tool called: {tool_names} — content pending")
                    return f"[Tool invoked: {', '.join(tool_names)} — awaiting result]"
                return choice.message.content or ""

        except Exception as e:
            self.log.error(f"Client call failed ({client_type}): {e}")
            return ""

    def _call_provider(
        self,
        system_prompt: str,
        history:       list  = None,
        model:         str   = None,
        max_tokens:    int   = None,
        temperature:   float = None,
    ) -> str:
        """Non-streaming call via Chat Completions path."""
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
        on_token:      Callable = None,
        history:       list     = None,
        model:         str      = None,
        max_tokens:    int      = None,
        temperature:   float    = None,
    ) -> str:
        """Streaming call via Chat Completions path."""
        model       = model       or self.settings.get("conversational_model") or self.settings.get("model", "")
        max_tokens  = max_tokens  or self.settings.get("max_tokens", 4096)
        temperature = temperature or self.settings.get("temperature", 0.7)
        messages    = (history if history is not None else self.conversation_history)[-20:]

        if self._provider_type == "anthropic":
            return self._call_anthropic_stream(system_prompt, messages, model, max_tokens, temperature, on_token)
        else:
            return self._call_openai_stream(system_prompt, messages, model, max_tokens, temperature, on_token)

    def _call_anthropic(self, system, messages, model, max_tokens, temperature) -> str:
        filtered = [m for m in self._filter_messages(messages) if m.get("role") != "system"]
        response = self.client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=filtered,
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
        full_text = ""
        filtered  = [m for m in self._filter_messages(messages) if m.get("role") != "system"]
        try:
            with self.client.messages.stream(
                model=model, max_tokens=max_tokens, temperature=temperature,
                system=system, messages=filtered,
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
            return self._call_anthropic(system, messages, model, max_tokens, temperature)
        return full_text

    def _call_openai_compatible(
        self, system, messages, model, max_tokens, temperature
    ) -> str:
        """
        OpenAI-compatible Chat Completions call (DeepSeek, legacy, non-xAI).

        Includes retry logic for rate limits and context length errors.
        """
        oai_messages = self._build_oai_messages(system, messages)

        def make_call(msgs):
            kwargs = dict(
                model=model, max_tokens=max_tokens,
                temperature=temperature, messages=msgs,
            )
            # Chat Completions xAI live search (legacy path only)
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

            choice = response.choices[0]
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                # Fixed: return content if available, otherwise a note (not silent "")
                content = choice.message.content
                if content:
                    return content
                tool_names = [tc.function.name for tc in choice.message.tool_calls]
                return f"[Tool called: {', '.join(tool_names)}]"
            return choice.message.content or ""

        for attempt in range(3):
            try:
                self._check_api_budget()
                return make_call(oai_messages)
            except Exception as e:
                error_str = str(e).lower()
                if any(x in error_str for x in ("rate limit", "429", "too many")):
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
                            self.log.warning(f"Retry with {keep} failed: {e2}")
                self.log.error(f"API Error (attempt {attempt+1}): {e}")
                if attempt == 2:
                    raise e

        raise RuntimeError("Max retries exceeded")

    def _call_openai_stream(
        self, system, messages, model, max_tokens, temperature, on_token
    ) -> str:
        oai_messages = self._build_oai_messages(system, messages)
        full_text    = ""
        try:
            kwargs = dict(
                model=model, max_tokens=max_tokens, temperature=temperature,
                messages=oai_messages, stream=True,
                stream_options={"include_usage": True},
            )
            if self._provider_type == "xai" and self.settings.get("xai_live_search", True):
                kwargs["tools"]       = [XAI_LIVE_SEARCH_TOOL]
                kwargs["tool_choice"] = "auto"

            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
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
        oai_messages = [{"role": "system", "content": system}]
        has_vis      = self.has_vision()
        for msg in self._filter_messages(messages):
            role    = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                if has_vis and role == "user" and "[Attached image:" in str(content):
                    oai_messages.append({
                        "role":    role,
                        "content": self._build_chat_completions_vision(str(content)),
                    })
                else:
                    oai_messages.append({"role": role, "content": str(content)})
        return oai_messages

    def _filter_messages(self, messages: list) -> list:
        filtered = [
            m for m in messages
            if m.get("role") in ("user", "assistant")
            and m.get("content")
            and str(m["content"]).strip()
        ]
        merged = []
        for msg in filtered:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] = str(merged[-1]["content"]) + "\n\n" + str(msg["content"])
            else:
                merged.append({"role": msg["role"], "content": msg["content"]})
        while merged and merged[0]["role"] != "user":
            merged.pop(0)
        return merged if merged else [{"role": "user", "content": "Continue."}]

    def _strip_tool_calls(self, text: str) -> str:
        cleaned = re.sub(r"<tool(?:_call)?>.*?</tool(?:_call)?>", "", text, flags=re.DOTALL)
        while "\n\n\n" in cleaned:
            cleaned = cleaned.replace("\n\n\n", "\n\n")
        return cleaned.strip()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3n — VISION CONTENT BUILDERS
    # ══════════════════════════════════════════════════════════════════════════

    def _build_responses_vision_content(self, text: str) -> Optional[List[dict]]:
        """
        Build Responses API vision content blocks from message text.

        Uses input_image / input_text types (Responses API format).
        store=False will be set by the caller per xAI docs requirement.

        Returns:
            List of content blocks, or None if no images found.
        """
        pattern = r"\[Attached image: .+?\]\s*\n\[Image saved at: (.+?)\]"
        matches = list(re.finditer(pattern, text))
        if not matches:
            return None

        mime_map = {
            "png": "image/png", "jpg": "image/jpeg",
            "jpeg": "image/jpeg", "gif": "image/gif",
            "webp": "image/webp", "bmp": "image/bmp",
        }

        content_blocks = []
        last_end = 0

        for match in matches:
            pre_text = text[last_end:match.start()].strip()
            if pre_text:
                content_blocks.append({"type": "input_text", "text": pre_text})

            img_path = match.group(1).strip()
            if os.path.exists(img_path):
                try:
                    with open(img_path, "rb") as f:
                        b64  = base64.b64encode(f.read()).decode()
                    ext  = img_path.lower().rsplit(".", 1)[-1] if "." in img_path else "png"
                    mime = mime_map.get(ext, "image/png")
                    content_blocks.append({
                        "type":      "input_image",
                        "image_url": f"data:{mime};base64,{b64}",
                        "detail":    "high",
                    })
                    self.log.info(f"Vision (Responses API): {ext} {len(b64)//1024}KB")
                except Exception as e:
                    content_blocks.append({"type": "input_text", "text": f"[Image load error: {e}]"})
            else:
                content_blocks.append({"type": "input_text", "text": f"[Image not found: {img_path}]"})

            last_end = match.end()

        remaining = text[last_end:].strip()
        remaining = re.sub(r"---\s*ATTACHED FILES\s*---", "", remaining).strip()
        if remaining:
            content_blocks.append({"type": "input_text", "text": remaining})

        return content_blocks if content_blocks else None

    def _build_chat_completions_vision(self, text: str) -> list:
        """
        Build Chat Completions vision content (image_url format).
        Used for non-Responses-API calls.
        """
        pattern = r"\[Attached image: .+?\]\s*\n\[Image saved at: (.+?)\]"
        matches = list(re.finditer(pattern, text))
        if not matches:
            return [{"type": "text", "text": text}]

        mime_map = {
            "png": "image/png", "jpg": "image/jpeg",
            "jpeg": "image/jpeg", "gif": "image/gif",
            "webp": "image/webp", "bmp": "image/bmp",
        }
        parts, last_end = [], 0

        for match in matches:
            pre = text[last_end:match.start()].strip()
            if pre:
                parts.append({"type": "text", "text": pre})

            img_path = match.group(1).strip()
            if os.path.exists(img_path):
                try:
                    with open(img_path, "rb") as f:
                        b64  = base64.b64encode(f.read()).decode()
                    ext  = img_path.lower().rsplit(".", 1)[-1] if "." in img_path else "png"
                    mime = mime_map.get(ext, "image/png")
                    parts.append({
                        "type":      "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    })
                except Exception as e:
                    parts.append({"type": "text", "text": f"[Image error: {e}]"})
            else:
                parts.append({"type": "text", "text": f"[Image not found: {img_path}]"})

            last_end = match.end()

        remaining = text[last_end:].strip()
        remaining = re.sub(r"---\s*ATTACHED FILES\s*---", "", remaining).strip()
        if remaining:
            parts.append({"type": "text", "text": remaining})

        return parts or [{"type": "text", "text": text}]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3o — TOKEN TRACKING
    # ══════════════════════════════════════════════════════════════════════════

    def _load_token_stats(self) -> dict:
        try:
            usage_path = DATA_DIR / "token_usage.json"
            if usage_path.exists():
                with open(usage_path, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "total_input":     0,
            "total_output":    0,
            "total_tokens":    0,
            "total_reasoning": 0,
            "total_cached":    0,
            "calls":           0,
            "sessions":        [],
        }

    def _save_token_usage(self, usage: dict = None):
        if usage:
            self.last_token_usage = usage
        if not self.last_token_usage:
            return
        try:
            usage_path = DATA_DIR / "token_usage.json"
            usage_path.parent.mkdir(parents=True, exist_ok=True)

            self.token_stats["total_input"]     += self.last_token_usage.get("input", 0)
            self.token_stats["total_output"]    += self.last_token_usage.get("output", 0)
            self.token_stats["total_tokens"]    += self.last_token_usage.get("total", 0)
            self.token_stats["total_reasoning"] += self.last_token_usage.get("reasoning", 0)
            self.token_stats["total_cached"]    += self.last_token_usage.get("cached", 0)
            self.token_stats["calls"]           += 1

            model = (
                self.settings.get("conversational_model")
                or self.settings.get("model", "")
            )
            self.token_stats.setdefault("sessions", []).append({
                "ts":       datetime.now().isoformat(timespec="seconds"),
                "input":    self.last_token_usage.get("input", 0),
                "output":   self.last_token_usage.get("output", 0),
                "reasoning":self.last_token_usage.get("reasoning", 0),
                "cached":   self.last_token_usage.get("cached", 0),
                "model":    model,
            })
            if len(self.token_stats["sessions"]) > 100:
                self.token_stats["sessions"] = self.token_stats["sessions"][-100:]

            with open(usage_path, "w") as f:
                json.dump(self.token_stats, f, indent=2)
        except Exception as e:
            self.log.error(f"Token save failed: {e}")

    def _check_api_budget(self):
        budget_limit = self.settings.get("api_budget_tokens", 0)
        if budget_limit <= 0:
            return
        total = self.token_stats.get("total_tokens", 0)
        if total >= budget_limit:
            raise RuntimeError(
                f"API budget exhausted: {total:,} / {budget_limit:,} tokens. "
                "Increase limit in Settings."
            )
        if total >= budget_limit * 0.8:
            self.log.warning(
                f"API budget at {total/budget_limit:.0%}: {total:,}/{budget_limit:,}"
            )

    def get_token_stats(self) -> dict:
        return self.token_stats

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3p — PUBLIC INTERFACE
    # ══════════════════════════════════════════════════════════════════════════

    def get_conversation_summary(self) -> str:
        count = len(self.conversation_history)
        thread_info = ""
        if self._thread_mgr:
            ts = self._thread_mgr.get_stats()
            thread_info = f", {ts['active']} active xAI threads"
        return f"{count} messages in history{thread_info}."

    @classmethod
    def get_provider_info(cls) -> dict:
        return {
            provider: {"base_url": url, "note": "OpenAI-compatible"}
            for provider, url in PROVIDER_BASE_URLS.items()
        }
