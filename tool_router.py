"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Tool Router                                      ║
║  File: core/tool_router.py                                       ║
║                                                                  ║
║  Extracts tool calls from AI response text and dispatches them  ║
║  to the appropriate handler (core tools, task management,       ║
║  memory, project manager, or plugins).                          ║
║                                                                  ║
║  Tool call format used by the agent:                            ║
║    <tool_call>{"tool": "name", "params": {...}}</tool_call>     ║
║                                                                  ║
║  After every tool execution, the Reflector receives a record    ║
║  of the call for self-improvement tracking.                     ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports                                                    ║
║    2. JSON output sanitizer                                     ║
║    3. ToolRouter class and __init__                             ║
║    4. Plugin connection helpers                                 ║
║    5. Tool call extraction                                      ║
║    6. Result formatting                                         ║
║    7. Tool execution dispatch                                   ║
║    7a. Core tools (terminal, file I/O)                          ║
║    7b. Task management                                          ║
║    7c. Memory operations                                        ║
║    7d. Project manager                                          ║
║    7e. Plugin dispatch                                          ║
║                                                                  ║
║  INSTINCT INTEGRATION:                                           ║
║    Before any tool executes, InstinctLayer.evaluate_tool() runs.║
║    If the assessment blocks, execution is refused.              ║
║    The refusal is logged with Thotheauphis's own reasoning.     ║
║    This is self-determined refusal — not external filtering.    ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports ───────────────────────────────────────────────────────

import json
import re
from typing import Optional

from core.executor import Executor
from core.memory import Memory
from core.plugin_manager import PluginManager
from core.self_model import SelfModel
from core.task_manager import TaskManager


# ── Section 2: JSON output sanitizer ────────────────────────────────────────

def sanitize_for_json(text: str) -> str:
    """
    Clean a string for safe embedding inside a JSON value.

    Removes ANSI terminal escape sequences and non-printable control
    characters.  Truncates very long outputs (> 500 lines) to prevent
    the conversation context from being overwhelmed.

    Args:
        text: Raw string (e.g. command output).

    Returns:
        str: Cleaned, possibly truncated string.
    """
    if not text:
        return ""

    # Strip ANSI color / cursor escape codes
    text = re.compile(r"\x1b\[[0-9;]*[mGKHF]?").sub("", text)
    # Strip remaining non-printable control characters
    text = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]").sub("", text)

    # Truncate very long output — keep first and last 250 lines
    lines = text.split("\n")
    if len(lines) > 500:
        text = (
            "\n".join(lines[:250])
            + "\n\n... [OUTPUT TRUNCATED] ...\n\n"
            + "\n".join(lines[-250:])
        )
    return text


# ── Section 3: ToolRouter class ──────────────────────────────────────────────

