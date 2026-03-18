# WatcherB 仕様書 v1

## 概要

gokraxパイプラインの進捗をリアルタイム監視するデスクトップGUI。
Discord #gokrax チャンネルのメッセージを受信し、プロジェクトごとのパイプライン状態を可視化する。

## 動機

- gokraxの進捗確認にDiscordクライアントを開く必要がある
- ラボや外出先など、自宅以外からも監視したい
- パイプラインのpipeline.json直読みは外部からアクセスできない
- Discord経由なら場所を問わずリアルタイム監視可能

## 技術スタック

- **Python 3.10+**
- **PySide6**: GUI フレームワーク
- **discord.py**: Discord Gateway API（メッセージ受信）
- **python-dotenv**: 設定管理

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
│  │              │  │       kaneko             │  │
│  └──────────────┘  └─────────────────────────┘  │
│                                                  │
│  [Status Bar: Connected | Last msg: 13:13]       │
└─────────────────────────────────────────────────┘

┌──────────────┐
│ Discord Bot  │  ← QThread で非同期実行
│ (受信専用)    │
└──────────────┘
```

## 画面構成

### 1. メインウィンドウ

- **左ペイン: プロジェクトステータスパネル**
  - プロジェクトごとにカード表示
  - 現在の状態（IDLE / DESIGN_PLAN / ... / DONE）
  - パイプライン進捗バー（状態に応じた進捗率）
  - 最終更新時刻

- **右ペイン: メッセージログ**
  - #gokrax のメッセージをリアルタイム表示
  - タイムスタンプ + メッセージ内容
  - 自動スクロール（最新メッセージを追従）
  - メッセージ種別で色分け（後述）

- **ステータスバー**
  - 接続状態（Connected / Disconnected / Reconnecting）
  - 最終受信メッセージの時刻

### 2. システムトレイ

- 最小化時にシステムトレイに格納
- トレイアイコンクリックで復元
- 状態変化時にトレイ通知（バルーン）

## メッセージ分類

#gokrax に投稿されるメッセージは以下のパターン:

### 状態遷移
```
[PJ] STATE_A → STATE_B (MM/DD HH:MM)
[Queue][PJ] STATE_A → STATE_B (MM/DD HH:MM)
```

### CC進捗
```
[PJ] 📋 CC Plan 開始 (model: xxx) (MM/DD HH:MM)
[PJ] ✅ CC Plan 完了 (MM/DD HH:MM)
[PJ] 🔨 CC Impl 開始 (model: xxx) (MM/DD HH:MM)
[PJ] ✅ CC Impl 完了 (MM/DD HH:MM)
```

### 催促
```
[PJ] STATE: 担当者 agent を催促 (MM/DD HH:MM)
[PJ] レビュアーを催促: agent1, agent2 (MM/DD HH:MM)
```

### REVISE対象
```
[PJ] REVISE対象:
#N: X P0 (reviewer1, reviewer2)
```

### マージサマリー
```
**[PJ] マージサマリー**
**#N: title** (`hash`)
  🟢 **reviewer**: APPROVE — comment
  🟡 **reviewer**: P1 — comment
```

### 対象Issue
```
[PJ] 対象Issue:
#N: title
```

## テーマ

ダークテーマ固定。QSSで全体に適用する。配色は以下を基調とする:
- 背景: #1e1e2e
- テキスト: #cdd6f4
- アクセント: #89b4fa
- カード背景: #313244

## 色分けルール

| メッセージ種別 | 背景色 |
|---|---|
| 状態遷移 | デフォルト |
| CC開始 | 薄青 |
| CC完了 | 薄緑 |
| 催促 | 薄黄 |
| REVISE / P0 | 薄赤 |
| マージサマリー | 薄緑 |
| BLOCKED | 赤 |
| DONE | 緑 |

## パイプライン状態と進捗率

```
IDLE                →  0%
DESIGN_PLAN         → 10%
DESIGN_REVIEW       → 20%
DESIGN_REVISE       → 15%  (後退)
DESIGN_APPROVED     → 30%
IMPLEMENTATION      → 50%
CODE_REVIEW         → 70%
CODE_REVISE         → 65%  (後退)
CODE_APPROVED       → 85%
MERGE_SUMMARY_SENT  → 95%
DONE                → 100%
BLOCKED             → 現在値で停止（赤表示）
```

## Discord Bot

### 接続

- discord.py の `Client` を使用
- Gateway Intents: `MESSAGE_CONTENT`, `GUILDS`, `GUILD_MESSAGES`
- 受信専用（メッセージ送信は一切行わない）
- 監視対象: `CHANNEL_ID` で指定した1チャンネルのみ

### イベントループ共存

- discord.py の asyncio ループを QThread 内で実行
- メッセージ受信時に Qt Signal でメインスレッドに通知
- GUIの操作は全てメインスレッドで実行

### 再接続

- discord.py の自動再接続に任せる
- 接続状態変化時にステータスバーを更新

## 設定

### .env（秘匿情報のみ）

```
DISCORD_BOT_TOKEN=xxx    # Discord bot token
```

### config.py（アプリケーション設定）

```python
# Discord
CHANNEL_ID = 1474050582049329213   # 監視対象チャンネル
HISTORY_LIMIT = 20                 # 起動時に読み込む過去メッセージ件数

# UI
WINDOW_TITLE = "WatcherB"
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
LEFT_PANEL_WIDTH = 280             # プロジェクトステータスパネル幅

# パイプライン状態→進捗率マッピング
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
    "BLOCKED": -1,                # 特殊: 現在値で停止+赤表示
}
```

## ファイル構成

```
WatcherB/
├── watcher.py          # エントリポイント + QMainWindow
├── discord_client.py   # Discord bot (QThread)
├── message_parser.py   # メッセージ解析・分類
├── widgets.py          # カスタムウィジェット（ステータスカード等）
├── config.py           # 設定読み込み
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── SPEC.md
```

## Phase 1（MVP）

- [ ] Discord受信 + メッセージログ表示
- [ ] 起動時に過去メッセージ読み込み（Discord REST API、件数は config.py で設定）
- [ ] メッセージ種別の色分け
- [ ] 接続状態表示
- [ ] 自動スクロール

## Phase 2

- [ ] プロジェクトステータスパネル（状態遷移メッセージから状態を推定）
- [ ] 進捗バー
- [ ] システムトレイ格納
- [ ] トレイ通知

## Phase 3（将来）

- [ ] 複数チャンネル監視
- [ ] メッセージフィルタ（PJ別、種別別）

- ダークテーマ固定（Phase 1から適用）

## 制約

- **送信機能はデフォルト OFF**（`config.SEND_ENABLED = False`）。ON にするとメインパネル下部にテキスト入力欄が表示され、#gokrax チャンネルへのメッセージ送信が可能になる。設定変更はアプリ再起動で反映。
- **Discord bot tokenが必要**（既存のbotアカウントを流用可能）
- **Windows / Linux 両対応**（PySide6はクロスプラットフォーム）
- **1インスタンスで1チャンネル監視**（Phase 3で拡張）
