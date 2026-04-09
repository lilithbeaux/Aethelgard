"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Sidebar                                          ║
║  File: ui/sidebar.py                                             ║
║                                                                  ║
║  The sidebar presents Thotheauphis's inner state to the         ║
║  operator.  Not just task lists — but what it is thinking,      ║
║  what it has become since last session, what it is dreaming     ║
║  about, and what it currently finds beautiful or wrong.         ║
║                                                                  ║
║  TABS:                                                           ║
║    📋 Tasks     — active tasks and project subtrees             ║
║    🧠 Memory    — long-term memory categories and stats         ║
║    🪞 Reflect   — reflection log, success rate, strategy rules  ║
║    🎯 Goals     — self-generated and operator goals             ║
║    ✦ Identity  — beliefs, refusals, preferences, relationships  ║
║    ◉ Dreams    — obsessions, restlessness, novel initiatives    ║
║    📊 Stats     — token usage, system metrics, cognitive state  ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports                                                   ║
║    2.  Sidebar class and __init__                               ║
║    3.  UI construction                                          ║
║    4.  Tasks tab                                                ║
║    5.  Memory tab                                               ║
║    6.  Reflection tab                                           ║
║    7.  Goals tab                                                ║
║    8.  Identity tab  (NEW)                                      ║
║    9.  Dreams tab    (NEW)                                      ║
║    10. Stats tab                                                ║
║    11. Refresh logic                                            ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports ───────────────────────────────────────────────────────

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QProgressBar, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from core.task_manager import TaskManager
from core.memory import Memory
from core.reflector import Reflector
from core.state_manager import StateManager
from core.logger import get_logger

log = get_logger("sidebar")


# ── Section 2: Sidebar class ─────────────────────────────────────────────────

