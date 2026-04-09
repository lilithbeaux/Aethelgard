"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Context Router and History Compressor            ║
║  File: core/context_router.py                                    ║
║                                                                  ║
║  The Context Router classifies each incoming message and         ║
║  determines the minimum context needed to respond well.          ║
║  This saves 60–90% of tokens on simple messages.                ║
║                                                                  ║
║  Classification output drives:                                   ║
║    • reasoning depth   (1 = minimal, 5 = full autonomous)       ║
║    • which context flags to load (memory, tasks, reflections)   ║
║    • max_tokens and temperature for the call                     ║
║                                                                  ║
║  The HistoryCompressor collapses old conversation turns into     ║
║  a compact summary when the history grows too long.              ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports and path constants                                 ║
║    2. Classification pattern lists                              ║
║    3. ContextRouter class                                       ║
║    4. HistoryCompressor class                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and path constants ────────────────────────────────────

import re
import json
import os
from datetime import datetime
from pathlib import Path

from core.logger import get_logger

log      = get_logger("router")
DATA_DIR = Path(__file__).parent.parent / "data"

# Shared path for conversation summaries written by HistoryCompressor
SUMMARY_PATH = DATA_DIR / "conversation_summary.json"


# ── Section 2: Classification pattern lists ──────────────────────────────────
# These lists drive the intent classifier.  All patterns are English.
# Patterns are checked in priority order inside ContextRouter.classify().

# Short greetings and one-word responses → SMALLTALK (depth 1)
SMALLTALK_PATTERNS = [
    r"^(hi|hey|hello|yo|sup)\s*[!?.]*$",
    r"^(good\s*(morning|evening|afternoon))\s*[!?.]*$",
    r"^(how\s*are\s*you|what'?s?\s*up)\s*[?!.]*$",
    r"^(thanks|thx|ok|okay|cool|nice|great|got\s*it)\s*[!?.]*$",
    r"^(bye|ciao|see\s*ya|later)\s*[!?.]*$",
    r"^(yes|no|yep|nope|sure|agreed|correct)\s*[!?.]*$",
]

# Words that imply an action should be taken → TASK or DEV
ACTION_KEYWORDS = [
    "create", "build", "make", "write", "install", "deploy", "start", "run",
    "execute", "delete", "remove", "fix", "repair", "debug", "change", "update",
    "modify", "edit", "implement", "develop", "configure", "setup", "search",
    "find", "lookup", "research", "analyze", "show", "list", "compare", "check",
    "download", "open", "read", "scrape", "generate",
]

# Technical words that indicate a dev-level request → DEV (depth 4)
DEV_KEYWORDS = [
    "python", "javascript", "html", "css", "react", "api", "server",
    "function", "class", "import", "bug", "error", "traceback", "exception",
    "git", "commit", "docker", "database", "sql", "script", "code",
    "file", "folder", "path", "terminal", "bash", "pip", "npm",
    "package", "module", "library", "async", "thread", "socket",
]

# Memory / recall keywords → RECALL (depth 2, loads memory)
RECALL_KEYWORDS = [
    "remember", "recall", "what did i", "what was", "last time",
    "previously", "earlier", "yesterday", "my name", "about me",
    "you know", "did you know",
]

# Self-modification / architecture keywords → SELF_EDIT (depth 4)
SELF_KEYWORDS = [
    "self_edit", "your code", "your architecture", "improve yourself",
    "modify yourself", "change your", "edit your", "self-improvement",
    "your source", "your files",
]


# ── Section 3: ContextRouter class ───────────────────────────────────────────

