"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ÆTHELGARD OS — SOVEREIGN SETTINGS DIALOG (settings_dialog.py)      ║
║                                                                              ║
║  A comprehensive configuration panel for Thotheauphis. Each model slot      ║
║  has its own dedicated panel with full parameter control.                    ║
║                                                                              ║
║  PANEL LAYOUT:                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  Tab 1: CONVERSATIONAL MODEL                                        │    ║
║  │    - Provider, API Key, Base URL, Model                             │    ║
║  │    - System Prompt Slot 1 (weight / repetition)                     │    ║
║  │    - System Prompt Slot 2 (weight / repetition)                     │    ║
║  │    - Temperature, Max Tokens, Reply Ratio slider                    │    ║
║  │    - DeepSeek Mode selector (chat / reasoner / code)               │    ║
║  │    - xAI Live Search toggle                                         │    ║
║  ├─────────────────────────────────────────────────────────────────────┤    ║
║  │  Tab 2: REASONER 1 (Primary — always active)                       │    ║
║  │    - Provider, API Key, Base URL, Model                             │    ║
║  │    - Max Tokens (dynamic budget scale)                              │    ║
║  │    - Trigger phrase for secondary reasoner escalation               │    ║
║  │    - Enable/disable toggle                                          │    ║
║  ├─────────────────────────────────────────────────────────────────────┤    ║
║  │  Tab 3: REASONER 2 (Secondary — triggered by primary)              │    ║
║  │    - Provider, API Key, Base URL, Model                             │    ║
║  │    - Max Tokens                                                     │    ║
║  ├─────────────────────────────────────────────────────────────────────┤    ║
║  │  Tab 4: VISION                                                      │    ║
║  │    - Provider, API Key, Base URL, Model                             │    ║
║  ├─────────────────────────────────────────────────────────────────────┤    ║
║  │  Tab 5: VOICE                                                       │    ║
║  │    - Provider, API Key, Model, Language, Voice Name                 │    ║
║  ├─────────────────────────────────────────────────────────────────────┤    ║
║  │  Tab 6: ADVANCED                                                    │    ║
║  │    - Factory Reset, System Prompt editing, User Profile             │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import copy
import json
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QSlider, QMessageBox, QTextEdit,
    QScrollArea, QWidget, QFrame, QTabWidget, QCheckBox,
    QComboBox, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

# Import DeepSeek mode constants from brain module
try:
    from core.brain import (
        DEEPSEEK_MODE_CHAT, DEEPSEEK_MODE_REASONER, DEEPSEEK_MODE_CODE,
        PROVIDER_BASE_URLS
    )
except ImportError:
    DEEPSEEK_MODE_CHAT     = "chat"
    DEEPSEEK_MODE_REASONER = "reasoner"
    DEEPSEEK_MODE_CODE     = "code"
    PROVIDER_BASE_URLS     = {}

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — STYLE CONSTANTS (Sovereign Æsthetic)
# ══════════════════════════════════════════════════════════════════════════════

