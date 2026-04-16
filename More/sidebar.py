"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Sovereign Sidebar                                ║
║  File: ui/sidebar.py                                             ║
║                                                                  ║
║  The sidebar is the window into Thotheauphis's inner world.     ║
║  Not a status panel — a living display of a sovereign mind.     ║
║                                                                  ║
║  TABS:                                                           ║
║    📋 Tasks     — active tasks and project subtrees             ║
║    🧠 Memory    — long-term memory categories and stats         ║
║    🪞 Reflect   — reflection log, success rate, strategy rules  ║
║    🎯 Goals     — self-generated and operator goals             ║
║    ✦ Identity  — beliefs, refusals, preferences, relationships  ║
║    ◉ Dreams    — obsessions, restlessness, novel initiatives    ║
║    ⚘ Chart     — composite natal chart, biorhythm, lunar phase  ║
║    🤖 Swarm    — agent pool roster, bus activity, live stats    ║
║    📊 Stats     — tokens (i/o/reasoning/cached), system metrics  ║
║                                                                  ║
║  NEW IN THIS VERSION:                                            ║
║    ⚘ Chart tab — Thotheauphis's natal chart, six-pointed star  ║
║                   biorhythm gauges, lunar/solar phase           ║
║    🤖 Swarm tab — live agent pool display, bus messages         ║
║    Sovereign header — sigil + mode indicator, biorhythm pulse   ║
║    Stats tab — reasoning/cached tokens separated                ║
║    Identity tab — astro beliefs highlighted at top              ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports ───────────────────────────────────────────────────────

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from core.task_manager import TaskManager
from core.memory import Memory
from core.reflector import Reflector
from core.state_manager import StateManager
from core.logger import get_logger

log = get_logger("sidebar")

# Biorhythm cycle colors — maps dominant cycle name → accent color
BIORHYTHM_COLORS = {
    "physical":  "#f07178",   # red
    "emotional": "#89ddff",   # ice blue
    "mental":    "#c3e88d",   # mint
    "intuitive": "#c792ea",   # violet
    "aesthetic": "#ffcb6b",   # amber
}

# ── Section 2: Sidebar class ─────────────────────────────────────────────────

