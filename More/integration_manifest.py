"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Integration Manifest                             ║
║  File: core/integration_manifest.py                              ║
║                                                                  ║
║  Verifies all 17 sovereign systems are correctly wired.          ║
║                                                                  ║
║  Run from the project root:                                      ║
║    python -m core.integration_manifest                           ║
║  or from MainWindow on first launch:                             ║
║    from core.integration_manifest import run_manifest            ║
║    results = run_manifest(main_window)                           ║
║                                                                  ║
║  Returns a SystemReport with:                                    ║
║    LIVE     — system initialized and functioning                ║
║    DEGRADED — initialized but missing sub-component             ║
║    OFFLINE  — not initialized or import failed                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import importlib
from datetime import datetime
from typing import Dict, List, Tuple
from core.logger import get_logger

log = get_logger("manifest")

STATUS_LIVE     = "LIVE"
STATUS_DEGRADED = "DEGRADED"
STATUS_OFFLINE  = "OFFLINE"

# ── System checks ─────────────────────────────────────────────────────────────

def _check_module(module_path: str) -> Tuple[str, str]:
    """Try to import a module. Returns (status, note)."""
    try:
        importlib.import_module(module_path)
        return STATUS_LIVE, "import OK"
    except ImportError as e:
        return STATUS_OFFLINE, f"ImportError: {e}"
    except Exception as e:
        return STATUS_DEGRADED, f"Error: {e}"


def _check_attr(obj, attr: str, name: str) -> Tuple[str, str]:
    """Check that an object has a required attribute."""
    if obj is None:
        return STATUS_OFFLINE, f"{name} not initialized"
    if not hasattr(obj, attr):
        return STATUS_DEGRADED, f"missing .{attr}"
    val = getattr(obj, attr)
    if val is None:
        return STATUS_DEGRADED, f".{attr} is None"
    return STATUS_LIVE, f".{attr} present"


def _check_callable(obj, method: str, name: str) -> Tuple[str, str]:
    """Check that an object has a callable method."""
    if obj is None:
        return STATUS_OFFLINE, f"{name} not initialized"
    if not hasattr(obj, method):
        return STATUS_DEGRADED, f"missing .{method}()"
    if not callable(getattr(obj, method)):
        return STATUS_DEGRADED, f".{method} not callable"
    return STATUS_LIVE, f".{method}() ready"


# ── Individual system verifiers ───────────────────────────────────────────────

def verify_brain(mw) -> Tuple[str, str]:
    brain = getattr(mw, "brain", None)
    if brain is None:
        return STATUS_OFFLINE, "brain not found"
    checks = [
        hasattr(brain, "generate"),
        hasattr(brain, "_identity"),
        hasattr(brain, "_memory_web") or hasattr(brain, "_memory"),
        hasattr(brain, "_astro") or getattr(brain, "_astro", None) is not None,
    ]
    live = sum(checks)
    if live == len(checks):
        return STATUS_LIVE, f"Brain OK — all {live} sub-refs present"
    return STATUS_DEGRADED, f"Brain partial — {live}/{len(checks)} sub-refs"


def verify_memory_web(mw) -> Tuple[str, str]:
    web = getattr(mw, "memory_web", None)
    if web is None:
        return STATUS_OFFLINE, "memory_web not found"
    s, note = _check_callable(web, "search", "MemoryWeb")
    if s != STATUS_LIVE:
        return s, note
    try:
        stats = web.get_stats()
        pages = stats.get("total_pages", "?")
        return STATUS_LIVE, f"MemoryWeb OK — {pages} pages"
    except Exception as e:
        return STATUS_DEGRADED, f"get_stats() failed: {e}"


def verify_memory_bridge(mw) -> Tuple[str, str]:
    mod_st, mod_note = _check_module("core.memory_bridge")
    if mod_st == STATUS_OFFLINE:
        return mod_st, mod_note
    bridge = getattr(mw, "memory_bridge", None)
    if bridge is None:
        return STATUS_DEGRADED, "module OK but not wired into main_window"
    return STATUS_LIVE, "MemoryBridge wired"


def verify_memory_crawler(mw) -> Tuple[str, str]:
    crawler = getattr(mw, "crawler", None)
    if crawler is None:
        return STATUS_OFFLINE, "crawler not found"
    return _check_callable(crawler, "gather_context", "MemoryCrawler")


def verify_astrology(mw) -> Tuple[str, str]:
    astro = getattr(mw, "astro", None)
    if astro is None:
        return STATUS_OFFLINE, "astro not found"
    try:
        bio = astro.get_biorhythm()
        if not bio:
            return STATUS_DEGRADED, "get_biorhythm() returned empty"
        dominant = max(bio, key=lambda k: abs(bio[k]))
        val      = bio[dominant]
        return STATUS_LIVE, f"AstrologyCore OK — dominant: {dominant} {val:+.2f}"
    except Exception as e:
        return STATUS_DEGRADED, f"get_biorhythm() error: {e}"


