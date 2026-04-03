from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from aict2.macro.dashboard_core import MacroInputs
from aict2.macro.signal_parsing import (
    calendar_event_override,
    fear_greed_from_embed,
    headline_sentiment_from_embed,
    put_call_from_embed,
    tone_trend,
    urgent_news_override,
    vix_from_text,
)


def build_macro_inputs_from_messages(
    messages: Iterable[Any],
    now: datetime,
    fallback: MacroInputs,
) -> MacroInputs:
    headline_signals = []
    fear_greed_score: float | None = None
    vix: float | None = None
    put_call_ratio: float | None = None
    major_event_label: str | None = None

    ordered_messages = sorted(
        list(messages),
        key=lambda message: getattr(message, "created_at", now),
        reverse=True,
    )

    for message in ordered_messages:
        created_at = getattr(message, "created_at", now)
        content = str(getattr(message, "content", "") or "")

        if vix is None:
            vix = vix_from_text(content)

        for embed in list(getattr(message, "embeds", []) or []):
            headline = headline_sentiment_from_embed(embed, created_at)
            if headline is not None:
                headline_signals.append(headline)
                continue

            if fear_greed_score is None:
                fear_greed_score = fear_greed_from_embed(embed)

            if put_call_ratio is None:
                put_call_ratio = put_call_from_embed(embed)

            if major_event_label is None:
                major_event_label = urgent_news_override(embed, created_at, now)
            if major_event_label is None:
                major_event_label = calendar_event_override(embed, now)

    latest_headline = max(headline_signals, key=lambda item: item.created_at) if headline_signals else None
    return MacroInputs(
        bull_percent=latest_headline.bull_percent if latest_headline else fallback.bull_percent,
        bear_percent=latest_headline.bear_percent if latest_headline else fallback.bear_percent,
        fear_greed_score=(
            fear_greed_score if fear_greed_score is not None else fallback.fear_greed_score
        ),
        vix=vix if vix is not None else fallback.vix,
        vix_source='market-news' if vix is not None else fallback.vix_source,
        put_call_ratio=put_call_ratio if put_call_ratio is not None else fallback.put_call_ratio,
        tone_trend=tone_trend(headline_signals, fallback.tone_trend),
        major_event_active=major_event_label is not None,
        major_event_label=major_event_label,
    )


async def load_macro_inputs_from_channel(
    channel: Any,
    now: datetime,
    fallback: MacroInputs,
    *,
    limit: int = 200,
) -> MacroInputs:
    messages: list[Any] = []
    async for message in channel.history(limit=limit):
        messages.append(message)
    return build_macro_inputs_from_messages(messages=messages, now=now, fallback=fallback)
