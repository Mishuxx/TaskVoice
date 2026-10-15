"""
ui/tokens.py
============
Design tokens and styling definitions for Taskmaster.
A dark HUD / gamer aesthetic inspired by modern tactical dashboards.
"""

# ---------------------------------------------------------------------------
# Color Tokens
# ---------------------------------------------------------------------------
BG_DARK = "#0D1015"           # App main background
BG_DOTS = "#1B2130"           # Subtle 22px dot grid
BG_SIDEBAR = "#11151C"        # Left sidebar
BG_SURFACE = "#161B24"        # Cards, inputs, containers
BG_NAV_ACTIVE = "#1E2430"     # Active navigation button background
BG_CAT_ACTIVE = "#1C1730"     # Active category background
BORDER_CAT_ACTIVE = "#3B2F63" # Active category border
BORDER_SUBTLE = "#232A36"     # Card & divider borders

TEXT_PRIMARY = "#E8ECF2"      # Main text
TEXT_SECONDARY = "#9AA4B5"    # Subtitles, placeholders, labels
TEXT_MUTED = "#64748B"        # Very muted text

# Accents
ACCENT_VIOLET = "#7C3AED"     # Main brand violet
ACCENT_VIOLET_HOVER = "#6D28D9"
ACCENT_VIOLET_SOFT = "#A78BFA"
ACCENT_VIOLET_LIGHT = "#C4B5FD"

ACCENT_TURQUOISE = "#2DD4BF"  # Progress, checks, highlights
ACCENT_TURQUOISE_BRIGHT = "#5EEAD4"
XP_EMPTY_BLOCK = "#2A2F3D"

ACCENT_GOLD = "#F5B544"       # XP coins, rewards, medals, badges
ACCENT_GOLD_BG = "#2B2111"

# Categories
COLOR_ESTUDIO = "#60A5FA"
COLOR_PERSONAL = "#C084FC"
COLOR_SALUD = "#34D399"
COLOR_TRABAJO = "#F59E0B"

CATEGORY_COLORS = {
    "Estudio": COLOR_ESTUDIO,
    "Personal": COLOR_PERSONAL,
    "Salud": COLOR_SALUD,
    "Trabajo": COLOR_TRABAJO,
}

# Priorities
PRIORITY_LOW_COLOR = "#64748B"    # Baja - Grey
PRIORITY_MED_COLOR = "#60A5FA"    # Media - Blue
PRIORITY_HIGH_COLOR = "#F59E0B"   # Alta - Orange / Amber

PRIORITY_LOW_LABEL = "Baja"
PRIORITY_MED_LABEL = "Media"
PRIORITY_HIGH_LABEL = "Alta"

PRIORITY_COLORS = {
    1: PRIORITY_LOW_COLOR,
    2: PRIORITY_MED_COLOR,
    3: PRIORITY_HIGH_COLOR,
}

PRIORITY_NAMES = {
    1: PRIORITY_LOW_LABEL,
    2: PRIORITY_MED_LABEL,
    3: PRIORITY_HIGH_LABEL,
}

PRIORITY_XP = {
    1: 30,
    2: 60,
    3: 100,
}

# Typography
FONT_FAMILY = "Manrope"
FONT_MONO = "JetBrains Mono"

# ---------------------------------------------------------------------------
# Global App Stylesheet (QSS)
# ---------------------------------------------------------------------------
TASKMASTER_QSS = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: 'Manrope', 'Segoe UI', Arial, sans-serif;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {BG_DARK};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_SUBTLE};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_VIOLET_SOFT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 0;
}}

/* Tooltips */
QToolTip {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 11px;
}}

/* Dialogs */
QDialog {{
    background-color: {BG_SIDEBAR};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 12px;
}}

/* Form inputs in dialogs */
QLineEdit, QTextEdit, QSpinBox, QDateTimeEdit, QComboBox {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT_VIOLET};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    selection-background-color: {BG_NAV_ACTIVE};
}}

/* Buttons general */
QPushButton {{
    font-family: 'Manrope', 'Segoe UI', sans-serif;
    font-weight: 600;
    font-size: 13px;
}}

QMessageBox {{
    background-color: {BG_SIDEBAR};
    color: {TEXT_PRIMARY};
}}
"""
