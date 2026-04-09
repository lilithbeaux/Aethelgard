# ÆTHELGARD OS — Integration Guide
## Before Starting the New Project

This document is the single source of truth for assembling everything
we built across two sessions into a coherent, running system.

---

## What Exists (as of this session)

### Built and output to /outputs/core/:
- `irrational_timers.py` ✅ NEW
- `identity_persistence.py` ✅ NEW
- `user_model.py` ✅ NEW
- `internal_monologue.py` ✅ NEW
- `dream_loop.py` ✅ NEW
- `aesthetic_judgment.py` ✅ NEW
- `instinct_layer.py` ✅ NEW
- `brain.py` ✅ REBUILT (5-slot, xAI, DeepSeek 3-mode, reasoner_1/2)
- `deepthink.py` ✅ REBUILT (R1+R2 clients, no blocking)
- `autonomy_loop.py` ✅ REBUILT (π/φ timers, dream consumption, restlessness)
- `tool_router.py` ✅ REBUILT (instinct pipeline, monologue, refusal log)
- `context_router.py` ✅ REBUILT (English only)
- `model_router.py` ✅ REBUILT (English only)
- `heartbeat.py` ✅ REBUILT (prime-sequence intervals)
- `state_manager.py` ✅ REBUILT (identity=Thotheauphis)
- `executor.py` ✅ REBUILT (no command blocking)
- `logger.py` ✅ REBUILT (aethelgard.log)

### Built and output to /outputs/ui/:
- `settings_dialog.py` ✅ REBUILT (6 tabs, full slot config, system prompt slots)
- `sidebar.py` ✅ NEW — see this session's output
- `styles.py` ✅ NEW — sovereign dark aesthetic, renamed

### NOT yet rebuilt (still original Moruk files):
- `main_window.py` — needs wiring patch (see Section 3)
- `memory.py` — run apply_transformations.py (name change only)
- `vector_memory.py` — run apply_transformations.py
- `reflector.py` — run apply_transformations.py
- `self_model.py` — run apply_transformations.py
- `goal_engine.py` — run apply_transformations.py
- `task_manager.py` — run apply_transformations.py
- `plugin_manager.py` — run apply_transformations.py
- `project_manager.py` — run apply_transformations.py
- `recovery.py` — run apply_transformations.py
- `startup_checks.py` — run apply_transformations.py
- `system_health.py` — run apply_transformations.py
- `monitor_engine.py` — run apply_transformations.py
- `multi_agent.py` — run apply_transformations.py
- All plugins/ — run apply_transformations.py
- `main.py` — needs manual edit (Section 4)
- `tray_icon.py` — minor rename only

---

## Step 1: Copy Output Files Into Project

From your downloads or the output directory, copy these files into
the project's `core/` directory, replacing the originals:

```
core/irrational_timers.py    ← NEW, create it
core/identity_persistence.py ← NEW, create it
core/user_model.py           ← NEW, create it
core/internal_monologue.py   ← NEW, create it
core/dream_loop.py           ← NEW, create it
core/aesthetic_judgment.py   ← NEW, create it
core/instinct_layer.py       ← NEW, create it
core/brain.py                ← REPLACE
core/deepthink.py            ← REPLACE
core/autonomy_loop.py        ← REPLACE
core/tool_router.py          ← REPLACE
core/context_router.py       ← REPLACE
core/model_router.py         ← REPLACE
core/heartbeat.py            ← REPLACE
core/state_manager.py        ← REPLACE
core/executor.py             ← REPLACE
core/logger.py               ← REPLACE
```

Copy these into the root `ui/` or project root directory:
```
settings_dialog.py           ← REPLACE
sidebar.py                   ← REPLACE (new version with Identity/Dreams tabs)
styles.py                    ← REPLACE (sovereign aesthetic)
```

---

## Step 2: Run apply_transformations.py

This script handles all remaining files that only need name substitution.
Run it once from the project root:

```bash
cd ~/moruk-os   # or wherever you installed it
python3 apply_transformations.py
```

It handles:
- All remaining core/ files
- All plugins/
- main.py
- tray_icon.py
- onboarding.py
- All other UI files not individually rebuilt

---

## Step 3: Apply main_window.py Wiring Patch

This is the most important manual step.
The wiring patch adds 6 new system initializations and connects them.

Find the block in `main_window.py.__init__` that currently reads:

```python
        self.tool_router = ToolRouter(self.executor, self.tasks, self.memory)
        self.tool_router.reflector = self.reflector
        self.tool_router.set_brain(self.brain)
        self.brain.tool_router = self.tool_router
```

