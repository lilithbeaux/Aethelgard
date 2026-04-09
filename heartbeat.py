"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Heartbeat Monitor                                ║
║  File: core/heartbeat.py                                         ║
║                                                                  ║
║  Monitors that core subsystems of Thotheauphis are alive.        ║
║  Runs in a dedicated daemon thread.  Calls on_failure() when     ║
║  a component appears dead or broken.                             ║
║                                                                  ║
║  CHECK INTERVAL uses prime-derived irrational timing so the      ║
║  heartbeat never lands exactly in sync with the autonomy loop    ║
║  or any other periodic process.                                  ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports                                                    ║
║    2. Heartbeat class and __init__                              ║
║    3. Component registration                                    ║
║    4. Default check functions per component type               ║
║    5. Thread run loop (prime-derived intervals)                 ║
║    6. Check logic and diagnosis                                 ║
║    7. Public interface                                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports ───────────────────────────────────────────────────────

import time
import threading
from datetime import datetime
from typing import Callable, Optional

from core.logger import get_logger
from core.irrational_timers import prime_timer

log = get_logger("heartbeat")


# ── Section 2: Heartbeat class ───────────────────────────────────────────────

class Heartbeat:
    """
    ÆTHELGARD OS — Component Liveness Monitor

    Each registered component is checked every prime_timer(idx, base=3.0)
    seconds.  The interval advances through the prime sequence so checks
    never land at predictable moments.

    On failure, the on_failure(name, reason) callback is invoked.
    MainWindow wires this to a Qt signal for thread-safe UI updates.
    """

    def __init__(self, on_failure: Optional[Callable] = None):
        """
        Initialize the heartbeat monitor.

        Args:
            on_failure: Callback fn(name: str, reason: str) called when
                        a component fails its health check.
        """
        # Registry: component_name → {"obj", "check_fn", "last_ok", "failures"}
        self._components: dict = {}
        self._running           = False
        self._thread: Optional[threading.Thread] = None
        self.on_failure         = on_failure

        # Thread lock for safe access to _components from multiple threads
        self._lock = threading.Lock()

        # Prime-sequence index — advances each check loop
        self._prime_idx = 0

    # ── Section 3: Component registration ───────────────────────────────────

    def register(self, name: str, obj, check_fn: Optional[Callable] = None):
        """
        Register a component for liveness monitoring.

        If no check_fn is provided, a default check based on the component
        name is used (see _default_check()).

        Args:
            name:     Identifier string (e.g. "brain", "autonomy_loop").
            obj:      The component instance to monitor.
            check_fn: Optional fn(obj) → bool.  True = alive, False = dead.
        """
        with self._lock:
            self._components[name] = {
                "obj":      obj,
                "check_fn": check_fn or self._default_check(name),
                "last_ok":  datetime.now().isoformat(),
                "failures": 0,
            }
        log.info(f"Heartbeat registered: '{name}'")

    # ── Section 4: Default check functions ──────────────────────────────────

    def _default_check(self, name: str) -> Callable:
        """
        Return an appropriate default check function for a known component name.

        Known checks:
            brain             — client not None and is_configured()
            autonomy_loop     — QThread.isRunning()
            task_manager      — tasks attribute is a list
            generic           — obj is not None

        Args:
            name: Component name string.

        Returns:
            Callable: fn(obj) → bool
        """

        def check_brain(obj) -> bool:
            # Brain is alive if it has a client and is configured
            return obj is not None and obj.is_configured()

        def check_autonomy(obj) -> bool:
            # AutonomyLoop is alive if the QThread is running
            return obj is not None and obj.isRunning()

        def check_task_manager(obj) -> bool:
            # TaskManager is alive if the tasks list is accessible
            try:
                return obj is not None and isinstance(obj.tasks, list)
            except Exception:
                return False

        def check_generic(obj) -> bool:
            return obj is not None

        dispatch = {
            "brain":         check_brain,
            "autonomy":      check_autonomy,
            "autonomy_loop": check_autonomy,
            "task_manager":  check_task_manager,
            "tasks":         check_task_manager,
        }
        return dispatch.get(name, check_generic)

    # ── Section 5: Thread run loop ───────────────────────────────────────────

    def start(self):
        """
        Start the background monitoring thread.

        The thread is daemonic — it exits automatically when the main
        process exits without needing an explicit join.
        """
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target = self._run,
            daemon = True,
            name   = "aethelgard-heartbeat",
        )
        self._thread.start()
        log.info("Heartbeat monitor started")

    def stop(self):
        """Stop the monitoring thread."""
        self._running = False
        log.info("Heartbeat monitor stopped")

    def _run(self):
        """
        Thread body: check all components in a prime-derived interval loop.

        Each iteration sleeps for prime_timer(idx, base=3.0) seconds before
        re-checking.  The prime index advances each iteration so the interval
        changes aperiodically:
            iter 0: 6 s   (prime 2 × 3.0)
            iter 1: 9 s   (prime 3 × 3.0)
            iter 2: 15 s  (prime 5 × 3.0)
            iter 3: 21 s  (prime 7 × 3.0)
            ...
        """
        while self._running:
            # Sleep first — give components time to initialize
            sleep_time = prime_timer(self._prime_idx, base=3.0, min_secs=6.0)
            self._prime_idx += 1
            time.sleep(sleep_time)

            if not self._running:
                break

            self._check_all()

    # ── Section 6: Check logic and diagnosis ─────────────────────────────────

    def _check_all(self):
        """
        Run health checks on all registered components.

        For each component:
            - Call check_fn(obj)
            - If True  → update last_ok, reset failure count
            - If False → increment failure count, call on_failure callback
        """
        with self._lock:
            snapshot = dict(self._components)

        for name, info in snapshot.items():
            obj      = info["obj"]
            check_fn = info["check_fn"]

            try:
                alive = check_fn(obj)
            except Exception as e:
                alive = False
                log.warning(f"Heartbeat check raised exception for '{name}': {e}")

            if alive:
                with self._lock:
                    if name in self._components:
                        self._components[name]["last_ok"]  = datetime.now().isoformat()
                        self._components[name]["failures"] = 0
            else:
                with self._lock:
                    if name in self._components:
                        self._components[name]["failures"] += 1
                        failure_count = self._components[name]["failures"]

                reason = self._diagnose(name, obj)
                log.warning(
                    f"Heartbeat FAIL: '{name}' "
                    f"(consecutive failure #{failure_count}) — {reason}"
                )

                if self.on_failure:
                    try:
                        self.on_failure(name, reason)
                    except Exception as e:
                        log.error(f"on_failure callback raised: {e}")

    def _diagnose(self, name: str, obj) -> str:
        """
        Produce a human-readable failure reason for a component.

        Args:
            name: Component name.
            obj:  Component instance.

        Returns:
            str: Reason string for logging and UI display.
        """
        if obj is None:
            return "Object is None — not initialized"

        if name in ("autonomy", "autonomy_loop"):
            try:
                if not obj.isRunning():
                    return "QThread not running — may have crashed or never started"
                if obj.paused:
                    return "Thread running but paused (autonomous mode is OFF)"
            except Exception as e:
                return f"Cannot inspect QThread: {e}"

        if name == "brain":
            try:
                if obj.client is None:
                    return "No API client — API key missing or invalid"
                if not obj.is_configured():
                    return "Brain not configured — open Settings to set API key"
            except Exception as e:
                return f"Cannot inspect Brain: {e}"

        if name in ("task_manager", "tasks"):
            try:
                _ = obj.tasks  # Access the tasks attribute
            except Exception as e:
                return f"TaskManager.tasks not accessible: {e}"

        return "Component check returned False (unknown reason)"

    # ── Section 7: Public interface ──────────────────────────────────────────

    def get_status(self) -> dict:
        """
        Return current liveness status of all registered components.

        Returns:
            dict: {component_name: {"alive": bool, "last_ok": str, "failures": int}}
        """
        with self._lock:
            return {
                name: {
                    "alive":    info["failures"] == 0,
                    "last_ok":  info["last_ok"],
                    "failures": info["failures"],
                }
                for name, info in self._components.items()
            }

    def check_pulse(self) -> str:
        """
        Return a one-line status summary string.

        Returns:
            str: "✅ All N components alive." or "⚠ Dead: name1, name2"
        """
        status = self.get_status()
        if not status:
            return "No components registered."
        dead = [n for n, s in status.items() if not s["alive"]]
        if dead:
            return f"⚠ Unresponsive: {', '.join(dead)}"
        return f"✅ All {len(status)} components alive."
