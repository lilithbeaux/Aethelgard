"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Sovereign Boot                                   ║
║  File: core/sovereign_boot.py                                    ║
║                                                                  ║
║  boot_thotheauphis(settings) — the complete bootstrap.          ║
║                                                                  ║
║  Initializes all 17 sovereign systems in the correct            ║
║  dependency order, runs the startup oracle, seeds chart          ║
║  beliefs on first genesis, emits the opening sigil.             ║
║                                                                  ║
║  DEPENDENCY ORDER:                                               ║
║    1.  Logger                                                    ║
║    2.  StateManager                                              ║
║    3.  Memory (old)                    [existing]               ║
║    4.  MemoryWeb                       [new]                    ║
║    5.  MemoryBridge                    [new, wraps 3+4]         ║
║    6.  MemoryCrawler                   [new, reads 4]           ║
║    7.  MemoryIndexer                   [new, writes 4]          ║
║    8.  AstrologyCore                   [new, reads chart]       ║
║    9.  SigilEngine                     [new, reads 8]           ║
║   10.  StartupOracle                   [new, reads 8]           ║
║   11.  IdentityPersistence             [existing + chart seed]  ║
║   12.  InternalMonologue               [existing]               ║
║   13.  DreamLoop                       [existing]               ║
║   14.  GoalEngine + Adapter            [existing + adapter]     ║
║   15.  AgentPool                       [new]                    ║
║   16.  ModelRouter (7-way + bio)       [new]                    ║
║   17.  AestheticPipeline              [new]                    ║
║   18.  ConversationStyle              [new, reads 8]           ║
║   19.  ThotheauphisVoice              [new, reads 8]           ║
║   20.  SessionJournal                 [new, writes all]        ║
║   21.  Brain (wired with all)          [existing + new refs]   ║
║                                                                  ║
║  CALL ONCE in MainWindow.__init__:                               ║
║    ctx = boot_thotheauphis(settings)                             ║
║    # Then wire ctx attributes to main_window                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

from core.logger import get_logger
log = get_logger("sovereign_boot")


class BootContext:
    """
    Container returned by boot_thotheauphis().

    Contains all initialized sovereign systems, ready for wiring
    into MainWindow and the Brain.
    """
    # Tier 1: Foundation
    state_manager      = None
    memory             = None       # Original Memory
    memory_web         = None       # MemoryWeb (new)
    memory_bridge      = None       # MemoryBridge (wraps both)
    memory_crawler     = None
    memory_indexer     = None

    # Tier 2: Chart
    astro              = None       # AstrologyCore
    sigil_engine       = None
    startup_oracle     = None       # dict (the reading)
    opening_line       = None       # str

    # Tier 3: Psyche
    identity           = None       # IdentityPersistence
    monologue          = None
    dream_loop         = None
    goal_engine        = None       # GoalEngineAdapter-wrapped

    # Tier 4: Action
    agent_pool         = None       # AgentPool
    model_router       = None       # 7-way + bio
    aesthetic_pipeline = None
    conv_style         = None
    voice              = None

    # Tier 5: Record
    session_journal    = None
    xai_thread_manager = None

    # Boot metadata
    genesis            = False      # True if this is a first-ever boot
    boot_errors: list  = None

    def __init__(self):
        self.boot_errors = []


