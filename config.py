"""WatcherB application configuration."""

import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv

load_dotenv()

# Discord
DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID: int = int(os.getenv("CHANNEL_ID", "0"))  # #gokrax chennel ID
HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "20"))

# Command sending feature (default OFF. Set True and restart to enable)
SEND_ENABLED: bool = os.getenv("SEND_ENABLED", "false").lower() in ("true", "1", "yes")

# Quick-send command buttons: (label, command, needs_confirm)
# qrun starts batch execution of the queue, so it requires confirmation.
SEND_BUTTONS: list[tuple[str, str, bool]] = [
    ("qrun", "qrun", True),
    ("qstatus", "qstatus", False),
    ("status", "status", False),
]
GITLAB_BASE_URL: str = os.getenv("GITLAB_BASE_URL", "https://gitlab.com/gitlab-org")

# GitLab Issue Browser
GITLAB_URL: str = os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/")
GITLAB_TOKEN: str = os.getenv("GITLAB_TOKEN", "")

def _parse_gitlab_projects(raw: str) -> list[str]:
    """Parse comma-separated GITLAB_PROJECTS string into list of project paths."""
    return [p.strip() for p in raw.split(",") if p.strip()]

_gitlab_projects_raw: str = os.getenv("GITLAB_PROJECTS", "")
GITLAB_PROJECTS: list[str] = _parse_gitlab_projects(_gitlab_projects_raw)
ISSUE_LIST_WIDTH: int = int(os.getenv("ISSUE_LIST_WIDTH", "280"))

# Icon (my_icon.png overrides default if present)
_project_root = Path(__file__).parent
_custom_icon_candidates = [_project_root / "my_icon.png", _project_root / "my_icon.jpg"]
_custom_icon = next((p for p in _custom_icon_candidates if p.exists()), None)
ICON_PATH: Path = _custom_icon if _custom_icon else _project_root / "icon.png"
ENV_PATH: Path = _project_root / ".env"

# UI
WINDOW_TITLE: str = "WatcherB"
WINDOW_WIDTH: int = int(os.getenv("WINDOW_WIDTH", "1000"))
WINDOW_HEIGHT: int = int(os.getenv("WINDOW_HEIGHT", "800"))
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
FONT_FAMILY: str = os.getenv("FONT_FAMILY", "Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace")
FONT_SIZE: int = int(os.getenv("FONT_SIZE", "20"))
FONT_SIZE_TIMESTAMP: int = 3  # Timestamp font size (px)
FONT_SIZE_STATUS: int = 20   # Status bar font size (px)
LINE_HEIGHT: float = float(os.getenv("LINE_HEIGHT", "2.3"))

# reload() で管理するキー一覧
_MANAGED_ENV_KEYS: set[str] = {
    "DISCORD_BOT_TOKEN", "CHANNEL_ID", "HISTORY_LIMIT", "SEND_ENABLED",
    "GITLAB_BASE_URL", "GITLAB_URL", "GITLAB_TOKEN", "GITLAB_PROJECTS",
    "ISSUE_LIST_WIDTH", "WINDOW_WIDTH", "WINDOW_HEIGHT",
    "FONT_FAMILY", "FONT_SIZE", "LINE_HEIGHT",
}

# 前回 .env から読み込まれたキーを記録（環境変数由来の設定を保持するため）
_last_dotenv_keys: set[str] = set(dotenv_values().keys()) & _MANAGED_ENV_KEYS


