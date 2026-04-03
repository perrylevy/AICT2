from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from zoneinfo import ZoneInfo

import discord

from aict2.macro.dashboard_core import MacroInputs
from aict2.macro.market_news import build_macro_inputs_from_messages, load_macro_inputs_from_channel

ET = ZoneInfo("America/New_York")


@dataclass
class FakeMessage:
    created_at: datetime
    content: str = ""
    embeds: list[discord.Embed] = field(default_factory=list)


@dataclass
class FakeChannel:
    messages: list[FakeMessage]

    async def history(self, limit: int = 200):
        _ = limit
        for message in self.messages:
            yield message


def _headline_embed(bull: float, bear: float) -> discord.Embed:
    embed = discord.Embed(
        title="Headline Sentiment (Last 12h)",
        description="Directional split from all tracked headlines: **Bearish Tilt**",
    )
    embed.add_field(name="Bullish", value=f"**{bull:.1f}%** (4)", inline=True)
    embed.add_field(name="Bearish", value=f"**{bear:.1f}%** (6)", inline=True)
    embed.add_field(name="Neutral", value="1", inline=True)
    return embed


def _fear_greed_embed(score: float, rating: str) -> discord.Embed:
    return discord.Embed(title=f"Fear & Greed: {score:.0f} — {rating}")


def _put_call_embed(index_ratio: float) -> discord.Embed:
    embed = discord.Embed(title="CBOE Put/Call Ratio — 2026-04-02")
    embed.add_field(name="Total P/C", value="**0.80**", inline=True)
    embed.add_field(name="Index P/C", value=f"**{index_ratio:.2f}**", inline=True)
    embed.add_field(name="Equity P/C", value="**0.66**", inline=True)
    return embed


def _calendar_embed() -> discord.Embed:
    return discord.Embed(
        title="📅 US Economic Calendar — Thursday, April 02, 2026",
        description=(
            "**1 high-impact 🔴** · **1 medium-impact 🟠**\n\n"
            "🔴 **10:00 AM ET** — ISM Services PMI\n"
            "\u200b \u200b \u200b Forecast: `52.0` | Prior: `52.6`\n"
            "🟠 **02:00 PM ET** — FOMC Minutes\n"
            "\u200b \u200b \u200b Forecast: `—` | Prior: `—`"
        ),
    )


def _urgent_news_embed() -> discord.Embed:
    embed = discord.Embed(title="🚨 Tariff escalation hits semiconductor outlook")
    embed.set_footer(text="Source: Bloomberg Markets • Urgency: CRITICAL")
    return embed


def test_build_macro_inputs_from_messages_uses_latest_signals_and_trend() -> None:
    now = datetime(2026, 4, 2, 9, 25, tzinfo=ET)
    messages = [
        FakeMessage(
            created_at=datetime(2026, 4, 2, 8, 0, tzinfo=ET),
            embeds=[_headline_embed(38.0, 62.0)],
        ),
        FakeMessage(
            created_at=datetime(2026, 4, 2, 9, 0, tzinfo=ET),
            embeds=[_headline_embed(44.0, 56.0)],
        ),
        FakeMessage(
            created_at=datetime(2026, 4, 2, 9, 5, tzinfo=ET),
            embeds=[_fear_greed_embed(28.0, "Fear")],
        ),
        FakeMessage(
            created_at=datetime(2026, 4, 2, 9, 10, tzinfo=ET),
            embeds=[_put_call_embed(0.91)],
        ),
        FakeMessage(
            created_at=datetime(2026, 4, 2, 8, 55, tzinfo=ET),
            embeds=[_calendar_embed()],
        ),
    ]

    inputs = build_macro_inputs_from_messages(
        messages=messages,
        now=now,
        fallback=MacroInputs(
            bull_percent=50.0,
            bear_percent=50.0,
            fear_greed_score=50.0,
            vix=22.4,
            vix_source="fallback",
            put_call_ratio=0.75,
            tone_trend="stable",
            major_event_active=False,
            major_event_label=None,
        ),
    )

    assert inputs.bull_percent == 44.0
    assert inputs.bear_percent == 56.0
    assert inputs.fear_greed_score == 28.0
    assert inputs.vix == 22.4
    assert inputs.vix_source == "fallback"
    assert inputs.put_call_ratio == 0.91
    assert inputs.tone_trend == "improving"
    assert inputs.major_event_active is True
    assert inputs.major_event_label is not None
    assert "ISM Services PMI" in inputs.major_event_label


def test_build_macro_inputs_from_messages_flags_urgent_news_override() -> None:
    now = datetime(2026, 4, 2, 11, 0, tzinfo=ET)
    messages = [
        FakeMessage(
            created_at=datetime(2026, 4, 2, 10, 35, tzinfo=ET),
            embeds=[_urgent_news_embed()],
        ),
    ]

    inputs = build_macro_inputs_from_messages(
        messages=messages,
        now=now,
        fallback=MacroInputs(
            bull_percent=52.0,
            bear_percent=48.0,
            fear_greed_score=55.0,
            vix=18.5,
            vix_source="fallback",
            put_call_ratio=0.71,
            tone_trend="stable",
            major_event_active=False,
            major_event_label=None,
        ),
    )

    assert inputs.major_event_active is True
    assert inputs.major_event_label is not None
    assert "Tariff escalation" in inputs.major_event_label
    assert inputs.vix == 18.5
    assert inputs.vix_source == "fallback"


def test_build_macro_inputs_from_messages_can_parse_vix_from_text_content() -> None:
    now = datetime(2026, 4, 2, 12, 0, tzinfo=ET)
    messages = [
        FakeMessage(
            created_at=datetime(2026, 4, 2, 11, 55, tzinfo=ET),
            content="Macro pulse: VIX 24.6, volatility elevated into lunch.",
        ),
    ]

    inputs = build_macro_inputs_from_messages(
        messages=messages,
        now=now,
        fallback=MacroInputs(
            bull_percent=50.0,
            bear_percent=50.0,
            fear_greed_score=50.0,
            vix=18.0,
            vix_source="fallback",
            put_call_ratio=0.75,
            tone_trend="stable",
            major_event_active=False,
            major_event_label=None,
        ),
    )

    assert inputs.vix == 24.6
    assert inputs.vix_source == "market-news"


def test_load_macro_inputs_from_channel_reads_async_history() -> None:
    now = datetime(2026, 4, 2, 9, 25, tzinfo=ET)
    channel = FakeChannel(
        messages=[
            FakeMessage(
                created_at=datetime(2026, 4, 2, 9, 0, tzinfo=ET),
                embeds=[_headline_embed(44.0, 56.0)],
            ),
            FakeMessage(
                created_at=datetime(2026, 4, 2, 9, 5, tzinfo=ET),
                embeds=[_fear_greed_embed(28.0, "Fear")],
            ),
        ]
    )

    inputs = asyncio.run(
        load_macro_inputs_from_channel(
            channel,
            now=now,
            fallback=MacroInputs(
                bull_percent=50.0,
                bear_percent=50.0,
                fear_greed_score=50.0,
                vix=18.0,
                vix_source="fallback",
                put_call_ratio=0.75,
                tone_trend="stable",
                major_event_active=False,
                major_event_label=None,
            ),
        )
    )

    assert inputs.bull_percent == 44.0
    assert inputs.fear_greed_score == 28.0
