# WatcherB 仕様書

[English](spec.md) | [日本語](spec_ja.md)

## 目次

- [概要](#概要)
- [技術スタック](#技術スタック)
- [インストール](#インストール)
- [アーキテクチャ](#アーキテクチャ)
- [画面構成](#画面構成)
- [メッセージ分類](#メッセージ分類)
- [テーマ](#テーマ)
- [パイプライン状態と進捗率](#パイプライン状態と進捗率)
- [Discord Bot](#discord-bot)
- [設定](#設定)
- [ファイル構成](#ファイル構成)
- [キーボードショートカット](#キーボードショートカット)
- [制約](#制約)

---

## 概要

[gokrax](https://github.com/atakalive/gokrax) パイプラインの進捗をリアルタイム監視するデスクトップGUI。
gokraxの進捗確認にDiscordクライアントを開き続ける不便さを解消する。
Discord チャンネルのメッセージを受信し、プロジェクトごとのパイプライン状態を可視化する。

## 技術スタック

- **Python 3.10+**
- **PySide6**: GUI フレームワーク
- **discord.py**: Discord Gateway API（メッセージ受信・送信）
- **python-dotenv**: .env 読み込み

## インストール

### 1. リポジトリ取得

```bash
git clone https://github.com/atakalive/WatcherB.git
cd WatcherB
```

### 2. 依存パッケージ

```bash
pip install -r requirements.txt
```

### 3. Discord Bot の準備

WatcherB は受信用の Discord bot を使用する。gokrax とは別のbotを用意すること（同一bot だと gokrax 側で自己投稿除外とコマンド受付が矛盾する）。

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリケーション作成
2. Bot → **MESSAGE CONTENT INTENT** を ON
3. Bot Token を取得
4. OAuth2 → URL Generator で `bot` スコープ、`Read Message History` + `Send Messages` + `View Channels` 権限で招待URLを生成
5. 監視対象サーバーにbotを招待

### 4. 設定ファイル

`.env.example` をコピーして `.env` を作成:

```bash
cp .env.example .env
```

`.env` を編集（必須項目）:

```
DISCORD_BOT_TOKEN=your_bot_token_here
CHANNEL_ID=123456789012345678    # gokrax通知チャンネルのID
SEND_ENABLED=true                # コマンド送信を使う場合
GITLAB_BASE_URL=https://gitlab.com/YOUR_NAMESPACE  # GitLab Issue リンク用
```

オプション項目（未指定時はデフォルト値を使用）:

```
HISTORY_LIMIT=20                 # 起動時に読み込む過去メッセージ数
WINDOW_WIDTH=1000                # ウィンドウ幅
WINDOW_HEIGHT=800                # ウィンドウ高さ
FONT_SIZE=20                     # メッセージログのフォントサイズ
FONT_FAMILY=Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace
LINE_HEIGHT=2.3                  # メッセージログの行高
```

### 5. 起動

**Windows:**
- `run.bat` — コンソールなし（pythonw）
- `run_debug.bat` — コンソール付き（エラー表示）

**Linux / macOS:**
```bash
python3 watcher.py
```

初回は `run_debug.bat`（Windows）または直接 `python3 watcher.py` で起動してエラーがないか確認すること。

## アーキテクチャ

```
┌─────────────────────────────────────────────────┐
│  WatcherB (PySide6 QMainWindow)                 │
│                                                  │
│  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ Project      │  │ Message Log             │  │
│  │ Status Panel │  │                         │  │
│  │              │  │ 13:13 [gokrax] DESIGN   │  │
│  │ gokrax       │  │       _REVIEW →         │  │
│  │ ██████░░ REV │  │       DESIGN_REVISE     │  │
│  │              │  │ 13:11 [gokrax] DESIGN   │  │
│  │ TrajOpt      │  │       _PLAN →           │  │
│  │ ████████ DONE│  │       DESIGN_REVIEW     │  │
│  │              │  │ 13:09 [gokrax] 催促:    │  │
│  │ Issue: #12   │  │       kaneko             │  │
│  └──────────────┘  └─────────────────────────┘  │
│                                                  │
│  [Status Bar: Connected | Last msg: 13:13]       │
└─────────────────────────────────────────────────┘

┌──────────────┐
│ Discord Bot  │  ← QThread で非同期実行
│ (受信/送信)   │
└──────────────┘
```

## 画面構成

### 1. スプラッシュスクリーン

起動時に表示されるフレームレスウィンドウ（360×200px）。

- アプリ名「WatcherB」とステータスメッセージを表示
- プログレスバーで初期化進捗を表示
- ドラッグで移動可能（画面端でクランプ）
- メインウィンドウの準備完了後に自動で閉じる

### 2. メインウィンドウ

- **左ペイン: プロジェクトステータスパネル**（幅200px固定）
  - プロジェクトごとにカード表示（メッセージ受信時に自動生成）
  - 現在の状態（IDLE / INITIALIZE / DESIGN_PLAN / ... / DONE）
  - パイプライン進捗バー（状態に応じた進捗率）
  - GitLab Issue リンク（クリックでブラウザ表示、`GITLAB_BASE_URL` ベース）
  - 最終更新時刻
  - IDLE / DONE 状態ではIssueリンクを非表示

- **右ペイン: メッセージログ**
  - 監視チャンネルのメッセージをリアルタイム表示
  - 起動時に過去メッセージを `HISTORY_LIMIT` 件ロード
  - タイムスタンプ + メッセージ内容
  - 自動スクロール（最新メッセージを追従）
  - ユーザが上方にスクロールすると自動スクロール一時停止、最下部に戻ると再開
  - メッセージ種別で色分け
  - 状態名と矢印（→）をハイライト表示
  - Markdown太字（`**text**`）をHTML `<b>` に変換

- **ステータスバー**
  - 接続状態（Connected / Disconnected / Reconnecting）
  - 最終受信メッセージの時刻

### 3. システムトレイ

- 最小化時にシステムトレイに格納（ウィンドウ閉じ = トレイ格納）
- トレイアイコンクリックで復元
- コンテキストメニュー: Show / Exit
- BLOCKED 状態遷移時にトレイ通知（バルーン）

### 4. コマンド送信（オプション）

- `SEND_ENABLED=true`（.env）で有効化。デフォルト OFF
- メインパネル下部にテキスト入力欄が表示される
- 監視チャンネルへのメッセージ送信が可能（gokrax コマンド等）
- 設定変更はアプリ再起動で反映

## メッセージ分類

message_parser.py で以下の4種別に分類する（判定順序は上から優先）:

| 種別 | 判定条件 |
|------|----------|
| `blocked` | `→ BLOCKED` を含む |
| `done` | `→ DONE` を含む |
| `transition` | `[PJ] STATE_A → STATE_B` パターンにマッチ |
| `info` | 上記に該当しないもの |

### ParsedMessage 構造

```python
@dataclass
class ParsedMessage:
    msg_type: str           # "blocked" / "done" / "transition" / "info"
    project: Optional[str]  # プロジェクト名（[PJ] から抽出）
    raw_text: str           # 元メッセージ
    timestamp: str          # HH:MM 形式
    extra: dict             # 追加情報（以下参照）
```

`extra` フィールド:
- transition / blocked / done: `from_state`, `to_state`
- info（`Target Issues:` を含む場合）: `issues`（Issue番号のリスト）

### メッセージパターン

#### 状態遷移
```
[PJ] STATE_A → STATE_B (MM/DD HH:MM)
[Queue][PJ] STATE_A → STATE_B (MM/DD HH:MM)
```

#### CC進捗
```
[PJ] 📋 CC Plan 開始 (model: xxx) (MM/DD HH:MM)
[PJ] ✅ CC Plan 完了 (MM/DD HH:MM)
[PJ] 🔨 CC Impl 開始 (model: xxx) (MM/DD HH:MM)
[PJ] ✅ CC Impl 完了 (MM/DD HH:MM)
```

#### 催促
```
[PJ] STATE: 担当者 agent を催促 (MM/DD HH:MM)
[PJ] レビュアーを催促: agent1, agent2 (MM/DD HH:MM)
```

#### マージサマリー
```
**[PJ] マージサマリー**
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
※ `PROMPT_LANG=en` の場合は `[PJ] Target Issues:` 形式

## テーマ

ダークテーマ固定（Catppuccin Mocha ベース）。

| 要素 | 色 |
|------|-----|
| 背景 | `#1e1e2e` |
| サーフェス | `#313244` |
| テキスト | `#cdd6f4` |
| サブテキスト | `#a6adc8` |
| アクセント | `#89b4fa` |
| 緑 | `#a6e3a1` |
| 黄 | `#f9e2af` |
| 赤 | `#f38ba8` |
| 桃 | `#fab387` |

### メッセージ色分け

| メッセージ種別 | 背景色 |
|---|---|
| `transition` | デフォルト |
| `blocked` | `#5f1e1e` |
| `done` | `#1e3f2e` |
| `info` | デフォルト |

### 状態表示色

| 状態グループ | 色 |
|---|---|
| IDLE | subtext（グレー） |
| INITIALIZE | accent（青） |
| DESIGN_* | accent（青） |
| ASSESSMENT | peach（オレンジ） |
| IMPLEMENTATION | peach（オレンジ） |
| CODE_* | blue（青） |
| MERGE_SUMMARY_SENT / DONE | green（緑） |
| BLOCKED | red（赤） |

## パイプライン状態と進捗率

```
IDLE                →   0%
INITIALIZE          →   5%
DESIGN_PLAN         →  10%
DESIGN_REVIEW       →  20%
DESIGN_REVIEW_NPASS →  25%  (再レビュー)
DESIGN_REVISE       →  15%  (後退)
DESIGN_APPROVED     →  30%
ASSESSMENT          →  40%
IMPLEMENTATION      →  50%
CODE_REVIEW         →  70%
CODE_REVIEW_NPASS   →  75%  (再レビュー)
CODE_REVISE         →  65%  (後退)
CODE_APPROVED       →  85%
MERGE_SUMMARY_SENT  →  95%
DONE                → 100%
BLOCKED             →  現在値で停止（赤表示）
```

## Discord Bot

### 接続

- discord.py の `Client` を使用
- Gateway Intents: `MESSAGE_CONTENT`, `GUILDS`, `GUILD_MESSAGES`
- 監視対象: `.env` の `CHANNEL_ID` で指定した1チャンネル
- `SEND_ENABLED=true` 時のみ送信機能有効
- 自分自身（bot）のメッセージは無視

### イベントループ共存

- discord.py の asyncio ループを QThread 内で実行
- メッセージ受信時に Qt Signal でメインスレッドに通知
- GUIの操作は全てメインスレッドで実行

### Signal

| Signal | 引数 | 説明 |
|--------|------|------|
| `message_received` | `dict` | 新規メッセージ受信時 |
| `history_loaded` | `list` | 起動時の過去メッセージロード完了時 |
| `connection_changed` | `str` | 接続状態変化時（`"connected"` / `"disconnected"` / `"reconnecting"`） |

### 再接続

- discord.py の自動再接続に任せる
- 接続状態変化時にステータスバーを更新

## 設定

### .env（秘匿・環境固有）

必須:

```
DISCORD_BOT_TOKEN=xxx    # Discord bot token
CHANNEL_ID=0             # 監視対象チャンネルID
SEND_ENABLED=true        # コマンド送信機能 (true/false)
GITLAB_BASE_URL=https://gitlab.com/YOUR_NAMESPACE  # GitLab Issue リンクのベースURL
```

オプション（デフォルト値あり）:

```
HISTORY_LIMIT=20         # 起動時に読み込む過去メッセージ数
WINDOW_WIDTH=1000        # ウィンドウ幅 (px)
WINDOW_HEIGHT=800        # ウィンドウ高さ (px)
FONT_SIZE=20             # メッセージログのフォントサイズ (px)
FONT_FAMILY=Consolas, Cascadia Code, Noto Sans Mono CJK JP, monospace
LINE_HEIGHT=2.3          # メッセージログの行高
```

### config.py（アプリケーション設定）

.env の値は `os.getenv()` 経由で読み込む。UI設定・テーマ・進捗マッピング等はconfig.pyに直接定義。

### アイコン

カスタムアイコンに対応。以下の優先順位で検索:
1. `my_icon.png`
2. `my_icon.jpg`
3. `icon.png`（デフォルト）

## ファイル構成

```
WatcherB/
├── watcher.py          # エントリポイント + QMainWindow + MessageLog
├── discord_client.py   # Discord bot (QThread)
├── message_parser.py   # メッセージ解析・分類
├── widgets.py          # カスタムウィジェット（ProjectCard, ProjectPanel, WatcherTrayIcon, SplashScreen）
├── config.py           # 設定（.envから秘匿値読み込み + UI設定）
├── requirements.txt
├── .env.example
├── .gitignore
├── .gitattributes
├── icon.png            # デフォルトアイコン
├── run.bat             # Windows起動（コンソールなし）
├── run_debug.bat       # Windows起動（コンソール付き）
├── LICENSE
├── README.md
├── README_ja.md
├── CLAUDE.md           # 開発ガイド
└── docs/
    ├── spec.md         # Specification (English)
    └── spec_ja.md      # 本仕様書（日本語）
```

## キーボードショートカット

| キー | 動作 |
|------|------|
| Ctrl + = / Ctrl + + | フォント拡大（最大30px） |
| Ctrl + - | フォント縮小（最小8px） |
| Ctrl + 0 | フォントサイズリセット（13px） |

## 制約

- **1インスタンスで1チャンネル監視**
- **QTextBrowser の CSS サポートが限定的**: `<table>` ベースレイアウト、`<font color>` で色指定。inline style の `border-left`, `padding-left` 等は効かない
- **タイムスタンプはローカルタイムゾーンに変換して表示**