class ContextRouter:
    """
    ÆTHELGARD OS — Intent Classifier and Context Builder

    Classifies each user message into an intent category and depth level,
    then builds the minimal context string needed for that depth.

    Depth levels:
        1 — SMALLTALK      — no context loaded
        2 — QUESTION       — memory loaded
        3 — TASK           — memory + tasks loaded
        4 — DEV/SELF_EDIT  — full context (memory, tasks, reflections)
        5 — AUTONOMOUS     — full context + goal context
    """

    # Depth level constants
    DEPTH_MINIMAL   = 1
    DEPTH_QUESTION  = 2
    DEPTH_TASK      = 3
    DEPTH_DEV       = 4
    DEPTH_AUTONOMOUS = 5

    def __init__(self):
        self.message_count = 0

    def classify(self, message: str, has_attachments: bool = False) -> dict:
        """
        Classify a user message and return routing parameters.

        Args:
            message:         The user's raw input text.
            has_attachments: True if the message includes file/image attachments.

        Returns:
            dict with keys:
                "intent"        — str intent label
                "depth"         — int 1–5
                "context_flags" — dict of bool flags: memory, tasks, reflections, state
                "max_tokens"    — int suggested max token count
                "temperature"   — float sampling temperature
        """
        msg_lower = message.lower().strip()
        self.message_count += 1

        # Attachments always go to task level with memory context
        if has_attachments:
            return self._make_result(
                "task", self.DEPTH_TASK,
                memory=True, tasks=False, reflections=False, state=True,
            )

        # ── Smalltalk: short, greeting-like messages ──────────────────────
        if self._is_smalltalk(msg_lower):
            log.info(f"Router: SMALLTALK — '{msg_lower[:40]}'")
            return self._make_result(
                "smalltalk", self.DEPTH_MINIMAL,
                memory=False, tasks=False, reflections=False, state=False,
                max_tokens=200, temperature=0.5,
            )

        # ── Self-edit / architecture modification ─────────────────────────
        if self._has_keywords(msg_lower, SELF_KEYWORDS):
            log.info(f"Router: SELF_EDIT — '{msg_lower[:40]}'")
            return self._make_result(
                "self_edit", self.DEPTH_DEV,
                memory=True, tasks=True, reflections=True, state=True,
            )

        # ── Memory recall ─────────────────────────────────────────────────
        if self._has_keywords(msg_lower, RECALL_KEYWORDS):
            log.info(f"Router: RECALL — '{msg_lower[:40]}'")
            return self._make_result(
                "recall", self.DEPTH_QUESTION,
                memory=True, tasks=False, reflections=False, state=True,
                max_tokens=600,
            )

        # ── Dev + action: code task ───────────────────────────────────────
        if (
            self._has_keywords(msg_lower, DEV_KEYWORDS)
            and self._has_keywords(msg_lower, ACTION_KEYWORDS)
        ):
            log.info(f"Router: DEV — '{msg_lower[:40]}'")
            return self._make_result(
                "dev", self.DEPTH_DEV,
                memory=True, tasks=True, reflections=True, state=True,
            )

        # ── General action task ───────────────────────────────────────────
        if self._has_keywords(msg_lower, ACTION_KEYWORDS):
            log.info(f"Router: TASK — '{msg_lower[:40]}'")
            return self._make_result(
                "task", self.DEPTH_TASK,
                memory=True, tasks=True, reflections=False, state=True,
            )

        # ── Dev question (no action verb) ─────────────────────────────────
        if self._has_keywords(msg_lower, DEV_KEYWORDS):
            log.info(f"Router: DEV-QUESTION — '{msg_lower[:40]}'")
            return self._make_result(
                "question", self.DEPTH_QUESTION,
                memory=True, tasks=False, reflections=False, state=False,
                max_tokens=1200,
            )

        # ── Explicit question ─────────────────────────────────────────────
        question_starters = (
            "what ", "how ", "where ", "who ", "why ", "when ",
            "can ", "is ", "has ", "does ", "do ", "will ", "should ",
        )
        if (
            msg_lower.endswith("?")
            or msg_lower.startswith(question_starters)
        ):
            log.info(f"Router: QUESTION — '{msg_lower[:40]}'")
            return self._make_result(
                "question", self.DEPTH_QUESTION,
                memory=True, tasks=False, reflections=False, state=False,
                max_tokens=1200,
            )

        # ── Long message → probably a task ───────────────────────────────
        if len(message) > 100:
            log.info(f"Router: TASK (long message) — '{msg_lower[:40]}'")
            return self._make_result(
                "task", self.DEPTH_TASK,
                memory=True, tasks=True, reflections=False, state=True,
            )

        # ── Default: question ─────────────────────────────────────────────
        log.info(f"Router: QUESTION (default) — '{msg_lower[:40]}'")
        return self._make_result(
            "question", self.DEPTH_QUESTION,
            memory=True, tasks=False, reflections=False, state=False,
            max_tokens=1000,
        )

    def build_context(
        self,
        classification: dict,
        state=None,
        memory=None,
        tasks=None,
        reflector=None,
        query: str = "",
    ) -> str:
        """
        Build the context string from loaded subsystems based on classification flags.

        Only loads the subsystems flagged as needed, keeping the context
        string minimal and token-efficient.

        Args:
            classification: Result of classify().
            state:          StateManager instance (optional).
            memory:         Memory instance (optional).
            tasks:          TaskManager instance (optional).
            reflector:      Reflector instance (optional).
            query:          The user's query for semantic memory search.

        Returns:
            str: Multi-section context string to inject into the system prompt.
        """
        flags = classification["context_flags"]
        parts = []

        # State summary (mode, session, active goal)
        if flags.get("state") and state:
            parts.append(state.get_context_summary())

        # Memory context (semantic search against query)
        if flags.get("memory") and memory:
            ctx = memory.get_memory_context(query=query, max_entries=5)
            if ctx and "No stored" not in ctx:
                parts.append(ctx)

        # Active tasks
        if flags.get("tasks") and tasks:
            ctx = tasks.get_task_context()
            if ctx and "No active" not in ctx:
                parts.append(ctx)

        # Reflection context (strategy rules, recent actions)
        if flags.get("reflections") and reflector:
            ctx = reflector.get_reflection_context()
            if ctx:
                parts.append(ctx)

        context = "\n".join(parts)
        log.info(
            f"Context built: ~{len(context.split())} words "
            f"({classification['intent']}, depth={classification['depth']})"
        )
        return context

    # ── Private helpers ───────────────────────────────────────────────────────

    def _is_smalltalk(self, msg: str) -> bool:
        """True if msg matches a smalltalk pattern and is short (< 60 chars)."""
        if len(msg) > 60:
            return False
        return any(re.match(p, msg, re.IGNORECASE) for p in SMALLTALK_PATTERNS)

    def _has_keywords(self, msg: str, keywords: list) -> bool:
        """True if any keyword from the list appears in msg."""
        return any(kw in msg for kw in keywords)

    def _make_result(
        self,
        intent:      str,
        depth:       int,
        memory:      bool = False,
        tasks:       bool = False,
        reflections: bool = False,
        state:       bool = False,
        max_tokens:  int  = 4096,
        temperature: float = 0.7,
    ) -> dict:
        """Build and return a classification result dict."""
        return {
            "intent": intent,
            "depth":  depth,
            "context_flags": {
                "memory":      memory,
                "tasks":       tasks,
                "reflections": reflections,
                "state":       state,
            },
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }


