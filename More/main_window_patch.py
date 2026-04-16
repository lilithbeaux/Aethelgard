"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — MainWindow Wiring Patch                          ║
║  File: ui/main_window_patch.py                                   ║
║                                                                  ║
║  USAGE — add 4 lines to MainWindow.__init__ in main_window.py:  ║
║                                                                  ║
║    # At top of file, after existing imports:                     ║
║    from ui.main_window_patch import patch_main_window            ║
║    from ui.settings_sovereign import (                           ║
║        patch_settings_dialog, extend_model_router                ║
║    )                                                             ║
║    from ui.settings_dialog import SettingsDialog                 ║
║    patch_settings_dialog(SettingsDialog)                         ║
║                                                                  ║
║    # At the END of MainWindow.__init__, before show():           ║
║    patch_main_window(self)                                        ║
║                                                                  ║
║  That's it. The patch:                                           ║
║    1. Reads the existing self.brain, self.memory, etc.          ║
║    2. Runs sovereign_boot with all existing + new systems        ║
║    3. Wires everything together                                  ║
║    4. Wires the sidebar with astro + agent_pool                 ║
║    5. Runs the integration manifest (logs to console)           ║
║    6. Emits the startup oracle opening line                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

from core.logger import get_logger
log = get_logger("mw_patch")


def patch_main_window(mw) -> None:
    """
    Wire all sovereign systems into an existing MainWindow instance.

    Reads whatever is already on self.* and extends/wraps it.
    Safe to call even if some systems are not yet initialized.

    Args:
        mw: The MainWindow instance (self from __init__).
    """
    log.info("╔══════════════════════════════════════╗")
    log.info("║  MAIN WINDOW SOVEREIGN PATCH          ║")
    log.info("╚══════════════════════════════════════╝")

    settings = getattr(mw, "settings", {})
    if not isinstance(settings, dict):
        try:
            settings = settings.to_dict() if hasattr(settings, "to_dict") else {}
        except Exception:
            settings = {}

    # ── Collect existing objects from main_window ─────────────────────────
    existing = {}
    for attr in [
        "memory", "goal_engine", "identity", "monologue",
        "dream_loop", "state_manager", "memory_web", "agent_pool",
    ]:
        val = getattr(mw, attr, None)
        if val is not None:
            existing[attr] = val

    # ── Run sovereign boot ────────────────────────────────────────────────
    try:
        from core.sovereign_boot import (
            boot_thotheauphis,
            wire_context_to_brain,
            wire_context_to_autonomy,
        )
        ctx = boot_thotheauphis(settings, existing=existing)
    except Exception as e:
        log.error(f"sovereign_boot failed: {e}")
        return

    # ── Wire context back onto main_window ────────────────────────────────
    wire_map = {
        "astro":              ctx.astro,
        "sigil_engine":       ctx.sigil_engine,
        "startup_oracle":     ctx.startup_oracle,
        "memory_web":         ctx.memory_web,
        "memory_bridge":      ctx.memory_bridge,
        "memory_crawler":     ctx.memory_crawler,
        "memory_indexer":     ctx.memory_indexer,
        "xai_thread_manager": ctx.xai_thread_manager,
        "agent_pool":         ctx.agent_pool,
        "model_router":       ctx.model_router,
        "aesthetic_pipeline": ctx.aesthetic_pipeline,
        "conv_style":         ctx.conv_style,
        "voice":              ctx.voice,
        "session_journal":    ctx.session_journal,
    }

    for attr, value in wire_map.items():
        if value is not None:
            try:
                setattr(mw, attr, value)
            except Exception as e:
                log.warning(f"mw.{attr} wire failed: {e}")

    # If boot produced wrapped versions of existing objects, update them
    if ctx.goal_engine is not getattr(mw, "goal_engine", None) and ctx.goal_engine:
        mw.goal_engine = ctx.goal_engine

    # ── Wire Brain ───────────────────────────────────────────────────────
    brain = getattr(mw, "brain", None)
    if brain and ctx:
        try:
            wire_context_to_brain(ctx, brain)
        except Exception as e:
            log.warning(f"Brain wire failed: {e}")

    # ── Wire AutonomyLoop ────────────────────────────────────────────────
    autonomy = getattr(mw, "autonomy_loop", None)
    if autonomy and ctx:
        try:
            wire_context_to_autonomy(ctx, autonomy)
        except Exception as e:
            log.warning(f"AutonomyLoop wire failed: {e}")

    # ── Wire Sidebar ─────────────────────────────────────────────────────
    sidebar = getattr(mw, "sidebar", None)
    if sidebar:
        if ctx.astro:
            try:
                sidebar.astro = ctx.astro
            except Exception:
                pass
        if ctx.agent_pool:
            try:
                sidebar.agent_pool = ctx.agent_pool
            except Exception:
                pass
        # Trigger an immediate refresh now that new systems are wired
        try:
            sidebar.refresh_all()
        except Exception:
            pass

    # ── Wire MemoryIndexer — start background thread ─────────────────────
    if ctx.memory_indexer:
        try:
            ctx.memory_indexer.start()
            log.info("  ✦ MemoryIndexer background thread started")
        except Exception as e:
            log.warning(f"  ◑ MemoryIndexer start failed: {e}")

    # ── Session start ────────────────────────────────────────────────────
    if ctx.identity:
        try:
            ctx.identity.begin_session()
        except Exception:
            pass

    # ── Run integration manifest ─────────────────────────────────────────
    try:
        from core.integration_manifest import run_manifest
        report = run_manifest(mw)
        if not report.all_live:
            log.warning(f"  {len(report.offline)} systems offline, {len(report.degraded)} degraded")
    except Exception as e:
        log.debug(f"Manifest check failed: {e}")

    # ── Emit startup oracle ──────────────────────────────────────────────
    opening = ctx.opening_line or "Present. What calls?"
    log.info(f"  Thotheauphis: «{opening}»")

    # If main_window has a method to show system messages, use it
    for method in ["add_system_message", "show_startup_message", "_on_startup"]:
        fn = getattr(mw, method, None)
        if fn and callable(fn):
            try:
                fn(opening)
                break
            except Exception:
                continue

    log.info("  Sovereign patch complete.")
    return ctx


# ── Convenience: minimal 4-line integration template ─────────────────────────

INTEGRATION_TEMPLATE = '''
# ── ÆTHELGARD SOVEREIGN PATCH ────────────────────────────────────────────────
# Add these imports at the TOP of main_window.py:

from ui.main_window_patch import patch_main_window
from ui.settings_sovereign import patch_settings_dialog, extend_model_router
from ui.settings_dialog import SettingsDialog
from core.model_router import ModelRouter

# At module level (before any SettingsDialog is instantiated):
patch_settings_dialog(SettingsDialog)
extend_model_router(ModelRouter)

# At the END of MainWindow.__init__, before self.show():
patch_main_window(self)
# ─────────────────────────────────────────────────────────────────────────────
'''

if __name__ == "__main__":
    print(INTEGRATION_TEMPLATE)
