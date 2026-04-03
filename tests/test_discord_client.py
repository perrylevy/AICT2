from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from aict2.bot.client import MessageExecutionContext, create_discord_client
from aict2.bot.runtime import build_runtime
from aict2.bot.settings import load_settings
from aict2.context.macro_memory import MacroSnapshot

ET = ZoneInfo("America/New_York")


@dataclass
class FakeAuthor:
    bot: bool = False


@dataclass
class FakeChannel:
    name: str


@dataclass
class FakeMessage:
    channel: FakeChannel
    content: str
    attachments: list[object]
    author: FakeAuthor


def test_create_discord_client_returns_discord_client(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "AICT2_DISCORD_TOKEN": "token-123",
            "AICT2_WATCH_CHANNELS": "aict2",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        }
    )
    runtime = build_runtime(settings)

    client = create_discord_client(settings, runtime)

    assert isinstance(client, discord.Client)


def test_discord_client_on_message_uses_adapter_and_context_provider(tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    async def fake_adapter(**kwargs):
        observed.update(kwargs)
        return "ok"

    def fake_context_provider(message):
        _ = message
        return MessageExecutionContext(
            current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
            macro_state="Risk-Off",
            vix=22.4,
            bias="bullish",
            daily_profile="continuation",
            entry=20000,
            stop=19990,
            target=20035,
        )

    settings = load_settings(
        {
            "AICT2_DISCORD_TOKEN": "token-123",
            "AICT2_WATCH_CHANNELS": "aict2",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        }
    )
    runtime = build_runtime(settings)
    client = create_discord_client(
        settings,
        runtime,
        adapter=fake_adapter,
        context_provider=fake_context_provider,
    )
    message = FakeMessage(
        channel=FakeChannel(name="aict2"),
        content="!accuracy report",
        attachments=[],
        author=FakeAuthor(bot=False),
    )

    asyncio.run(client.on_message(message))

    assert observed["message"] == message
    assert observed["watch_channels"] == ("aict2",)
    assert observed["macro_state"] == "Risk-Off"
    assert observed["record_store"] is runtime.record_store


def test_default_context_provider_uses_latest_macro_snapshot(tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    async def fake_adapter(**kwargs):
        observed.update(kwargs)
        return "ok"

    settings = load_settings(
        {
            "AICT2_DISCORD_TOKEN": "token-123",
            "AICT2_WATCH_CHANNELS": "aict2",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        }
    )
    runtime = build_runtime(settings)
    runtime.macro_store.save_latest(
        MacroSnapshot(
            macro_state="Risk-Off",
            vix=23.1,
            volatility_regime="high",
            event_risk="high",
            override_reason="Powell speech imminent",
        )
    )
    client = create_discord_client(settings, runtime, adapter=fake_adapter)
    message = FakeMessage(
        channel=FakeChannel(name="aict2"),
        content="!accuracy report",
        attachments=[],
        author=FakeAuthor(bot=False),
    )

    asyncio.run(client.on_message(message))

    assert observed["macro_state"] == "Risk-Off"
    assert observed["vix"] == 23.1