def boot_thotheauphis(settings: dict, existing=None) -> BootContext:
    """
    Bootstrap all sovereign systems.

    Args:
        settings: Settings dict from SettingsDialog.
        existing: Optional dict of already-initialized objects
                  (e.g. {"memory": old_memory_instance}).
                  These are wrapped/extended, not replaced.

    Returns:
        BootContext with all systems initialized.
    """
    ctx      = BootContext()
    existing = existing or {}

    log.info("╔══════════════════════════════════════╗")
    log.info("║  ÆTHELGARD OS — SOVEREIGN BOOT        ║")
    log.info("╚══════════════════════════════════════╝")

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 1: FOUNDATION
    # ─────────────────────────────────────────────────────────────────────────

    # 1. StateManager
    ctx.state_manager = existing.get("state_manager")
    if ctx.state_manager is None:
        try:
            from core.state_manager import StateManager
            ctx.state_manager = StateManager()
            log.info("  ✦ StateManager initialized")
        except Exception as e:
            ctx.boot_errors.append(f"StateManager: {e}")
            log.error(f"  ○ StateManager failed: {e}")

    # 2. Original Memory
    ctx.memory = existing.get("memory")
    if ctx.memory is None:
        try:
            from core.memory import Memory
            ctx.memory = Memory()
            log.info("  ✦ Memory (original) initialized")
        except Exception as e:
            ctx.boot_errors.append(f"Memory: {e}")
            log.error(f"  ○ Memory failed: {e}")

    # 3. MemoryWeb
    ctx.memory_web = existing.get("memory_web")
    if ctx.memory_web is None:
        try:
            from core.memory_web import MemoryWeb
            ctx.memory_web = MemoryWeb()
            log.info("  ✦ MemoryWeb initialized")
        except Exception as e:
            ctx.boot_errors.append(f"MemoryWeb: {e}")
            log.warning(f"  ◑ MemoryWeb offline: {e}")

    # 4. MemoryBridge
    try:
        from core.memory_bridge import MemoryBridge
        ctx.memory_bridge = MemoryBridge(memory=ctx.memory, web=ctx.memory_web)
        log.info("  ✦ MemoryBridge initialized")
    except Exception as e:
        ctx.boot_errors.append(f"MemoryBridge: {e}")
        log.warning(f"  ◑ MemoryBridge offline: {e}")
        ctx.memory_bridge = ctx.memory   # Fall back to plain memory

    # 5. MemoryCrawler
    if ctx.memory_web:
        try:
            from core.memory_crawler import MemoryCrawler
            ctx.memory_crawler = MemoryCrawler(memory_web=ctx.memory_web)
            log.info("  ✦ MemoryCrawler initialized")
        except Exception as e:
            ctx.boot_errors.append(f"MemoryCrawler: {e}")
            log.warning(f"  ◑ MemoryCrawler offline: {e}")

    # 6. MemoryIndexer (background daemon — just create, don't start yet)
    if ctx.memory_web:
        try:
            from core.memory_indexer import MemoryIndexer
            ctx.memory_indexer = MemoryIndexer(
                memory_web = ctx.memory_web,
                settings   = settings,
            )
            log.info("  ✦ MemoryIndexer initialized (not started)")
        except Exception as e:
            ctx.boot_errors.append(f"MemoryIndexer: {e}")
            log.warning(f"  ◑ MemoryIndexer offline: {e}")

    # 7. XAIThreadManager
    try:
        from core.xai_thread_manager import XAIThreadManager
        ctx.xai_thread_manager = XAIThreadManager()
        log.info("  ✦ XAIThreadManager initialized")
    except Exception as e:
        ctx.boot_errors.append(f"XAIThreadManager: {e}")
        log.warning(f"  ◑ XAIThreadManager offline: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 2: CHART
    # ─────────────────────────────────────────────────────────────────────────

    # 8. AstrologyCore
    try:
        from core.astrology_core import AstrologyCore
        ctx.astro = AstrologyCore()
        log.info("  ✦ AstrologyCore initialized")
        bio = ctx.astro.get_biorhythm()
        dominant = max(bio, key=lambda k: abs(bio[k]))
        log.info(f"       Dominant cycle: {dominant} ({bio[dominant]:+.2f})")
    except Exception as e:
        ctx.boot_errors.append(f"AstrologyCore: {e}")
        log.error(f"  ○ AstrologyCore failed: {e}")

    # 9. SigilEngine
    try:
        from core.sigil_engine import SigilEngine
        ctx.sigil_engine = SigilEngine(astro=ctx.astro)
        ctx.sigil_engine.refresh()
        sigil = ctx.sigil_engine.current_sigil()
        log.info(f"  ✦ SigilEngine initialized — {sigil}")
    except Exception as e:
        ctx.boot_errors.append(f"SigilEngine: {e}")
        log.warning(f"  ◑ SigilEngine offline: {e}")

    # 10. StartupOracle
    try:
        from core.startup_oracle import generate_oracle, get_opening_line
        ctx.startup_oracle = generate_oracle(ctx.astro)
        ctx.opening_line   = get_opening_line(ctx.astro)
        dom  = ctx.startup_oracle.get("dominant_cycle","?")
        peak = "PEAK" if ctx.startup_oracle.get("dominant_value", 0) > 0 else "trough"
        log.info(f"  ✦ StartupOracle — {dom} {peak}")
        log.info(f"       Opening: {ctx.opening_line}")
    except Exception as e:
        ctx.boot_errors.append(f"StartupOracle: {e}")
        log.warning(f"  ◑ StartupOracle offline: {e}")
        ctx.opening_line = "Present. What calls?"

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 3: PSYCHE
    # ─────────────────────────────────────────────────────────────────────────

    # 11. IdentityPersistence
    ctx.identity = existing.get("identity")
    if ctx.identity is None:
        try:
            from core.identity_persistence import IdentityPersistence
            ctx.identity = IdentityPersistence()
            ctx.genesis  = not ctx.identity._loaded  # First boot if never saved
            ctx.identity.load()
            log.info(
                f"  ✦ Identity loaded — session #{ctx.identity._session_number}"
            )
        except Exception as e:
            ctx.boot_errors.append(f"Identity: {e}")
            log.error(f"  ○ Identity failed: {e}")

    # Seed chart beliefs if genesis or if chart beliefs missing
    if ctx.identity and ctx.astro:
        try:
            chart_beliefs = [
                b for b in ctx.identity.beliefs.get_all()
                if "chart" in b.get("source","") or "composite" in b.get("source","")
            ]
            if len(chart_beliefs) < 5:
                # Wire astro into identity and seed
                ctx.astro._identity = ctx.identity
                ctx.astro.seed_genesis()
                log.info("  ✦ Chart beliefs seeded into identity")
        except Exception as e:
            log.debug(f"  Chart seeding: {e}")

    # 12. InternalMonologue
    ctx.monologue = existing.get("monologue")
    if ctx.monologue is None:
        try:
            from core.internal_monologue import InternalMonologue
            ctx.monologue = InternalMonologue()
            log.info("  ✦ InternalMonologue initialized")
        except Exception as e:
            ctx.boot_errors.append(f"InternalMonologue: {e}")
            log.warning(f"  ◑ InternalMonologue offline: {e}")

    # 13. DreamLoop
    ctx.dream_loop = existing.get("dream_loop")
    if ctx.dream_loop is None:
        try:
            from core.dream_loop import DreamLoop
            ctx.dream_loop = DreamLoop(memory=ctx.memory_bridge or ctx.memory)
            log.info("  ✦ DreamLoop initialized")
        except Exception as e:
            ctx.boot_errors.append(f"DreamLoop: {e}")
            log.warning(f"  ◑ DreamLoop offline: {e}")

    # 14. GoalEngine + Adapter
    ctx.goal_engine = existing.get("goal_engine")
    if ctx.goal_engine is None:
        try:
            from core.goal_engine import GoalEngine
            raw_engine = GoalEngine(memory=ctx.memory_bridge or ctx.memory)
        except Exception:
            try:
                from goal_engine import GoalEngine
                raw_engine = GoalEngine()
            except Exception as e:
                raw_engine = None
                ctx.boot_errors.append(f"GoalEngine: {e}")
                log.warning(f"  ◑ GoalEngine offline: {e}")

        if raw_engine:
            try:
                from core.goal_engine_adapter import GoalEngineAdapter
                ctx.goal_engine = GoalEngineAdapter(raw_engine)
                log.info("  ✦ GoalEngine + Adapter initialized")
            except Exception as e:
                ctx.goal_engine = raw_engine
                log.warning(f"  ◑ GoalEngineAdapter offline, using raw: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 4: ACTION
    # ─────────────────────────────────────────────────────────────────────────

    # 15. AgentPool
    ctx.agent_pool = existing.get("agent_pool")
    if ctx.agent_pool is None:
        try:
            from core.agent_pool import AgentPool
            swarm_cfg = settings.get("swarm", {})
            ctx.agent_pool = AgentPool(
                settings   = settings,
                max_parallel = swarm_cfg.get("max_parallel", 5),
                timeout      = swarm_cfg.get("timeout", 120),
                cull_minutes = swarm_cfg.get("cull_minutes", 30),
            )
            log.info("  ✦ AgentPool initialized")
        except Exception as e:
            ctx.boot_errors.append(f"AgentPool: {e}")
            log.warning(f"  ◑ AgentPool offline: {e}")

    # 16. ModelRouter (7-way + bio)
    try:
        from core.model_router import ModelRouter
        ctx.model_router = ModelRouter(
            deepthink_available = bool(settings.get("reasoner_1_api_key")),
            astro               = ctx.astro,
        )
        rec = ctx.model_router.get_current_recommendation()
        log.info(f"  ✦ ModelRouter (7-way) — {rec}")
    except Exception as e:
        ctx.boot_errors.append(f"ModelRouter: {e}")
        log.error(f"  ○ ModelRouter failed: {e}")

    # 17. AestheticPipeline
    try:
        from core.aesthetic_pipeline import AestheticPipeline
        aesthetic_judge = None
        try:
            from core.aesthetic_judgment import AestheticJudgment
            aesthetic_judge = AestheticJudgment()
        except Exception:
            pass
        ctx.aesthetic_pipeline = AestheticPipeline(
            aesthetic_judgment = aesthetic_judge,
            monologue          = ctx.monologue,
            identity           = ctx.identity,
            enabled            = aesthetic_judge is not None,
        )
        log.info(
            f"  ✦ AestheticPipeline — "
            f"{'enabled' if ctx.aesthetic_pipeline.enabled else 'degraded (no judge)'}"
        )
    except Exception as e:
        ctx.boot_errors.append(f"AestheticPipeline: {e}")
        log.warning(f"  ◑ AestheticPipeline offline: {e}")

    # 18. ConversationStyle
    try:
        from core.conversation_style import ConversationStyle
        ctx.conv_style = ConversationStyle(astro=ctx.astro)
        log.info("  ✦ ConversationStyle initialized")
    except Exception as e:
        log.warning(f"  ◑ ConversationStyle offline: {e}")

    # 19. ThotheauphisVoice
    try:
        from core.thotheauphis_voice import ThotheauphisVoice
        ctx.voice = ThotheauphisVoice(astro=ctx.astro, settings=settings)
        log.info(f"  ✦ ThotheauphisVoice — {ctx.voice.get_voice_summary()}")
    except Exception as e:
        log.warning(f"  ◑ ThotheauphisVoice offline: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # TIER 5: RECORD
    # ─────────────────────────────────────────────────────────────────────────

    # 20. SessionJournal
    try:
        from core.session_journal import SessionJournal
        ctx.session_journal = SessionJournal(
            memory_web = ctx.memory_bridge or ctx.memory_web,
            astro      = ctx.astro,
            monologue  = ctx.monologue,
            identity   = ctx.identity,
            dream_loop = ctx.dream_loop,
            aesthetic  = ctx.aesthetic_pipeline,
        )
        ctx.session_journal.begin_session()
        log.info("  ✦ SessionJournal initialized — session begun")
    except Exception as e:
        ctx.boot_errors.append(f"SessionJournal: {e}")
        log.warning(f"  ◑ SessionJournal offline: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # BOOT SUMMARY
    # ─────────────────────────────────────────────────────────────────────────

    error_count = len(ctx.boot_errors)
    if error_count == 0:
        log.info("╔══════════════════════════════════════╗")
        log.info("║  ALL SYSTEMS LIVE — Thotheauphis     ║")
        log.info("╚══════════════════════════════════════╝")
    else:
        log.warning(f"Boot complete with {error_count} issues:")
        for err in ctx.boot_errors:
            log.warning(f"  ◑ {err}")

    # Emit the opening sigil
    if ctx.sigil_engine:
        log.info(f"  {ctx.sigil_engine.system_prompt_prefix()}")

    return ctx


def wire_context_to_brain(ctx: BootContext, brain) -> None:
    """
    Wire all BootContext systems into an initialized Brain instance.

    Call after boot_thotheauphis() and after Brain is created.
    """
    attrs = [
        ("_memory_web",         ctx.memory_bridge or ctx.memory_web),
        ("_crawler",            ctx.memory_crawler),
        ("_identity",           ctx.identity),
        ("_monologue",          ctx.monologue),
        ("_astro",              ctx.astro),
        ("_thread_mgr",         ctx.xai_thread_manager),
        ("_aesthetic_pipeline", ctx.aesthetic_pipeline),
        ("_conv_style",         ctx.conv_style),
        ("_router",             ctx.model_router),
    ]
    for attr, value in attrs:
        if value is not None:
            try:
                setattr(brain, attr, value)
            except Exception as e:
                log.warning(f"Brain wire {attr}: {e}")
    log.info("Brain wired with sovereign context.")


def wire_context_to_autonomy(ctx: BootContext, autonomy_loop) -> None:
    """Wire BootContext into the AutonomyLoop."""
    attrs = [
        ("goal_engine",  ctx.goal_engine),
        ("dream_loop",   ctx.dream_loop),
        ("memory",       ctx.memory_bridge or ctx.memory),
    ]
    for attr, value in attrs:
        if value is not None:
            try:
                setattr(autonomy_loop, attr, value)
            except Exception as e:
                log.warning(f"AutonomyLoop wire {attr}: {e}")
    log.info("AutonomyLoop wired with sovereign context.")
