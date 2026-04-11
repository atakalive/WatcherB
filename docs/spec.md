# WatcherB Specification

[English](spec.md) | [日本語](spec_ja.md)

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Architecture](#architecture)
- [UI Layout](#ui-layout)
- [Message Classification](#message-classification)
- [Theme](#theme)
- [Pipeline States and Progress](#pipeline-states-and-progress)
- [Discord Bot](#discord-bot)
- [GitLab Issue Browser](#gitlab-issue-browser)
- [Configuration](#configuration)
- [File Structure](#file-structure)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Limitations](#limitations)

---

## Overview

A desktop GUI for real-time monitoring of [gokrax](https://github.com/atakalive/gokrax) pipeline progress.
Eliminates the inconvenience of keeping a Discord client open just to check gokrax status.
Receives messages from a Discord channel and visualizes per-project pipeline state.

## Tech Stack

- **Python 3.10+**
- **PySide6**: GUI framework
- **discord.py**: Discord Gateway API (message receive/send)
- **requests**: GitLab API v4 (synchronous HTTP)
- **python-dotenv**: .env loading

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/atakalive/WatcherB.git
cd WatcherB
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up a Discord Bot

WatcherB uses its own Discord bot for receiving messages. Use a separate bot from gokrax (using the same bot would cause conflicts between gokrax's self-message filtering and command handling).

1. Create an application on the [Discord Developer Portal](https://discord.com/developers/applications)
2. Bot → Enable **MESSAGE CONTENT INTENT**
3. Copy the Bot Token
4. OAuth2 → URL Generator: select `bot` scope, grant `Read Message History` + `Send Messages` + `View Channels` permissions, and generate an invite URL
5. Invite the bot to the server you want to monitor

### 4. Configuration File

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` (required fields):

```
DISCORD_BOT_TOKEN=your_bot_token_here
CHANNEL_ID=123456789012345678    # gokrax notification channel ID
SEND_ENABLED=true                # Enable command sending
GITLAB_BASE_URL=https://gitlab.com/YOUR_NAMESPACE  # Base URL for GitLab Issue links
```

Optional fields (defaults are used if omitted):

```
HISTORY_LIMIT=20                 # Number of past messages to load on startup
WINDOW_WIDTH=1000                # Window width
WINDOW_HEIGHT=800                # Window height
FONT_SIZE=20                     # Message log font size
FONT_FAMILY=Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace
LINE_HEIGHT=2.3                  # Message log line height
```

### 5. Launch

**Windows:**
- `run.bat` — No console (pythonw)
- `run_debug.bat` — With console (shows errors)

**Linux / macOS:**
```bash
python3 watcher.py
```

On first launch, use `run_debug.bat` (Windows) or run `python3 watcher.py` directly to check for errors.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  WatcherB (PySide6 QMainWindow)                      │
│                                                       │
│  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ Project      │  │ QTabBar [Pipeline] [Issues]  │  │
│  │ Status Panel │  │ (hidden in Normal mode)       │  │
│  │              │  ├──────────────────────────────┤  │
│  │ gokrax    ◀──click──  QStackedWidget           │  │
│  │ ██████░░ REV │  │  idx 0: MessageLog           │  │
│  │              │  │  idx 1: Issue Splitter        │  │
│  │ TrajOpt      │  │    ┌────────────┬─────────┐  │  │
│  │ ████████ DONE│  │    │ IssueList  │ IssueDtl│  │  │
│  │              │  │    └────────────┴─────────┘  │  │
│  └──────────────┘  └──────────────────────────────┘  │
│                                                       │
│  [Status Bar: Connected | Last msg: 13:13]            │
└──────────────────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐
│ Discord Bot  │  │ GitLabThread │
│ (recv/send)  │  │ (API client) │
│ ← QThread    │  │ ← QThread    │
│   asyncio    │  │   sync HTTP  │
└──────────────┘  └──────────────┘
```

## UI Layout

### 1. Splash Screen

A frameless window (360×200px) shown at startup.

- Displays the app name "WatcherB" and a status message
- Shows initialization progress via a progress bar
- Draggable (clamped to screen edges)
- Closes automatically when the main window is ready

### 2. Main Window

- **Left Pane: Project Status Panel** (fixed width 200px)
  - Card display per project (pre-populated from `GITLAB_PROJECTS` + auto-generated on message receipt)
  - Current state (IDLE / INITIALIZE / DESIGN_PLAN / ... / DONE)
  - Pipeline progress bar (progress percentage based on state)
  - GitLab Issue link (opens in browser, based on `GITLAB_BASE_URL`)
  - Last update time
  - Issue link hidden in IDLE / DONE states
  - Clicking a project card with a configured project path enters Issue Mode (see [GitLab Issue Browser](#gitlab-issue-browser))

- **Right Pane** (two modes via QStackedWidget)
  - **Normal Mode** (default): MessageLog only, tab bar hidden
  - **Issue Mode**: Tab bar with [Pipeline] [Issues] tabs; Issues tab shows IssueListWidget + IssueDetailWidget side-by-side

- **Right Pane: Message Log** (Normal Mode / Pipeline tab)
  - Real-time display of messages from the monitored channel
  - Loads `HISTORY_LIMIT` past messages on startup
  - Timestamp + message content
  - Auto-scroll (follows latest messages)
  - Auto-scroll pauses when user scrolls up, resumes when scrolled back to bottom
  - Color-coded by message type
  - State names and arrows (→) are highlighted
  - Markdown bold (`**text**`) converted to HTML `<b>`

- **Status Bar**
  - Connection status (Connected / Disconnected / Reconnecting)
  - Timestamp of last received message

### 3. System Tray

- Minimizes to system tray on window close (close = tray)
- Click tray icon to restore
- Context menu: Show / Exit
- Tray notification (balloon) on BLOCKED state transition

### 4. Command Input (Optional)

- Enabled with `SEND_ENABLED=true` in `.env`. Off by default
- A text input field appears at the bottom of the main panel
- Allows sending messages to the monitored channel (gokrax commands, etc.)
- Configuration changes require an app restart

## Message Classification

message_parser.py classifies messages into 4 types (evaluated in order of priority):

| Type | Condition |
|------|-----------|
| `blocked` | Contains `→ BLOCKED` |
| `done` | Contains `→ DONE` |
| `transition` | Matches `[PJ] STATE_A → STATE_B` pattern |
| `info` | Anything not matching the above |

### ParsedMessage Structure

```python
@dataclass
class ParsedMessage:
    msg_type: str           # "blocked" / "done" / "transition" / "info"
    project: Optional[str]  # Project name (extracted from [PJ])
    raw_text: str           # Original message
    timestamp: str          # HH:MM format
    extra: dict             # Additional info (see below)
```

`extra` field:
- transition / blocked / done: `from_state`, `to_state`
- info (when containing `Target Issues:`): `issues` (list of Issue numbers)

### Message Patterns

#### State Transitions
```
[PJ] STATE_A → STATE_B (MM/DD HH:MM)
[Queue][PJ] STATE_A → STATE_B (MM/DD HH:MM)
```

#### CC Progress
```
[PJ] 📋 CC Plan started (model: xxx) (MM/DD HH:MM)
[PJ] ✅ CC Plan completed (MM/DD HH:MM)
[PJ] 🔨 CC Impl started (model: xxx) (MM/DD HH:MM)
[PJ] ✅ CC Impl completed (MM/DD HH:MM)
```

#### Nudges
```
[PJ] STATE: Nudging agent (MM/DD HH:MM)
[PJ] Nudging reviewers: agent1, agent2 (MM/DD HH:MM)
```

#### Merge Summary
```
**[PJ] Merge Summary**
**#N: title** (`hash`)
  🟢 **reviewer**: APPROVE — comment
  🟡 **reviewer**: P1 — comment
```

#### Target Issues
```
[PJ] 対象Issue:
#12: Issue title
#34: Issue title
```
Note: With `PROMPT_LANG=en`, the format is `[PJ] Target Issues:` instead.

## Theme

Fixed dark theme (based on Catppuccin Mocha).

| Element | Color |
|---------|-------|
| Background | `#1e1e2e` |
| Surface | `#313244` |
| Text | `#cdd6f4` |
| Subtext | `#a6adc8` |
| Accent | `#89b4fa` |
| Green | `#a6e3a1` |
| Yellow | `#f9e2af` |
| Red | `#f38ba8` |
| Peach | `#fab387` |

### Message Colors

| Message Type | Background Color |
|---|---|
| `transition` | Default |
| `blocked` | `#5f1e1e` |
| `done` | `#1e3f2e` |
| `info` | Default |

### State Display Colors

| State Group | Color |
|---|---|
| IDLE | Subtext (gray) |
| INITIALIZE | Accent (blue) |
| DESIGN_* | Accent (blue) |
| ASSESSMENT | Peach (orange) |
| IMPLEMENTATION | Peach (orange) |
| CODE_* | Blue |
| MERGE_SUMMARY_SENT / DONE | Green |
| BLOCKED | Red |

## Pipeline States and Progress

```
IDLE                →   0%
INITIALIZE          →   5%
DESIGN_PLAN         →  10%
DESIGN_REVIEW       →  20%
DESIGN_REVIEW_NPASS →  25%  (re-review)
DESIGN_REVISE       →  15%  (regression)
DESIGN_APPROVED     →  30%
ASSESSMENT          →  40%
IMPLEMENTATION      →  50%
CODE_REVIEW         →  70%
CODE_REVIEW_NPASS   →  75%  (re-review)
CODE_REVISE         →  65%  (regression)
CODE_APPROVED       →  85%
MERGE_SUMMARY_SENT  →  95%
DONE                → 100%
BLOCKED             →  Stops at current value (displayed in red)
```

## Discord Bot

### Connection

- Uses discord.py `Client`
- Gateway Intents: `MESSAGE_CONTENT`, `GUILDS`, `GUILD_MESSAGES`
- Monitors: single channel specified by `CHANNEL_ID` in `.env`
- Send functionality only enabled when `SEND_ENABLED=true`
- Ignores messages from itself (the bot)

### Event Loop Coexistence

- discord.py's asyncio loop runs inside a QThread
- Messages are forwarded to the main thread via Qt Signals
- All GUI operations are performed on the main thread

### Signals

| Signal | Arguments | Description |
|--------|-----------|-------------|
| `message_received` | `dict` | Fired on new message receipt |
| `history_loaded` | `list` | Fired when past message loading completes on startup |
| `connection_changed` | `str` | Fired on connection state change (`"connected"` / `"disconnected"` / `"reconnecting"`) |

### Reconnection

- Relies on discord.py's automatic reconnection
- Status bar updates on connection state changes

## GitLab Issue Browser

An integrated panel for browsing GitLab issues without leaving WatcherB. For full implementation details, see [plan/gitlab-issue-browser-spec-rev6.md](../plan/gitlab-issue-browser-spec-rev6.md).

### UI Modes

- **Normal Mode** (default): Pipeline view only. Tab bar is hidden, right panel shows MessageLog
- **Issue Mode**: Activated by clicking a project card in the left panel (requires `project_path` via `GITLAB_PROJECTS`). Tab bar appears with **[Pipeline]** and **[Issues]** tabs. Issues tab is initially active
- Click the same project card again or press **Escape** to return to Normal Mode

### Issue List

- Displays issues for the selected project, fetched from GitLab API v4
- Filter by state: Open (default) / Closed / All via dropdown
- Reload button to re-fetch from API
- Pagination support up to `MAX_PAGES` × 100 items (default: 2000); truncation warning shown when limit is reached
- Results are cached per `(project, state_filter)` to avoid redundant API calls

### Issue Detail

- Shows issue title, description, and comments (non-system notes only)
- Markdown rendering: bold, code blocks (fenced and inline), links, and lists converted to HTML for QTextBrowser
- Truncation warning displayed when comment count exceeds the pagination limit

### GitLabThread

- Runs in a QThread using synchronous `requests` library with `QWaitCondition` for request queuing (not asyncio)
- Signals: `issues_loaded`, `issue_detail_loaded`, `list_error`, `detail_error`
- Request ID-based stale response filtering prevents outdated API results from overwriting the UI
- Session-based HTTP connection pooling; shutdown via `Session.close()`

### Module Structure

All issue browsing code is in the `issue_browser/` package:

| File | Description |
|------|-------------|
| `gitlab_client.py` | GitLabThread — QThread-based API client |
| `widgets.py` | IssueListWidget (list + filter) and IssueDetailWidget (detail view) |
| `markdown.py` | Minimal Markdown-to-HTML converter for QTextBrowser |

## Configuration

### .env (Secrets / Environment-Specific)

Required:

```
DISCORD_BOT_TOKEN=xxx    # Discord bot token
CHANNEL_ID=0             # Channel ID to monitor
SEND_ENABLED=true        # Command sending (true/false)
GITLAB_BASE_URL=https://gitlab.com/YOUR_NAMESPACE  # Base URL for GitLab Issue links
```

GitLab Issue Browser:

```
GITLAB_URL=https://gitlab.com              # GitLab instance URL (default: https://gitlab.com)
GITLAB_TOKEN=glpat-xxx                     # Personal access token (read_api scope; required for private repos)
GITLAB_PROJECTS=ns/proj1,ns/proj2          # Comma-separated full project paths
```

Optional (defaults provided):

```
HISTORY_LIMIT=20         # Past messages to load on startup
WINDOW_WIDTH=1000        # Window width (px)
WINDOW_HEIGHT=800        # Window height (px)
FONT_SIZE=20             # Message log font size (px)
FONT_FAMILY=Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace
LINE_HEIGHT=2.3          # Message log line height
ISSUE_LIST_WIDTH=280     # Issue list pane width (px)
```

### config.py (Application Settings)

Values from `.env` are read via `os.getenv()`. UI settings, theme, progress mappings, etc. are defined directly in config.py.

### Icons

Custom icons are supported. Searched in the following priority order:
1. `my_icon.png`
2. `my_icon.jpg`
3. `icon.png` (default)

## File Structure

```
WatcherB/
├── watcher.py              # Entry point + QMainWindow + MessageLog
├── discord_client.py       # Discord bot (QThread)
├── message_parser.py       # Message parsing and classification
├── widgets.py              # Custom widgets (ProjectCard, ProjectPanel, WatcherTrayIcon, SplashScreen)
├── config.py               # Configuration (.env secrets + UI settings)
├── issue_browser/          # GitLab Issue Browser
│   ├── __init__.py
│   ├── gitlab_client.py    # GitLabThread — QThread-based API client
│   ├── widgets.py          # IssueListWidget, IssueDetailWidget
│   └── markdown.py         # Markdown-to-HTML converter
├── requirements.txt
├── .env.example
├── .gitignore
├── .gitattributes
├── icon.png                # Default icon
├── run.bat                 # Windows launch (no console)
├── run_debug.bat           # Windows launch (with console)
├── LICENSE
├── README.md
├── README_ja.md
├── CLAUDE.md               # Development guide
├── docs/
│   ├── spec.md             # This specification (English)
│   └── spec_ja.md          # Specification (Japanese)
└── plan/
    └── gitlab-issue-browser-spec-rev6.md  # Issue Browser design spec
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl + = / Ctrl + + | Increase font size (max 30px) |
| Ctrl + - | Decrease font size (min 8px) |
| Ctrl + 0 | Reset font size (13px) |
| Escape | Exit Issue mode (return to Normal mode) |

## Limitations

- **One instance monitors one channel**
- **QTextBrowser CSS support is limited**: Uses `<table>`-based layout and `<font color>` for coloring. Inline styles like `border-left`, `padding-left` do not work
- **Timestamps are displayed in local timezone**
- **GitLab Issue Browser is read-only** — no issue creation, editing, or commenting
- **Issue data is fetched on demand** — no real-time updates via webhooks or polling
- **Maximum 2000 issues per project per fetch** (`MAX_PAGES` × 100 items per page)