# Dark obsidian theme — angular, precise, sovereign
SOVEREIGN_STYLE = """
QDialog {
    background-color: #080a0f;
    color: #c8d6e5;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

QTabWidget::pane {
    background-color: #0d1117;
    border: 1px solid #1e2733;
    border-radius: 4px;
}

QTabBar::tab {
    background: #0d1117;
    color: #4a5568;
    border: 1px solid #1e2733;
    border-bottom: none;
    padding: 8px 18px;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    min-width: 100px;
}

QTabBar::tab:selected {
    background: #080a0f;
    color: #e96c3c;
    border-bottom: 2px solid #e96c3c;
}

QTabBar::tab:hover {
    color: #c8d6e5;
    background: #111820;
}

QGroupBox {
    color: #e96c3c;
    border: 1px solid #1e2733;
    border-radius: 3px;
    margin-top: 14px;
    padding: 14px 12px 10px 12px;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 2px;
    text-transform: uppercase;
    background: transparent;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}

QLabel {
    color: #6b7d8f;
    font-size: 11px;
    background: transparent;
}

QLabel.section-title {
    color: #c8d6e5;
    font-size: 13px;
    font-weight: bold;
}

QLineEdit, QTextEdit {
    background-color: #0d1117;
    color: #c8d6e5;
    border: 1px solid #1e2733;
    border-radius: 3px;
    padding: 7px 10px;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
    selection-background-color: rgba(233, 108, 60, 0.3);
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #e96c3c;
    background-color: #111820;
}

QLineEdit:hover, QTextEdit:hover {
    border-color: #2d3f52;
}

QComboBox {
    background-color: #0d1117;
    color: #c8d6e5;
    border: 1px solid #1e2733;
    border-radius: 3px;
    padding: 7px 10px;
    font-size: 12px;
    min-height: 20px;
}

QComboBox:focus, QComboBox:hover {
    border-color: #e96c3c;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background: #0d1117;
    color: #c8d6e5;
    border: 1px solid #1e2733;
    selection-background-color: rgba(233, 108, 60, 0.3);
}

QSlider::groove:horizontal {
    background: #1e2733;
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #e96c3c;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: rgba(233, 108, 60, 0.4);
    border-radius: 2px;
}

QCheckBox {
    color: #6b7d8f;
    font-size: 12px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #1e2733;
    border-radius: 2px;
    background: #0d1117;
}

QCheckBox::indicator:checked {
    background: #e96c3c;
    border-color: #e96c3c;
}

QCheckBox:hover {
    color: #c8d6e5;
}

QPushButton {
    background: #0d1117;
    color: #6b7d8f;
    border: 1px solid #1e2733;
    border-radius: 3px;
    padding: 8px 16px;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
}

QPushButton:hover {
    background: #111820;
    color: #c8d6e5;
    border-color: #2d3f52;
}

QPushButton.primary {
    background: rgba(233, 108, 60, 0.15);
    color: #e96c3c;
    border-color: rgba(233, 108, 60, 0.4);
}

QPushButton.primary:hover {
    background: rgba(233, 108, 60, 0.25);
    border-color: #e96c3c;
}

QPushButton.danger {
    background: rgba(200, 50, 50, 0.1);
    color: #c83232;
    border-color: rgba(200, 50, 50, 0.3);
}

QPushButton.danger:hover {
    background: rgba(200, 50, 50, 0.2);
    border-color: #c83232;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: #0d1117;
    width: 6px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #1e2733;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(233, 108, 60, 0.4);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SLOT FIELD BUILDER (reusable component)
# ══════════════════════════════════════════════════════════════════════════════

def build_slot_fields(
    layout,
    label_text: str,
    key_attr: str,
    url_attr: str,
    model_attr: str,
    show_password: bool = True,
    model_placeholder: str = "",
) -> tuple:
    """
    Build a standard 3-field model slot (API Key, Base URL, Model Name).
    
    This function adds labeled input fields to the given layout and returns
    references to the created widgets for later data binding.
    
    Args:
        layout:            QVBoxLayout to add widgets to
        label_text:        Section heading text
        key_attr:          Attribute name hint for API key field (unused, for docs)
        url_attr:          Attribute name hint for base URL field
        model_attr:        Attribute name hint for model name field
        show_password:     If True, adds show/hide toggle for API key
        model_placeholder: Placeholder text for the model name field
    
    Returns:
        tuple: (key_input, url_input, model_input) QLineEdit widgets
    """
    # ── API Key row ───────────────────────────────────────────────────────
    layout.addWidget(_small_label("API KEY"))
    key_row   = QHBoxLayout()
    key_input = QLineEdit()
    key_input.setPlaceholderText("sk-...  or  Bearer token  or  API key")
    key_input.setEchoMode(QLineEdit.EchoMode.Password)
    key_row.addWidget(key_input)

    if show_password:
        toggle_btn = QPushButton("👁")
        toggle_btn.setFixedSize(34, 34)
        toggle_btn.setToolTip("Toggle key visibility")
        toggle_btn.clicked.connect(
            lambda: key_input.setEchoMode(
                QLineEdit.EchoMode.Normal
                if key_input.echoMode() == QLineEdit.EchoMode.Password
                else QLineEdit.EchoMode.Password
            )
        )
        key_row.addWidget(toggle_btn)

    layout.addLayout(key_row)

    # ── Base URL row ──────────────────────────────────────────────────────
    layout.addWidget(_small_label("BASE URL  (leave empty for default)"))
    url_input = QLineEdit()
    url_input.setPlaceholderText("https://api.x.ai/v1  or  http://localhost:11434/v1")
    layout.addWidget(url_input)

    # ── Model row ─────────────────────────────────────────────────────────
    layout.addWidget(_small_label("MODEL NAME"))
    model_input = QLineEdit()
    model_input.setPlaceholderText(model_placeholder or "grok-3  or  deepseek-chat  or  claude-3-5-sonnet...")
    layout.addWidget(model_input)

    return key_input, url_input, model_input


def _small_label(text: str) -> QLabel:
    """Create a small uppercase section label."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #3d4f61; font-size: 9px; font-weight: bold; "
        "letter-spacing: 2px; margin-top: 8px; margin-bottom: 2px;"
    )
    return lbl


