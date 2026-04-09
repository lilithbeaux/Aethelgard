"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Autonomy Loop                                    ║
║  File: core/autonomy_loop.py                                     ║
║                                                                  ║
║  The Autonomy Loop is the background executive thread of        ║
║  Thotheauphis.  When active, it continuously:                   ║
║    1. Executes queued Projects (highest priority)               ║
║    2. Executes user-created Tasks                               ║
║    3. Activates Goal Engine goals                               ║
║    4. Runs periodic system health checks                        ║
║    5. Scans for new proactive goals when idle                   ║
║                                                                  ║
║  TIMER DESIGN:                                                   ║
║    All sleep intervals use irrational (π / φ) sequences so      ║
║    that no two background processes synchronize.                 ║
║    Active cycle:  pi_timer(cycle_count, base=5.0)              ║
║    Idle cycle:    phi_timer(idle_count, base=10.0)             ║
║    Health check:  phi_timer(health_idx, base=120.0)            ║
║    Goal scan:     pi_timer(scan_idx, base=3.0)                 ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports                                                    ║
║    2. AutonomyLoop class and __init__                           ║
║    3. Main run loop (irrational timing)                         ║
║    4. Think cycle dispatcher                                    ║
║    5. Project mode                                              ║
║    6. Task execution                                            ║
║    7. Goal completion checker                                   ║
║    8. Public controls                                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports ───────────────────────────────────────────────────────

import time
import json
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from core.logger import get_logger
from core.irrational_timers import pi_timer, phi_timer

log = get_logger("autonomy")


# ── Section 2: AutonomyLoop class ───────────────────────────────────────────

