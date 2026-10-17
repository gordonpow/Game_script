"""
GameScript Pro - 深色工業風主題
統一的 Qt StyleSheet 定義
"""

# ── 色彩系統 ──────────────────────────────────────────────────
COLORS = {
    "bg_primary":    "#0A0A0F",   # 主背景（最深）
    "bg_secondary":  "#12121A",   # 面板背景
    "bg_card":       "#1A1A26",   # 卡片背景
    "bg_hover":      "#22223A",   # Hover 狀態
    "bg_selected":   "#1E2A4A",   # 選中狀態
    "bg_input":      "#0F0F1C",   # 輸入框背景

    "border":        "#2A2A3D",   # 一般邊框
    "border_bright": "#3A3A5A",   # 亮邊框
    "border_accent": "#FF6B35",   # 強調邊框

    "accent":        "#FF6B35",   # 主強調色（工業橙）
    "accent_hover":  "#FF8C5A",   # 強調色 Hover
    "accent_dim":    "#CC5528",   # 暗版強調色
    "accent2":       "#00D4FF",   # 次強調色（青）
    "accent2_dim":   "#0099CC",

    "text_primary":  "#E8E8F0",   # 主文字
    "text_secondary":"#8888A0",   # 次要文字
    "text_muted":    "#8888A0",   # 柔和次要文字 (別名)
    "text_dim":      "#555570",   # 暗淡文字


    "success":       "#00E87A",   # 成功（綠）
    "warning":       "#FFD700",   # 警告（黃）
    "error":         "#FF4444",   # 錯誤（紅）
    "running":       "#00E87A",   # 執行中（綠）
    "paused":        "#FFD700",   # 暫停（黃）

    # 節點顏色
    "node_key":      "#2A4A8A",   # 按鍵節點（藍）
    "node_mouse":    "#2A6A3A",   # 滑鼠節點（綠）
    "node_wait":     "#5A4A10",   # 等待節點（黃棕）
    "node_gamepad":  "#5A2A6A",   # 搖桿節點（紫）
    "node_repeat":   "#3A3A3A",   # 重複節點（灰）

    "node_key_border":     "#4A7AFF",
    "node_mouse_border":   "#4AFF7A",
    "node_wait_border":    "#FFD700",
    "node_gamepad_border": "#AA4AFF",
    "node_repeat_border":  "#888888",
}


