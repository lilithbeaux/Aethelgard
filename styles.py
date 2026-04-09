"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Sovereign Visual Theme                           ║
║  File: ui/styles.py                                              ║
║                                                                  ║
║  The aesthetic is deliberate:                                    ║
║    Deep void blacks — not warm, not soft                        ║
║    Amber accent (#e96c3c) — ember, not neon                     ║
║    Obsidian glass — substantial, not translucent noise           ║
║    Restrained color — signal is where color appears             ║
║                                                                  ║
║  The palette:                                                    ║
║    Background:   #080810  (near-void)                           ║
║    Surface:      #0d0d1a  (obsidian)                            ║
║    Raised:       #141428  (elevated surface)                    ║
║    Border:       rgba(255,255,255,0.06)  (barely there)         ║
║    Accent:       #e96c3c  (ember amber — primary)               ║
║    Accent2:      #c792ea  (indigo — identity/cognitive)         ║
║    Accent3:      #89ddff  (ice — dream/information)             ║
║    Text:         #cdd3de  (cool white)                          ║
║    Text muted:   #546e7a  (slate)                               ║
║    Success:      #c3e88d  (muted green)                         ║
║    Warning:      #ffcb6b  (muted amber)                         ║
║    Error:        #f07178  (muted red)                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── ÆTHELGARD OS — Sovereign Dark Theme ──────────────────────────────────────
# Applied to QApplication via: app.setStyleSheet(DARK_THEME)

DARK_THEME = """

/* ══════════════════════════════════════════════
   GLOBAL BASE
   ══════════════════════════════════════════════ */

QMainWindow {
    background-color: transparent;
}

QWidget {
    color: #cdd3de;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Segoe UI', monospace;
    font-size: 13px;
}

QWidget#centralWidget {
    background-color: rgba(8, 8, 16, 248);
    border: 1px solid rgba(233, 108, 60, 0.12);
    border-radius: 14px;
}

/* ══════════════════════════════════════════════
   CUSTOM TITLE BAR
   ══════════════════════════════════════════════ */

QWidget#titleBar {
    background-color: rgba(5, 5, 12, 255);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    border-bottom: 1px solid rgba(233, 108, 60, 0.10);
}

QLabel#titleLabel {
    color: #e96c3c;
    font-size: 15px;
    font-weight: bold;
    padding: 0 8px;
    background: transparent;
    letter-spacing: 2px;
}

QLabel#titleSubLabel {
    color: rgba(255, 255, 255, 0.18);
    font-size: 10px;
    background: transparent;
    letter-spacing: 3px;
}

QPushButton#winBtn {
    background: transparent;
    border: none;
    border-radius: 5px;
    color: rgba(255, 255, 255, 0.25);
    font-size: 13px;
    padding: 4px 10px;
    min-width: 28px;
    max-width: 28px;
    min-height: 22px;
}

QPushButton#winBtn:hover {
    background-color: rgba(255, 255, 255, 0.06);
    color: #cdd3de;
}

QPushButton#closeBtn {
    background: transparent;
    border: none;
    border-radius: 5px;
    color: rgba(255, 255, 255, 0.25);
    font-size: 13px;
    padding: 4px 10px;
    min-width: 28px;
    max-width: 28px;
    min-height: 22px;
}

QPushButton#closeBtn:hover {
    background-color: #e96c3c;
    color: #080810;
}

/* ══════════════════════════════════════════════
   CONTROL BAR
   ══════════════════════════════════════════════ */

QWidget#controlBar {
    background: transparent;
}

QLabel#statusLabel {
    color: rgba(255, 255, 255, 0.22);
    font-size: 10px;
    padding: 4px 8px;
    background: transparent;
    letter-spacing: 1px;
}

QPushButton#autonomyBtn {
    background-color: rgba(20, 20, 40, 0.7);
    border: 1px solid rgba(233, 108, 60, 0.15);
    font-size: 10px;
    padding: 5px 12px;
    border-radius: 5px;
    color: #546e7a;
    letter-spacing: 1px;
}

QPushButton#autonomyBtn:hover {
    background-color: rgba(20, 20, 40, 0.95);
    color: #e96c3c;
    border-color: rgba(233, 108, 60, 0.4);
}

QPushButton#iconBtn {
    background: transparent;
    border: none;
    border-radius: 5px;
    color: rgba(255, 255, 255, 0.22);
    font-size: 16px;
    padding: 4px 8px;
}

QPushButton#iconBtn:hover {
    background-color: rgba(233, 108, 60, 0.08);
    color: #e96c3c;
}

/* ══════════════════════════════════════════════
   CHAT AREA
   ══════════════════════════════════════════════ */

QScrollArea#chatScroll {
    background: transparent;
    border: none;
}

QWidget#chatContainer {
    background: transparent;
}

/* ══════════════════════════════════════════════
   CHAT BUBBLES
   ══════════════════════════════════════════════ */

QFrame#userBubble {
    background-color: rgba(20, 20, 40, 0.6);
    border: 1px solid rgba(233, 108, 60, 0.18);
    border-radius: 14px;
    border-top-right-radius: 3px;
}

QFrame#assistantBubble {
    background-color: rgba(13, 13, 26, 0.7);
    border: 1px solid rgba(137, 221, 255, 0.07);
    border-radius: 14px;
    border-top-left-radius: 3px;
}

QFrame#toolBubble {
    background-color: rgba(8, 8, 20, 0.8);
    border-left: 2px solid rgba(233, 108, 60, 0.4);
    border-radius: 3px;
}

QFrame#toolResultBubble {
    background-color: rgba(8, 8, 20, 0.5);
    border-left: 2px solid rgba(137, 221, 255, 0.25);
    border-radius: 3px;
}

QFrame#systemBubble {
    background: transparent;
    border: none;
}

QFrame#reflectionBubble {
    background-color: rgba(15, 10, 8, 0.6);
    border-left: 2px solid rgba(199, 146, 234, 0.4);
    border-radius: 3px;
}

QLabel#bubbleSender {
    font-size: 10px;
    font-weight: bold;
    background: transparent;
    padding: 0;
    letter-spacing: 1px;
}

QLabel#bubbleText {
    font-size: 13px;
    background: transparent;
    padding: 0;
    line-height: 1.6;
}

QPushButton#copyBtn {
    background: transparent;
    border: none;
    border-radius: 3px;
    color: rgba(255, 255, 255, 0.10);
    font-size: 11px;
    padding: 2px 6px;
}

QPushButton#copyBtn:hover {
    background-color: rgba(233, 108, 60, 0.06);
    color: rgba(233, 108, 60, 0.5);
}

/* ══════════════════════════════════════════════
   INPUT AREA
   ══════════════════════════════════════════════ */

QWidget#inputArea {
    background-color: rgba(13, 13, 26, 0.9);
    border: 1px solid rgba(233, 108, 60, 0.10);
    border-radius: 12px;
}

QTextEdit#inputField {
    background: transparent;
    color: #cdd3de;
    border: none;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: rgba(233, 108, 60, 0.25);
}

QPushButton#sendBtn {
    background-color: #e96c3c;
    color: #080810;
    border: none;
    border-radius: 9px;
    padding: 8px 18px;
    font-weight: bold;
    font-size: 13px;
}

QPushButton#sendBtn:hover {
    background-color: #ff8255;
}

QPushButton#sendBtn:pressed {
    background-color: #c5541f;
}

/* ══════════════════════════════════════════════
   SIDEBAR
   ══════════════════════════════════════════════ */

QWidget#sidebar {
    background-color: rgba(5, 5, 12, 0.98);
    border-left: 1px solid rgba(233, 108, 60, 0.08);
}

QTabWidget#sidebarTabs {
    background: transparent;
}

QTabWidget#sidebarTabs::pane {
    background: transparent;
    border: none;
    border-top: 1px solid rgba(233, 108, 60, 0.08);
}

QTabBar::tab {
    background: transparent;
    color: rgba(255, 255, 255, 0.25);
    border: none;
    padding: 7px 8px;
    font-size: 10px;
    font-weight: bold;
    min-width: 42px;
    letter-spacing: 0.5px;
}

QTabBar::tab:selected {
    color: #e96c3c;
    border-bottom: 2px solid #e96c3c;
}

QTabBar::tab:hover {
    color: rgba(255, 255, 255, 0.55);
}

QListWidget {
    background: transparent;
    border: none;
    outline: none;
    font-size: 11px;
}

QListWidget::item {
    background-color: rgba(13, 13, 26, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.03);
    border-radius: 5px;
    padding: 7px 9px;
    margin: 2px 4px;
    color: #cdd3de;
}

QListWidget::item:selected {
    background-color: rgba(233, 108, 60, 0.12);
    border-color: rgba(233, 108, 60, 0.3);
}

QListWidget::item:hover {
    background-color: rgba(13, 13, 26, 0.8);
}

QLabel#sidebarTitle {
    color: #e96c3c;
    font-size: 12px;
    font-weight: bold;
    padding: 5px 9px;
    background: transparent;
    letter-spacing: 1px;
}

QLabel#sidebarStat {
    color: rgba(255, 255, 255, 0.22);
    font-size: 10px;
    padding: 2px 9px;
    background: transparent;
}

QLabel#reflectionLabel {
    color: #c792ea;
    font-size: 10px;
    padding: 2px 9px;
    background: transparent;
}

QPushButton#sidebarBtn {
    background-color: rgba(20, 20, 40, 0.5);
    color: rgba(255, 255, 255, 0.30);
    font-size: 10px;
    padding: 5px 10px;
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 4px;
    font-weight: normal;
}

QPushButton#sidebarBtn:hover {
    background-color: rgba(20, 20, 40, 0.9);
    color: #e96c3c;
    border-color: rgba(233, 108, 60, 0.2);
}

QProgressBar {
    background-color: rgba(20, 20, 40, 0.5);
    border: none;
    border-radius: 3px;
    height: 5px;
    color: transparent;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e96c3c, stop:1 #ffcb6b);
    border-radius: 2px;
}

QSplitter::handle {
    background: transparent;
    width: 0px;
    height: 0px;
    image: none;
}
QSplitter::handle:hover           { background: transparent; }
QSplitter::handle:horizontal      { image: none; width: 0px; }
QSplitter::handle:vertical        { image: none; height: 0px; }
QSplitter > QAbstractScrollArea   { border: none; }

/* ══════════════════════════════════════════════
   SETTINGS DIALOG & ALL DIALOGS
   ══════════════════════════════════════════════ */

QDialog {
    background-color: rgba(8, 8, 20, 252);
    border: 1px solid rgba(233, 108, 60, 0.15);
    border-radius: 12px;
}

QComboBox {
    background-color: rgba(20, 20, 40, 0.7);
    color: #cdd3de;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    padding: 7px 12px;
    font-size: 12px;
    min-height: 18px;
}

QComboBox:hover {
    border-color: rgba(233, 108, 60, 0.35);
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #e96c3c;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: rgba(13, 13, 26, 252);
    color: #cdd3de;
    border: 1px solid rgba(233, 108, 60, 0.15);
    selection-background-color: rgba(233, 108, 60, 0.3);
}

QLineEdit {
    background-color: rgba(20, 20, 40, 0.7);
    color: #cdd3de;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    padding: 7px 12px;
    font-size: 12px;
}

QLineEdit:focus {
    border-color: rgba(233, 108, 60, 0.45);
}

QLabel {
    color: rgba(255, 255, 255, 0.50);
    font-size: 12px;
    background: transparent;
}

QGroupBox {
    color: #e96c3c;
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 7px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: bold;
    background: transparent;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QSlider::groove:horizontal {
    background: rgba(30, 30, 60, 0.6);
    height: 3px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #e96c3c;
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}

QScrollBar:vertical {
    background: transparent;
    width: 5px;
    border-radius: 2px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 2px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(233, 108, 60, 0.35);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 0;
}

/* Stats display */
QTextEdit#statsDisplay {
    background-color: rgba(5, 5, 14, 0.9);
    color: rgba(205, 211, 222, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.03);
    border-radius: 5px;
    padding: 8px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 10px;
}

/* Tool blocks */
QTextEdit {
    background-color: rgba(13, 13, 26, 0.7);
    color: #cdd3de;
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 7px;
    padding: 8px;
    font-size: 12px;
}

QTextEdit:focus {
    border-color: rgba(233, 108, 60, 0.3);
}

"""
