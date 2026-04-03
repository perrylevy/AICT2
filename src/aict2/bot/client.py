from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord

from aict2.bot.discord_adapter import handle_discord_message
from aict2.bot.runtime import BotRuntime
from aict2.bot.settings import BotSettings
from aict2.context.macro_memory import MacroSnapshot

ET = ZoneInfo('America/New_York')


@dataclass(frozen=True, slots=True)
class MessageExecutionContext:
    current_time: datetime
    macro_state: str
    vix: float
    bias: str | None
    daily_profile: str | None
    entry: float
    stop: float
    target: float


AdapterCallable = Callable[..., Awaitable[str | None]]
ContextProvider = Callable[[Any], MessageExecutionContext]


def _default_context_provider(message: Any) -> MessageExecutionContext:
    _ = message
    return MessageExecutionContext(
        current_time=datetime.now(ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
    )


def build_store_backed_context_provider(runtime: BotRuntime) -> ContextProvider:
    def provider(message: Any) -> MessageExecutionContext:
        _ = message
        snapshot: MacroSnapshot | None = runtime.macro_store.load_latest()
        if snapshot is None:
            return _default_context_provider(message)
        return MessageExecutionContext(
            current_time=datetime.now(ET),
            macro_state=snapshot.macro_state,
            vix=snapshot.vix,
            bias=None,
            daily_profile=None,
            entry=0.0,
            stop=0.0,
            target=0.0,
        )

    return provider


class AICT2Client(discord.Client):
    def __init__(
        self,
        settings: BotSettings,
        runtime: BotRuntime,
        *,
        adapter: AdapterCallable,
        context_provider: ContextProvider,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._settings = settings
        self._runtime = runtime
        self._adapter = adapter
        self._context_provider = context_provider

    async def on_message(self, message: Any) -> None:
        context = self._context_provider(message)
        await self._adapter(
            message=message,
            watch_channels=self._settings.watch_channels,
            current_time=context.current_time,
            macro_state=context.macro_state,
            vix=context.vix,
            bias=context.bias,
            daily_profile=context.daily_profile,
            entry=context.entry,
            stop=context.stop,
            target=context.target,
            memory_store=self._runtime.memory_store,
            record_store=self._runtime.record_store,
            message_id=str(getattr(message, 'id', '')),  # tests may not provide ids yet
        )


def create_discord_client(
    settings: BotSettings,
    runtime: BotRuntime,
    *,
    adapter: AdapterCallable = handle_discord_message,
    context_provider: ContextProvider | None = None,
) -> discord.Client:
    provider = context_provider or build_store_backed_context_provider(runtime)
    return AICT2Client(
        settings=settings,
        runtime=runtime,
        adapter=adapter,
        context_provider=provider,
    )