MAIN_STYLESHEET = f"""
/* ══════════════════════════════════════════════════════
   GameScript Pro - Dark Industrial Theme
   ══════════════════════════════════════════════════════ */

/* ── 全域基底 ── */
* {{
    font-family: "Consolas", "JetBrains Mono", "Courier New", monospace;
    font-size: 12px;
    color: {COLORS['text_primary']};
    outline: none;
}}

QMainWindow, QDialog, QWidget {{
    background-color: {COLORS['bg_primary']};
}}

/* ── 捲軸 ── */
QScrollBar:vertical {{
    background: {COLORS['bg_secondary']};
    width: 8px;
    border: none;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border_bright']};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['accent']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: {COLORS['bg_secondary']};
    height: 8px;
    border: none;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['border_bright']};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLORS['accent']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ── 面板 / 容器 ── */
QFrame#panel {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
}}

/* ── 按鈕 ── */
QPushButton {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border_bright']};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['accent']};
    color: {COLORS['accent']};
}}
QPushButton:pressed {{
    background-color: {COLORS['accent_dim']};
    border-color: {COLORS['accent']};
}}
QPushButton:disabled {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_dim']};
    border-color: {COLORS['border']};
}}

/* 強調按鈕（主操作） */
QPushButton#btn_accent {{
    background-color: {COLORS['accent']};
    color: #000000;
    border: none;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton#btn_accent:hover {{
    background-color: {COLORS['accent_hover']};
    color: #000000;
}}
QPushButton#btn_accent:pressed {{
    background-color: {COLORS['accent_dim']};
    color: #FFFFFF;
}}

/* 危險按鈕 */
QPushButton#btn_danger {{
    border-color: {COLORS['error']};
    color: {COLORS['error']};
}}
QPushButton#btn_danger:hover {{
    background-color: #3A1010;
    border-color: {COLORS['error']};
}}

/* 成功按鈕（錄製中） */
QPushButton#btn_record {{
    border-color: {COLORS['success']};
    color: {COLORS['success']};
}}
QPushButton#btn_record:hover {{
    background-color: #103A20;
}}

/* ── 輸入框 ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border_bright']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['accent_dim']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS['accent']};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {COLORS['bg_card']};
    border: none;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {COLORS['bg_hover']};
}}

/* ── 下拉選單 ── */
QComboBox {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border_bright']};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:hover {{
    border-color: {COLORS['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {COLORS['text_secondary']};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border_accent']};
    selection-background-color: {COLORS['bg_selected']};
    outline: none;
}}

/* ── 清單與樹狀 ── */
QListWidget, QTreeWidget {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    alternate-background-color: {COLORS['bg_card']};
    outline: none;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 4px 6px;
    border-radius: 3px;
}}
QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {COLORS['bg_hover']};
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {COLORS['bg_selected']};
    color: {COLORS['accent']};
}}
QTreeWidget::branch {{
    background: {COLORS['bg_secondary']};
}}

/* ── 標籤 ── */
QLabel {{
    background: transparent;
    border: none;
}}
QLabel#label_section {{
    color: {COLORS['accent']};
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QLabel#label_status_ok {{
    color: {COLORS['success']};
    font-weight: bold;
}}
QLabel#label_status_err {{
    color: {COLORS['error']};
    font-weight: bold;
}}
QLabel#label_status_warn {{
    color: {COLORS['warning']};
    font-weight: bold;
}}

/* ── 分頁 (Tab) ── */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    background: {COLORS['bg_secondary']};
    top: -1px;
}}
QTabBar::tab {{
    background: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 6px 16px;
    border-radius: 4px 4px 0 0;
    color: {COLORS['text_secondary']};
}}
QTabBar::tab:selected {{
    background: {COLORS['bg_secondary']};
    color: {COLORS['accent']};
    border-top: 2px solid {COLORS['accent']};
}}
QTabBar::tab:hover {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_primary']};
}}

/* ── 核取方塊 ── */
QCheckBox {{
    spacing: 6px;
    color: {COLORS['text_primary']};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLORS['border_bright']};
    border-radius: 3px;
    background: {COLORS['bg_input']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}
QCheckBox::indicator:hover {{
    border-color: {COLORS['accent']};
}}

/* ── 單選按鈕 ── */
QRadioButton {{
    spacing: 6px;
    color: {COLORS['text_primary']};
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLORS['border_bright']};
    border-radius: 7px;
    background: {COLORS['bg_input']};
}}
QRadioButton::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

/* ── 滑桿 ── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {COLORS['bg_card']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    background: {COLORS['accent']};
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {COLORS['accent']};
    border-radius: 2px;
}}

/* ── GroupBox ── */
QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    margin-top: 16px;
    padding: 8px;
    color: {COLORS['text_secondary']};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {COLORS['accent']};
    font-weight: bold;
}}

/* ── 分隔線 ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    border: none;
    background: {COLORS['border']};
    max-height: 1px;
    max-width: 1px;
}}

/* ── 工具提示 ── */
QToolTip {{
    background: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['accent']};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ── 進度條 ── */
QProgressBar {{
    background: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    text-align: center;
    color: {COLORS['text_primary']};
    height: 18px;
}}
QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS['accent_dim']},
        stop:1 {COLORS['accent']}
    );
    border-radius: 3px;
}}

/* ── 狀態列 ── */
QStatusBar {{
    background: {COLORS['bg_secondary']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_secondary']};
    font-size: 11px;
}}

/* ── 選單 ── */
QMenuBar {{
    background: {COLORS['bg_secondary']};
    border-bottom: 1px solid {COLORS['border']};
}}
QMenuBar::item {{
    padding: 4px 10px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {COLORS['bg_hover']};
    color: {COLORS['accent']};
}}
QMenu {{
    background: {COLORS['bg_card']};
    border: 1px solid {COLORS['border_accent']};
    border-radius: 4px;
}}
QMenu::item {{
    padding: 6px 16px;
}}
QMenu::item:selected {{
    background: {COLORS['bg_selected']};
    color: {COLORS['accent']};
}}
QMenu::separator {{
    height: 1px;
    background: {COLORS['border']};
    margin: 4px 8px;
}}

/* ── 訊息框 ── */
QMessageBox {{
    background: {COLORS['bg_secondary']};
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ── 分隔器 ── */
QSplitter::handle {{
    background: {COLORS['border']};
}}
QSplitter::handle:hover {{
    background: {COLORS['accent']};
}}
QSplitter::handle:horizontal {{
    width: 3px;
}}
QSplitter::handle:vertical {{
    height: 3px;
}}
"""


def get_node_style(node_type: str) -> str:
    """根據節點類型回傳對應的卡片樣式"""
    from models.node import NodeType
    type_map = {
        NodeType.KEY_DOWN:      ("node_key",     "node_key_border"),
        NodeType.KEY_UP:        ("node_key",     "node_key_border"),
        NodeType.KEY_CLICK:     ("node_key",     "node_key_border"),
        NodeType.MOUSE_MOVE:    ("node_mouse",   "node_mouse_border"),
        NodeType.MOUSE_CLICK:   ("node_mouse",   "node_mouse_border"),
        NodeType.MOUSE_SCROLL:  ("node_mouse",   "node_mouse_border"),
        NodeType.WAIT_FIXED:    ("node_wait",    "node_wait_border"),
        NodeType.WAIT_RANDOM:   ("node_wait",    "node_wait_border"),
        NodeType.GAMEPAD_BUTTON:("node_gamepad", "node_gamepad_border"),
        NodeType.GAMEPAD_AXIS:  ("node_gamepad", "node_gamepad_border"),
        NodeType.REPEAT_BLOCK:  ("node_repeat",  "node_repeat_border"),
        NodeType.WAIT_USER_KEY: ("node_wait",    "node_wait_border"),
    }
    bg_key, border_key = type_map.get(node_type, ("bg_card", "border"))
    return (COLORS.get(bg_key, COLORS["bg_card"]),
            COLORS.get(border_key, COLORS["border"]))


NODE_ICONS = {
    "KEY_DOWN":      "⬇",
    "KEY_UP":        "⬆",
    "KEY_CLICK":     "⌨",
    "MOUSE_MOVE":    "↗",
    "MOUSE_CLICK":   "🖱",
    "MOUSE_SCROLL":  "↕",
    "WAIT_FIXED":    "⏱",
    "WAIT_RANDOM":   "🎲",
    "GAMEPAD_BUTTON":"🎮",
    "GAMEPAD_AXIS":  "🕹",
    "REPEAT_BLOCK":  "↺",
    "WAIT_USER_KEY": "⏸",
}
