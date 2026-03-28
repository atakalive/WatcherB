# WatcherB

[English](README.md) | [日本語](README_ja.md)

A GUI monitor for the [gokrax](https://gitlab.com/atakalive/gokrax) pipeline. Receives and displays Discord channel messages in real time.

## Setup

### 1. Clone the repository

```bash
git clone https://gitlab.com/atakalive/WatcherB.git
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
```

Set `SEND_ENABLED=true` to enable command sending.

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
4. OAuth2 → URL Generator: select `bot` scope with `Read Message History` + `View Channels` permissions to generate an invite URL
5. Invite the bot to the server you want to monitor

Use a separate bot from gokrax's notification bot (sharing the same bot causes conflicts between self-post filtering and command handling on the gokrax side).

## Controls

| Key | Action |
|-----|--------|
| Ctrl + = / Ctrl + + | Increase font size |
| Ctrl + - | Decrease font size |
| Ctrl + 0 | Reset font size |

- Closing the window minimises it to the system tray
- Right-click the tray icon → Quit to exit

## Customisation

### .env (environment-specific)

- `DISCORD_BOT_TOKEN` — Discord bot token
- `CHANNEL_ID` — channel ID to monitor
- `SEND_ENABLED` — command sending (`true`/`false`, default: `false`)

### Icon

Place `my_icon.png` (or `my_icon.jpg`) in the project root to use a custom window/tray icon. If not present, the default `icon.png` is used.

### config.py (UI settings)

- `HISTORY_LIMIT` — number of past messages to load on startup
- `FONT_SIZE` / `FONT_FAMILY` / `LINE_HEIGHT` — font settings
- `WINDOW_WIDTH` / `WINDOW_HEIGHT` — window size
- `COLORS` — theme colours (Catppuccin Mocha base)

## License

MIT License
