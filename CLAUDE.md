# CLAUDE.md — WatcherB 開発ガイド

## プロジェクト概要

Discord #gokrax チャンネルのメッセージをリアルタイム受信・表示するデスクトップGUI。
仕様書: `docs/SPEC.md`

## 技術スタック

- Python 3.10+
- PySide6 (GUI)
- discord.py (Discord Gateway API)
- python-dotenv (.env読み込み)

## ファイル構成

```
watcher.py          # エントリポイント + QMainWindow
discord_client.py   # Discord bot (QThread内で実行)
message_parser.py   # メッセージ解析・分類
widgets.py          # カスタムウィジェット（ステータスカード等）
config.py           # 全設定値（既に作成済み。ここから読め）
```

## 絶対ルール

1. **設定値は全て config.py から読め。** ハードコードするな
2. **discord.py の asyncio ループと PySide6 の Qt イベントループを混ぜるな。** discord.py は QThread 内で実行し、Qt Signal でメインスレッドに通知する
3. **メッセージ送信は一切するな。** read-only
4. **ダークテーマ固定。** config.py の COLORS を使え
5. **Windows / Linux 両対応。** OS固有APIを使うな

## イベントループ共存パターン

```python
class DiscordThread(QThread):
    message_received = Signal(dict)  # メインスレッドへの通知

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run_bot())

    async def _run_bot(self):
        client = discord.Client(intents=...)
        @client.event
        async def on_message(msg):
            self.message_received.emit({...})  # Signal emit はスレッドセーフ
        await client.start(token)
```

## メッセージ分類

message_parser.py で以下の種別に分類する:
- `transition`: 状態遷移 (`[PJ] STATE_A → STATE_B`)
- `cc_start`: CC開始 (`📋 CC Plan 開始` / `🔨 CC Impl 開始`)
- `cc_done`: CC完了 (`✅ CC Plan 完了` / `✅ CC Impl 完了`)
- `nudge`: 催促 (`担当者 xxx を催促` / `レビュアーを催促`)
- `revise`: REVISE関連 (`REVISE対象:`)
- `merge_summary`: マージサマリー (`マージサマリー`)
- `blocked`: BLOCKED遷移 (`→ BLOCKED`)
- `done`: DONE遷移 (`→ DONE`)
- `issue_list`: Issue一覧 (`対象Issue:`)
- `unknown`: 上記に該当しないもの

## 起動時の過去メッセージ読み込み

Discord REST API (`channel.history(limit=HISTORY_LIMIT)`) で起動時に過去メッセージを取得し、ログに表示する。古い順に追加すること。

## Phase 1 スコープ

Phase 1 では以下のみ実装する:
- Discord受信 + メッセージログ表示
- 起動時に過去メッセージ読み込み
- メッセージ種別の色分け
- 接続状態表示（ステータスバー）
- 自動スクロール
- ダークテーマ

Phase 2 の機能（プロジェクトステータスパネル、進捗バー、システムトレイ）は実装しない。
widgets.py は Phase 2 用のスタブ（空ファイル）として置いておけ。

## Phase 2 スコープ

Phase 2 では以下を実装する:

### プロジェクトステータスパネル（左ペイン）
- QSplitter で左右ペイン分割（左=ステータス、右=メッセージログ）
- 左ペインの初期幅は `config.LEFT_PANEL_WIDTH`
- プロジェクトごとにカード表示（QWidget）
- カードに表示する情報:
  - プロジェクト名
  - 現在の状態（IDLE, DESIGN_PLAN, ... DONE）
  - 進捗バー（`config.STATE_PROGRESS` から算出）
  - 最終更新時刻
- **状態はメッセージから推定する**（状態遷移メッセージをパースして更新）

### 状態推定ロジック（message_parser.py に追加）
状態遷移メッセージ `[PJ] STATE_A → STATE_B` から:
- プロジェクト名を `_extract_project()` で取得（既存）
- 遷移先状態を正規表現で取得
- `[Queue][PJ]` プレフィクスも対応

```python
_STATE_CHANGE_RE = re.compile(
    r"(\w+)\s*→\s*(\w+)"
)
```

### widgets.py に実装するもの
- `ProjectCard(QWidget)`: プロジェクト1つ分のカード
  - プロジェクト名ラベル
  - 状態ラベル（状態に応じて色変更）
  - QProgressBar（`config.STATE_PROGRESS` でマッピング）
  - 最終更新時刻ラベル
- `ProjectPanel(QScrollArea)`: ProjectCard を縦に並べるパネル
  - `update_project(project_name, new_state, timestamp)` メソッド
  - 未知のプロジェクトは自動追加

### 状態の色
- IDLE: subtext色（グレー）
- DESIGN_*: accent色（青）
- IMPLEMENTATION: peach色（オレンジ）
- CODE_*: blue色（青）
- DONE: green色（緑）
- BLOCKED: red色（赤）

### QTextBrowser の制約（重要）
QTextBrowser は CSS サポートが限定的:
- ✅ 効く: `<font color>`, `<table>`, `valign`, `<b>`, `<font size="N">`
- ❌ 効かない: `border-left`, `padding-left`, inline `style` の一部
- レイアウトは `<table>` ベースで組め
- 色は `<font color="...">` を使え

### システムトレイ
- QSystemTrayIcon でトレイ格納
- ウィンドウ閉じるとトレイに最小化（終了はトレイメニューから）
- 状態変化時にトレイ通知（showMessage）

### 既存コードの変更点
- `watcher.py` の `MainWindow._setup_ui()` を修正: QSplitter で左右分割
- `_on_message_received` で ProjectPanel を更新
- `_on_history_loaded` でも ProjectPanel を更新（過去メッセージから初期状態構築）