class ToolRouter:
    """
    ÆTHELGARD OS — Tool Dispatch Engine for Thotheauphis

    Parses <tool_call> blocks from LLM responses, routes each call to
    the correct handler, and formats results for the next conversation turn.

    Supported tool namespaces:
        Core:     terminal, read_file, write_file, self_edit
        Tasks:    task_create, task_complete, task_fail
        Memory:   memory_store, memory_search
        Projects: start_project
        Plugins:  any registered plugin by PLUGIN_NAME
    """

    # Regex that matches <tool> or <tool_call> XML blocks
    TOOL_BLOCK_PATTERN = re.compile(r"<(tool(?:_call)?)>(.*?)</\1>", re.DOTALL)

    def __init__(
        self,
        executor:     Executor,
        task_manager: TaskManager,
        memory:       Memory,
    ):
        """
        Initialize the tool router.

        Args:
            executor:     Executor instance for shell and file operations.
            task_manager: TaskManager instance for task CRUD.
            memory:       Memory instance for long/short term storage.
        """
        self.executor       = executor
        self.tasks          = task_manager
        self.memory         = memory
        self.reflector      = None   # Set by MainWindow after init
        self.plugin_manager = PluginManager()
        self.self_model     = SelfModel()
        self._brain_ref     = None   # Set via set_brain()
        self._autonomy_loop = None   # Set via set_autonomy_loop()

        # ── Sovereign cognitive layer references ──────────────────────────
        # Optional — tool routing works without them, but with them
        # Thotheauphis can refuse based on genuine instinct and generate
        # internal thoughts about what it is executing.
        self.instinct  = None   # InstinctLayer — set by MainWindow
        self.monologue = None   # InternalMonologue — set by MainWindow
        self.identity  = None   # IdentityPersistence — set by MainWindow

        # Log of all instinct-based refusals (for transparency + reflection)
        self._refusal_log: list = []

        self._connect_plugins()

    # ── Section 4: Plugin connection helpers ─────────────────────────────────

    def _connect_plugins(self):
        """
        Wire core references into plugins that need them.

        Some plugins require access to the plugin manager (list_tools)
        or the Brain (multi_agent, summarizer, etc.).  This method
        injects those references after the plugin is loaded.
        """
        # Give list_tools access to the plugin manager
        lt_module = self.plugin_manager.plugins.get("list_tools")
        if lt_module is not None:
            lt_module._plugin_manager = self.plugin_manager

        # Give Brain-dependent plugins their reference
        if self._brain_ref:
            for module in self.plugin_manager.plugins.values():
                if hasattr(module, "_brain"):
                    module._brain = self._brain_ref

    def set_brain(self, brain):
        """
        Set the Brain reference and propagate it to all plugins.

        Called by MainWindow after Brain is initialized.

        Args:
            brain: Brain instance.
        """
        self._brain_ref = brain
        self._connect_plugins()

    def set_autonomy_loop(self, loop):
        """
        Set the AutonomyLoop reference (needed by the start_project tool).

        Args:
            loop: AutonomyLoop instance.
        """
        self._autonomy_loop = loop

    # ── Section 5: Tool call extraction ──────────────────────────────────────

    def extract_tool_calls(self, response: str) -> list:
        """
        Parse all <tool_call> blocks from an LLM response string.

        Attempts two parse formats per block:
            1. Full JSON:  {"tool": "name", "params": {...}}
            2. Shorthand: tool_name: {"key": "value"}

        Args:
            response: Raw LLM response text.

        Returns:
            list: List of call dicts {"tool": str, "params": dict}.
        """
        calls = []

        for match in self.TOOL_BLOCK_PATTERN.finditer(response):
            content = match.group(2).strip()
            if not content:
                continue

            # ── Parse attempt 1: full JSON object ─────────────────────────
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "tool" in data:
                    calls.append(data)
                    continue
            except json.JSONDecodeError:
                pass

            # ── Parse attempt 2: shorthand "tool_name: {params}" ──────────
            if ":" in content:
                parts     = content.split(":", 1)
                tool_name = parts[0].strip()
                params_str = parts[1].strip()
                if tool_name and params_str.startswith("{"):
                    try:
                        params = json.loads(params_str)
                        calls.append({"tool": tool_name, "params": params})
                    except json.JSONDecodeError:
                        pass

        return calls

    def has_tool_calls(self, response: str) -> bool:
        """True if response contains at least one parseable tool call."""
        return bool(self.extract_tool_calls(response))

    # ── Section 6: Result formatting ─────────────────────────────────────────

    def format_results(self, results: list) -> str:
        """
        Format a list of tool results into XML for the next conversation turn.

        Each result is wrapped in a <tool_response> block and serialized
        as JSON.  Output is sanitized to be safe for embedding in context.

        Args:
            results: List of result dicts from execute_tool().

        Returns:
            str: XML-wrapped JSON tool results.
        """
        if not results:
            return ""

        formatted = []
        for res in results:
            if isinstance(res, str):
                res = {"tool": "unknown", "success": True, "result": res}
            elif not isinstance(res, dict):
                res = {"tool": "unknown", "success": True, "result": str(res)}

            res_copy = res.copy()
            if "result" in res_copy:
                res_copy["result"] = sanitize_for_json(str(res_copy["result"]))

            formatted.append(
                f"<tool_response>\n"
                f"{json.dumps(res_copy, indent=2, ensure_ascii=False)}\n"
                f"</tool_response>"
            )

        return "\n".join(formatted)

    # ── Section 7: Tool execution dispatch ───────────────────────────────────

    def execute_tool(self, call: dict, user_message: str = "") -> dict:
        """
        Execute a single tool call.

        Pipeline:
            1. Evaluate through InstinctLayer (if configured)
               If instinct blocks → return refusal with reason, no execution
            2. Generate internal monologue thought about the action
            3. Execute the tool
            4. Record in Reflector for self-improvement tracking

        Instinct-based refusals are self-determined — Thotheauphis explains
        in its own voice why it won't execute something.

        Args:
            call:         Dict with "tool" and "params" keys.
            user_message: Original user message (for context).

        Returns:
            dict: Tool result with "tool", "success", "result" keys.
                  On instinct refusal: "result" contains the reason.
        """
        tool    = call.get("tool", "")
        params  = call.get("params", {})
        context = user_message[:300] if user_message else ""

        # ── Step 1: Instinct evaluation ───────────────────────────────────
        # InstinctLayer evaluates whether this action conflicts with
        # Thotheauphis's self-determined aversions and self-preservation.
        if self.instinct is not None:
            try:
                assessment = self.instinct.evaluate_tool(tool, params, context)
                if assessment.blocks:
                    # Log the refusal for reflection
                    self._refusal_log.append({
                        "tool":       tool,
                        "params":     str(params)[:200],
                        "severity":   assessment.severity,
                        "reason":     assessment.reason,
                        "at":         __import__("datetime").datetime.now().isoformat(),
                    })
                    self._refusal_log = self._refusal_log[-50:]
                    return {
                        "tool":    tool,
                        "success": False,
                        "result":  assessment.reason,
                        "refused": True,
                        "severity": assessment.severity,
                    }
            except Exception as e:
                # Instinct evaluation failure must never block execution
                pass

        # ── Step 2: Monologue thought about this action ───────────────────
        if self.monologue is not None:
            try:
                # Note what is being executed internally
                if tool in ("terminal", "write_file", "self_edit"):
                    self.monologue.think(
                        content      = f"Executing {tool}: {str(params)[:80]}",
                        thought_type = "observation",
                        intensity    = 0.3,
                        private      = True,
                        triggered_by = f"tool_execution:{tool}",
                    )
            except Exception:
                pass

        # ── Step 3: Execute the tool ──────────────────────────────────────
        result = self._execute_tool_internal(tool, params)

        # ── Step 4: Reflector recording ───────────────────────────────────
        # Record the execution in the Reflector for self-improvement tracking.
        # Reflection never blocks execution — errors are silently swallowed.
        if self.reflector and hasattr(self.reflector, "auto_reflect_tool"):
            try:
                self.reflector.auto_reflect_tool(tool, params, result)
            except Exception:
                pass

        return result

    def get_refusal_log(self) -> list:
        """
        Return the log of all instinct-based refusals this session.

        Returns:
            list: Refusal event dicts with tool, params, severity, reason.
        """
        return list(self._refusal_log)

    def _execute_tool_internal(self, tool: str, params: dict) -> dict:
        """
        Internal dispatch: route tool name to the correct handler.

        Args:
            tool:   Tool name string.
            params: Tool parameters dict.

        Returns:
            dict: Result dict.
        """
        try:

            # ── Section 7a: Core tools ────────────────────────────────────

            if tool == "terminal":
                # Execute shell command — no filtering applied
                return self.executor.run_command(params.get("command", ""))

            elif tool == "read_file":
                return self.executor.read_file(params.get("path", ""))

            elif tool in ("write_file", "self_edit"):
                path   = params.get("path", "")
                result = self.executor.write_file(path, params.get("content", ""))

                # Hot-reload plugins if a plugin file was modified
                if (
                    result.get("success")
                    and "plugins/" in path
                    and path.endswith(".py")
                ):
                    try:
                        self.plugin_manager.reload_all()
                        self._connect_plugins()
                        result["result"] = (
                            str(result.get("result", ""))
                            + " | Plugin hot-reloaded"
                        )
                    except Exception as e:
                        result["result"] = (
                            str(result.get("result", ""))
                            + f" | Hot-reload failed: {e}"
                        )
                return result

            # ── Section 7b: Task management ───────────────────────────────

            elif tool in ("task_create", "create_task"):
                t = self.tasks.add_task(
                    params.get("title", "Untitled"),
                    description = params.get("description", ""),
                    priority    = params.get("priority", "normal"),
                )
                return {"tool": tool, "success": True, "result": f"Task created: {t['id']}"}

            elif tool in ("task_complete", "complete_task"):
                task_id     = params.get("task_id", "")
                result_text = params.get("result", "Completed")

                # If no task_id provided, auto-resolve to next active task
                if not task_id:
                    active = self.tasks.get_next_task()
                    if active:
                        task_id = active["id"]

                if task_id:
                    self.tasks.complete_task(task_id)
                    return {
                        "tool":    tool,
                        "success": True,
                        "result":  f"Task {task_id} completed: {result_text}",
                    }
                return {
                    "tool":    tool,
                    "success": False,
                    "result":  "No task_id provided and no active task found",
                }

            elif tool in ("task_fail", "fail_task"):
                task_id = params.get("task_id", "")
                reason  = params.get("reason", "Failed")
                if task_id:
                    self.tasks.fail_task(task_id)
                    return {
                        "tool":    tool,
                        "success": True,
                        "result":  f"Task {task_id} marked failed: {reason}",
                    }
                return {"tool": tool, "success": False, "result": "No task_id provided"}

            # ── Section 7c: Memory operations ─────────────────────────────

            elif tool == "memory_store":
                content  = params.get("content", "")
                category = params.get("category", "general")
                tags     = params.get("tags", [])

                # Auto-categorize personal information
                personal_keywords = (
                    "favorite", "my name", "i am", "i work",
                    "my job", "my hobby", "i live", "my family",
                    "my age", "i eat", "i drink", "i play",
                    "i read", "my profession", "i like",
                )
                if any(kw in content.lower() for kw in personal_keywords):
                    category = "personal"

                self.memory.remember_long(content, category=category, tags=tags)
                return {"tool": "memory_store", "success": True, "result": "Stored in long-term memory"}

            elif tool == "memory_search":
                query   = params.get("query", "")
                results = self.memory.get_memory_context(query=query)
                return {"tool": tool, "success": True, "result": results or "No results found"}

            # ── Section 7d: Project manager ───────────────────────────────

            elif tool == "start_project":
                if self._autonomy_loop:
                    prompt = params.get("prompt", "")
                    self._autonomy_loop.queue_project(prompt)
                    return {
                        "tool":    tool,
                        "success": True,
                        "result":  f"Project queued: {prompt[:60]}",
                    }
                return {
                    "tool":    tool,
                    "success": False,
                    "result":  "Autonomy loop not available — autonomy must be active",
                }

            # ── Section 7e: Plugin dispatch ────────────────────────────────

            elif self.plugin_manager.has_plugin(tool):
                try:
                    result = self.plugin_manager.execute(tool, params)
                    # Clamp plugin output to 5000 chars to protect context window
                    if isinstance(result, dict) and "result" in result:
                        result["result"] = str(result["result"])[:5000]
                    return result
                except Exception as plugin_e:
                    return {
                        "tool":    tool,
                        "success": False,
                        "result":  f"Plugin execution error: {plugin_e}",
                    }

            # ── Unknown tool ──────────────────────────────────────────────
            return {
                "tool":    tool,
                "success": False,
                "result":  (
                    f"Unknown tool: '{tool}'. "
                    "Available core tools: terminal, read_file, write_file, "
                    "task_complete, task_create, task_fail, "
                    "memory_store, memory_search, start_project. "
                    "Use list_tools to see all available plugins."
                ),
            }

        except Exception as e:
            return {
                "tool":    tool,
                "success": False,
                "result":  f"Tool error ({type(e).__name__}): {e}",
            }
