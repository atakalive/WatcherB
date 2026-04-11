# WatcherB

[English](README.md) | [日本語](README_ja.md)

A GUI monitor for the [gokrax](https://github.com/atakalive/gokrax) pipeline. Receives and displays Discord channel messages in real time, and browses GitLab issues directly within the app.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/atakalive/WatcherB.git
cd WatcherB
```

### 2. Dependencies

Python 3.10 or later.

```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

```
DISCORD_BOT_TOKEN=your_bot_token_here
CHANNEL_ID=your_discord_ch_id_here
SEND_ENABLED=false
GITLAB_BASE_URL=https://gitlab.com/YOUR_NAMESPACE
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your_gitlab_token_here
GITLAB_PROJECTS=namespace/project1,namespace/project2
```

Set `SEND_ENABLED=true` to enable command sending. Set `GITLAB_TOKEN` and `GITLAB_PROJECTS` to enable the GitLab Issue Browser.

`.env` is listed in `.gitignore` and will not be pushed to git.

### 4. Launch

**Windows:**
- `run.bat` — no console (pythonw)
- `run_debug.bat` — with console (shows errors)

**Linux / macOS:**
```bash
python3 watcher.py
```

Start with the console the first time and check for errors.

## Discord Bot Setup

WatcherB receives messages through a Discord bot.

1. Create an application on the [Discord Developer Portal](https://discord.com/developers/applications)
2. Bot → enable **MESSAGE CONTENT INTENT**
3. Copy the bot token and paste it into `.env`
4. OAuth2 → URL Generator: select `bot` scope with `Read Message History` + `Send Messages` + `View Channels` permissions to generate an invite URL
5. Invite the bot to the server you want to monitor

Use a separate bot from gokrax's notification bot (sharing the same bot causes conflicts between self-post filtering and command handling on the gokrax side).

## Controls

| Key | Action |
|-----|--------|
| Ctrl + = / Ctrl + + | Increase font size |
| Ctrl + - | Decrease font size |
| Ctrl + 0 | Reset font size |
| Escape | Exit Issue mode (return to Pipeline view) |

- Closing the window minimises it to the system tray
- Right-click the tray icon → Quit to exit

## Customisation

### .env (environment-specific)

**Required:**

- `DISCORD_BOT_TOKEN` — Discord bot token
- `CHANNEL_ID` — channel ID to monitor
- `SEND_ENABLED` — command sending (`true`/`false`, default: `false`)
- `GITLAB_BASE_URL` — base URL for GitLab issue links (default: `https://gitlab.com/gitlab-org`)

**GitLab Issue Browser:**

- `GITLAB_URL` — GitLab instance URL (default: `https://gitlab.com`)
- `GITLAB_TOKEN` — personal access token with `read_api` scope (required for private repos)
- `GITLAB_PROJECTS` — comma-separated full project paths (e.g. `atakalive/gokrax,atakalive/WatcherB`)

**Optional:**
- `HISTORY_LIMIT` — number of past messages to load on startup (default: `20`)
- `FONT_SIZE` — message log font size in px (default: `20`)
- `FONT_FAMILY` — font family (default: `Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace`)
- `LINE_HEIGHT` — line height multiplier (default: `2.3`)
- `WINDOW_WIDTH` — window width in px (default: `1000`)
- `WINDOW_HEIGHT` — window height in px (default: `800`)
- `ISSUE_LIST_WIDTH` — issue list pane width in px (default: `280`)

### Icon

Place `my_icon.png` (or `my_icon.jpg`) in the project root to use a custom window/tray icon. If not present, the default `icon.png` is used.

### config.py (UI settings)

- `COLORS` — theme colours (Catppuccin Mocha base)
- Other UI constants not exposed via `.env`

## GitLab Issue Browser

Click a project name in the left panel to browse its GitLab issues. A tab bar appears with **Pipeline** and **Issues** tabs. The issue list supports filtering by Open / Closed / All, and selecting an issue displays its description and comments with Markdown rendering. Press Escape to return to Pipeline view.

Requires `GITLAB_PROJECTS` in `.env`. Set `GITLAB_TOKEN` for private repositories. See [docs/spec.md](docs/spec.md) for full details.

## Specification

For detailed technical specification, see [docs/spec.md](docs/spec.md).

## License

MIT License