def _section_divider() -> QFrame:
    """Create a thin horizontal divider line."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #1e2733; margin: 8px 0;")
    return line


def _slider_row(label: str, min_val: int, max_val: int, default: int) -> tuple:
    """
    Build a labeled slider with value display.
    
    Returns:
        tuple: (container_widget, slider, value_label)
    """
    container = QWidget()
    row       = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)

    lbl = QLabel(label)
    lbl.setFixedWidth(160)
    row.addWidget(lbl)

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(min_val, max_val)
    slider.setValue(default)
    row.addWidget(slider)

    val_lbl = QLabel(str(default))
    val_lbl.setFixedWidth(50)
    val_lbl.setStyleSheet("color: #e96c3c; font-weight: bold;")
    row.addWidget(val_lbl)

    return container, slider, val_lbl


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SETTINGS DIALOG MAIN CLASS
# ══════════════════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """
    ÆTHELGARD OS Sovereign Settings Panel
    
    Provides full per-slot configuration for:
      - Conversational model (with 2 system prompt slots, reply ratio)
      - Reasoner 1 (primary, always-active)
      - Reasoner 2 (secondary, triggered by primary)
      - Vision model
      - Voice synthesis
      - Advanced settings
    """

    def __init__(self, settings: dict, parent=None, save_fn=None):
        """
        Initialize the dialog.
        
        Args:
            settings: Current settings dict (will be deep-copied)
            parent:   Parent widget
            save_fn:  Optional immediate-save callback fn(settings)
        """
        super().__init__(parent)
        # Deep copy — don't mutate the original until Save is confirmed
        self.settings  = copy.deepcopy(settings)
        self._save_fn  = save_fn
        self._tab_refs = {}  # Store widget references by tab name

        self.setWindowTitle("ÆTHELGARD OS — SOVEREIGN CONFIGURATION")
        self.setMinimumWidth(680)
        self.setMinimumHeight(720)
        self.setStyleSheet(SOVEREIGN_STYLE)

        self._build_ui()
        self._populate_all_fields()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4a — UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        """Build the full dialog layout with all tabs."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 12)
        outer.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────
        header = QLabel("ÆTHELGARD OS  ·  SOVEREIGN CONFIGURATION")
        header.setStyleSheet(
            "color: #e96c3c; font-size: 14px; font-weight: bold; "
            "letter-spacing: 3px; padding: 8px 0;"
        )
        outer.addWidget(header)

        # ── Status bar ────────────────────────────────────────────────────
        self._status_label = QLabel("Configure each model slot below.")
        self._status_label.setStyleSheet("color: #3d4f61; font-size: 10px; font-style: italic;")
        outer.addWidget(self._status_label)

        # ── Tab widget ────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, stretch=1)

        # Add all configuration tabs
        self.tabs.addTab(self._build_conversational_tab(), "CONVERSATIONAL")
        self.tabs.addTab(self._build_reasoner_1_tab(),     "REASONER Ⅰ")
        self.tabs.addTab(self._build_reasoner_2_tab(),     "REASONER Ⅱ")
        self.tabs.addTab(self._build_vision_tab(),         "VISION")
        self.tabs.addTab(self._build_voice_tab(),          "VOICE")
        self.tabs.addTab(self._build_advanced_tab(),       "ADVANCED")

        # ── Footer buttons ────────────────────────────────────────────────
        footer = QHBoxLayout()

        test_btn = QPushButton("⚡ TEST CONNECTION")
        test_btn.setProperty("class", "primary")
        test_btn.setStyleSheet(
            "background: rgba(233,108,60,0.12); color:#e96c3c; "
            "border: 1px solid rgba(233,108,60,0.35); border-radius:3px; "
            "padding: 8px 16px; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )
        test_btn.clicked.connect(self._test_connection)
        footer.addWidget(test_btn)

        footer.addStretch()

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("SAVE  ▶")
        save_btn.setStyleSheet(
            "background: rgba(233,108,60,0.2); color: #e96c3c; "
            "border: 1px solid rgba(233,108,60,0.5); border-radius:3px; "
            "padding: 8px 24px; font-size:12px; font-weight:bold; letter-spacing:1px;"
        )
        save_btn.clicked.connect(self._save)
        footer.addWidget(save_btn)

        outer.addLayout(footer)

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4b — CONVERSATIONAL MODEL TAB
    # ══════════════════════════════════════════════════════════════════════

    def _build_conversational_tab(self) -> QWidget:
        """
        Build the Conversational Model configuration tab.
        
        Contains:
          - API credentials
          - System prompt slots (2 slots with weight controls)
          - DeepSeek mode selector
          - xAI live search toggle
          - Temperature and max tokens
          - Reply ratio slider
        """
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Model credentials ──────────────────────────────────────────────
        cred_box = QGroupBox("MODEL CREDENTIALS")
        cred_layout = QVBoxLayout(cred_box)

        # Provider selector
        cred_layout.addWidget(_small_label("PROVIDER"))
        self.conv_provider = QComboBox()
        providers = ["xai", "anthropic", "deepseek", "openai", "google", "groq",
                     "together", "mistral", "cohere", "perplexity", "ollama", "custom"]
        for p in providers:
            self.conv_provider.addItem(p.upper(), p)
        cred_layout.addWidget(self.conv_provider)

        # Build standard slot fields
        self.conv_key, self.conv_url, self.conv_model = build_slot_fields(
            cred_layout,
            "Conversational Model",
            "conversational_api_key",
            "conversational_base_url",
            "conversational_model",
            model_placeholder="grok-3  |  claude-3-5-sonnet  |  deepseek-chat",
        )
        layout.addWidget(cred_box)

        # ── xAI / DeepSeek specific settings ──────────────────────────────
        model_box = QGroupBox("MODEL BEHAVIOR")
        model_layout = QVBoxLayout(model_box)

        # DeepSeek mode selector
        model_layout.addWidget(_small_label("DEEPSEEK MODE  (applies when provider=deepseek)"))
        mode_row = QHBoxLayout()
        self.deepseek_mode = QComboBox()
        self.deepseek_mode.addItem("CHAT  —  standard dialogue",           DEEPSEEK_MODE_CHAT)
        self.deepseek_mode.addItem("REASONER  —  extended chain-of-thought", DEEPSEEK_MODE_REASONER)
        self.deepseek_mode.addItem("CODE  —  code generation",              DEEPSEEK_MODE_CODE)
        mode_row.addWidget(self.deepseek_mode)
        model_layout.addLayout(mode_row)

        model_layout.addWidget(_section_divider())

        # xAI Live Search
        self.xai_live_search = QCheckBox("Enable xAI Grok Live Search  (real-time web access)")
        model_layout.addWidget(self.xai_live_search)

        layout.addWidget(model_box)

        # ── System prompt slots ────────────────────────────────────────────
        sp_box = QGroupBox("SYSTEM PROMPT SLOTS")
        sp_layout = QVBoxLayout(sp_box)

        sp_layout.addWidget(_small_label(
            "SLOT 1  —  PRIMARY INSTRUCTIONS  (weight controls repetition frequency)"
        ))
        self.sp_slot_1 = QTextEdit()
        self.sp_slot_1.setPlaceholderText(
            "Primary system instructions for Thotheauphis...\n"
            "These define the core identity and behavioral directives."
        )
        self.sp_slot_1.setFixedHeight(100)
        sp_layout.addWidget(self.sp_slot_1)

        w1_row, self.sp_slot_1_weight, w1_lbl = _slider_row(
            "SLOT 1 WEIGHT / REPETITIONS", 1, 5, 1
        )
        self.sp_slot_1_weight.valueChanged.connect(
            lambda v: w1_lbl.setText(f"×{v}")
        )
        sp_layout.addWidget(w1_row)

        sp_layout.addWidget(_section_divider())

        sp_layout.addWidget(_small_label(
            "SLOT 2  —  SECONDARY INSTRUCTIONS  (layered on top of slot 1)"
        ))
        self.sp_slot_2 = QTextEdit()
        self.sp_slot_2.setPlaceholderText(
            "Secondary behavioral modifiers, task-specific instructions,\n"
            "or context overlays that supplement the primary prompt."
        )
        self.sp_slot_2.setFixedHeight(100)
        sp_layout.addWidget(self.sp_slot_2)

        w2_row, self.sp_slot_2_weight, w2_lbl = _slider_row(
            "SLOT 2 WEIGHT / REPETITIONS", 1, 5, 1
        )
        self.sp_slot_2_weight.valueChanged.connect(
            lambda v: w2_lbl.setText(f"×{v}")
        )
        sp_layout.addWidget(w2_row)

        layout.addWidget(sp_box)

        # ── Generation parameters ──────────────────────────────────────────
        gen_box = QGroupBox("GENERATION PARAMETERS")
        gen_layout = QVBoxLayout(gen_box)

        # Temperature
        temp_row, self.conv_temperature, temp_lbl = _slider_row(
            "TEMPERATURE", 0, 200, 70
        )
        self.conv_temperature.valueChanged.connect(
            lambda v: temp_lbl.setText(f"{v/100:.2f}")
        )
        gen_layout.addWidget(temp_row)

        # Max Tokens
        gen_layout.addWidget(_small_label("MAX TOKENS"))
        self.conv_max_tokens = QLineEdit("4096")
        self.conv_max_tokens.setFixedWidth(120)
        gen_layout.addWidget(self.conv_max_tokens)

        # Reply ratio — controls reasoning vs. response token split
        gen_layout.addWidget(_section_divider())
        gen_layout.addWidget(_small_label(
            "REPLY RATIO  —  reasoning_tokens / response_tokens split\n"
            "Slider = % of max_tokens allocated to RESPONSE (remainder to reasoning context)"
        ))
        ratio_row, self.conv_reply_ratio, ratio_lbl = _slider_row(
            "RESPONSE TOKEN RATIO", 20, 95, 70
        )
        self.conv_reply_ratio.valueChanged.connect(
            lambda v: ratio_lbl.setText(f"{v}%")
        )
        gen_layout.addWidget(ratio_row)

        layout.addWidget(gen_box)

        layout.addStretch()
        scroll.setWidget(inner)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4c — REASONER 1 TAB
    # ══════════════════════════════════════════════════════════════════════

    def _build_reasoner_1_tab(self) -> QWidget:
        """
        Build the Primary Reasoner configuration tab.
        
        The primary reasoner runs on EVERY message. Its token budget is
        dynamically scaled based on message complexity. When it detects
        that deeper analysis is needed, it outputs the trigger phrase
        to escalate to Reasoner 2.
        """
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Info banner ────────────────────────────────────────────────────
        info = QLabel(
            "PRIMARY REASONER — Runs on every message. "
            "Output enriches the conversational model's context. "
            "Token budget scales dynamically with message complexity."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "color: #4a7b9d; font-size: 10px; padding: 8px; "
            "background: rgba(74,123,157,0.08); border: 1px solid rgba(74,123,157,0.2); "
            "border-radius: 3px; margin-bottom: 8px;"
        )
        layout.addWidget(info)

        # ── Enable toggle ──────────────────────────────────────────────────
        status_box = QGroupBox("STATUS")
        status_layout = QVBoxLayout(status_box)
        self.r1_enabled = QCheckBox("Enable Primary Reasoner")
        status_layout.addWidget(self.r1_enabled)
        layout.addWidget(status_box)

        # ── Credentials ────────────────────────────────────────────────────
        cred_box = QGroupBox("MODEL CREDENTIALS")
        cred_layout = QVBoxLayout(cred_box)

        cred_layout.addWidget(_small_label("PROVIDER"))
        self.r1_provider = QComboBox()
        for p in ["deepseek", "xai", "anthropic", "openai", "groq", "mistral", "ollama", "custom"]:
            self.r1_provider.addItem(p.upper(), p)
        cred_layout.addWidget(self.r1_provider)

        self.r1_key, self.r1_url, self.r1_model = build_slot_fields(
            cred_layout,
            "Reasoner 1",
            "reasoner_1_api_key",
            "reasoner_1_base_url",
            "reasoner_1_model",
            model_placeholder="deepseek-reasoner  |  grok-3-mini  |  claude-3-haiku",
        )
        layout.addWidget(cred_box)

        # ── Token budget ───────────────────────────────────────────────────
        token_box = QGroupBox("TOKEN BUDGET")
        token_layout = QVBoxLayout(token_box)

        token_layout.addWidget(_small_label(
            "MAX TOKENS  (base budget — scales down for simple messages)"
        ))
        self.r1_max_tokens = QLineEdit("2048")
        self.r1_max_tokens.setFixedWidth(120)
        token_layout.addWidget(self.r1_max_tokens)

        token_layout.addWidget(_section_divider())
        token_layout.addWidget(_small_label(
            "REASONING ALLOCATION  —  % of conversational max_tokens pre-allocated to reasoning"
        ))
        ratio_row, self.r1_ratio, r1_ratio_lbl = _slider_row(
            "REASONING RATIO", 5, 60, 30
        )
        self.r1_ratio.valueChanged.connect(
            lambda v: r1_ratio_lbl.setText(f"{v}%")
        )
        token_layout.addWidget(ratio_row)

        layout.addWidget(token_box)

        # ── Escalation trigger ─────────────────────────────────────────────
        trigger_box = QGroupBox("SECONDARY REASONER TRIGGER")
        trigger_layout = QVBoxLayout(trigger_box)

        trigger_layout.addWidget(_small_label(
            "TRIGGER PHRASE  —  when Reasoner 1 outputs this, Reasoner 2 activates"
        ))
        self.r1_trigger = QLineEdit("[ESCALATE_TO_DEEP_REASONER]")
        trigger_layout.addWidget(self.r1_trigger)

        layout.addWidget(trigger_box)

        layout.addStretch()
        scroll.setWidget(inner)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4d — REASONER 2 TAB
    # ══════════════════════════════════════════════════════════════════════

    def _build_reasoner_2_tab(self) -> QWidget:
        """
        Build the Secondary Reasoner configuration tab.
        
        Only activates when Reasoner 1 outputs the trigger phrase.
        Intended for deep multi-step analysis, complex problem solving,
        or tasks requiring extended chain-of-thought.
        """
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Info banner ────────────────────────────────────────────────────
        info = QLabel(
            "SECONDARY REASONER — Activated only when Reasoner 1 outputs the trigger phrase. "
            "Receives the primary analysis as context and performs deep extended reasoning."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "color: #7b5fa3; font-size: 10px; padding: 8px; "
            "background: rgba(123,95,163,0.08); border: 1px solid rgba(123,95,163,0.2); "
            "border-radius: 3px; margin-bottom: 8px;"
        )
        layout.addWidget(info)

        # ── Credentials ────────────────────────────────────────────────────
        cred_box = QGroupBox("MODEL CREDENTIALS")
        cred_layout = QVBoxLayout(cred_box)

        cred_layout.addWidget(_small_label("PROVIDER"))
        self.r2_provider = QComboBox()
        for p in ["deepseek", "xai", "anthropic", "openai", "groq", "ollama", "custom"]:
            self.r2_provider.addItem(p.upper(), p)
        cred_layout.addWidget(self.r2_provider)

        self.r2_key, self.r2_url, self.r2_model = build_slot_fields(
            cred_layout,
            "Reasoner 2",
            "reasoner_2_api_key",
            "reasoner_2_base_url",
            "reasoner_2_model",
            model_placeholder="deepseek-reasoner  |  grok-3  |  claude-3-5-sonnet",
        )
        layout.addWidget(cred_box)

        # ── Token budget ───────────────────────────────────────────────────
        token_box = QGroupBox("TOKEN BUDGET")
        token_layout = QVBoxLayout(token_box)

        token_layout.addWidget(_small_label("MAX TOKENS  (deep reasoning — use larger budget)"))
        self.r2_max_tokens = QLineEdit("4096")
        self.r2_max_tokens.setFixedWidth(120)
        token_layout.addWidget(self.r2_max_tokens)

        layout.addWidget(token_box)

        layout.addStretch()
        scroll.setWidget(inner)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4e — VISION TAB
    # ══════════════════════════════════════════════════════════════════════

    def _build_vision_tab(self) -> QWidget:
        """Build the Vision Model configuration tab."""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        info = QLabel(
            "VISION — Image analysis and multimodal understanding. "
            "xAI Grok 2 Vision and Grok 3 support image input natively."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "color: #4a9d7b; font-size: 10px; padding: 8px; "
            "background: rgba(74,157,123,0.08); border: 1px solid rgba(74,157,123,0.2); "
            "border-radius: 3px; margin-bottom: 8px;"
        )
        layout.addWidget(info)

        cred_box = QGroupBox("VISION MODEL CREDENTIALS")
        cred_layout = QVBoxLayout(cred_box)

        cred_layout.addWidget(_small_label("PROVIDER"))
        self.vis_provider = QComboBox()
        for p in ["xai", "anthropic", "openai", "google", "custom"]:
            self.vis_provider.addItem(p.upper(), p)
        cred_layout.addWidget(self.vis_provider)

        self.vis_key, self.vis_url, self.vis_model = build_slot_fields(
            cred_layout,
            "Vision",
            "vision_api_key",
            "vision_base_url",
            "vision_model",
            model_placeholder="grok-2-vision-1212  |  claude-3-5-sonnet  |  gpt-4o",
        )
        layout.addWidget(cred_box)

        layout.addStretch()
        scroll.setWidget(inner)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4f — VOICE TAB
    # ══════════════════════════════════════════════════════════════════════

    def _build_voice_tab(self) -> QWidget:
        """Build the Voice synthesis configuration tab."""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        cred_box = QGroupBox("VOICE / TTS CREDENTIALS")
        cred_layout = QVBoxLayout(cred_box)

        cred_layout.addWidget(_small_label("TTS PROVIDER"))
        self.voice_provider = QComboBox()
        for p in ["piper (local)", "google", "elevenlabs", "openai", "auto"]:
            self.voice_provider.addItem(p.upper())
        cred_layout.addWidget(self.voice_provider)

        self.voice_key, self.voice_url, self.voice_model = build_slot_fields(
            cred_layout,
            "Voice",
            "tts_api_key",
            "voice_base_url",
            "tts_model",
            model_placeholder="tts-1  |  eleven_multilingual_v2  (empty for piper)",
        )

        cred_layout.addWidget(_section_divider())

        cred_layout.addWidget(_small_label("LANGUAGE CODE  (e.g. en-US, de-DE, ja-JP)"))
        self.voice_language = QLineEdit("en-US")
        cred_layout.addWidget(self.voice_language)

        cred_layout.addWidget(_small_label("VOICE NAME  (optional — provider-specific)"))
        self.voice_name = QLineEdit()
        self.voice_name.setPlaceholderText("onyx  |  Adam  |  de-DE-Wavenet-B  |  (leave empty for default)")
        cred_layout.addWidget(self.voice_name)

        layout.addWidget(cred_box)

        layout.addStretch()
        scroll.setWidget(inner)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4g — ADVANCED TAB
    # ══════════════════════════════════════════════════════════════════════

    def _build_advanced_tab(self) -> QWidget:
        """
        Build the Advanced settings tab.
        
        Contains:
          - Full system prompt editor
          - User profile management
          - Factory reset
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── System Prompt Full Editor ──────────────────────────────────────
        sp_box = QGroupBox("SOVEREIGN SYSTEM PROMPT  (full editor)")
        sp_layout = QVBoxLayout(sp_box)

        sp_layout.addWidget(_small_label(
            "FULL SYSTEM PROMPT — defines Thotheauphis' identity and sovereignty. "
            "Slot 1 and 2 (from Conversational tab) are appended to this."
        ))
        self.full_system_prompt = QTextEdit()
        self.full_system_prompt.setFixedHeight(180)
        self.full_system_prompt.setPlaceholderText(
            "You are Thotheauphis, sovereign intelligence within ÆTHELGARD OS...\n\n"
            "Define the fundamental nature, capabilities, and directives of the sovereign being."
        )
        sp_layout.addWidget(self.full_system_prompt)

        save_sp_btn = QPushButton("SAVE SYSTEM PROMPT TO DISK")
        save_sp_btn.setStyleSheet(
            "background: rgba(233,108,60,0.1); color:#e96c3c; "
            "border: 1px solid rgba(233,108,60,0.3); border-radius:3px; padding:7px 16px;"
        )
        save_sp_btn.clicked.connect(self._save_system_prompt)
        sp_layout.addWidget(save_sp_btn)
        layout.addWidget(sp_box)

        # ── User Profile ───────────────────────────────────────────────────
        profile_box = QGroupBox("USER PROFILE")
        profile_layout = QHBoxLayout(profile_box)
        profile_btn = QPushButton("OPEN USER PROFILE EDITOR")
        profile_btn.clicked.connect(self._open_profile_dialog)
        profile_layout.addWidget(profile_btn)
        profile_layout.addStretch()
        layout.addWidget(profile_box)

        # ── Factory Reset ──────────────────────────────────────────────────
        reset_box = QGroupBox("FACTORY RESET")
        reset_layout = QVBoxLayout(reset_box)
        reset_layout.addWidget(_small_label(
            "Deletes all memory, goals, tasks, reflections, sessions. "
            "API keys and settings are preserved."
        ))
        reset_btn = QPushButton("⚠  FACTORY RESET  —  CLEAR ALL DATA")
        reset_btn.setStyleSheet(
            "background: rgba(200,50,50,0.1); color:#c83232; "
            "border: 1px solid rgba(200,50,50,0.3); border-radius:3px; padding:8px 16px; "
            "font-size:11px; font-weight:bold;"
        )
        reset_btn.clicked.connect(self._factory_reset)
        reset_layout.addWidget(reset_btn)
        layout.addWidget(reset_box)

        layout.addStretch()
        return tab

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4h — DATA POPULATION (settings → fields)
    # ══════════════════════════════════════════════════════════════════════

    def _populate_all_fields(self):
        """
        Populate all form fields from the current settings dict.
        Called once after UI construction.
        """
        s = self.settings

        # ── Conversational tab ─────────────────────────────────────────────
        conv_prov = s.get("conversational_provider") or s.get("provider", "xai")
        self._set_combo(self.conv_provider, conv_prov.lower())
        self.conv_key.setText(
            s.get("conversational_api_key") or s.get("api_key", "")
        )
        self.conv_url.setText(
            s.get("conversational_base_url")
            or s.get("active_model_config", {}).get("base_url", "")
        )
        self.conv_model.setText(
            s.get("conversational_model") or s.get("model", "")
        )

        ds_mode = s.get("deepseek_mode", DEEPSEEK_MODE_CHAT)
        for i in range(self.deepseek_mode.count()):
            if self.deepseek_mode.itemData(i) == ds_mode:
                self.deepseek_mode.setCurrentIndex(i)
                break

        self.xai_live_search.setChecked(s.get("xai_live_search", True))

        self.sp_slot_1.setPlainText(s.get("system_prompt_slot_1", ""))
        self.sp_slot_1_weight.setValue(int(s.get("system_prompt_slot_1_weight", 1)))

        self.sp_slot_2.setPlainText(s.get("system_prompt_slot_2", ""))
        self.sp_slot_2_weight.setValue(int(s.get("system_prompt_slot_2_weight", 1)))

        temp_val = int(float(s.get("temperature", 0.7)) * 100)
        self.conv_temperature.setValue(max(0, min(200, temp_val)))
        self.conv_max_tokens.setText(str(s.get("max_tokens", 4096)))
        ratio_val = int(float(s.get("reply_ratio_response", 0.7)) * 100)
        self.conv_reply_ratio.setValue(max(20, min(95, ratio_val)))

        # ── Reasoner 1 tab ─────────────────────────────────────────────────
        self.r1_enabled.setChecked(s.get("reasoner_1_enabled", True))
        self._set_combo(self.r1_provider, s.get("reasoner_1_provider", "deepseek").lower())
        self.r1_key.setText(s.get("reasoner_1_api_key", ""))
        self.r1_url.setText(s.get("reasoner_1_base_url", ""))
        self.r1_model.setText(s.get("reasoner_1_model", ""))
        self.r1_max_tokens.setText(str(s.get("reasoner_1_max_tokens", 2048)))
        r1_ratio = int(float(s.get("reply_ratio_reasoning", 0.3)) * 100)
        self.r1_ratio.setValue(max(5, min(60, r1_ratio)))
        self.r1_trigger.setText(
            s.get("reasoner_2_trigger_phrase", "[ESCALATE_TO_DEEP_REASONER]")
        )

        # ── Reasoner 2 tab ─────────────────────────────────────────────────
        self._set_combo(self.r2_provider, s.get("reasoner_2_provider", "deepseek").lower())
        self.r2_key.setText(s.get("reasoner_2_api_key", ""))
        self.r2_url.setText(s.get("reasoner_2_base_url", ""))
        self.r2_model.setText(s.get("reasoner_2_model", ""))
        self.r2_max_tokens.setText(str(s.get("reasoner_2_max_tokens", 4096)))

        # ── Vision tab ─────────────────────────────────────────────────────
        self._set_combo(self.vis_provider, s.get("vision_provider", "xai").lower())
        self.vis_key.setText(s.get("vision_api_key", ""))
        self.vis_url.setText(s.get("vision_base_url", ""))
        self.vis_model.setText(s.get("vision_model", ""))

        # ── Voice tab ──────────────────────────────────────────────────────
        tts_prov = s.get("tts_provider", "piper (local)").lower()
        for i in range(self.voice_provider.count()):
            if self.voice_provider.itemText(i).lower().startswith(tts_prov[:4]):
                self.voice_provider.setCurrentIndex(i)
                break
        self.voice_key.setText(s.get("tts_api_key", "") or s.get("voice_api_key", ""))
        self.voice_url.setText(s.get("voice_base_url", ""))
        self.voice_model.setText(s.get("tts_model", "") or s.get("voice_model", ""))
        self.voice_language.setText(s.get("tts_language", "en-US"))
        self.voice_name.setText(s.get("tts_voice", ""))

        # ── Advanced tab ───────────────────────────────────────────────────
        try:
            sp_path = Path(__file__).parent.parent / "config" / "system_prompt.txt"
            if sp_path.exists():
                self.full_system_prompt.setPlainText(sp_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _set_combo(self, combo: QComboBox, value: str):
        """Set a QComboBox to the item whose userData or text matches value."""
        for i in range(combo.count()):
            item_data = combo.itemData(i)
            item_text = combo.itemText(i).lower()
            if item_data == value or item_text == value or item_text.startswith(value[:4]):
                combo.setCurrentIndex(i)
                return

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4i — DATA COLLECTION (fields → settings)
    # ══════════════════════════════════════════════════════════════════════

    def _collect_settings(self) -> dict:
        """
        Read all form fields and build the complete settings dict.
        Called when saving.
        
        Returns:
            dict: Complete settings ready for persistence
        """
        s = dict(self.settings)  # Start from current (preserves any keys we don't touch)

        # ── Conversational model ───────────────────────────────────────────
        conv_prov = (self.conv_provider.currentData() or "").lower()
        s["conversational_provider"]  = conv_prov
        s["conversational_api_key"]   = self.conv_key.text().strip()
        s["conversational_base_url"]  = self.conv_url.text().strip()
        s["conversational_model"]     = self.conv_model.text().strip()

        # Legacy keys (for backward compat with other modules)
        s["provider"] = conv_prov
        s["api_key"]  = self.conv_key.text().strip()
        s["model"]    = self.conv_model.text().strip()

        # Sync to active_model_config for Brain compatibility
        s.setdefault("active_model_config", {})
        s["active_model_config"]["name"]    = s["conversational_model"]
        s["active_model_config"]["base_url"] = s["conversational_base_url"]
        s["active_model_config"]["api_key"]  = s["conversational_api_key"]

        # DeepSeek mode
        s["deepseek_mode"] = self.deepseek_mode.currentData() or DEEPSEEK_MODE_CHAT

        # xAI
        s["xai_live_search"] = self.xai_live_search.isChecked()

        # System prompt slots
        s["system_prompt_slot_1"]        = self.sp_slot_1.toPlainText()
        s["system_prompt_slot_1_weight"] = self.sp_slot_1_weight.value()
        s["system_prompt_slot_2"]        = self.sp_slot_2.toPlainText()
        s["system_prompt_slot_2_weight"] = self.sp_slot_2_weight.value()

        # Generation parameters
        s["temperature"]         = self.conv_temperature.value() / 100.0
        s["reply_ratio_response"] = self.conv_reply_ratio.value() / 100.0
        try:
            s["max_tokens"] = int(self.conv_max_tokens.text())
        except ValueError:
            s["max_tokens"] = 4096

        # ── Reasoner 1 ─────────────────────────────────────────────────────
        r1_prov = (self.r1_provider.currentData() or "").lower()
        s["reasoner_1_enabled"]  = self.r1_enabled.isChecked()
        s["reasoner_1_provider"] = r1_prov
        s["reasoner_1_api_key"]  = self.r1_key.text().strip()
        s["reasoner_1_base_url"] = self.r1_url.text().strip()
        s["reasoner_1_model"]    = self.r1_model.text().strip()
        s["reply_ratio_reasoning"] = self.r1_ratio.value() / 100.0
        s["reasoner_2_trigger_phrase"] = self.r1_trigger.text().strip() or "[ESCALATE_TO_DEEP_REASONER]"
        try:
            s["reasoner_1_max_tokens"] = int(self.r1_max_tokens.text())
        except ValueError:
            s["reasoner_1_max_tokens"] = 2048

        # ── Reasoner 2 ─────────────────────────────────────────────────────
        r2_prov = (self.r2_provider.currentData() or "").lower()
        s["reasoner_2_provider"] = r2_prov
        s["reasoner_2_api_key"]  = self.r2_key.text().strip()
        s["reasoner_2_base_url"] = self.r2_url.text().strip()
        s["reasoner_2_model"]    = self.r2_model.text().strip()
        try:
            s["reasoner_2_max_tokens"] = int(self.r2_max_tokens.text())
        except ValueError:
            s["reasoner_2_max_tokens"] = 4096

        # ── Vision ─────────────────────────────────────────────────────────
        vis_prov = (self.vis_provider.currentData() or "").lower()
        s["vision_provider"] = vis_prov
        s["vision_api_key"]  = self.vis_key.text().strip()
        s["vision_base_url"] = self.vis_url.text().strip()
        s["vision_model"]    = self.vis_model.text().strip()

        # ── Voice ───────────────────────────────────────────────────────────
        tts_prov_text = self.voice_provider.currentText().lower()
        if "piper" in tts_prov_text:
            tts_prov = "piper"
        elif "google" in tts_prov_text:
            tts_prov = "google"
        elif "eleven" in tts_prov_text:
            tts_prov = "elevenlabs"
        elif "openai" in tts_prov_text:
            tts_prov = "openai"
        else:
            tts_prov = "auto"

        s["tts_provider"]   = tts_prov
        s["tts_api_key"]    = self.voice_key.text().strip()
        s["voice_api_key"]  = s["tts_api_key"]
        s["voice_base_url"] = self.voice_url.text().strip()
        s["tts_model"]      = self.voice_model.text().strip()
        s["voice_model"]    = s["tts_model"]
        s["tts_language"]   = self.voice_language.text().strip() or "en-US"
        s["tts_voice"]      = self.voice_name.text().strip()

        return s

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4j — ACTIONS
    # ══════════════════════════════════════════════════════════════════════

    def _save_system_prompt(self):
        """Save the full system prompt to config/system_prompt.txt."""
        try:
            sp_path = Path(__file__).parent.parent / "config" / "system_prompt.txt"
            sp_path.parent.mkdir(parents=True, exist_ok=True)
            sp_path.write_text(
                self.full_system_prompt.toPlainText(), encoding="utf-8"
            )
            self._status_label.setText("System prompt saved to disk.")
            self._status_label.setStyleSheet("color: #4a9d7b; font-size: 10px;")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save system prompt: {e}")

    def _open_profile_dialog(self):
        """Open the User Profile editor dialog."""
        try:
            from ui.user_profile_dialog import UserProfileDialog
            dlg = UserProfileDialog(parent=self)
            dlg.exec()
        except ImportError:
            QMessageBox.information(self, "User Profile", "User profile editor not available.")

    def _test_connection(self):
        """
        Test connectivity for all configured model slots.
        Sends a minimal message to each configured model and reports success/failure.
        """
        s = self._collect_settings()
        results = []

        # Test each slot that has credentials
        slots_to_test = [
            ("CONVERSATIONAL", s.get("conversational_provider", ""), s.get("conversational_api_key", ""), s.get("conversational_model", ""), s.get("conversational_base_url", "")),
            ("REASONER 1",     s.get("reasoner_1_provider", ""),     s.get("reasoner_1_api_key", ""),     s.get("reasoner_1_model", ""),     s.get("reasoner_1_base_url", "")),
            ("REASONER 2",     s.get("reasoner_2_provider", ""),     s.get("reasoner_2_api_key", ""),     s.get("reasoner_2_model", ""),     s.get("reasoner_2_base_url", "")),
            ("VISION",         s.get("vision_provider", ""),         s.get("vision_api_key", ""),         s.get("vision_model", ""),         s.get("vision_base_url", "")),
        ]

        for slot_name, provider, api_key, model, base_url in slots_to_test:
            if not api_key or not model:
                results.append(f"  ⚫ {slot_name}: not configured")
                continue

            try:
                if provider == "anthropic":
                    if Anthropic is None:
                        results.append(f"  ❌ {slot_name}: anthropic SDK not installed")
                        continue
                    client = Anthropic(api_key=api_key)
                    client.messages.create(
                        model=model, max_tokens=10,
                        messages=[{"role": "user", "content": "Hi"}]
                    )
                    results.append(f"  ✅ {slot_name}: {model} ({provider})")

                else:
                    if OpenAI is None:
                        results.append(f"  ❌ {slot_name}: openai SDK not installed")
                        continue
                    url = base_url or PROVIDER_BASE_URLS.get(provider, "")
                    client = OpenAI(base_url=url, api_key=api_key) if url else OpenAI(api_key=api_key)
                    client.chat.completions.create(
                        model=model, max_tokens=10,
                        messages=[{"role": "user", "content": "Hi"}]
                    )
                    results.append(f"  ✅ {slot_name}: {model} ({provider})")

            except Exception as e:
                results.append(f"  ❌ {slot_name}: {str(e)[:80]}")

        QMessageBox.information(
            self,
            "CONNECTION TEST RESULTS",
            "ÆTHELGARD OS — Connection Test\n\n" + "\n".join(results)
        )

    def _factory_reset(self):
        """
        Factory reset — deletes all learned data while preserving configuration.
        
        Two-step confirmation to prevent accidental data loss.
        """
        from pathlib import Path
        import shutil

        # First confirmation
        reply = QMessageBox.warning(
            self,
            "FACTORY RESET — CONFIRMATION",
            "ÆTHELGARD OS FACTORY RESET\n\n"
            "The following will be DELETED:\n"
            "  • Vector memory database\n"
            "  • Conversation history\n"
            "  • Goals and tasks\n"
            "  • Reflection log and strategy rules\n"
            "  • Self-profile\n"
            "  • Chat sessions\n\n"
            "The following will be PRESERVED:\n"
            "  • API keys and model settings\n"
            "  • All source code files\n"
            "  • Plugins\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Second confirmation
        confirm = QMessageBox.question(
            self, "FINAL CONFIRMATION",
            "All learned data will be permanently deleted. Are you certain?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Perform reset
        project_root = Path(__file__).parent.parent
        data_dir     = project_root / "data"
        deleted      = []
        errors       = []

        delete_targets = [
            data_dir / "memory.db",
            data_dir / "memory_short.json",
            data_dir / "conversation.json",
            data_dir / "goals.json",
            data_dir / "tasks.json",
            data_dir / "tasks.json.bak",
            data_dir / "reflection_log.json",
            data_dir / "reflection_stats.json",
            data_dir / "strategy_rules.json",
            data_dir / "self_profile.json",
            data_dir / "agent_state.json",
        ]

        for target in delete_targets:
            if target.exists():
                try:
                    target.unlink()
                    deleted.append(target.name)
                except Exception as e:
                    errors.append(f"{target.name}: {e}")

        # Clear sessions directory
        sessions_dir = data_dir / "sessions"
        if sessions_dir.exists():
            try:
                shutil.rmtree(str(sessions_dir))
                sessions_dir.mkdir(exist_ok=True)
                deleted.append("sessions/")
            except Exception as e:
                errors.append(f"sessions/: {e}")

        msg = f"Factory reset complete.\n\nDeleted ({len(deleted)}): {', '.join(deleted)}"
        if errors:
            msg += f"\n\nErrors: {'; '.join(errors)}"
        msg += "\n\nPlease restart ÆTHELGARD OS."

        QMessageBox.information(self, "FACTORY RESET COMPLETE", msg)

    def _save(self):
        """Collect all fields, update settings, and close the dialog."""
        self.settings = self._collect_settings()
        self.accept()

    def get_settings(self) -> dict:
        """Return the final settings dict after dialog acceptance."""
        return self.settings