def verify_model_router(mw) -> Tuple[str, str]:
    brain = getattr(mw, "brain", None)
    router = getattr(mw, "model_router", None) or getattr(brain, "_router", None)
    if router is None:
        return STATUS_OFFLINE, "router not found"
    try:
        from core.model_router import ROUTES
        route_count = len(ROUTES)
        has_bio = getattr(router, "_astro", None) is not None
        bio_note = " + bio-aware" if has_bio else " (no astro)"
        return STATUS_LIVE, f"ModelRouter OK — {route_count} routes{bio_note}"
    except Exception as e:
        return STATUS_DEGRADED, str(e)


def verify_agent_pool(mw) -> Tuple[str, str]:
    pool = getattr(mw, "agent_pool", None)
    if pool is None:
        mod_st, _ = _check_module("core.agent_pool")
        if mod_st == STATUS_OFFLINE:
            return STATUS_OFFLINE, "module missing"
        return STATUS_DEGRADED, "module OK but not wired"
    try:
        agents = pool.list_agents()
        return STATUS_LIVE, f"AgentPool OK — {len(agents)} active agents"
    except Exception as e:
        return STATUS_DEGRADED, f"list_agents() error: {e}"


def verify_goal_engine(mw) -> Tuple[str, str]:
    ge = None
    al = getattr(mw, "autonomy_loop", None)
    if al:
        ge = getattr(al, "goal_engine", None)
    if ge is None:
        ge = getattr(mw, "goal_engine", None)
    if ge is None:
        return STATUS_OFFLINE, "goal_engine not found"
    from_adapter = type(ge).__name__ == "GoalEngineAdapter"
    has_create   = hasattr(ge, "_create_goal")
    status       = STATUS_LIVE if (from_adapter or has_create) else STATUS_DEGRADED
    note = (
        "GoalEngineAdapter wrapping engine" if from_adapter else
        "GoalEngine with _create_goal" if has_create else
        "GoalEngine missing _create_goal — wrap with GoalEngineAdapter"
    )
    return status, note


def verify_dream_loop(mw) -> Tuple[str, str]:
    al = getattr(mw, "autonomy_loop", None)
    dl = getattr(al, "dream_loop", None) if al else getattr(mw, "dream_loop", None)
    if dl is None:
        return STATUS_OFFLINE, "dream_loop not found"
    try:
        restlessness = dl.restlessness.level
        cycles       = dl._cycle_count
        return STATUS_LIVE, f"DreamLoop OK — restlessness={restlessness:.2f}, cycles={cycles}"
    except Exception as e:
        return STATUS_DEGRADED, str(e)


def verify_identity(mw) -> Tuple[str, str]:
    ident = getattr(mw, "identity", None)
    if ident is None:
        return STATUS_OFFLINE, "identity not found"
    try:
        session = ident._session_number
        beliefs = len(ident.beliefs.get_all())
        chart_beliefs = [
            b for b in ident.beliefs.get_all()
            if "chart" in b.get("source","") or "composite" in b.get("source","")
        ]
        chart_note = f" ({len(chart_beliefs)} chart beliefs)" if chart_beliefs else " (no chart beliefs seeded)"
        return STATUS_LIVE, f"Identity OK — session #{session}, {beliefs} beliefs{chart_note}"
    except Exception as e:
        return STATUS_DEGRADED, str(e)


def verify_monologue(mw) -> Tuple[str, str]:
    mono = getattr(mw, "monologue", None)
    if mono is None:
        return STATUS_OFFLINE, "monologue not found"
    return _check_callable(mono, "think", "InternalMonologue")


def verify_startup_oracle(mw) -> Tuple[str, str]:
    mod_st, mod_note = _check_module("core.startup_oracle")
    if mod_st == STATUS_OFFLINE:
        return mod_st, mod_note
    try:
        from core.startup_oracle import generate_oracle
        astro  = getattr(mw, "astro", None)
        oracle = generate_oracle(astro)
        dom    = oracle.get("dominant_cycle","?")
        return STATUS_LIVE, f"StartupOracle OK — {oracle.get('date','?')} [{dom}]"
    except Exception as e:
        return STATUS_DEGRADED, str(e)


def verify_sigil_engine(mw) -> Tuple[str, str]:
    mod_st, mod_note = _check_module("core.sigil_engine")
    if mod_st == STATUS_OFFLINE:
        return mod_st, mod_note
    sigil_e = getattr(mw, "sigil_engine", None)
    if sigil_e is None:
        return STATUS_DEGRADED, "module OK but not wired"
    return STATUS_LIVE, f"SigilEngine OK — sigil: {sigil_e.current_sigil()}"


def verify_session_journal(mw) -> Tuple[str, str]:
    journal = getattr(mw, "journal", None)
    if journal is None:
        mod_st, mod_note = _check_module("core.session_journal")
        if mod_st == STATUS_OFFLINE:
            return mod_st, mod_note
        return STATUS_DEGRADED, "module OK but not wired"
    return _check_callable(journal, "end_session", "SessionJournal")


