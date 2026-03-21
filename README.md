# WatcherB

[gokrax](https://gitlab.com/atakalive/gokrax) パイプライン監視GUI。Discord チャンネルのメッセージをリアルタイム受信・表示する。

## セットアップ

### 1. リポジトリ取得

```bash
git clone https://gitlab.com/atakalive/WatcherB.git
cd WatcherB
```

### 2. 依存パッケージ

Python 3.10 以上。

```bash
pip install -r requirements.txt
```

### 3. 設定ファイル

`.env.example` をコピーして `.env` を作成し、各項目を埋める:

```bash
cp .env.example .env
```

```
DISCORD_BOT_TOKEN=your_bot_token_here
CHANNEL_ID=your_discord_ch_id_here
SEND_ENABLED=false
```

コマンド送信機能を使う場合は `SEND_ENABLED=true` に変更する。

`.env` は `.gitignore` に含まれており、git に push されない。

### 4. 起動

**Windows:**
- `run.bat` — コンソールなし（pythonw）
- `run_debug.bat` — コンソール付き（エラー表示）

**Linux / macOS:**
```bash
python3 watcher.py
```

初回はコンソール付きで起動し、エラーがないことを確認する。

## Discord Bot の準備

WatcherB は Discord bot 経由でメッセージを受信する。

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリケーション作成
2. Bot → **MESSAGE CONTENT INTENT** を ON
3. Bot Token を取得し `.env` に記入
4. OAuth2 → URL Generator で `bot` スコープ、`Read Message History` + `View Channels` 権限で招待URLを生成
5. 監視対象サーバーに bot を招待

gokrax の通知用 bot とは別の bot を用意すること（同一 bot だと gokrax 側で自己投稿除外とコマンド受付が矛盾する）。

## 操作

| キー | 動作 |
|------|------|
| Ctrl + = / Ctrl + + | フォント拡大 |
| Ctrl + - | フォント縮小 |
| Ctrl + 0 | フォントサイズリセット |

- ウィンドウを閉じるとシステムトレイに格納される
- トレイアイコン右クリック → Quit で終了

## カスタマイズ

### .env（環境固有）

- `DISCORD_BOT_TOKEN` — Discord bot トークン
- `CHANNEL_ID` — 監視チャンネルID
- `SEND_ENABLED` — コマンド送信機能（`true`/`false`、デフォルト: `false`）

### config.py（UI設定）

- `HISTORY_LIMIT` — 起動時の過去メッセージ読み込み件数
- `FONT_SIZE` / `FONT_FAMILY` / `LINE_HEIGHT` — フォント設定
- `WINDOW_WIDTH` / `WINDOW_HEIGHT` — ウィンドウサイズ
- `COLORS` — テーマカラー（Catppuccin Mocha ベース）

## ライセンス

MIT License