# ── Section 4: HistoryCompressor class ──────────────────────────────────────

class HistoryCompressor:
    """
    ÆTHELGARD OS — Conversation History Compressor

    When the conversation history exceeds COMPRESS_AFTER turns, this class
    compresses the older portion into a compact summary and keeps only the
    most recent KEEP_RECENT turns in full.

    This prevents unbounded token growth in long conversations.
    """

    # Compress when history length exceeds this value
    COMPRESS_AFTER = 10
    # Number of recent turns to keep in full (not compressed)
    KEEP_RECENT    = 4

    def __init__(self):
        self.summary_path = SUMMARY_PATH
        self.summaries    = self._load_summaries()

    def _load_summaries(self) -> list:
        """Load existing conversation summaries from disk."""
        if self.summary_path.exists():
            try:
                with open(self.summary_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_summaries(self):
        """
        Atomically save summaries to disk.
        Keeps only the last 20 summaries to prevent unbounded growth.
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = self.summary_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.summaries[-20:], f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.summary_path)
        except Exception as e:
            log.error(f"Failed to save conversation summaries: {e}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def should_compress(self, history: list) -> bool:
        """True if history is long enough to benefit from compression."""
        return len(history) > self.COMPRESS_AFTER

    def compress(self, history: list) -> list:
        """
        Compress older history turns into a summary.

        The returned list contains:
            [0] — A "user" message containing the summary text
            [1] — An "assistant" acknowledgement
            [2:] — The last KEEP_RECENT messages verbatim

        Args:
            history: Current full conversation history.

        Returns:
            list: Compressed history, shorter than the input.
        """
        if len(history) <= self.KEEP_RECENT:
            return history

        old_messages = history[:-self.KEEP_RECENT]
        recent       = history[-self.KEEP_RECENT:]

        # Extract topics, tools, and key actions from old messages
        topics      = set()
        tools_used  = set()
        key_actions = []

        for msg in old_messages:
            content = str(msg.get("content", ""))[:200]
            role    = msg.get("role", "")

            if role == "user":
                for word in content.lower().split():
                    if len(word) > 4 and word not in {
                        "there", "about", "would", "could", "should",
                        "these", "their", "which", "where", "after",
                    }:
                        topics.add(word)

            if "<tool_call>" in content:
                tools = re.findall(r'"tool":\s*"(\w+)"', content)
                tools_used.update(tools)

            if role == "assistant" and len(content) > 50:
                key_actions.append(content.split("\n")[0][:100])

        summary = {
            "timestamp":   datetime.now().isoformat(),
            "message_count": len(old_messages),
            "topics":      list(topics)[:20],
            "tools_used":  list(tools_used),
            "key_actions": key_actions[-5:],
        }

        self.summaries.append(summary)
        self._save_summaries()

        summary_text = self._format_summary(summary)
        compressed   = [
            {
                "role":    "user",
                "content": f"[Previous conversation summary: {summary_text}]",
            },
            {
                "role":    "assistant",
                "content": "Understood. I have context from our previous conversation.",
            },
        ]
        compressed.extend(recent)

        old_words = sum(len(str(m.get("content", "")).split()) for m in history)
        new_words = sum(len(str(m.get("content", "")).split()) for m in compressed)
        log.info(
            f"History compressed: {len(history)} → {len(compressed)} messages, "
            f"~{old_words} → ~{new_words} words"
        )
        return compressed

    def _format_summary(self, summary: dict) -> str:
        """Format a summary dict into a readable string."""
        parts = []
        if summary.get("topics"):
            parts.append(f"Topics: {', '.join(summary['topics'][:10])}")
        if summary.get("tools_used"):
            parts.append(f"Tools used: {', '.join(summary['tools_used'])}")
        if summary.get("key_actions"):
            parts.append(f"Actions: {'; '.join(summary['key_actions'][:3])}")
        return " | ".join(parts) if parts else "General conversation"

    def get_context_summary(self) -> str:
        """Return the most recent summary as a context string."""
        if not self.summaries:
            return ""
        last = self.summaries[-1]
        return f"Previous context: {self._format_summary(last)}"
