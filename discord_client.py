"""WatcherB Discord client — run discord.py in a QThread."""

import asyncio
from typing import Optional

import discord
from PySide6.QtCore import QThread, Signal

import config


class DiscordThread(QThread):
    """Run discord.py in a QThread.

    The asyncio event loop runs inside this thread.
    All communication with the main thread uses Signal/Slot.
    """

    message_received = Signal(dict)
    history_loaded = Signal(list)
    connection_changed = Signal(str)  # "connected" / "disconnected" / "reconnecting"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[discord.Client] = None

    def run(self):
        """QThread entry point. Create asyncio loop and run the bot."""
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
        """Set up and start the Discord client."""
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
        """Fetch past messages on startup and emit."""
        channel = self._client.get_channel(config.CHANNEL_ID)
        if channel is None:
            try:
                channel = await self._client.fetch_channel(config.CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden):
                return

        messages = []
        async for msg in channel.history(limit=config.HISTORY_LIMIT):
            messages.append(self._msg_to_dict(msg))

        # history() returns newest first, so reverse to chronological order
        messages.reverse()
        self.history_loaded.emit(messages)

    @staticmethod
    def _msg_to_dict(message: discord.Message) -> dict:
        """Convert discord.Message to a dict for cross-thread transfer."""
        return {
            "content": message.content,
            "author": message.author.display_name,
            "created_at": message.created_at,
            "message_id": message.id,
        }

    def send_message(self, content: str) -> None:
        """Send a message to the monitored channel from the main thread.

        Schedules a coroutine on the discord.py asyncio loop.
        Does nothing if _loop or _client is None (not connected).
        """
        if self._loop is None or self._client is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._send(content), self._loop
        )

    async def _send(self, content: str) -> None:
        """Actual send operation (runs in the discord.py asyncio loop)."""
        channel = self._client.get_channel(config.CHANNEL_ID)
        if channel is None:
            try:
                channel = await self._client.fetch_channel(config.CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden):
                return
        await channel.send(content)

    def request_stop(self):
        """Request a safe shutdown from the main thread."""
        if self._loop is not None and self._client is not None:
            asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