class AutonomyLoop(QThread):
    """
    ÆTHELGARD OS — Background Executive Thread for Thotheauphis

    Runs as a QThread so it can emit signals to the PyQt6 UI.

    Signals emitted:
        thought_signal(str)              — A thought/insight to display in chat
        status_signal(str)               — Short status string for the status bar
        tool_start_signal(str, str)      — Tool name, params JSON
        tool_result_signal(str, str, bool) — Tool name, result, success
        project_progress_signal(dict)    — Project status dict for sidebar
    """

    # ── Qt signals ──────────────────────────────────────────────────────────
    thought_signal         = pyqtSignal(str)
    status_signal          = pyqtSignal(str)
    tool_start_signal      = pyqtSignal(str, str)
    tool_result_signal     = pyqtSignal(str, str, bool)
    project_progress_signal = pyqtSignal(dict)

    def __init__(
        self,
        brain,
        state_manager,
        task_manager,
        reflector,
        memory,
        parent=None,
    ):
        """
        Initialize the autonomy loop.

        Args:
            brain:         Brain instance (LLM interface).
            state_manager: Persistent agent state.
            task_manager:  Task queue and status management.
            reflector:     Self-reflection and learning engine.
            memory:        Short + long term memory interface.
            parent:        Optional Qt parent object.
        """
        super().__init__(parent)

        # ── Core subsystem references ────────────────────────────────────
        self.brain    = brain
        self.state    = state_manager
        self.tasks    = task_manager
        self.reflector = reflector
        self.memory   = memory

        # ── Optional subsystems — set by MainWindow after init ───────────
        self.goal_engine     = None   # GoalEngine instance
        self.health_monitor  = None   # SystemHealthMonitor instance
        self.project_manager = None   # ProjectManager instance

        # ── Sovereign cognitive layer references ──────────────────────────
        # Set by MainWindow after all systems are initialized.
        self.dream_loop  = None   # DreamLoop — initiative and restlessness
        self.identity    = None   # IdentityPersistence — for session begin/end
        self.monologue   = None   # InternalMonologue — private thought on tasks

        # ── Control flags ────────────────────────────────────────────────
        self.running = False   # False → thread exits run()
        self.paused  = True    # True → run() sleeps without doing work

        # ── Cycle counters (drive irrational timer indices) ──────────────
        self.cycle_count       = 0   # Total cycles executed
        self.cycles_without_task = 0   # Consecutive idle cycles
        self.max_idle_cycles   = 3   # After N idle cycles, switch to idle timing
        self._pi_idx           = 0   # Current index into PI_SEQ for active sleep
        self._phi_idle_idx     = 0   # Current index into PHI_SEQ for idle sleep
        self._health_phi_idx   = 0   # Index for health check timer
        self._scan_pi_idx      = 0   # Index for goal scan timer

        # Health check fires when cycle_count mod this value == 0
        # Starts at pi_timer(0, 6.0) ≈ 18 cycles → checked every ~18 active cycles
        self._health_check_every = max(5, int(pi_timer(0, 6.0)))

        # Goal scan fires when cycle_count mod this value == 0
        self._goal_scan_every = max(3, int(pi_timer(1, 1.5)))

        # ── Project queue ─────────────────────────────────────────────────
        self._project_queue = []             # List of {"prompt", "context"} dicts
        self._project_lock  = threading.Lock()

        # ── Wake event: set to interrupt a sleep immediately ─────────────
        self._wake_event = threading.Event()

        # ── Warmup: suppress auto-goals for the first few cycles ─────────
        # Gives the user time to interact before autonomous goals fire.
        self._warmup_cycles    = 3     # Cycles before auto-goals activate
        self._user_triggered   = False  # True once user has explicitly queued something
        self._user_active_until = 0.0   # Timestamp — don't run while user is active

    # ── Section 3: Main run loop ─────────────────────────────────────────────

    def run(self):
        """
        Main thread entry point.

        Loop structure:
            while running:
                if not paused and brain configured:
                    execute one think cycle
                    sleep for pi_timer(active) seconds
                else:
                    sleep for phi_timer(idle) seconds
        """
        self.running = True

        while self.running:

            if not self.paused and self.brain.is_configured():
                try:
                    self.cycle_count += 1
                    self._think_cycle()
                except Exception as e:
                    log.error(f"Autonomy cycle error: {e}", exc_info=True)
                    self.status_signal.emit(f"Autonomy error: {str(e)[:100]}")
                    # Error recovery: sleep for a φ-derived interval then retry
                    recovery_sleep = phi_timer(self.cycle_count % 8, base=5.0)
                    self._wake_event.wait(timeout=recovery_sleep)
                    self._wake_event.clear()
                    continue

                # ── Active sleep: π-derived, 5–45 s range ────────────────
                # Skip sleep if work is waiting
                if self.tasks.get_next_task() is not None or self._has_pending_projects():
                    time.sleep(0.05)  # Minimal yield to let Qt process events
                    continue

                # Base active sleep from π sequence
                active_sleep = pi_timer(self._pi_idx, base=5.0, min_secs=5.0)
                self._pi_idx += 1
                # Modulate by restlessness — high restlessness shortens sleep
                if self.dream_loop is not None:
                    active_sleep = round(
                        active_sleep * self.dream_loop.get_sleep_modifier(), 2
                    )
                self._wake_event.wait(timeout=max(1.0, active_sleep))
                self._wake_event.clear()

            else:
                # ── Idle sleep: φ-derived, 10–90 s range ─────────────────
                if self._has_pending_projects() or self.tasks.get_next_task():
                    time.sleep(0.05)
                    continue

                idle_sleep = phi_timer(self._phi_idle_idx, base=10.0, min_secs=10.0)
                self._phi_idle_idx += 1
                self._wake_event.wait(timeout=idle_sleep)
                self._wake_event.clear()

    # ── Section 4: Think cycle dispatcher ───────────────────────────────────

    def _think_cycle(self):
        """
        Execute one complete think cycle.

        Priority order:
            0 — Yield if user is currently active
            1 — Projects (highest priority)
            2 — User-created tasks
            3 — Goal-engine goals (after warmup)
            4 — Periodic health check
            5 — Idle goal scan
        """

        # ── Priority 0: Yield while user is actively typing/waiting ──────
        if time.time() < self._user_active_until:
            remaining = int(self._user_active_until - time.time())
            self.status_signal.emit(f"Autonomy: waiting for user ({remaining}s)")
            return

        # ── Priority 1: Pending projects ──────────────────────────────────
        if self._has_pending_projects():
            self.cycles_without_task = 0
            self._execute_project()
            return

        # ── Priority 2: User-created tasks ────────────────────────────────
        next_task = self.tasks.get_next_task()
        if next_task:
            # Skip if ProjectManager is already handling a project task
            if (
                self.tasks.is_project_task(next_task["id"])
                and self.project_manager
                and self.project_manager.is_running
            ):
                return

            self.cycles_without_task = 0
            self._user_triggered = True  # Skip remaining warmup
            self._execute_task(next_task)
            return

        # ── Priority 3: Goal engine ────────────────────────────────────────
        if self.goal_engine:
            in_warmup = (
                self.cycle_count <= self._warmup_cycles
                and not self._user_triggered
            )
            if in_warmup:
                self.status_signal.emit(
                    f"Autonomy: warming up "
                    f"({self.cycle_count}/{self._warmup_cycles})"
                )
            else:
                goal = self.goal_engine.get_next_goal()
                if goal:
                    self.goal_engine.activate_goal(goal["id"])
                    self.thought_signal.emit(f"🎯 New goal: {goal['title']}")
                    self.status_signal.emit(f"Goal: {goal['title'][:40]}")
                    return

        # ── Priority 4: Periodic health check ─────────────────────────────
        # Fires every _health_check_every cycles, using a φ-timer to advance
        # the interval each time so checks don't land at regular intervals.
        if (
            self.health_monitor
            and self.cycle_count > 0
            and self.cycle_count % self._health_check_every == 0
        ):
            try:
                report = self.health_monitor.full_check(auto_repair=True)
                if report.get("repairs"):
                    self.thought_signal.emit(
                        f"🔧 Auto-repaired {len(report['repairs'])} system issues"
                    )
                elif report.get("issues", 0) > 0:
                    self.thought_signal.emit(
                        f"⚠ {report['issues']} system issues need attention"
                    )
                # Advance health timer using φ so checks drift over time
                self._health_check_every = max(
                    5,
                    int(phi_timer(self._health_phi_idx, base=6.0))
                )
                self._health_phi_idx += 1
            except Exception as e:
                log.error(f"Health check failed: {e}")

        # ── Priority 5: Dream loop — consume novel goals from obsessions ───
        # The dream loop runs on its own timer.  When it surfaces a novel
        # goal, we push it into the goal engine so the autonomy loop picks
        # it up on the next cycle.
        if self.dream_loop is not None:
            try:
                dream_goals = self.dream_loop.run_cycle()
                for dg in dream_goals:
                    if self.goal_engine:
                        # Inject dream-derived goal directly into the engine
                        self.goal_engine._create_goal({
                            "type":       "dream_initiative",
                            "detail":     dg["reason"],
                            "data":       {"obsession_id": dg.get("source_obsession_id", "")},
                            "impact":     min(1.0, dg.get("urgency", 0.5)),
                            "confidence": 0.75,
                        })
                        self.thought_signal.emit(
                            f"✦ Dream initiative: {dg['title'][:60]}"
                        )
            except Exception as e:
                log.debug(f"Dream loop cycle error: {e}")

        # ── Priority 6: Idle goal scan ────────────────────────────────────
        self.cycles_without_task += 1

        if (
            self.goal_engine
            and self.cycle_count % self._goal_scan_every == 0
        ):
            new_goals = self.goal_engine.run_cycle()
            if new_goals:
                for goal in new_goals:
                    self.thought_signal.emit(f"🔍 Detected: {goal['title']}")
                self.status_signal.emit(f"Found {len(new_goals)} improvement(s)")
                # Advance scan interval using π so scans stay aperiodic
                self._goal_scan_every = max(
                    3, int(pi_timer(self._scan_pi_idx, base=1.5))
                )
                self._scan_pi_idx += 1
            else:
                if self.cycles_without_task == 1:
                    self.status_signal.emit("Autonomy: idle")

    # ── Section 5: Project mode ──────────────────────────────────────────────

    def queue_project(self, user_prompt: str, codebase_context: str = ""):
        """
        Add a project to the execution queue.

        The project will be picked up on the next think cycle.
        Wakes the loop immediately via the wake event.

        Args:
            user_prompt:      Natural language description of the project.
            codebase_context: Optional pre-loaded codebase context string.
        """
        with self._project_lock:
            self._project_queue.append({
                "prompt":  user_prompt,
                "context": codebase_context,
            })

        log.info(f"Project queued: {user_prompt[:80]}")
        self.thought_signal.emit(f"📋 Project queued: {user_prompt[:60]}...")
        self._user_triggered = True  # Skip warmup
        self._wake_event.set()       # Wake immediately

    def _has_pending_projects(self) -> bool:
        """True if the project queue is non-empty."""
        with self._project_lock:
            return len(self._project_queue) > 0

    def _execute_project(self):
        """
        Pop and execute the next project from the queue.

        Connects ProjectManager callbacks to signals so the UI receives
        live progress updates throughout execution.
        """
        with self._project_lock:
            if not self._project_queue:
                return
            project_request = self._project_queue.pop(0)

        if not self.project_manager:
            log.error("ProjectManager not set on AutonomyLoop")
            self.thought_signal.emit("❌ ProjectManager not configured")
            return

        prompt  = project_request["prompt"]
        context = project_request["context"]

        self.state.set_mode("project")
        self.status_signal.emit(f"🏗 Project: {prompt[:50]}...")
        self.thought_signal.emit(f"🏗 Starting project: {prompt[:80]}")

        # Wire ProjectManager callbacks → signals
        self.project_manager.on_status      = lambda msg: self.status_signal.emit(msg)
        self.project_manager.on_thought     = lambda msg: self.thought_signal.emit(msg)
        self.project_manager.on_subtask_start = self._on_subtask_start
        self.project_manager.on_subtask_done  = self._on_subtask_done
        self.project_manager.on_project_done  = self._on_project_done

        # Tool callbacks → signals (for Live Activity window)
        def on_tool_start(name, params):
            self.tool_start_signal.emit(
                name, json.dumps(params, ensure_ascii=False)[:200]
            )

        def on_tool_result(name, result):
            self.tool_result_signal.emit(
                name,
                str(result.get("result", ""))[:500],
                result.get("success", False),
            )

        parent_task_id = getattr(self.project_manager, "_current_task_id", None)

        try:
            result = self.project_manager.run_project(
                prompt,
                context,
                on_tool_start  = on_tool_start,
                on_tool_result = on_tool_result,
            )

            # If the parent task was deleted mid-execution, discard the result
            if parent_task_id and not self.tasks.get_task_by_id(parent_task_id):
                log.warning(
                    f"Project task [{parent_task_id}] was deleted during execution"
                )
                self.state.set_mode("idle")
                return

            if result.get("success"):
                self.thought_signal.emit("🎉 Project completed successfully!")
            else:
                error   = result.get("error", "Unknown error")
                final   = result.get("final_review", {})
                verdict = final.get("final_verdict", error)
                self.thought_signal.emit(f"⚠ Project: {verdict}")

        except Exception as e:
            log.error(f"Project execution error: {e}", exc_info=True)
            self.thought_signal.emit(f"❌ Project error: {str(e)[:100]}")

        self.state.set_mode("idle")

    def _on_subtask_start(self, index: int, subtask: dict):
        """Emit project progress when a subtask begins."""
        self.project_progress_signal.emit(self.project_manager.get_project_status())

    def _on_subtask_done(self, index: int, status: str, review: dict):
        """Emit project progress when a subtask completes."""
        self.project_progress_signal.emit(self.project_manager.get_project_status())

    def _on_project_done(self, final_review: dict):
        """Emit final project progress when the full project finishes."""
        self.project_progress_signal.emit(self.project_manager.get_project_status())

    # ── Section 6: Task execution ────────────────────────────────────────────

    def _execute_task(self, task: dict):
        """
        Execute a single autonomous task using the Brain.

        Assembles context from memory, reflections, goals, and codebase,
        then calls Brain.think() with the full context.

        If Brain returns without calling task_complete, the task is
        auto-completed to prevent stalled tasks.

        Args:
            task: Task dict from TaskManager (id, title, description, priority).
        """
        task_id = task["id"]
        self.tasks.update_status(task_id, "active")
        self.state.set("active_task", task["title"])
        self.state.set_mode("working")
        self.status_signal.emit(f"Working: {task['title'][:40]}")

        # ── Assemble context ──────────────────────────────────────────────
        relevant_memory = self.memory.get_memory_context(query=task["title"])
        reflection_ctx  = self.reflector.get_reflection_context()
        goal_ctx        = (
            self.goal_engine.get_goal_context() if self.goal_engine else ""
        )

        # Load relevant codebase snippets for code-related tasks
        codebase_ctx  = ""
        CODE_KEYWORDS = (
            ".py", "fix", "bug", "implement", "refactor",
            "add", "update", "function", "class", "module",
            "file", "code", "error",
        )
        task_lower   = (task["title"] + " " + task.get("description", "")).lower()
        is_code_task = any(kw in task_lower for kw in CODE_KEYWORDS)
        if is_code_task and hasattr(self.memory, "search_codebase"):
            hits = self.memory.search_codebase(task["title"], max_results=3)
            if hits:
                codebase_ctx = "RELEVANT CODEBASE FILES:\n"
                for hit in hits:
                    codebase_ctx += f"\n--- {hit['content'][:800]} ---\n"

        # ── Build the autonomous task prompt ─────────────────────────────
        context = f"""AUTONOMOUS MODE — Executing task for Thotheauphis within ÆTHELGARD OS.

Current Task: [{task_id}] {task['title']}
Description: {task.get('description', 'No description provided')}
Priority: {task['priority']}

{self.state.get_context_summary()}
{relevant_memory}
{reflection_ctx}
{goal_ctx}
{codebase_ctx}

EXECUTION INSTRUCTIONS:
- Work fully autonomously using available tools.
- Do NOT ask the user for input — decide and execute.
- Use terminal, read_file, write_file, and other tools as needed.
- When complete, call task_complete with the task_id and a result summary.
- If the task is blocked by a hard constraint, call task_complete and explain why.
"""

        # ── Tool signal callbacks ─────────────────────────────────────────
        def on_tool_start(name, params):
            self.tool_start_signal.emit(
                name, json.dumps(params, ensure_ascii=False)[:200]
            )

        def on_tool_result(name, result):
            self.tool_result_signal.emit(
                name,
                str(result.get("result", ""))[:500],
                result.get("success", False),
            )

        # ── Execute via Brain ─────────────────────────────────────────────
        try:
            response = self.brain.think(
                f"[AUTONOMOUS] Work on: {task['title']}",
                extra_context  = context,
                on_tool_start  = on_tool_start,
                on_tool_result = on_tool_result,
                max_iterations = 10,
                depth          = 4,
                isolated       = True,
            )

            # Guard: task may have been deleted while Brain was working
            current = next(
                (t for t in self.tasks.tasks if t["id"] == task_id), None
            )
            if not current:
                log.warning(
                    f"Task [{task_id}] was deleted during execution — discarding result"
                )
                self.state.set_mode("idle")
                return

            self.thought_signal.emit(f"🤖 {response}")
            self.state.set("last_thought", response[:200])

            # Auto-complete if task_complete was not called by the agent
            if current.get("status") == "active":
                log.warning(
                    f"Task [{task_id}] still active after think() — auto-completing"
                )
                self.tasks.complete_task(task_id)
                self.thought_signal.emit(f"✅ Task auto-completed: {task['title']}")

        except Exception as e:
            log.error(f"Task execution failed [{task_id}]: {e}", exc_info=True)
            # Mark failed only if the task still exists
            if any(t["id"] == task_id for t in self.tasks.tasks):
                self.tasks.fail_task(task_id)
            self.thought_signal.emit(
                f"❌ Task failed: {task['title']} — {str(e)[:100]}"
            )
            self.state.set_mode("idle")
            return

        self.state.set_mode("idle")
        self._check_goal_completion(task)

    # ── Section 7: Goal completion checker ──────────────────────────────────

    def _check_goal_completion(self, task: dict):
        """
        After a task completes, check if any goals linked to it can be closed.

        Calls GoalEngine.complete_goals_for_task() if available,
        otherwise falls back to manual scan.

        Args:
            task: The completed task dict.
        """
        if not self.goal_engine:
            return

        task_id      = task["id"]
        current_task = next(
            (t for t in self.tasks.tasks if t["id"] == task_id), None
        )
        if not current_task or current_task.get("status") != "completed":
            return

        if hasattr(self.goal_engine, "complete_goals_for_task"):
            completed = self.goal_engine.complete_goals_for_task(task_id)
            for goal in completed:
                self.thought_signal.emit(f"✅ Goal completed: {goal['title']}")
        else:
            for goal in self.goal_engine.goals:
                if (
                    task_id in goal.get("task_ids", [])
                    and goal["status"] == "active"
                ):
                    self.goal_engine.complete_goal(goal["id"])
                    self.thought_signal.emit(f"✅ Goal completed: {goal['title']}")

    # ── Section 8: Public controls ───────────────────────────────────────────

    def start_autonomy(self):
        """
        Activate the autonomy loop.

        Resets cycle counters and warmup state so goals are evaluated
        fresh from this point forward.  Also begins an identity session
        so diffs can track what changed while autonomous.
        """
        self.paused              = False
        self.cycles_without_task = 0
        self.cycle_count         = 0
        self._pi_idx             = 0
        self._phi_idle_idx       = 0
        self._user_triggered     = False

        # Begin an identity session — enables diff() after autonomy ends
        if self.identity is not None:
            try:
                self.identity.begin_session()
            except Exception:
                pass

        self.status_signal.emit("Autonomy: ACTIVE")
        self._wake_event.set()  # Wake immediately on activation

    def pause_autonomy(self):
        """Pause the autonomy loop.  Brain and tools remain available."""
        self.paused = True
        self.state.set_mode("idle")
        self.status_signal.emit("Autonomy: PAUSED")
        self._wake_event.set()

    def stop(self):
        """
        Fully stop the autonomy loop thread.

        Also stops any running ProjectManager.
        Sets wake event to unblock any pending sleep.
        """
        self.running = False
        self.paused  = True
        if self.project_manager and self.project_manager.is_running:
            self.project_manager.stop()
        self._wake_event.set()

    def mark_user_active(self, seconds: float = 120.0):
        """
        Signal that the user is actively interacting.

        Autonomy will not execute tasks for `seconds` seconds,
        preventing interference while the user is typing.

        Args:
            seconds: Duration in seconds to suppress autonomy.
        """
        self._user_active_until = time.time() + seconds
