"""WatcherB アプリケーション設定."""

import os
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID: int = 1474050582049329213  # #dev-bar
HISTORY_LIMIT: int = 20  # 起動時に読み込む過去メッセージ件数

# UI
WINDOW_TITLE: str = "WatcherB"
WINDOW_WIDTH: int = 1000
WINDOW_HEIGHT: int = 700
LEFT_PANEL_WIDTH: int = 350

# テーマ (Catppuccin Mocha ベース)
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

# メッセージ種別→背景色
MSG_COLORS = {
    "transition": None,        # デフォルト
    "cc_start": "#1e3a5f",     # 薄青
    "cc_done": "#1e3f2e",      # 薄緑
    "nudge": "#3f3a1e",        # 薄黄
    "revise": "#3f1e1e",       # 薄赤
    "merge_summary": "#1e3f2e",# 薄緑
    "blocked": "#5f1e1e",      # 赤
    "done": "#1e3f2e",         # 緑
    "issue_list": None,        # デフォルト
    "unknown": None,           # デフォルト
}

# パイプライン状態→進捗率 (%)
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
    "BLOCKED": -1,  # 特殊: 現在値で停止+赤表示
}

# フォント
FONT_FAMILY: str = "Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace"
FONT_SIZE: int = 20          # メッセージログのフォントサイズ (px)
FONT_SIZE_TIMESTAMP: int = 18  # タイムスタンプのフォントサイズ (px)
FONT_SIZE_STATUS: int = 20   # ステータスバーのフォントサイズ (px)
LINE_HEIGHT: float = 2.3     # 行間 (倍率)

# メッセージログ
TIMESTAMP_WIDTH: int = 42         # タイムスタンプカラム幅 (px)