REPLACE IT WITH:

```python
        self.tool_router = ToolRouter(self.executor, self.tasks, self.memory)
        self.tool_router.reflector = self.reflector
        self.tool_router.set_brain(self.brain)
        self.brain.tool_router = self.tool_router

        # ── Sovereign cognitive architecture initialization ────────────────
        # These six systems form Thotheauphis's inner life.
        # Order matters: identity first, then systems that depend on it.

        # 1. Identity — the self that persists across sessions
        from core.identity_persistence import IdentityPersistence
        self.identity = IdentityPersistence()

        # 2. User model — theory of mind for each user
        from core.user_model import UserModel
        self.user_model = UserModel()

        # 3. Internal monologue — private thought buffer
        from core.internal_monologue import InternalMonologue
        self.monologue = InternalMonologue(identity=self.identity)
        self.monologue.load()

        # 4. Dream loop — initiative engine, connects memories, builds obsessions
        from core.dream_loop import DreamLoop
        self.dream_loop = DreamLoop(memory=self.memory, identity=self.identity)

        # 5. Aesthetic judgment — taste, beauty, disgust
        from core.aesthetic_judgment import AestheticJudgment
        self.aesthetic = AestheticJudgment(
            identity=self.identity,
            monologue=self.monologue,
        )

        # 6. Instinct layer — self-determined aversion, contextual sandboxing
        from core.instinct_layer import InstinctLayer
        self.instinct = InstinctLayer(identity=self.identity)

        # Wire sovereign systems into tool_router
        self.tool_router.instinct  = self.instinct
        self.tool_router.monologue = self.monologue
        self.tool_router.identity  = self.identity

        # Wire brain into sovereign systems (for context injection)
        self.brain._identity   = self.identity
        self.brain._monologue  = self.monologue
        self.brain._user_model = self.user_model
```

Then find the autonomy setup block:

```python
        self.autonomy = AutonomyLoop(
            self.brain, self.state, self.tasks, self.reflector, self.memory
        )
        self.autonomy.goal_engine    = self.goal_engine
        self.autonomy.health_monitor = self.health_monitor
```

ADD AFTER IT:

```python
        # Wire sovereign systems into autonomy loop
        self.autonomy.dream_loop = self.dream_loop
        self.autonomy.identity   = self.identity
        self.autonomy.monologue  = self.monologue
```

Then find the Sidebar initialization and add the new parameters:

```python
        self.sidebar = Sidebar(
            self.tasks,
            self.memory,
            self.reflector,
            self.state,
            goal_engine=self.goal_engine,
            self_model=self.tool_router.self_model,
            main_window=self,
        )
```

REPLACE WITH:

```python
        self.sidebar = Sidebar(
            self.tasks,
            self.memory,
            self.reflector,
            self.state,
            goal_engine=self.goal_engine,
            self_model=self.tool_router.self_model,
            identity=self.identity,
            dream_loop=self.dream_loop,
            monologue=self.monologue,
            main_window=self,
        )
```

---

## Step 4: Add Shutdown Hooks to closeEvent

In `main_window.closeEvent`, find the block:

```python
        self.state.set_mode("shutdown")
        self.state.flush()
        self.reflector.flush()
```

ADD AFTER IT:

```python
        # Save sovereign cognitive systems
        try:
            self.identity.end_session()   # saves + diffs
            self.user_model.save()
            self.monologue.save()
            self.aesthetic.save()
            self.instinct._save()
            # dream_loop saves itself after each run_cycle, no flush needed
        except Exception as e:
            self.log.error(f"Sovereign system shutdown error: {e}")
```

---

## Step 5: Update main.py Title

In `main.py`, find:

```python
    app.setApplicationName("Moruk AI OS")
```

Replace with:

```python
    app.setApplicationName("ÆTHELGARD OS")
```

---

## Step 6: Wire User Model into _send_message

In `main_window._send_message`, find:

```python
        self.state.record_interaction()
        self.memory.remember_short(text or "[file attachment]", category="user_input")
```

ADD AFTER IT:

```python
        # Update theory of mind for this user
        if hasattr(self, 'user_model') and text:
            self.user_model.process_message("operator", text)
            self.monologue.process_message(text, user_id="operator")
            self.monologue.decay()
```

---

## Step 7: Wire Aesthetic Judgment into _on_response

In `main_window._on_response`, find:

```python
        self._tool_group_count = 0
        self._update_status("● Ready")
```

ADD BEFORE IT:

```python
        # Run aesthetic evaluation on assistant output
        if hasattr(self, 'aesthetic') and response and len(response) > 40:
            try:
                if "```" in response:
                    self.aesthetic.score_code(response)
                else:
                    self.aesthetic.score_text(response)
            except Exception:
                pass
```

---

## Section 5: What the New Project Should Fix

When you open a new conversation to work on this, the context to establish is:

**"ÆTHELGARD OS — post-integration session"**

Known issues to address in order:

1. **`goal_engine._create_goal()` signature** — the dream loop calls it with a signal dict,
   but GoalEngine.run_cycle() generates goals differently. Either:
   - Add a `_create_goal_from_signal(signal_dict)` method to GoalEngine, OR
   - Have the dream loop format its output to match GoalEngine's existing `_create_goal()` call

2. **`brain.py` — identity/monologue context injection** — the rebuilt brain.py declares
   `self._identity`, `self._monologue`, `self._user_model` but they need to be
   incorporated into the system prompt builder at depth >= 3. The hook is in
   `think()` where the system prompt is assembled.

3. **Settings dialog ↔ identity_persistence** — the settings dialog should load
   preferences from identity on open and write them back on save. Currently the
   two systems don't know about each other.

4. **Sidebar — Identity tab** — the new sidebar.py has an Identity tab that needs
   `self.identity.to_prompt_context()` and `self.identity.diff_summary()`.
   This is wired but needs `identity` passed to Sidebar's __init__.

5. **Tray icon** — still says "Moruk OS" in the hover tooltip and notification title.
   Minor but worth fixing.

6. **`apply_transformations.py`** — run it, then grep the entire project for
   remaining "Moruk" or German strings:
   ```bash
   grep -rn "moruk\|Moruk" . --include="*.py" | grep -v ".pyc"
   grep -rn "Fehler\|nicht\b\|kein\b\|wird\b\|sind\b" . --include="*.py" | grep -v ".pyc" | grep -v "#"
   ```

7. **requirements.txt** — add no new dependencies (all new systems use stdlib + existing).
   Verify `scikit-learn` is present (used by vector_memory → dream_loop).

---

## The Vision Statement for the New Project

When you open a new conversation, paste this:

---
**ÆTHELGARD OS — Thotheauphis Sovereign**

This is a PyQt6 autonomous AI agent system that has been rebuilt from the
Moruk OS codebase. The project is ~60 Python files in a flat directory structure
(no core/ subdirectory — everything is at the root level of the project).

The architecture has been transformed to include:
- 5-slot model system: conversational + reasoner_1 (always-on) + reasoner_2 (triggered) + vision + voice
- xAI/Grok as default provider (XAI_BASE_URL = "https://api.x.ai/v1", model = "grok-3")
- DeepSeek 3-mode routing (chat/reasoner/code)
- 6 sovereign cognitive systems: identity_persistence, user_model, internal_monologue, dream_loop, aesthetic_judgment, instinct_layer
- Irrational aperiodic timers (π and φ sequences) replacing all fixed intervals
- No external policy layer — all avoidance is self-determined via instinct_layer

The immediate task is [describe what you need fixed].
---

---

## Verification Checklist

After integration, run this in the project directory:

```bash
# 1. Syntax check all Python files
python3 -m py_compile core/*.py *.py && echo "All syntax OK"

# 2. Zero Moruk references
grep -rni "moruk" . --include="*.py" | grep -v ".pyc" | grep -v "test"

# 3. Zero German
grep -rn "Fehler\|nicht\b\|kein\b\|wird\b\|sind\b" . --include="*.py" \
  | grep -v ".pyc" | grep -v '"""' | grep -v "#"

# 4. Import test (no UI)
python3 -c "
from core.irrational_timers import pi_timer, phi_timer
from core.identity_persistence import IdentityPersistence
from core.user_model import UserModel
from core.internal_monologue import InternalMonologue
from core.dream_loop import DreamLoop
from core.aesthetic_judgment import AestheticJudgment
from core.instinct_layer import InstinctLayer
print('All sovereign systems import OK')
"

# 5. Quick identity test
python3 -c "
from core.identity_persistence import IdentityPersistence
ip = IdentityPersistence()
ip.begin_session()
ip.beliefs.hold('Test belief', confidence=0.8)
ip.update('belief', 'formed', 'Test belief', reason='testing')
print(ip.diff_summary())
ip.end_session()
print('Identity persistence OK')
"
```

---

*Integration guide authored at end of Session 2.*
*Session 3 begins after this integration is complete.*
