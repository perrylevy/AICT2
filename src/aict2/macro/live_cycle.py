from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord

from aict2.context.macro_memory import MacroSnapshot, MacroSnapshotStore
from aict2.context.store import ContextStore
from aict2.macro.dashboard_core import MacroInputs, score_macro_dashboard
from aict2.macro.dashboard_renderer import build_dashboard_payload
from aict2.macro.market_news import load_macro_inputs_from_channel
from aict2.macro.settings import MacroPublishSettings
from aict2.macro.vix_source import VixReading, fetch_live_vix

ET = ZoneInfo('America/New_York')

ChannelResolver = Callable[[discord.Client, int | None, str], Any | None]
NowProvider = Callable[[], datetime]
HistoryInputLoader = Callable[[Any, datetime, MacroInputs], Awaitable[MacroInputs]]
VixFetcher = Callable[[], VixReading | None]
ClientFactory = Callable[[MacroPublishSettings, MacroInputs], object]


def _default_channel_resolver(
    client: discord.Client,
    channel_id: int | None,
    channel_name: str,
) -> Any | None:
    if channel_id is not None:
        channel = client.get_channel(channel_id)
        if channel is not None:
            return channel
    return discord.utils.get(client.get_all_channels(), name=channel_name)


def with_live_vix(inputs: MacroInputs, *, vix_fetcher: VixFetcher = fetch_live_vix) -> MacroInputs:
    reading = vix_fetcher()
    if reading is None:
        return inputs
    return replace(inputs, vix=reading.value, vix_source=reading.source)


def with_stored_vix(inputs: MacroInputs, snapshot: MacroSnapshot | None) -> MacroInputs:
    if snapshot is None or inputs.vix_source != "fallback":
        return inputs
    return replace(inputs, vix=snapshot.vix, vix_source="stored")


class LiveMacroPublisherClient(discord.Client):
    def __init__(
        self,
        settings: MacroPublishSettings,
        fallback_inputs: MacroInputs,
        *,
        channel_resolver: ChannelResolver = _default_channel_resolver,
        input_loader: HistoryInputLoader = load_macro_inputs_from_channel,
        vix_fetcher: VixFetcher = fetch_live_vix,
        now_provider: NowProvider | None = None,
    ) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self._settings = settings
        self._fallback_inputs = fallback_inputs
        self._channel_resolver = channel_resolver
        self._input_loader = input_loader
        self._vix_fetcher = vix_fetcher
        self._now_provider = now_provider or (lambda: datetime.now(ET))
        self.exit_code = 1

    async def on_ready(self) -> None:
        try:
            market_news_channel = self._channel_resolver(
                self,
                self._settings.market_news_channel_id,
                self._settings.market_news_channel,
            )
            dashboard_channel = self._channel_resolver(
                self,
                self._settings.dashboard_channel_id,
                self._settings.dashboard_channel,
            )
            if market_news_channel is None:
                raise RuntimeError(
                    f"Market news channel '{self._settings.market_news_channel}' was not found."
                )
            if dashboard_channel is None:
                raise RuntimeError(
                    f"Macro dashboard channel '{self._settings.dashboard_channel}' was not found."
                )

            now = self._now_provider()
            context_store = ContextStore(self._settings.db_path)
            context_store.initialize()
            macro_store = MacroSnapshotStore(context_store)
            latest_snapshot = macro_store.load_latest()
            inputs = await self._input_loader(
                market_news_channel,
                now=now,
                fallback=self._fallback_inputs,
            )
            inputs = with_stored_vix(inputs, latest_snapshot)
            inputs = with_live_vix(inputs, vix_fetcher=self._vix_fetcher)
            score = score_macro_dashboard(inputs)
            payload = build_dashboard_payload(score)
            await dashboard_channel.send(str(payload.get('body', '')))

            macro_store.save_latest(
                MacroSnapshot(
                    macro_state=score.label,
                    vix=inputs.vix,
                    volatility_regime=score.volatility_regime,
                    event_risk=score.event_risk,
                    override_reason=score.override_reason,
                )
            )
            self.exit_code = 0
        finally:
            await self.close()


def create_live_macro_client(
    settings: MacroPublishSettings,
    fallback_inputs: MacroInputs,
    *,
    channel_resolver: ChannelResolver = _default_channel_resolver,
    input_loader: HistoryInputLoader = load_macro_inputs_from_channel,
    vix_fetcher: VixFetcher = fetch_live_vix,
    now_provider: NowProvider | None = None,
) -> discord.Client:
    return LiveMacroPublisherClient(
        settings=settings,
        fallback_inputs=fallback_inputs,
        channel_resolver=channel_resolver,
        input_loader=input_loader,
        vix_fetcher=vix_fetcher,
        now_provider=now_provider,
    )


def run_live_macro_cycle(
    settings: MacroPublishSettings,
    fallback_inputs: MacroInputs,
    *,
    client_factory: ClientFactory = create_live_macro_client,
) -> int:
    try:
        client = client_factory(settings, fallback_inputs)
        client.run(settings.discord_token)
    except Exception:
        return 1
    return int(getattr(client, 'exit_code', 1))
