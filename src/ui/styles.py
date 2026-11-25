"""Qt stylesheet (QSS) and palette constants matching SPAudiobookPlayer."""

BG_MAIN = "#444444"
BG_DARK = "#373737"
BG_HOVER = "#4a4a4a"
BG_BLACK = "#1e1e1e"
BG_DISABLED = "#2a2a2a"
BG_FOCUS = "#404040"
BG_TABBAR = "#2c2c2c"

ACCENT = "#018574"
ACCENT_DARK = "#00634d"
ACCENT_LIGHT = "#02a58a"

TEXT = "#eaeaea"
TEXT_DIM = "#a0a0a0"
TEXT_MUTED = "#888888"
TEXT_BRIGHT = "#ffffff"
TEXT_DISABLED = "#666666"
BORDER = "#808080"

STATUS_OK = "#4ecca3"
STATUS_WARNING = "#f9ca24"
STATUS_ERROR = "#ff6b6b"

APP_QSS = f"""
QMainWindow {{
    background-color: {BG_MAIN};
}}

QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}

QFrame#TopBar {{
    background-color: {BG_DARK};
    border-bottom: 1px solid {BORDER};
}}

QFrame#KpiCard {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QFrame#KpiCard[status="clean"] {{
    border: 1px solid {STATUS_OK};
    background-color: #2b3d37;
}}

QFrame#KpiCard[status="suspect"] {{
    border: 1px solid {STATUS_WARNING};
    background-color: #3d3826;
}}

QFrame#KpiCard[status="upconvert"] {{
    border: 1px solid {STATUS_ERROR};
    background-color: #3f2b2b;
}}

QLabel {{
    background-color: transparent;
}}

QLabel#CardTitle {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}

QLabel#CardValue {{
    color: {TEXT_BRIGHT};
    font-size: 16px;
    font-weight: 700;
}}

QLabel#CardSub {{
    color: {TEXT_DIM};
    font-size: 11px;
}}

QPushButton {{
    background-color: {BG_DARK};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 6px 14px;
    min-height: 20px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: {TEXT_BRIGHT};
}}

QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_DARK}, stop:1 {ACCENT});
}}

QPushButton:disabled {{
    background-color: {BG_DISABLED};
    color: {TEXT_DISABLED};
    border-color: #555555;
}}

QPushButton#PrimaryBtn {{
    background-color: {ACCENT};
    border-color: {ACCENT_LIGHT};
    color: {TEXT_BRIGHT};
    font-weight: 600;
}}

QPushButton#PrimaryBtn:hover {{
    background-color: {ACCENT_LIGHT};
    border-color: {ACCENT_LIGHT};
}}

QPushButton#PrimaryBtn:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_DARK}, stop:1 {ACCENT});
}}

QPushButton#DangerBtn {{
    background-color: #7a2e2e;
    border-color: {STATUS_ERROR};
    color: {TEXT_BRIGHT};
}}

QPushButton#DangerBtn:hover {{
    background-color: #9e3838;
}}

QPushButton#DangerBtn:disabled {{
    background-color: {BG_DISABLED};
    color: {TEXT_DISABLED};
    border-color: #555555;
}}

QProgressBar {{
    background-color: {BG_BLACK};
    border: 1px solid {BORDER};
    border-radius: 3px;
    text-align: center;
    color: {TEXT_BRIGHT};
    height: 18px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
}}

QTabWidget {{
    background-color: {BG_DARK};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG_DARK};
    border-radius: 3px;
    top: -1px;
}}

QTabBar {{
    background-color: {BG_TABBAR};
}}

QTabBar::tab {{
    background-color: {BG_MAIN};
    color: {TEXT};
    padding: 8px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    margin-right: 2px;
    font-weight: 500;
}}

QTabBar::tab:hover {{
    background-color: {ACCENT};
    color: {TEXT_BRIGHT};
}}

QTabBar::tab:selected {{
    background-color: {ACCENT};
    color: {TEXT_BRIGHT};
    border-bottom: 1px solid {ACCENT};
    font-weight: 600;
}}

QTabBar::tab:!selected {{
    margin-top: 2px;
}}

QTableWidget {{
    background-color: {BG_DARK};
    alternate-background-color: {BG_TABBAR};
    gridline-color: #555555;
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {TEXT_BRIGHT};
}}

QHeaderView::section {{
    background-color: {BG_TABBAR};
    color: {TEXT};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #555555;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
}}

QComboBox {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 5px 8px;
    min-width: 6em;
    color: {TEXT};
}}

QComboBox:hover {{
    border-color: {ACCENT};
    background-color: {BG_HOVER};
}}

QComboBox QAbstractItemView {{
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    background-color: {BG_DARK};
    color: {TEXT};
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {BG_BLACK};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
    background-color: {BG_FOCUS};
}}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border-color: {TEXT_DIM};
}}

QLineEdit:disabled {{
    background-color: {BG_DISABLED};
    color: {TEXT_DISABLED};
    border-color: #555555;
}}

QSlider::groove:horizontal {{
    background: {BORDER};
    height: 8px;
    border-radius: 0px;
}}

QSlider::sub-page:horizontal {{
    background-color: {ACCENT};
}}

QSlider::add-page:horizontal {{
    background: {BORDER};
}}

QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border: 2px solid {BG_DARK};
    border-radius: 0px;
}}

QSlider::handle:horizontal:hover {{
    background: {ACCENT_LIGHT};
}}

QCheckBox {{
    spacing: 5px;
    color: {TEXT};
    background-color: transparent;
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 3px;
    border: 1px solid {BORDER};
    background-color: {BG_DARK};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
    background-color: {BG_HOVER};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT_LIGHT};
}}

QGroupBox {{
    background-color: {BG_MAIN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: {TEXT};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {TEXT};
}}

QScrollArea {{
    background-color: {BG_MAIN};
    border: none;
}}

QScrollBar:vertical {{
    background-color: {BG_DARK};
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER};
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    border: none;
    background: none;
}}

QScrollBar:horizontal {{
    background-color: {BG_DARK};
    height: 12px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {BORDER};
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {ACCENT};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    border: none;
    background: none;
}}
"""