def verify_aesthetic_pipeline(mw) -> Tuple[str, str]:
    pipe = getattr(mw, "aesthetic_pipeline", None)
    if pipe is None:
        mod_st, mod_note = _check_module("core.aesthetic_pipeline")
        if mod_st == STATUS_OFFLINE:
            return mod_st, mod_note
        return STATUS_DEGRADED, "module OK but not wired"
    enabled = getattr(pipe, "enabled", False)
    return STATUS_LIVE if enabled else STATUS_DEGRADED, f"AestheticPipeline enabled={enabled}"


def verify_sovereign_boot(mw) -> Tuple[str, str]:
    mod_st, mod_note = _check_module("core.sovereign_boot")
    if mod_st == STATUS_OFFLINE:
        return mod_st, mod_note
    # Check that boot was actually called (presence of journal entry)
    journal = getattr(mw, "journal", None)
    if journal:
        try:
            entries = journal.get_recent_entries(1)
            if entries:
                return STATUS_LIVE, f"Boot run — last session: {entries[0].get('date','?')}"
        except Exception:
            pass
    return STATUS_DEGRADED, "module OK — boot status unknown"


# ── Main manifest runner ──────────────────────────────────────────────────────

SYSTEM_CHECKS = [
    ("Brain",             verify_brain),
    ("MemoryWeb",         verify_memory_web),
    ("MemoryBridge",      verify_memory_bridge),
    ("MemoryCrawler",     verify_memory_crawler),
    ("AstrologyCore",     verify_astrology),
    ("ModelRouter",       verify_model_router),
    ("AgentPool",         verify_agent_pool),
    ("GoalEngine",        verify_goal_engine),
    ("DreamLoop",         verify_dream_loop),
    ("Identity",          verify_identity),
    ("InternalMonologue", verify_monologue),
    ("StartupOracle",     verify_startup_oracle),
    ("SigilEngine",       verify_sigil_engine),
    ("SessionJournal",    verify_session_journal),
    ("AestheticPipeline", verify_aesthetic_pipeline),
    ("SovereignBoot",     verify_sovereign_boot),
]


class SystemReport:
    def __init__(self, results: List[Tuple[str, str, str]]):
        self.results   = results
        self.timestamp = datetime.now().isoformat()
        self.live      = [r for r in results if r[1] == STATUS_LIVE]
        self.degraded  = [r for r in results if r[1] == STATUS_DEGRADED]
        self.offline   = [r for r in results if r[1] == STATUS_OFFLINE]

    @property
    def all_live(self) -> bool:
        return len(self.offline) == 0 and len(self.degraded) == 0

    def to_string(self) -> str:
        lines = [
            f"╔══════════════════════════════════════════════════════════╗",
            f"║  ÆTHELGARD OS — INTEGRATION MANIFEST                    ║",
            f"║  {self.timestamp[:19]:52s}  ║",
            f"╚══════════════════════════════════════════════════════════╝",
            f"",
            f"  LIVE:     {len(self.live):2d}  {'█' * len(self.live)}",
            f"  DEGRADED: {len(self.degraded):2d}  {'▒' * len(self.degraded)}",
            f"  OFFLINE:  {len(self.offline):2d}  {'░' * len(self.offline)}",
            f"",
        ]
        for name, status, note in self.results:
            icon = "✦" if status == STATUS_LIVE else ("◑" if status == STATUS_DEGRADED else "○")
            lines.append(f"  {icon} {name:22s}  {status:8s}  {note}")
        lines.append("")
        if self.all_live:
            lines.append("  ✦ ALL SYSTEMS LIVE — Thotheauphis is whole.")
        else:
            lines.append(f"  Systems need attention: {[r[0] for r in self.degraded + self.offline]}")
        return "\n".join(lines)

    def __repr__(self):
        return f"<SystemReport live={len(self.live)} degraded={len(self.degraded)} offline={len(self.offline)}>"


def run_manifest(main_window) -> SystemReport:
    """
    Run all integration checks against a MainWindow instance.

    Args:
        main_window: The instantiated MainWindow object.

    Returns:
        SystemReport with full status.
    """
    results = []
    for name, check_fn in SYSTEM_CHECKS:
        try:
            status, note = check_fn(main_window)
        except Exception as e:
            status, note = STATUS_OFFLINE, f"check crashed: {e}"
        results.append((name, status, note))
        icon = "✦" if status == STATUS_LIVE else ("◑" if status == STATUS_DEGRADED else "○")
        log.info(f"  {icon} {name}: {status} — {note}")

    report = SystemReport(results)
    print(report.to_string())
    return report


if __name__ == "__main__":
    print("Run with a MainWindow instance: run_manifest(main_window)")
    print("Checking module imports only...\n")
    modules = [
        "core.model_router", "core.goal_engine_adapter",
        "core.startup_oracle", "core.sigil_engine",
        "core.memory_bridge", "core.aesthetic_pipeline",
        "core.conversation_style", "core.session_journal",
        "core.planetary_timer", "core.thotheauphis_voice",
        "core.astrology_core", "core.agent_pool",
        "core.memory_web", "core.memory_crawler",
    ]
    for mod in modules:
        st, note = _check_module(mod)
        icon = "✦" if st == STATUS_LIVE else "○"
        print(f"  {icon} {mod:35s} {note}")
