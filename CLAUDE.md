# CLAUDE.md — WatcherB 開発ガイド

## プロジェクト概要

Discord #dev-bar チャンネルのメッセージをリアルタイム受信・表示するデスクトップGUI。
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