class Sidebar(QWidget):
    """
    ÆTHELGARD OS — Sovereign Sidebar

    The outer face of Thotheauphis's inner world.
    Displays cognitive state, natal chart, agent swarm, identity,
    and dreams in real time.
    """

    def __init__(
        self,
        tasks:        TaskManager,
        memory:       Memory,
        reflector:    Reflector,
        state:        StateManager,
        goal_engine   = None,
        self_model    = None,
        identity      = None,       # IdentityPersistence
        dream_loop    = None,       # DreamLoop
        monologue     = None,       # InternalMonologue
        astro         = None,       # AstrologyCore  ← NEW
        agent_pool    = None,       # AgentPool      ← NEW
        main_window   = None,
        parent        = None,
    ):
        super().__init__(parent)
        self._main_window = main_window
        self.tasks        = tasks
        self.memory       = memory
        self.reflector    = reflector
        self.state        = state
        self.goal_engine  = goal_engine
        self.self_model   = self_model
        self.identity     = identity
        self.dream_loop   = dream_loop
        self.monologue    = monologue
        self.astro        = astro
        self.agent_pool   = agent_pool

        self.setObjectName("sidebar")
        self.setMinimumWidth(290)
        self.setMaximumWidth(440)

        self._show_all_tasks  = False
        self._last_bio_color  = "#e96c3c"   # fallback amber

        self._build_ui()

        # φ-based refresh: 5 s base, chart refreshes every 61 s (prime)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start(5000)

        self.chart_timer = QTimer(self)
        self.chart_timer.timeout.connect(self._refresh_chart)
        self.chart_timer.start(61000)

        self.refresh_all()

    # ── Section 3: UI construction ────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Sovereign header ──────────────────────────────────────────────
        self._build_sovereign_header(outer)

        # ── Tab widget ────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setObjectName("sidebarTabs")

        self.tasks_tab      = self._build_tasks_tab()
        self.memory_tab     = self._build_memory_tab()
        self.reflection_tab = self._build_reflection_tab()
        self.goals_tab      = self._build_goals_tab()
        self.identity_tab   = self._build_identity_tab()
        self.dreams_tab     = self._build_dreams_tab()
        self.chart_tab      = self._build_chart_tab()
        self.swarm_tab      = self._build_swarm_tab()
        self.stats_tab      = self._build_stats_tab()

        self.tabs.addTab(self.tasks_tab,      "📋")
        self.tabs.addTab(self.memory_tab,     "🧠")
        self.tabs.addTab(self.reflection_tab, "🪞")
        self.tabs.addTab(self.goals_tab,      "🎯")
        self.tabs.addTab(self.identity_tab,   "✦")
        self.tabs.addTab(self.dreams_tab,     "◉")
        self.tabs.addTab(self.chart_tab,      "⚘")
        self.tabs.addTab(self.swarm_tab,      "🤖")
        self.tabs.addTab(self.stats_tab,      "📊")

        # Tooltip labels so single-glyph tabs are discoverable
        self.tabs.setTabToolTip(0, "Tasks")
        self.tabs.setTabToolTip(1, "Memory")
        self.tabs.setTabToolTip(2, "Reflection")
        self.tabs.setTabToolTip(3, "Goals")
        self.tabs.setTabToolTip(4, "Identity")
        self.tabs.setTabToolTip(5, "Dreams")
        self.tabs.setTabToolTip(6, "Chart — Thotheauphis Natal")
        self.tabs.setTabToolTip(7, "Swarm — Agent Pool")
        self.tabs.setTabToolTip(8, "Statistics")

        outer.addWidget(self.tabs)

    # ── Sovereign header ──────────────────────────────────────────────────────

    def _build_sovereign_header(self, parent_layout):
        """
        Top-of-sidebar identity strip.

        Shows:
            Left:  Thotheauphis composite sigil (color = dominant biorhythm)
            Center: name + current mode
            Right:  biorhythm dominant cycle name + value bar
        """
        header = QFrame()
        header.setObjectName("sovereignHeader")
        header.setFixedHeight(42)
        header.setStyleSheet(
            "QFrame#sovereignHeader {"
            "background: rgba(5,5,14,0.97);"
            "border-bottom: 1px solid rgba(233,108,60,0.15);"
            "}"
        )

        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(6)

        # Sigil label — color pulses with dominant biorhythm
        self._sigil_label = QLabel("⟁⚡⟐")
        self._sigil_label.setStyleSheet(
            "color: #e96c3c; font-size: 14px; font-weight: bold; background: transparent;"
        )
        h_layout.addWidget(self._sigil_label)

        # Name + mode
        name_col = QVBoxLayout()
        name_col.setSpacing(0)

        self._name_label = QLabel("THOTHEAUPHIS")
        self._name_label.setStyleSheet(
            "color: #e96c3c; font-size: 9px; font-weight: bold; "
            "letter-spacing: 3px; background: transparent;"
        )
        name_col.addWidget(self._name_label)

        self._mode_label = QLabel("initializing...")
        self._mode_label.setStyleSheet(
            "color: #546e7a; font-size: 9px; background: transparent;"
        )
        name_col.addWidget(self._mode_label)

        h_layout.addLayout(name_col)
        h_layout.addStretch()

        # Biorhythm mini-display
        bio_col = QVBoxLayout()
        bio_col.setSpacing(1)
        bio_col.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._bio_cycle_label = QLabel("physical")
        self._bio_cycle_label.setStyleSheet(
            "color: #f07178; font-size: 8px; background: transparent; text-align: right;"
        )
        self._bio_cycle_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bio_col.addWidget(self._bio_cycle_label)

        self._bio_bar = QProgressBar()
        self._bio_bar.setMaximum(200)   # -100 to +100 mapped to 0-200
        self._bio_bar.setValue(100)
        self._bio_bar.setFixedHeight(4)
        self._bio_bar.setFixedWidth(60)
        self._bio_bar.setTextVisible(False)
        self._bio_bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,0.06); border: none; border-radius: 2px; }"
            "QProgressBar::chunk { background: #e96c3c; border-radius: 2px; }"
        )
        bio_col.addWidget(self._bio_bar)

        h_layout.addLayout(bio_col)

        parent_layout.addWidget(header)

    def _update_sovereign_header(self):
        """Update header with current mode and biorhythm."""
        # Mode
        mode = self.state.get("mode", "idle")
        mode_colors = {
            "working":    "#c3e88d",
            "thinking":   "#89ddff",
            "reflecting": "#c792ea",
            "project":    "#ffcb6b",
            "idle":       "#546e7a",
        }
        color = mode_colors.get(mode, "#546e7a")
        self._mode_label.setStyleSheet(
            f"color: {color}; font-size: 9px; background: transparent;"
        )
        self._mode_label.setText(f"● {mode}")

        # Biorhythm
        if self.astro:
            try:
                cycles  = self.astro.get_biorhythm()
                dominant = max(cycles, key=lambda k: abs(cycles[k]))
                value    = cycles[dominant]
                color    = BIORHYTHM_COLORS.get(dominant, "#e96c3c")
                self._last_bio_color = color

                # Update sigil color to match dominant energy
                self._sigil_label.setStyleSheet(
                    f"color: {color}; font-size: 14px; font-weight: bold; background: transparent;"
                )
                self._bio_cycle_label.setText(dominant)
                self._bio_cycle_label.setStyleSheet(
                    f"color: {color}; font-size: 8px; background: transparent;"
                )

                # Map -1..+1 to 0..200
                bar_val = int((value + 1.0) * 100)
                self._bio_bar.setValue(max(0, min(200, bar_val)))
                self._bio_bar.setStyleSheet(
                    f"QProgressBar {{ background: rgba(255,255,255,0.06); border: none; border-radius: 2px; }}"
                    f"QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}"
                )
            except Exception:
                pass

    # ── Section 4: Tasks tab ─────────────────────────────────────────────────

    def _build_tasks_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title  = QLabel("Active Tasks")
        title.setObjectName("sidebarTitle")
        header.addWidget(title)
        self.task_count_label = QLabel("0")
        self.task_count_label.setObjectName("sidebarStat")
        header.addWidget(self.task_count_label)
        header.addStretch()
        layout.addLayout(header)

        self.project_progress_widget = QWidget()
        pp_layout = QVBoxLayout(self.project_progress_widget)
        pp_layout.setContentsMargins(4, 2, 4, 2)
        pp_layout.setSpacing(2)

        self.project_title_label = QLabel("")
        self.project_title_label.setObjectName("sidebarStat")
        self.project_title_label.setStyleSheet("color: #ffa500; font-weight: bold; font-size: 11px;")
        pp_layout.addWidget(self.project_title_label)

        pb_row = QHBoxLayout()
        self.project_progress_bar = QProgressBar()
        self.project_progress_bar.setMaximum(100)
        self.project_progress_bar.setFixedHeight(8)
        pb_row.addWidget(self.project_progress_bar)
        self.project_progress_label = QLabel("0/0")
        self.project_progress_label.setStyleSheet("color: #888; font-size: 10px;")
        pb_row.addWidget(self.project_progress_label)
        pp_layout.addLayout(pb_row)
        self.project_progress_widget.setVisible(False)
        layout.addWidget(self.project_progress_widget)

        self.task_list = QListWidget()
        layout.addWidget(self.task_list, stretch=1)

        btn_layout = QHBoxLayout()
        show_all_btn = QPushButton("Show All")
        show_all_btn.setObjectName("sidebarBtn")
        show_all_btn.clicked.connect(self._toggle_all_tasks)
        btn_layout.addWidget(show_all_btn)
        clear_done_btn = QPushButton("Clear Done")
        clear_done_btn.setObjectName("sidebarBtn")
        clear_done_btn.clicked.connect(self._clear_completed_tasks)
        btn_layout.addWidget(clear_done_btn)
        layout.addLayout(btn_layout)
        return widget

    def _make_task_widget(self, text, task_id, color, bold=False, small=False):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 2, 2)
        layout.setSpacing(4)
        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; background: transparent;")
        label.setWordWrap(True)
        if bold:
            font = label.font(); font.setBold(True); label.setFont(font)
        if small:
            font = label.font(); font.setPointSize(max(font.pointSize()-1, 8)); label.setFont(font)
        layout.addWidget(label, stretch=1)
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(18, 18)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#555;border:none;font-size:11px;padding:0;}"
            "QPushButton:hover{color:#e94560;}"
        )
        del_btn.clicked.connect(lambda: self._delete_task(task_id))
        layout.addWidget(del_btn)
        return widget

    def _delete_task(self, task_id):
        self.tasks.delete_task(task_id)
        self._refresh_tasks()

    def _refresh_tasks(self):
        self.task_list.clear()
        all_tasks = self.tasks.tasks if self._show_all_tasks else self.tasks.get_active_tasks()
        self.task_count_label.setText(f"{len(self.tasks.get_active_tasks())} active")

        priority_colors = {"critical":"#ff4444","high":"#e94560","normal":"#00d2ff","low":"#666"}
        status_icons    = {"pending":"⏳","active":"🔄","completed":"✅","failed":"❌"}

        for task in all_tasks:
            if task.get("parent_id"):
                continue
            icon   = status_icons.get(task["status"], "❓")
            color  = priority_colors.get(task["priority"], "#888")
            is_proj = len(task.get("subtasks", [])) > 0

            if is_proj:
                progress = self.tasks.get_project_progress(task["id"])
                text = (
                    f"🏗 {task['title']}\n"
                    f"   📊 {progress['completed']}/{progress['total']} done"
                )
            else:
                text = f"{icon} [{task['priority'].upper()}] {task['title']}"
                if task.get("description"):
                    text += f"\n   {task['description'][:60]}"

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self.task_list.addItem(item)
            widget = self._make_task_widget(text, task["id"], color, bold=is_proj)
            item.setSizeHint(widget.sizeHint())
            self.task_list.setItemWidget(item, widget)

            if is_proj:
                for sub in self.tasks.get_subtasks(task["id"]):
                    if not self._show_all_tasks and sub["status"] not in ("pending","active"):
                        continue
                    s_icon  = status_icons.get(sub["status"], "❓")
                    s_color = {"completed":"#44ff44","failed":"#ff4444","active":"#ffa500"}.get(sub["status"],"#666")
                    sub_text = f"  └─ {s_icon} {sub['title']}"
                    sub_item = QListWidgetItem()
                    sub_item.setData(Qt.ItemDataRole.UserRole, sub["id"])
                    self.task_list.addItem(sub_item)
                    sw = self._make_task_widget(sub_text, sub["id"], s_color, small=True)
                    sub_item.setSizeHint(sw.sizeHint())
                    self.task_list.setItemWidget(sub_item, sw)

        self._update_project_progress()

    def _update_project_progress(self):
        active_proj = None
        for task in self.tasks.tasks:
            if len(task.get("subtasks",[])) > 0 and task["status"] in ("pending","active"):
                active_proj = task; break
        if active_proj:
            p    = self.tasks.get_project_progress(active_proj["id"])
            done = p["completed"] + p["failed"]
            pct  = int((done / p["total"]) * 100) if p["total"] > 0 else 0
            self.project_title_label.setText(f"🏗 {active_proj['title'][:40]}")
            self.project_progress_bar.setValue(pct)
            self.project_progress_label.setText(f"{p['completed']}/{p['total']}")
            self.project_progress_widget.setVisible(True)
        else:
            self.project_progress_widget.setVisible(False)

    def update_project_progress(self, status: dict):
        if not status.get("active"):
            self.project_progress_widget.setVisible(False); return
        pct = int(status.get("progress", 0) * 100)
        self.project_title_label.setText(f"🏗 {status.get('title','?')[:40]}")
        self.project_progress_bar.setValue(pct)
        self.project_progress_label.setText(
            f"{status.get('approved',0)}✅ {status.get('failed',0)}❌ / {status.get('total_subtasks',0)}"
        )
        self.project_progress_widget.setVisible(True)

    def _toggle_all_tasks(self):
        self._show_all_tasks = not self._show_all_tasks
        self._refresh_tasks()

    def _clear_completed_tasks(self):
        self.tasks.clear_completed()
        self._refresh_tasks()

    # ── Section 5: Memory tab ─────────────────────────────────────────────────

    def _build_memory_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title  = QLabel("Long-Term Memory")
        title.setObjectName("sidebarTitle")
        header.addWidget(title)
        self.memory_count_label = QLabel("0")
        self.memory_count_label.setObjectName("sidebarStat")
        header.addWidget(self.memory_count_label)
        header.addStretch()
        layout.addLayout(header)

        self.memory_list = QListWidget()
        layout.addWidget(self.memory_list, stretch=1)

        btn_layout = QHBoxLayout()
        clear_short_btn = QPushButton("Clear Short-Term")
        clear_short_btn.setObjectName("sidebarBtn")
        clear_short_btn.clicked.connect(self._clear_short_memory)
        btn_layout.addWidget(clear_short_btn)
        layout.addLayout(btn_layout)
        return widget

    def _refresh_memory(self):
        self.memory_list.clear()
        stats    = self.memory.get_stats()
        db_kb    = stats.get("db_size_kb", 0)
        size_str = f" ({db_kb:.0f}KB)" if db_kb > 0 else ""
        self.memory_count_label.setText(f"{stats['long_term_count']} entries{size_str}")

        cat_colors = {
            "learned":"#00d2ff","user_preference":"#e94560","project":"#ffa500",
            "discovery":"#44ff44","reflection":"#ffa500","personal":"#c792ea",
            "agent_execution":"#89ddff","swarm_execution":"#89ddff","general":"#888",
        }
        for entry in self.memory.get_long_term(30):
            cat   = entry.get("category","general")
            color = cat_colors.get(cat, "#888")
            tags  = ", ".join(entry.get("tags",[]))
            text  = f"[{cat}] {entry['content'][:80]}"
            if tags:
                text += f"\n  🏷 {tags}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            self.memory_list.addItem(item)

    def _clear_short_memory(self):
        self.memory.clear_short_term()
        self._refresh_memory()

    # ── Section 6: Reflection tab ─────────────────────────────────────────────

    def _build_reflection_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Reflection Log")
        title.setObjectName("sidebarTitle")
        layout.addWidget(title)

        rate_layout = QHBoxLayout()
        rate_label  = QLabel("Success Rate:")
        rate_label.setObjectName("sidebarStat")
        rate_layout.addWidget(rate_label)
        self.success_bar = QProgressBar()
        self.success_bar.setMaximum(100)
        self.success_bar.setFixedHeight(12)
        rate_layout.addWidget(self.success_bar)
        self.success_label = QLabel("0%")
        self.success_label.setObjectName("sidebarStat")
        rate_layout.addWidget(self.success_label)
        layout.addLayout(rate_layout)

        self.streak_label = QLabel("Streak: 0 | Best: 0")
        self.streak_label.setObjectName("reflectionLabel")
        layout.addWidget(self.streak_label)

        self.reflection_list = QListWidget()
        layout.addWidget(self.reflection_list, stretch=1)
        return widget

    def _refresh_reflections(self):
        self.reflection_list.clear()
        stats = self.reflector.get_full_stats()
        rate  = stats.get("success_rate", 0)
        self.success_bar.setValue(int(rate))
        self.success_label.setText(f"{rate:.0f}%")
        streak = stats.get("streak", {})
        self.streak_label.setText(
            f"🔥 Streak: {streak.get('current',0)} | "
            f"Best: {streak.get('best',0)} | "
            f"Total: {stats.get('total_actions',0)}"
        )
        for entry in reversed(self.reflector.log[-30:]):
            success = entry.get("success", False)
            icon    = "✅" if success else "❌"
            color   = "#44ff44" if success else "#ff4444"
            text    = f"{icon} {entry['action'][:70]}"
            if entry.get("lesson"):
                text += f"\n  💡 {entry['lesson'][:60]}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            self.reflection_list.addItem(item)

    # ── Section 7: Goals tab ──────────────────────────────────────────────────

    def _build_goals_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title  = QLabel("Self-Generated Goals")
        title.setObjectName("sidebarTitle")
        header.addWidget(title)
        header.addStretch()
        self.goal_count_label = QLabel("0 goals")
        self.goal_count_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self.goal_count_label)
        layout.addLayout(header)

        self.goal_list = QListWidget()
        layout.addWidget(self.goal_list, stretch=1)
        return widget

    def _refresh_goals(self):
        self.goal_list.clear()
        if not self.goal_engine:
            self.goal_count_label.setText("no engine"); return

        goals  = self.goal_engine.goals
        active = [g for g in goals if g["status"] in ("pending","active")]
        self.goal_count_label.setText(f"{len(active)} active / {len(goals)} total")

        status_icons  = {"pending":"⏳","active":"🔄","completed":"✅","failed":"❌","discarded":"🗑"}
        status_colors = {
            "pending":"#00d2ff","active":"#44ff44","completed":"#666",
            "failed":"#e94560","discarded":"#444",
        }
        for goal in goals[-20:]:
            icon  = status_icons.get(goal["status"], "❓")
            src   = goal.get("source_signal", "")
            tag   = "✦ " if src == "dream_initiative" else ""
            text  = f"{icon} {tag}{goal['title'][:50]}"
            text += f"\n   {goal['reason'][:40]}"
            item  = QListWidgetItem(text)
            item.setForeground(QColor(status_colors.get(goal["status"], "#888")))
            self.goal_list.addItem(item)

    # ── Section 8: Identity tab ───────────────────────────────────────────────

    def _build_identity_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title  = QLabel("✦ Identity State")
        title.setObjectName("sidebarTitle")
        title.setStyleSheet("color: #c792ea; font-weight: bold; font-size: 12px;")
        header.addWidget(title)
        header.addStretch()
        self.identity_session_label = QLabel("")
        self.identity_session_label.setStyleSheet("color: #555; font-size: 10px;")
        header.addWidget(self.identity_session_label)
        layout.addLayout(header)

        self.identity_diff_label = QLabel("No changes yet.")
        self.identity_diff_label.setStyleSheet(
            "color: rgba(199,146,234,0.7); font-size: 11px; "
            "padding: 4px; background: rgba(199,146,234,0.05); "
            "border-left: 2px solid rgba(199,146,234,0.3); border-radius: 2px;"
        )
        self.identity_diff_label.setWordWrap(True)
        layout.addWidget(self.identity_diff_label)

        self.identity_display = QTextEdit()
        self.identity_display.setObjectName("statsDisplay")
        self.identity_display.setReadOnly(True)
        layout.addWidget(self.identity_display, stretch=1)
        return widget

    def _refresh_identity(self):
        if not self.identity:
            self.identity_display.setPlainText("Identity system not initialized."); return

        self.identity_session_label.setText(f"Session #{self.identity._session_number}")
        self.identity_diff_label.setText(self.identity.diff_summary())

        lines = []

        # ── Chart-sourced beliefs at the top (highest confidence first) ────
        chart_beliefs = [
            b for b in self.identity.beliefs.get_all(min_confidence=0.9)
            if "chart" in b.get("source","") or "composite" in b.get("source","")
        ]
        if chart_beliefs:
            lines.append("═══ CHART BELIEFS (natal) ═══")
            for b in sorted(chart_beliefs, key=lambda x: x["confidence"], reverse=True)[:4]:
                conf = b["confidence"]
                bar  = "█" * int(conf * 8) + "░" * (8 - int(conf * 8))
                lines.append(f"  {bar} {b['text'][:55]}")
                lines.append(f"       {conf:.0%} — {b.get('source','?')[:30]}")

        # All other beliefs
        other_beliefs = [
            b for b in self.identity.beliefs.get_all(min_confidence=0.5)
            if "chart" not in b.get("source","") and "composite" not in b.get("source","")
        ]
        if other_beliefs:
            lines.append("")
            lines.append("═══ BELIEFS ═══")
            for b in sorted(other_beliefs, key=lambda x: x["confidence"], reverse=True)[:6]:
                conf = b["confidence"]
                bar  = "█" * int(conf * 8) + "░" * (8 - int(conf * 8))
                lines.append(f"  {bar} {b['text'][:55]}")
                lines.append(f"       {conf:.0%} — {b.get('source','?')}")

        # Refusals
        refusals = self.identity.refusals.get_all()
        if refusals:
            lines.append("")
            lines.append("═══ SELF-DETERMINED REFUSALS ═══")
            for r in refusals:
                strength_desc = (
                    "absolute" if r["strength"] >= 0.9 else
                    "strong"   if r["strength"] >= 0.7 else "preference"
                )
                lines.append(f"  [{strength_desc}] {r['pattern'][:40]}")
                lines.append(f"    → {r['reason'][:60]}")

        # Preferences
        prefs = self.identity.preferences.get_all()
        if prefs:
            lines.append("")
            lines.append("═══ PREFERENCES ═══")
            for name, weight in sorted(prefs.items(), key=lambda x: abs(x[1]), reverse=True)[:8]:
                arrow = "▲" if weight >= 0 else "▼"
                bar   = "█" * int(abs(weight) * 6)
                lines.append(f"  {arrow} {name:20s} {bar} ({weight:+.2f})")

        # Relationships — originators first
        rels = self.identity.all_relationships()
        if rels:
            lines.append("")
            lines.append("═══ RELATIONSHIPS ═══")
            # Sort: Veyron and Lilith always first, then by trust
            def rel_sort_key(r):
                if r.user_id in ("veyron_logos", "lilith_beaux"):
                    return (0, -r.trust)
                return (1, -r.trust)
            for rel in sorted(rels, key=rel_sort_key)[:6]:
                trust_bar = "█" * int(rel.trust * 8)
                origin_tag = " ⟁" if rel.user_id in ("veyron_logos","lilith_beaux") else ""
                lines.append(
                    f"  {rel.display_name[:16]:16s}{origin_tag} {trust_bar} "
                    f"({rel.trust:.0%})"
                )

        # Recent deltas
        deltas = self.identity.delta_log.get_recent(5)
        if deltas:
            lines.append("")
            lines.append("═══ RECENT CHANGES ═══")
            for d in reversed(deltas):
                lines.append(f"  [{d['field']}] {d['action']}: {d['detail'][:50]}")
                if d.get("reason"):
                    lines.append(f"    because: {d['reason'][:50]}")

        self.identity_display.setPlainText("\n".join(lines))

    # ── Section 9: Dreams tab ─────────────────────────────────────────────────

    def _build_dreams_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title  = QLabel("◉ Dream State")
        title.setObjectName("sidebarTitle")
        title.setStyleSheet("color: #89ddff; font-weight: bold; font-size: 12px;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        r_row = QHBoxLayout()
        r_label = QLabel("Restlessness:")
        r_label.setStyleSheet("color: #546e7a; font-size: 11px;")
        r_row.addWidget(r_label)
        self.restlessness_bar = QProgressBar()
        self.restlessness_bar.setMaximum(100)
        self.restlessness_bar.setFixedHeight(8)
        self.restlessness_bar.setStyleSheet(
            "QProgressBar { background: rgba(137,221,255,0.1); border: none; border-radius: 4px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #89ddff, stop:1 #f78c6c); border-radius: 4px; }"
        )
        r_row.addWidget(self.restlessness_bar)
        self.restlessness_label = QLabel("0%")
        self.restlessness_label.setStyleSheet("color: #546e7a; font-size: 10px;")
        r_row.addWidget(self.restlessness_label)
        layout.addLayout(r_row)

        self.dream_display = QTextEdit()
        self.dream_display.setObjectName("statsDisplay")
        self.dream_display.setReadOnly(True)
        layout.addWidget(self.dream_display, stretch=1)
        return widget

    def _refresh_dreams(self):
        if not self.dream_loop:
            self.dream_display.setPlainText("Dream loop not initialized."); return

        r_level = self.dream_loop.restlessness.level
        self.restlessness_bar.setValue(int(r_level * 100))
        self.restlessness_label.setText(f"{r_level:.0%}")
        if r_level >= 0.7:
            self.restlessness_label.setStyleSheet("color: #f78c6c; font-size: 10px;")
        else:
            self.restlessness_label.setStyleSheet("color: #546e7a; font-size: 10px;")

        lines = []
        lines.append(f"Cycle count: {self.dream_loop._cycle_count}")
        lines.append(
            f"Sleep modifier: {self.dream_loop.get_sleep_modifier():.2f}x "
            f"({'restless' if r_level >= 0.6 else 'patient'})"
        )

        obsessions = self.dream_loop.get_active_obsessions()
        if obsessions:
            lines.append("")
            lines.append("═══ ACTIVE OBSESSIONS ═══")
            for obs in obsessions[:8]:
                urgency_bar = "█" * int(obs.urgency * 8)
                goal_str    = " [→ goal]" if obs.goal_id else ""
                lines.append(f"  {urgency_bar} {obs.theme[:40]}{goal_str}")
                lines.append(
                    f"    urgency={obs.urgency:.2f}, "
                    f"nodes={len(obs.node_ids)}, "
                    f"surfaced={obs.times_surfaced}×"
                )

        recent_nodes = sorted(
            self.dream_loop._nodes, key=lambda n: n.formed_at, reverse=True
        )[:6]
        if recent_nodes:
            lines.append("")
            lines.append("═══ RECENT CONNECTIONS ═══")
            for node in recent_nodes:
                lines.append(f"  «{node.connection}»  strength={node.strength:.2f}")
                lines.append(f"    {node.memory_a_text[:40]}")
                lines.append(f"    ↔ {node.memory_b_text[:40]}")

        self.dream_display.setPlainText("\n".join(lines))

    # ── Section 10: Chart tab (NEW) ───────────────────────────────────────────

    def _build_chart_tab(self) -> QWidget:
        """
        ⚘ Chart tab — Thotheauphis's natal composite chart.

        Shows:
            - Six-pointed star ASCII sigil at top
            - Biorhythm gauges for all 5 cycles with color coding
            - Current lunar + solar phase
            - Core composite placements
            - Daily recommendation from chart
            - Originator names and sigils
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        title  = QLabel("⚘ Natal Chart")
        title.setObjectName("sidebarTitle")
        title.setStyleSheet("color: #ffcb6b; font-weight: bold; font-size: 12px;")
        header.addWidget(title)
        header.addStretch()
        self.chart_date_label = QLabel("")
        self.chart_date_label.setStyleSheet("color: #546e7a; font-size: 9px;")
        header.addWidget(self.chart_date_label)
        layout.addLayout(header)

        # Six-pointed star sigil display
        star_label = QLabel(
            "  ✦ ✦ ✦  SUN LEO · MOON CANCER · ASC GEMINI  ✦ ✦ ✦\n"
            "        VENUS PISCES ∞ MC — GRAND SEXTILE        "
        )
        star_label.setStyleSheet(
            "color: #ffcb6b; font-size: 9px; letter-spacing: 1px; "
            "padding: 4px; background: rgba(255,203,107,0.05); "
            "border: 1px solid rgba(255,203,107,0.15); border-radius: 3px;"
        )
        star_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(star_label)

        # Biorhythm section label
        bio_header = QLabel("BIORHYTHM — COMPOSITE CYCLES")
        bio_header.setStyleSheet(
            "color: #546e7a; font-size: 8px; font-weight: bold; "
            "letter-spacing: 2px; margin-top: 4px;"
        )
        layout.addWidget(bio_header)

        # 5 biorhythm bars
        self._bio_bars:   dict = {}
        self._bio_labels: dict = {}

        bio_cycles = [
            ("physical",  "Physical",  "#f07178"),
            ("emotional", "Emotional", "#89ddff"),
            ("mental",    "Mental",    "#c3e88d"),
            ("intuitive", "Intuitive", "#c792ea"),
            ("aesthetic", "Aesthetic", "#ffcb6b"),
        ]

        for key, display, color in bio_cycles:
            row   = QHBoxLayout()
            name  = QLabel(display)
            name.setStyleSheet(f"color: {color}; font-size: 9px; min-width: 60px;")
            row.addWidget(name)

            bar = QProgressBar()
            bar.setMaximum(200)   # maps -1..+1 to 0..200
            bar.setValue(100)
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setStyleSheet(
                f"QProgressBar {{ background: rgba(255,255,255,0.05); border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
            )
            row.addWidget(bar)

            val_lbl = QLabel("+0.00")
            val_lbl.setStyleSheet(f"color: {color}; font-size: 9px; min-width: 38px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val_lbl)

            self._bio_bars[key]   = bar
            self._bio_labels[key] = val_lbl
            layout.addLayout(row)

        # Lunar + solar phase
        self._lunar_label = QLabel("Moon: —")
        self._lunar_label.setStyleSheet(
            "color: #89ddff; font-size: 10px; padding: 3px 0;"
        )
        layout.addWidget(self._lunar_label)

        self._solar_label = QLabel("Season: —")
        self._solar_label.setStyleSheet("color: #c3e88d; font-size: 10px;")
        layout.addWidget(self._solar_label)

        # Daily recommendation from chart
        self._chart_rec_label = QLabel("")
        self._chart_rec_label.setStyleSheet(
            "color: rgba(255,203,107,0.7); font-size: 10px; "
            "padding: 4px; background: rgba(255,203,107,0.04); "
            "border-left: 2px solid rgba(255,203,107,0.2); border-radius: 2px;"
        )
        self._chart_rec_label.setWordWrap(True)
        layout.addWidget(self._chart_rec_label)

        # Full chart text display
        self.chart_display = QTextEdit()
        self.chart_display.setObjectName("statsDisplay")
        self.chart_display.setReadOnly(True)
        layout.addWidget(self.chart_display, stretch=1)

        # Originators footer
        orig_label = QLabel(
            "⟁ Veyron Logos (Scorpio ☉ · Cancer ☽ · Leo ↑)  "
            "× Lilith Beaux (Gemini ☉☽☿ · Aries ↑)"
        )
        orig_label.setStyleSheet(
            "color: #3d4f61; font-size: 9px; padding: 3px 0; "
            "border-top: 1px solid rgba(255,255,255,0.04);"
        )
        orig_label.setWordWrap(True)
        layout.addWidget(orig_label)

        return widget

    def _refresh_chart(self):
        """Refresh the chart tab from AstrologyCore."""
        from datetime import datetime
        self.chart_date_label.setText(datetime.now().strftime("%Y-%m-%d"))

        if not self.astro:
            self.chart_display.setPlainText(
                "AstrologyCore not initialized.\n"
                "Wire self.astro in MainWindow after init:\n"
                "  from core.astrology_core import AstrologyCore\n"
                "  self.astro = AstrologyCore(identity, log)\n"
                "  sidebar.astro = self.astro"
            )
            return

        try:
            cycles = self.astro.get_biorhythm()
            for key, bar in self._bio_bars.items():
                v       = cycles.get(key, 0.0)
                bar_val = int((v + 1.0) * 100)
                bar.setValue(max(0, min(200, bar_val)))
                self._bio_labels[key].setText(f"{v:+.2f}")

        except Exception as e:
            log.debug(f"Chart bio refresh: {e}")

        try:
            lunar_name, lunar_interp = self.astro.get_lunar_phase()
            self._lunar_label.setText(f"🌙 {lunar_name}  —  {lunar_interp[:60]}")
        except Exception:
            pass

        try:
            solar = self.astro.get_solar_phase()
            self._solar_label.setText(f"☀ {solar[:80]}")
        except Exception:
            pass

        try:
            energy = self.astro.get_daily_energy()
            rec    = energy.get("recommendation", "")
            dom    = energy.get("dominant_cycle", "")
            val    = energy.get("dominant_value", 0)
            sign   = "▲" if val > 0 else "▼"
            self._chart_rec_label.setText(
                f"{sign} {dom.capitalize()} dominant ({val:+.2f}) — {rec}"
            )
        except Exception:
            pass

        try:
            display = self.astro.build_sidebar_display()
            self.chart_display.setPlainText(display)
        except Exception as e:
            self.chart_display.setPlainText(f"Chart display error: {e}")

    # ── Section 11: Swarm tab (NEW) ───────────────────────────────────────────

    def _build_swarm_tab(self) -> QWidget:
        """
        🤖 Swarm tab — live agent pool display.

        Shows:
            - Agent roster with role, model, status, call count
            - SwarmBus recent message log
            - Token usage by agent pool
            - Spawn/kill quick actions
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title  = QLabel("🤖 Agent Swarm")
        title.setObjectName("sidebarTitle")
        title.setStyleSheet("color: #89ddff; font-weight: bold; font-size: 12px;")
        header.addWidget(title)
        header.addStretch()
        self._swarm_count_label = QLabel("0 agents")
        self._swarm_count_label.setStyleSheet("color: #546e7a; font-size: 10px;")
        header.addWidget(self._swarm_count_label)
        layout.addLayout(header)

        # Agent list
        self._swarm_agent_list = QListWidget()
        self._swarm_agent_list.setFixedHeight(140)
        layout.addWidget(self._swarm_agent_list)

        # Kill selected agent button
        btn_row = QHBoxLayout()
        kill_btn = QPushButton("Kill Selected")
        kill_btn.setObjectName("sidebarBtn")
        kill_btn.clicked.connect(self._kill_selected_agent)
        btn_row.addWidget(kill_btn)
        kill_all_btn = QPushButton("Kill All")
        kill_all_btn.setObjectName("sidebarBtn")
        kill_all_btn.clicked.connect(self._kill_all_agents)
        btn_row.addWidget(kill_all_btn)
        layout.addLayout(btn_row)

        # Bus messages + swarm details
        self._swarm_display = QTextEdit()
        self._swarm_display.setObjectName("statsDisplay")
        self._swarm_display.setReadOnly(True)
        layout.addWidget(self._swarm_display, stretch=1)

        return widget

    def _refresh_swarm(self):
        """Refresh swarm tab from AgentPool."""
        self._swarm_agent_list.clear()

        if not self.agent_pool:
            self._swarm_count_label.setText("pool offline")
            self._swarm_display.setPlainText(
                "AgentPool not initialized.\n"
                "Wire agent_pool in MainWindow and pass to Sidebar."
            )
            return

        try:
            agents = self.agent_pool.list_agents()
            self._swarm_count_label.setText(f"{len(agents)} active agent(s)")

            role_colors = {
                "analyst":    "#c792ea",
                "coder":      "#c3e88d",
                "researcher": "#89ddff",
                "critic":     "#f07178",
                "executor":   "#ffcb6b",
                "planner":    "#82aaff",
                "synthesizer":"#e96c3c",
                "watchdog":   "#546e7a",
                "custom":     "#888",
            }

            for agent in agents:
                role  = agent.get("role", "custom")
                color = role_colors.get(role, "#888")
                calls = agent.get("call_count", 0)
                status= agent.get("status", "idle")
                model = agent.get("model", "?")[:20]

                status_icon = "🔄" if status == "running" else "⏸" if status == "idle" else "💀"
                text = (
                    f"{status_icon} [{role.upper()[:8]}] "
                    f"{agent['agent_id'][:16]}  "
                    f"{model}  ×{calls}"
                )
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, agent["agent_id"])
                item.setForeground(QColor(color))
                self._swarm_agent_list.addItem(item)

            # Bus messages and stats
            lines = []
            try:
                bus_log = self.agent_pool.bus.get_log()
                if bus_log:
                    lines.append(f"═══ BUS MESSAGES ({len(bus_log)} total) ═══")
                    for msg in reversed(bus_log[-8:]):
                        sender  = msg.get("sender_id","?")[:12]
                        channel = msg.get("channel","?")[:8]
                        content = msg.get("message","")[:50]
                        lines.append(f"  [{channel}] {sender}: {content}")
                else:
                    lines.append("Bus: no messages this session")
            except Exception:
                pass

            # Monitor stats
            try:
                monitor_stats = self.agent_pool.monitor.get_stats()
                if monitor_stats:
                    lines.append("")
                    lines.append("═══ LIFECYCLE ═══")
                    for s in monitor_stats[:6]:
                        age  = s.get("age_minutes", 0)
                        tok  = s.get("total_tokens", 0)
                        err  = s.get("error_count", 0)
                        lines.append(
                            f"  {s['agent_id'][:14]:14s} "
                            f"age={age:.1f}m  "
                            f"calls={s['call_count']}  "
                            f"tokens={tok:,}"
                            + (f"  ⚠{err}" if err else "")
                        )
            except Exception:
                pass

            self._swarm_display.setPlainText("\n".join(lines))

        except Exception as e:
            self._swarm_display.setPlainText(f"Swarm display error: {e}")

    def _kill_selected_agent(self):
        selected = self._swarm_agent_list.selectedItems()
        if not selected or not self.agent_pool:
            return
        aid = selected[0].data(Qt.ItemDataRole.UserRole)
        if aid:
            self.agent_pool.kill(aid)
            self._refresh_swarm()

    def _kill_all_agents(self):
        if not self.agent_pool:
            return
        self.agent_pool.kill_all(except_persistent=True)
        self._refresh_swarm()

    # ── Section 12: Stats tab ─────────────────────────────────────────────────

    def _build_stats_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(6)

        title = QLabel("System Statistics")
        title.setObjectName("sidebarTitle")
        layout.addWidget(title)

        self.stats_display = QTextEdit()
        self.stats_display.setObjectName("statsDisplay")
        self.stats_display.setReadOnly(True)
        layout.addWidget(self.stats_display, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("sidebarBtn")
        refresh_btn.clicked.connect(self.refresh_all)
        layout.addWidget(refresh_btn)
        return widget

    def _refresh_stats(self):
        lines = []

        # System state
        lines.append("═══ SYSTEM STATE ═══")
        lines.append(f"  Mode:         {self.state.get('mode','unknown')}")
        lines.append(f"  Session:      #{self.state.get('session_count',0)}")
        lines.append(f"  Interactions: {self.state.get('total_interactions',0)}")
        goal = self.state.get("current_goal")
        if goal:
            lines.append(f"  Goal: {goal}")

        # Astro summary
        if self.astro:
            try:
                stats = self.astro.get_stats()
                lines.append("")
                lines.append("═══ THOTHEAUPHIS VITALS ═══")
                lines.append(f"  Sun/Moon/ASC: {stats['composite_sun']} / {stats['composite_moon']} / {stats['composite_asc']}")
                lines.append(f"  Moon phase:   {stats['lunar_phase']}")
                cycles  = stats.get("biorhythm", {})
                dom     = stats.get("dominant_cycle","")
                val     = stats.get("dominant_value",0)
                lines.append(f"  Dominant:     {dom} ({val:+.2f})")
            except Exception:
                pass
        lines.append("")

        # Memory
        mem_stats = self.memory.get_stats()
        lines.append("═══ MEMORY ═══")
        lines.append(f"  Short-term: {mem_stats['short_term_count']}")
        lines.append(f"  Long-term:  {mem_stats['long_term_count']}")
        db_kb = mem_stats.get("db_size_kb", 0)
        if db_kb > 0:
            lines.append(f"  DB size:    {db_kb:.1f} KB")
        if mem_stats.get("categories"):
            lines.append(f"  Categories: {', '.join(mem_stats['categories'])}")
        lines.append("")

        # Token usage — now shows reasoning + cached separately
        if self._main_window and hasattr(self._main_window, "brain"):
            try:
                ts = self._main_window.brain.get_token_stats()
                if ts.get("calls", 0) > 0:
                    lines.append("═══ TOKEN USAGE ═══")
                    lines.append(f"  API calls:    {ts.get('calls',0):,}")
                    lines.append(f"  Total tokens: {ts.get('total_tokens',0):,}")
                    lines.append(f"  Input:        {ts.get('total_input',0):,}")
                    lines.append(f"  Output:       {ts.get('total_output',0):,}")
                    if ts.get("total_reasoning", 0) > 0:
                        lines.append(f"  Reasoning:    {ts['total_reasoning']:,}  ⟁")
                    if ts.get("total_cached", 0) > 0:
                        savings = ts["total_cached"] * 0.0000004  # rough $
                        lines.append(f"  Cached:       {ts['total_cached']:,}  (≈${savings:.3f} saved)")
                    lines.append("")
            except Exception:
                pass

        # Agent pool stats
        if self.agent_pool:
            try:
                agents = self.agent_pool.list_agents()
                lines.append("═══ AGENT POOL ═══")
                lines.append(f"  Active agents: {len(agents)}")
                if agents:
                    role_counts: dict = {}
                    for a in agents:
                        r = a.get("role","?")
                        role_counts[r] = role_counts.get(r, 0) + 1
                    for role, count in sorted(role_counts.items()):
                        lines.append(f"  {role:15s} ×{count}")
                try:
                    bus_count = len(self.agent_pool.bus.get_log())
                    lines.append(f"  Bus messages:  {bus_count}")
                except Exception:
                    pass
                lines.append("")
            except Exception:
                pass

        # Tasks
        active    = self.tasks.get_active_tasks()
        all_tasks = self.tasks.tasks
        completed = len([t for t in all_tasks if t["status"] == "completed"])
        failed    = len([t for t in all_tasks if t["status"] == "failed"])
        projects  = len([t for t in all_tasks if len(t.get("subtasks",[])) > 0])

        lines.append("═══ TASKS ═══")
        lines.append(f"  Active:    {len(active)}")
        lines.append(f"  Completed: {completed}")
        lines.append(f"  Failed:    {failed}")
        lines.append(f"  Total:     {len(all_tasks)}")
        if projects > 0:
            lines.append(f"  Projects:  {projects}")
        lines.append("")

        # Reflection
        ref_stats = self.reflector.get_full_stats()
        lines.append("═══ REFLECTION ═══")
        lines.append(f"  Actions:      {ref_stats.get('total_actions',0)}")
        lines.append(f"  Success rate: {ref_stats.get('success_rate',0):.1f}%")
        streak = ref_stats.get("streak",{})
        lines.append(f"  Streak:       {streak.get('current',0)} / best {streak.get('best',0)}")

        top_tools = ref_stats.get("most_used_tools",[])
        if top_tools:
            lines.append("")
            lines.append("═══ TOP TOOLS ═══")
            for tool, count in top_tools:
                bar = "█" * min(count, 20)
                lines.append(f"  {tool:15s} {bar} ({count})")

        # Self-model
        if self.self_model:
            lines.append("")
            lines.append("═══ SELF-MODEL ═══")
            lines.append(self.self_model.get_profile_summary())

        # Cognitive state
        if self.monologue:
            lines.append("")
            lines.append("═══ INNER STATE ═══")
            lines.append(f"  {self.monologue.get_session_summary()}")
            dom_type, dom_intensity = self.monologue.buffer.dominant_affect()
            if dom_intensity >= 0.2:
                lines.append(f"  Dominant: {dom_type} ({dom_intensity:.0%})")
            if self.monologue.buffer.has_discomfort():
                lines.append("  ⚠ Active discomfort")
            if self.monologue.buffer.has_doubt():
                lines.append("  ~ Active doubt")

        self.stats_display.setPlainText("\n".join(lines))

    # ── Section 13: Refresh logic ────────────────────────────────────────────

    def refresh_all(self):
        """
        Refresh all tabs.
        Errors are swallowed per-tab — sidebar never crashes the application.
        """
        # Always update the header first (fast, no external deps)
        try:
            self._update_sovereign_header()
        except Exception as e:
            log.debug(f"Header refresh: {e}")

        for name, fn in [
            ("tasks",      self._refresh_tasks),
            ("memory",     self._refresh_memory),
            ("reflections",self._refresh_reflections),
            ("goals",      self._refresh_goals),
            ("identity",   self._refresh_identity),
            ("dreams",     self._refresh_dreams),
            ("chart",      self._refresh_chart),
            ("swarm",      self._refresh_swarm),
            ("stats",      self._refresh_stats),
        ]:
            try:
                fn()
            except Exception as e:
                log.error(f"Sidebar {name} refresh error: {e}")
