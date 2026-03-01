"""WatcherB Discord client — QThread 内で discord.py を実行."""

import asyncio
from typing import Optional

import discord
from PySide6.QtCore import QThread, Signal

import config


class DiscordThread(QThread):
    """Discord Gateway に接続し、メッセージを Qt Signal で通知する.

    discord.py の asyncio ループはこのスレッド内で独立して動作する。
    メインスレッドとの通信は全て Signal/Slot 経由。
    """

    message_received = Signal(dict)
    history_loaded = Signal(list)
    connection_changed = Signal(str)  # "connected" / "disconnected" / "reconnecting"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[discord.Client] = None

    def run(self):
        """QThread エントリポイント. asyncio ループを作成して bot を実行."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_bot())
        except asyncio.CancelledError:
            pass
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    async def _run_bot(self):
        """Discord client をセットアップして開始."""
        intents = discord.Intents.default()
        intents.message_content = True

        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_ready():
            self.connection_changed.emit("connected")
            await self._load_history()

        @self._client.event
        async def on_message(message: discord.Message):
            if message.channel.id != config.CHANNEL_ID:
                return
            if message.author == self._client.user:
                return
            self.message_received.emit(self._msg_to_dict(message))

        @self._client.event
        async def on_disconnect():
            self.connection_changed.emit("disconnected")

        @self._client.event
        async def on_resumed():
            self.connection_changed.emit("connected")

        @self._client.event
        async def on_connect():
            self.connection_changed.emit("reconnecting")

        try:
            await self._client.start(config.DISCORD_BOT_TOKEN)
        except discord.LoginFailure:
            self.connection_changed.emit("disconnected")

    async def _load_history(self):
        """起動時に過去メッセージを取得して emit."""
        channel = self._client.get_channel(config.CHANNEL_ID)
        if channel is None:
            try:
                channel = await self._client.fetch_channel(config.CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden):
                return

        messages = []
        async for msg in channel.history(limit=config.HISTORY_LIMIT):
            messages.append(self._msg_to_dict(msg))

        # history() は新しい順で返すので逆順にする（古い順）
        messages.reverse()
        self.history_loaded.emit(messages)

    @staticmethod
    def _msg_to_dict(message: discord.Message) -> dict:
        """discord.Message をスレッド間転送用の dict に変換."""
        return {
            "content": message.content,
            "author": message.author.display_name,
            "created_at": message.created_at,
            "message_id": message.id,
        }

    def request_stop(self):
        """メインスレッドから安全に停止を要求する."""
        if self._loop is not None and self._client is not None:
            asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