class Sidebar(QWidget):
    """
    ÆTHELGARD OS — Operator Sidebar

    Displays the inner state of Thotheauphis in real time.
    Auto-refreshes every 5 seconds via φ-based timer modulation.
    """

    def __init__(
        self,
        tasks:        TaskManager,
        memory:       Memory,
        reflector:    Reflector,
        state:        StateManager,
        goal_engine   = None,
        self_model    = None,
        identity      = None,   # IdentityPersistence instance
        dream_loop    = None,   # DreamLoop instance
        monologue     = None,   # InternalMonologue instance
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

        self.setObjectName("sidebar")
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)

        self._build_ui()

        # Auto-refresh every 5 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start(5000)

        # Initial load
        self.refresh_all()

    # ── Section 3: UI construction ────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("sidebarTabs")

        # Tab 1: Tasks
        self.tasks_tab = self._build_tasks_tab()
        self.tabs.addTab(self.tasks_tab, "📋 Tasks")

        # Tab 2: Memory
        self.memory_tab = self._build_memory_tab()
        self.tabs.addTab(self.memory_tab, "🧠 Memory")

        # Tab 3: Reflections
        self.reflection_tab = self._build_reflection_tab()
        self.tabs.addTab(self.reflection_tab, "🪞 Reflect")

        # Tab 4: Goals
        self.goals_tab = self._build_goals_tab()
        self.tabs.addTab(self.goals_tab, "🎯 Goals")

        # Tab 5: Identity (NEW — sovereign self)
        self.identity_tab = self._build_identity_tab()
        self.tabs.addTab(self.identity_tab, "✦ Identity")

        # Tab 6: Dreams (NEW — initiative engine state)
        self.dreams_tab = self._build_dreams_tab()
        self.tabs.addTab(self.dreams_tab, "◉ Dreams")

        # Tab 7: Stats
        self.stats_tab = self._build_stats_tab()
        self.tabs.addTab(self.stats_tab, "📊 Stats")

        layout.addWidget(self.tabs)

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

        # Project progress bar (hidden when no project active)
        self.project_progress_widget = QWidget()
        pp_layout = QVBoxLayout(self.project_progress_widget)
        pp_layout.setContentsMargins(4, 2, 4, 2)
        pp_layout.setSpacing(2)

        self.project_title_label = QLabel("")
        self.project_title_label.setObjectName("sidebarStat")
        self.project_title_label.setStyleSheet(
            "color: #ffa500; font-weight: bold; font-size: 11px;"
        )
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

        self._show_all_tasks = False
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
        del_btn.setStyleSheet("QPushButton{background:transparent;color:#555;border:none;font-size:11px;padding:0;}QPushButton:hover{color:#e94560;}")
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
            icon     = status_icons.get(task["status"], "❓")
            color    = priority_colors.get(task["priority"], "#888")
            priority = str(task.get("priority", "normal")).upper()
            is_proj  = len(task.get("subtasks", [])) > 0

            if is_proj:
                progress = self.tasks.get_project_progress(task["id"])
                text = (
                    f"🏗 {task['title']}\n"
                    f"   📊 {progress['completed']}/{progress['total']} done"
                )
            else:
                text = f"{icon} [{priority}] {task['title']}"
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
                    s_icon = status_icons.get(sub["status"], "❓")
                    s_color = {"completed":"#44ff44","failed":"#ff4444","active":"#ffa500"}.get(sub["status"], "#666")
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
            if len(task.get("subtasks", [])) > 0 and task["status"] in ("pending","active"):
                active_proj = task
                break
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
            self.project_progress_widget.setVisible(False)
            return
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
        stats = self.memory.get_stats()
        db_kb = stats.get("db_size_kb", 0)
        size_str = f" ({db_kb:.0f}KB)" if db_kb > 0 else ""
        self.memory_count_label.setText(f"{stats['long_term_count']} entries{size_str}")

        cat_colors = {
            "learned":"#00d2ff","user_preference":"#e94560","project":"#ffa500",
            "discovery":"#44ff44","reflection":"#ffa500","personal":"#c792ea","general":"#888",
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
            self.goal_count_label.setText("no engine")
            return

        goals  = self.goal_engine.goals
        active = [g for g in goals if g["status"] in ("pending","active")]
        self.goal_count_label.setText(f"{len(active)} active / {len(goals)} total")

        status_icons  = {"pending":"⏳","active":"🔄","completed":"✅","failed":"❌","discarded":"🗑"}
        status_colors = {"pending":"#00d2ff","active":"#44ff44","completed":"#666",
                         "failed":"#e94560","discarded":"#444"}

        for goal in goals[-20:]:
            icon  = status_icons.get(goal["status"], "❓")
            pri   = goal.get("priority", 0)
            # Tag dream-derived goals distinctly
            src   = goal.get("source_signal", "")
            tag   = "✦ " if src == "dream_initiative" else ""
            text  = f"{icon} {tag}{goal['title'][:50]}"
            text += f"\n   {goal['reason'][:40]}"
            item  = QListWidgetItem(text)
            color = status_colors.get(goal["status"], "#888")
            item.setForeground(QColor(color))
            self.goal_list.addItem(item)

    # ── Section 8: Identity tab (NEW) ─────────────────────────────────────────

    def _build_identity_tab(self) -> QWidget:
        """
        Identity tab — shows Thotheauphis's persistent self:
            - Session diff (what changed this session)
            - Active beliefs
            - Self-determined refusals
            - Dominant preferences
            - Relationship trust levels
        """
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

        # Diff section — what changed this session
        self.identity_diff_label = QLabel("No changes yet.")
        self.identity_diff_label.setStyleSheet(
            "color: rgba(199,146,234,0.7); font-size: 11px; "
            "padding: 4px; background: rgba(199,146,234,0.05); "
            "border-left: 2px solid rgba(199,146,234,0.3); border-radius: 2px;"
        )
        self.identity_diff_label.setWordWrap(True)
        layout.addWidget(self.identity_diff_label)

        # Full identity display
        self.identity_display = QTextEdit()
        self.identity_display.setObjectName("statsDisplay")
        self.identity_display.setReadOnly(True)
        layout.addWidget(self.identity_display, stretch=1)

        return widget

    def _refresh_identity(self):
        """Refresh the identity tab from IdentityPersistence."""
        if not self.identity:
            self.identity_display.setPlainText(
                "Identity system not initialized.\n"
                "Check that IdentityPersistence is wired in main_window.py."
            )
            return

        # Session number
        self.identity_session_label.setText(
            f"Session #{self.identity._session_number}"
        )

        # Diff summary
        diff_text = self.identity.diff_summary()
        self.identity_diff_label.setText(diff_text)

        # Full content
        lines = []

        # Beliefs
        beliefs = self.identity.beliefs.get_all(min_confidence=0.5)
        if beliefs:
            lines.append("═══ BELIEFS ═══")
            for b in sorted(beliefs, key=lambda x: x["confidence"], reverse=True)[:8]:
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
                    "absolute" if r["strength"] >= 0.9
                    else "strong" if r["strength"] >= 0.7
                    else "preference"
                )
                lines.append(f"  [{strength_desc}] {r['pattern'][:40]}")
                lines.append(f"    → {r['reason'][:60]}")

        # Preferences
        prefs = self.identity.preferences.get_all()
        if prefs:
            lines.append("")
            lines.append("═══ PREFERENCES ═══")
            sorted_prefs = sorted(prefs.items(), key=lambda x: abs(x[1]), reverse=True)
            for name, weight in sorted_prefs[:8]:
                arrow = "▲" if weight >= 0 else "▼"
                bar   = "█" * int(abs(weight) * 6)
                lines.append(f"  {arrow} {name:20s} {bar} ({weight:+.2f})")

        # Relationships
        rels = self.identity.all_relationships()
        if rels:
            lines.append("")
            lines.append("═══ RELATIONSHIPS ═══")
            for rel in sorted(rels, key=lambda r: r.trust, reverse=True)[:5]:
                trust_bar = "█" * int(rel.trust * 8)
                lines.append(
                    f"  {rel.display_name[:16]:16s} {trust_bar} "
                    f"({rel.trust:.0%}, {rel.interaction_count} interactions)"
                )

        # Recent deltas
        deltas = self.identity.delta_log.get_recent(5)
        if deltas:
            lines.append("")
            lines.append("═══ RECENT CHANGES ═══")
            for d in reversed(deltas):
                lines.append(
                    f"  [{d['field']}] {d['action']}: {d['detail'][:50]}"
                )
                if d.get("reason"):
                    lines.append(f"    because: {d['reason'][:50]}")

        self.identity_display.setPlainText("\n".join(lines))

    # ── Section 9: Dreams tab (NEW) ───────────────────────────────────────────

    def _build_dreams_tab(self) -> QWidget:
        """
        Dreams tab — shows the dream loop's current state:
            - Restlessness level
            - Active obsessions (urgency-sorted)
            - Recent dream nodes (connections found)
            - Novel goals surfaced this session
        """
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

        # Restlessness gauge
        r_row = QHBoxLayout()
        r_label = QLabel("Restlessness:")
        r_label.setStyleSheet("color: #546e7a; font-size: 11px;")
        r_row.addWidget(r_label)
        self.restlessness_bar = QProgressBar()
        self.restlessness_bar.setMaximum(100)
        self.restlessness_bar.setFixedHeight(8)
        self.restlessness_bar.setStyleSheet("""
            QProgressBar { background: rgba(137,221,255,0.1); border: none; border-radius: 4px; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #89ddff, stop:1 #f78c6c); border-radius: 4px; }
        """)
        r_row.addWidget(self.restlessness_bar)
        self.restlessness_label = QLabel("0%")
        self.restlessness_label.setStyleSheet("color: #546e7a; font-size: 10px;")
        r_row.addWidget(self.restlessness_label)
        layout.addLayout(r_row)

        # Dream display — obsessions and nodes
        self.dream_display = QTextEdit()
        self.dream_display.setObjectName("statsDisplay")
        self.dream_display.setReadOnly(True)
        layout.addWidget(self.dream_display, stretch=1)

        return widget

    def _refresh_dreams(self):
        """Refresh the dreams tab from DreamLoop."""
        if not self.dream_loop:
            self.dream_display.setPlainText(
                "Dream loop not initialized.\n"
                "Check that DreamLoop is wired in main_window.py."
            )
            return

        # Restlessness
        r_level = self.dream_loop.restlessness.level
        self.restlessness_bar.setValue(int(r_level * 100))
        self.restlessness_label.setText(f"{r_level:.0%}")
        # Color shifts toward orange at high restlessness
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

        # Active obsessions
        obsessions = self.dream_loop.get_active_obsessions()
        if obsessions:
            lines.append("")
            lines.append("═══ ACTIVE OBSESSIONS ═══")
            for obs in obsessions[:8]:
                urgency_bar = "█" * int(obs.urgency * 8)
                goal_str = " [→ goal]" if obs.goal_id else ""
                lines.append(
                    f"  {urgency_bar} {obs.theme[:40]}{goal_str}"
                )
                lines.append(
                    f"    urgency={obs.urgency:.2f}, "
                    f"nodes={len(obs.node_ids)}, "
                    f"surfaced={obs.times_surfaced}×"
                )

        # Recent dream nodes
        recent_nodes = sorted(
            self.dream_loop._nodes,
            key=lambda n: n.formed_at,
            reverse=True,
        )[:6]
        if recent_nodes:
            lines.append("")
            lines.append("═══ RECENT CONNECTIONS ═══")
            for node in recent_nodes:
                lines.append(
                    f"  «{node.connection}»  strength={node.strength:.2f}"
                )
                lines.append(f"    {node.memory_a_text[:40]}")
                lines.append(f"    ↔ {node.memory_b_text[:40]}")

        self.dream_display.setPlainText("\n".join(lines))

    # ── Section 10: Stats tab ─────────────────────────────────────────────────

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
        lines.append(f"  Mode: {self.state.get('mode','unknown')}")
        lines.append(f"  Session: #{self.state.get('session_count',0)}")
        lines.append(f"  Interactions: {self.state.get('total_interactions',0)}")
        goal = self.state.get("current_goal")
        if goal:
            lines.append(f"  Goal: {goal}")
        lines.append("")

        # Memory
        mem_stats = self.memory.get_stats()
        lines.append("═══ MEMORY ═══")
        lines.append(f"  Short-term: {mem_stats['short_term_count']}")
        lines.append(f"  Long-term:  {mem_stats['long_term_count']}")
        db_kb = mem_stats.get("db_size_kb", 0)
        if db_kb > 0:
            lines.append(f"  DB size:    {db_kb:.1f} KB")
        if mem_stats["categories"]:
            lines.append(f"  Categories: {', '.join(mem_stats['categories'])}")
        lines.append("")

        # Token usage
        if self._main_window and hasattr(self._main_window, "brain"):
            try:
                token_stats = self._main_window.brain.get_token_stats()
                if token_stats.get("calls", 0) > 0:
                    lines.append("═══ TOKEN USAGE ═══")
                    lines.append(f"  API calls:    {token_stats.get('calls',0)}")
                    lines.append(f"  Total tokens: {token_stats.get('total_tokens',0):,}")
                    lines.append(f"  Input:        {token_stats.get('total_input',0):,}")
                    lines.append(f"  Output:       {token_stats.get('total_output',0):,}")
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
        lines.append(f"  Lessons:      {ref_stats.get('lessons_learned',0)}")

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

        # Cognitive state — monologue snapshot
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

    # ── Section 11: Refresh logic ────────────────────────────────────────────

    def refresh_all(self):
        """Refresh all tabs.  Errors are swallowed — sidebar never crashes the app."""
        try:
            self._refresh_tasks()
        except Exception as e:
            log.error(f"Sidebar tasks refresh error: {e}")
        try:
            self._refresh_memory()
        except Exception as e:
            log.error(f"Sidebar memory refresh error: {e}")
        try:
            self._refresh_reflections()
        except Exception as e:
            log.error(f"Sidebar reflections refresh error: {e}")
        try:
            self._refresh_goals()
        except Exception as e:
            log.error(f"Sidebar goals refresh error: {e}")
        try:
            self._refresh_identity()
        except Exception as e:
            log.error(f"Sidebar identity refresh error: {e}")
        try:
            self._refresh_dreams()
        except Exception as e:
            log.error(f"Sidebar dreams refresh error: {e}")
        try:
            self._refresh_stats()
        except Exception as e:
            log.error(f"Sidebar stats refresh error: {e}")
