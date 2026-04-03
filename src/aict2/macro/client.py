from __future__ import annotations

from collections.abc import Callable
from typing import Any

import discord

from aict2.macro.settings import MacroPublishSettings


ChannelResolver = Callable[[discord.Client, MacroPublishSettings], Any | None]
ClientFactory = Callable[[MacroPublishSettings, dict[str, object]], object]


def _default_channel_resolver(
    client: discord.Client,
    settings: MacroPublishSettings,
) -> Any | None:
    if settings.dashboard_channel_id is not None:
        channel = client.get_channel(settings.dashboard_channel_id)
        if channel is not None:
            return channel
    return discord.utils.get(client.get_all_channels(), name=settings.dashboard_channel)


class MacroPublisherClient(discord.Client):
    def __init__(
        self,
        settings: MacroPublishSettings,
        payload: dict[str, object],
        *,
        channel_resolver: ChannelResolver = _default_channel_resolver,
    ) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self._settings = settings
        self._payload = payload
        self._channel_resolver = channel_resolver

    async def on_ready(self) -> None:
        channel = self._channel_resolver(self, self._settings)
        if channel is None:
            raise RuntimeError(
                f"Macro dashboard channel '{self._settings.dashboard_channel}' was not found."
            )
        try:
            await channel.send(str(self._payload.get('body', '')))
        finally:
            await self.close()


def create_macro_client(
    settings: MacroPublishSettings,
    payload: dict[str, object],
    *,
    channel_resolver: ChannelResolver = _default_channel_resolver,
) -> discord.Client:
    return MacroPublisherClient(
        settings=settings,
        payload=payload,
        channel_resolver=channel_resolver,
    )


def publish_dashboard_message(
    settings: MacroPublishSettings,
    payload: dict[str, object],
    *,
    client_factory: ClientFactory = create_macro_client,
) -> int:
    try:
        client = client_factory(settings, payload)
        client.run(settings.discord_token)
    except Exception:
        return 1
    return 0
