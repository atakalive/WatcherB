"""WatcherB application configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID: int = int(os.getenv("CHANNEL_ID", "0"))  # #gokrax chennel ID
HISTORY_LIMIT: int = 20  # Number of past messages to load on startup

# Command sending feature (default OFF. Set True and restart to enable)
SEND_ENABLED: bool = os.getenv("SEND_ENABLED", "false").lower() in ("true", "1", "yes")
    
# Icon (my_icon.png overrides default if present)
_project_root = Path(__file__).parent
_custom_icon_candidates = [_project_root / "my_icon.png", _project_root / "my_icon.jpg"]
_custom_icon = next((p for p in _custom_icon_candidates if p.exists()), None)
ICON_PATH: Path = _custom_icon if _custom_icon else _project_root / "icon.png"

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
    "transition": None,
    "blocked": "#5f1e1e",
    "done": "#1e3f2e",
    "info": None,
}

# Pipeline state -> progress percentage (%)
STATE_PROGRESS = {
    "IDLE": 0,
    "INITIALIZE": 5,
    "DESIGN_PLAN": 10,
    "DESIGN_REVIEW": 20,
    "DESIGN_REVIEW_NPASS": 25,
    "DESIGN_REVISE": 15,
    "DESIGN_APPROVED": 30,
    "ASSESSMENT": 40,
    "IMPLEMENTATION": 50,
    "CODE_REVIEW": 70,
    "CODE_REVIEW_NPASS": 75,
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
    "INITIALIZE": COLORS["accent"],
    "DESIGN_PLAN": COLORS["accent"],
    "DESIGN_REVIEW": COLORS["accent"],
    "DESIGN_REVIEW_NPASS": COLORS["accent"],
    "DESIGN_REVISE": COLORS["accent"],
    "DESIGN_APPROVED": COLORS["accent"],
    "ASSESSMENT": COLORS["peach"],
    "IMPLEMENTATION": COLORS["peach"],
    "CODE_REVIEW": COLORS["blue"],
    "CODE_REVIEW_NPASS": COLORS["blue"],
    "CODE_REVISE": COLORS["blue"],
    "CODE_APPROVED": COLORS["blue"],
    "MERGE_SUMMARY_SENT": COLORS["green"],
    "DONE": COLORS["green"],
    "BLOCKED": COLORS["red"],
}

# Phase 2: System tray
TRAY_TOOLTIP: str = "WatcherB - Discord Monitor"
