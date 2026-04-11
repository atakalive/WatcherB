# CLAUDE.md — WatcherB 開発ガイド

## プロジェクト概要

Discord チャンネルのメッセージをリアルタイム受信・表示し、GitLab Issue をアプリ内で閲覧する [gokrax](https://gitlab.com/atakalive/gokrax) コンパニオン GUI。
仕様書: `docs/spec_ja.md` | Issue Browser 設計書: `plan/gitlab-issue-browser-spec-rev6.md`

## 技術スタック

- Python 3.10+
- PySide6 (GUI)
- discord.py (Discord Gateway API)
- requests (GitLab API v4)
- python-dotenv (.env読み込み)

## ファイル構成

```
watcher.py          # エントリポイント + QMainWindow
discord_client.py   # Discord bot (QThread内で実行)
message_parser.py   # メッセージ解析・分類
widgets.py          # カスタムウィジェット（ProjectCard, ProjectPanel等）
config.py           # 全設定値（ここから読め）
issue_browser/
  __init__.py
  gitlab_client.py  # GitLab API クライアント (QThread内で実行)
  widgets.py        # IssueListWidget, IssueDetailWidget
  markdown.py       # Markdown→HTML変換（QTextBrowser用）
```

## 絶対ルール

1. **設定値は全て config.py から読め。** ハードコードするな
2. **discord.py の asyncio ループと PySide6 の Qt イベントループを混ぜるな。** discord.py は QThread 内で実行し、Qt Signal でメインスレッドに通知する
3. **SEND_ENABLED=false の場合、メッセージ送信は一切するな。**
4. **ダークテーマ固定。** config.py の COLORS を使え
5. **Windows / Linux 両対応。** OS固有APIを使うな
6. **GitLab API (requests) も QThread 内で実行し、Qt Signal でメインスレッドに通知する。** DiscordThread と同パターンだが asyncio ではなく同期 HTTP + QWaitCondition を使う

## メッセージ分類

message_parser.py で以下の4種別に分類する:
- `transition`: 状態遷移 (`[PJ] STATE_A → STATE_B`)
- `blocked`: BLOCKED遷移 (`→ BLOCKED`)
- `done`: DONE遷移 (`→ DONE`)
- `info`: 上記に該当しないもの

## QTextBrowser の制約（重要）

QTextBrowser は CSS サポートが限定的:
- ✅ 効く: `<font color>`, `<table>`, `valign`, `<b>`, `<font size="N">`
- ❌ 効かない: `border-left`, `padding-left`, inline `style` の一部
- レイアウトは `<table>` ベースで組め
- 色は `<font color="...">` を使え
