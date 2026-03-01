# WatcherB

DevBar パイプライン監視GUI。Discord #dev-bar チャンネルのメッセージをリアルタイム受信・表示する。

## 要件

- Python 3.10+
- PySide6
- discord.py

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env
# .env に DISCORD_BOT_TOKEN と CHANNEL_ID を設定
python watcher.py
```
