# WatcherB

DevBar パイプライン監視GUI。Discord #dev-bar チャンネルのメッセージをリアルタイム受信・表示する。

## セットアップ (Windows)

### 1. リポジトリ取得

```powershell
git clone git@gitlab.com:atakalive/WatcherB.git
cd WatcherB
```

### 2. 依存パッケージ

Python 3.10以上が必要。

```powershell
pip install -r requirements.txt
```

### 3. 設定ファイル

`.env` をプロジェクトルートに作成（`.env.example` を参考）:

```
DISCORD_BOT_TOKEN=your_bot_token_here
```

**⚠ `.env` は `.gitignore` に含まれており、gitにpushされません。**

### 4. 起動

- `run.bat` — コンソールなし（pythonw）
- `run_debug.bat` — コンソール付き（エラー表示）

初回は `run_debug.bat` で起動してエラーがないか確認してください。

## Discord Bot の準備

WatcherBは受信専用のDiscord botを使います。

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリケーション作成
2. Bot → **MESSAGE CONTENT INTENT** を ON
3. Bot Token を取得して `.env` に記入
4. OAuth2 → URL Generator で `bot` スコープ、`Read Message History` + `View Channels` 権限で招待URLを生成
5. 監視対象サーバーにbotを招待

## 操作

| キー | 動作 |
|------|------|
| Ctrl + = / Ctrl + + | フォント拡大 |
| Ctrl + - | フォント縮小 |
| Ctrl + 0 | フォントサイズリセット |

- ウィンドウを閉じるとシステムトレイに格納
- トレイアイコン右クリック → Quit で終了

## カスタマイズ

`config.py` で各種設定を変更できます:

- `CHANNEL_ID` — 監視チャンネル
- `HISTORY_LIMIT` — 起動時の過去メッセージ読み込み件数
- `FONT_SIZE` / `FONT_FAMILY` / `LINE_HEIGHT` — フォント設定
- `TIMESTAMP_WIDTH` — タイムスタンプ列の幅
- `WINDOW_WIDTH` / `WINDOW_HEIGHT` — ウィンドウサイズ
- `COLORS` — テーマカラー（Catppuccin Mocha ベース）