def reload(dotenv_path: Path | None = None) -> None:
    """Re-read .env and update module-level settings.

    環境変数由来の設定は保持し、.env 由来のキーだけをクリア・再読み込みする。

    Args:
        dotenv_path: .env ファイルのパス。None の場合は load_dotenv() のデフォルト探索。

    Raises:
        ValueError: .env の値が不正な場合（型変換失敗等）。
            この場合、モジュール変数は変更されない（半更新状態にならない）。
    """
    global DISCORD_BOT_TOKEN, CHANNEL_ID, HISTORY_LIMIT, SEND_ENABLED
    global GITLAB_BASE_URL, GITLAB_URL, GITLAB_TOKEN, GITLAB_PROJECTS
    global ISSUE_LIST_WIDTH, ICON_PATH
    global WINDOW_WIDTH, WINDOW_HEIGHT
    global FONT_FAMILY, FONT_SIZE, LINE_HEIGHT
    global _last_dotenv_keys

    # 今回の .env の内容を取得（os.environ には触れない）
    current_dotenv: dict[str, str | None] = dotenv_values(dotenv_path)
    current_dotenv_keys: set[str] = set(current_dotenv.keys()) & _MANAGED_ENV_KEYS

    # 前回 .env にあったキー OR 今回 .env にあるキーだけを os.environ から削除
    # → シェル環境変数由来の設定は保持される
    keys_to_clear: set[str] = (_last_dotenv_keys | current_dotenv_keys) & _MANAGED_ENV_KEYS
    for key in keys_to_clear:
        os.environ.pop(key, None)

    load_dotenv(dotenv_path=dotenv_path, override=True)

    # 一時変数に読み込み（型変換失敗時は ValueError で中断、モジュール変数は無変更）
    new_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
    new_channel_id: int = int(os.getenv("CHANNEL_ID") or "0")
    new_history_limit: int = int(os.getenv("HISTORY_LIMIT") or "20")
    new_send_enabled: bool = os.getenv("SEND_ENABLED", "false").lower() in ("true", "1", "yes")
    new_gitlab_base_url: str = os.getenv("GITLAB_BASE_URL", "https://gitlab.com/gitlab-org")
    new_gitlab_url: str = os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/")
    new_gitlab_token: str = os.getenv("GITLAB_TOKEN", "")
    new_gitlab_projects: list[str] = _parse_gitlab_projects(os.getenv("GITLAB_PROJECTS", ""))
    new_issue_list_width: int = int(os.getenv("ISSUE_LIST_WIDTH") or "280")
    new_window_width: int = int(os.getenv("WINDOW_WIDTH") or "1000")
    new_window_height: int = int(os.getenv("WINDOW_HEIGHT") or "800")
    new_font_family: str = os.getenv("FONT_FAMILY", "Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace")
    new_font_size: int = int(os.getenv("FONT_SIZE") or "20")
    new_line_height: float = float(os.getenv("LINE_HEIGHT") or "2.3")

    _custom_icon: Path | None = next((p for p in _custom_icon_candidates if p.exists()), None)
    new_icon_path: Path = _custom_icon if _custom_icon else _project_root / "icon.png"

    # 全値の型変換が成功した場合のみ、一括代入
    DISCORD_BOT_TOKEN = new_token
    CHANNEL_ID = new_channel_id
    HISTORY_LIMIT = new_history_limit
    SEND_ENABLED = new_send_enabled
    GITLAB_BASE_URL = new_gitlab_base_url
    GITLAB_URL = new_gitlab_url
    GITLAB_TOKEN = new_gitlab_token
    GITLAB_PROJECTS = new_gitlab_projects
    ISSUE_LIST_WIDTH = new_issue_list_width
    ICON_PATH = new_icon_path
    WINDOW_WIDTH = new_window_width
    WINDOW_HEIGHT = new_window_height
    FONT_FAMILY = new_font_family
    FONT_SIZE = new_font_size
    LINE_HEIGHT = new_line_height
    _last_dotenv_keys = current_dotenv_keys

# Message log
TIMESTAMP_WIDTH: int = 65         # Timestamp column width (px)

# Phase 2: Project Card
CARD_PADDING: int = 12            # ProjectCard inner padding (px)
CARD_SPACING: int = 8             # Spacing between ProjectCards (px)
CARD_BORDER_RADIUS: int = 6       # ProjectCard border radius (px)
PROGRESS_BAR_HEIGHT: int = 8      # QProgressBar height (px)

# Splash screen
SPLASH_WIDTH: int = 360
SPLASH_HEIGHT: int = 200
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
# トレイクリック時、直前の非アクティブ化からこの秒数以内なら「クリック前は前面だった」とみなし格納する
TRAY_FOREGROUND_GRACE_SEC: float = 0.3

# GitLab Issue Browser: pagination
MAX_PAGES: int = 20  # ページネーション上限（20 × 100 = 2000 items）
