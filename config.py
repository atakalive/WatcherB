"""WatcherB application configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID: int = 1474050582049329213  # #gokrax
HISTORY_LIMIT: int = 20  # Number of past messages to load on startup

# Send feature (default OFF. Set True and restart to enable)
SEND_ENABLED: bool = True

# Icon
ICON_PATH: Path = Path(__file__).parent / "icon.jpg"

# UI
WINDOW_TITLE: str = "WatcherB"
WINDOW_WIDTH: int = 1000
WINDOW_HEIGHT: int = 800
LEFT_PANEL_WIDTH: int = 200

# Theme (Catppuccin Mocha based)
COLORS = {
    "bg": "#1e1e2e",
    "surface": "#313244",
    "text": "#cdd6f4",
    "subtext": "#a6adc8",
    "accent": "#89b4fa",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "red": "#f38ba8",
    "blue": "#89b4fa",
    "peach": "#fab387",
}

# Message type -> background color
MSG_COLORS = {
    "transition": None,        # default
    "cc_start": "#1e3a5f",     # light blue
    "cc_done": "#1e3f2e",      # light green
    "nudge": "#3f3a1e",        # light yellow
    "revise": "#3f1e1e",       # light red
    "merge_summary": "#1e3f2e",# light green
    "blocked": "#5f1e1e",      # red
    "done": "#1e3f2e",         # green
    "issue_list": None,        # default
    "unknown": None,           # default
}

# Pipeline state -> progress percentage (%)
STATE_PROGRESS = {
    "IDLE": 0,
    "DESIGN_PLAN": 10,
    "DESIGN_REVIEW": 20,
    "DESIGN_REVISE": 15,
    "DESIGN_APPROVED": 30,
    "IMPLEMENTATION": 50,
    "CODE_REVIEW": 70,
    "CODE_REVISE": 65,
    "CODE_APPROVED": 85,
    "MERGE_SUMMARY_SENT": 95,
    "DONE": 100,
    "BLOCKED": -1,  # Special: freeze at current value + red display
}

# Font
FONT_FAMILY: str = "Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace"
FONT_SIZE: int = 20          # Message log font size (px)
FONT_SIZE_TIMESTAMP: int = 3  # Timestamp font size (px)
FONT_SIZE_STATUS: int = 20   # Status bar font size (px)
LINE_HEIGHT: float = 2.3     # Line height (multiplier)

# Message log
TIMESTAMP_WIDTH: int = 65         # Timestamp column width (px)

# Phase 2: Project Card
CARD_PADDING: int = 12            # ProjectCard inner padding (px)
CARD_SPACING: int = 8             # Spacing between ProjectCards (px)
CARD_BORDER_RADIUS: int = 6       # ProjectCard border radius (px)
PROGRESS_BAR_HEIGHT: int = 8      # QProgressBar height (px)
FONT_SIZE_PROJECT_NAME: int = 14  # Project name font size (px)
FONT_SIZE_STATE_LABEL: int = 12   # State label font size (px)
FONT_SIZE_UPDATE_TIME: int = 10   # Last update time font size (px)

# Phase 2: State display colors
STATE_COLORS: dict = {
    "IDLE": COLORS["subtext"],
    "DESIGN_PLAN": COLORS["accent"],
    "DESIGN_REVIEW": COLORS["accent"],
    "DESIGN_REVISE": COLORS["accent"],
    "DESIGN_APPROVED": COLORS["accent"],
    "IMPLEMENTATION": COLORS["peach"],
    "CODE_REVIEW": COLORS["blue"],
    "CODE_REVISE": COLORS["blue"],
    "CODE_APPROVED": COLORS["blue"],
    "MERGE_SUMMARY_SENT": COLORS["green"],
    "DONE": COLORS["green"],
    "BLOCKED": COLORS["red"],
}

# Phase 2: System tray
TRAY_TOOLTIP: str = "WatcherB - Discord Monitor"
