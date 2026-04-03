from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class HeadlineSentiment:
    bull_percent: float
    bear_percent: float
    created_at: datetime


def extract_first_float(text: str) -> float | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def headline_sentiment_from_embed(embed: Any, created_at: datetime) -> HeadlineSentiment | None:
    title = str(getattr(embed, "title", "") or "")
    if "Headline Sentiment" not in title:
        return None

    bull_percent: float | None = None
    bear_percent: float | None = None
    for field in list(getattr(embed, "fields", []) or []):
        name = str(getattr(field, "name", "") or "")
        value = str(getattr(field, "value", "") or "")
        if name == "Bullish":
            bull_percent = extract_first_float(value)
        elif name == "Bearish":
            bear_percent = extract_first_float(value)

    if bull_percent is None or bear_percent is None:
        return None
    return HeadlineSentiment(
        bull_percent=bull_percent,
        bear_percent=bear_percent,
        created_at=created_at,
    )


def fear_greed_from_embed(embed: Any) -> float | None:
    title = str(getattr(embed, "title", "") or "")
    if "Fear & Greed" not in title:
        return None
    return extract_first_float(title)


def put_call_from_embed(embed: Any) -> float | None:
    title = str(getattr(embed, "title", "") or "")
    if "Put/Call Ratio" not in title:
        return None
    index_ratio: float | None = None
    equity_ratio: float | None = None
    for field in list(getattr(embed, "fields", []) or []):
        name = str(getattr(field, "name", "") or "")
        value = str(getattr(field, "value", "") or "")
        if name == "Index P/C":
            index_ratio = extract_first_float(value)
        elif name == "Equity P/C":
            equity_ratio = extract_first_float(value)
    return index_ratio if index_ratio is not None else equity_ratio


def vix_from_text(text: str) -> float | None:
    match = re.search(r"\bVIX\b[^0-9-]*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def calendar_event_override(embed: Any, now: datetime) -> str | None:
    title = str(getattr(embed, "title", "") or "")
    description = str(getattr(embed, "description", "") or "")
    if "US Economic Calendar" not in title:
        return None

    for raw_line in description.splitlines():
        line = raw_line.strip()
        match = re.search(
            r"(?P<impact>[^\s]+)\s+\*\*(?P<time>\d{1,2}:\d{2}\s+[AP]M)\s+ET\*\*\s+.+?\s+(?P<event>[^\n]+)$",
            line,
        )
        if match is None:
            continue
        impact = match.group("impact")
        time_text = match.group("time")
        event_name = match.group("event")
        event_dt = datetime.strptime(time_text, "%I:%M %p").replace(
            year=now.year,
            month=now.month,
            day=now.day,
            tzinfo=ET,
        )
        delta_minutes = (event_dt - now.astimezone(ET)).total_seconds() / 60
        if delta_minutes < 0:
            continue
        is_high_impact = "ðŸ”´" in impact or "🔴" in impact
        is_medium_impact = "ðŸŸ " in impact or "🟠" in impact
        if is_high_impact and delta_minutes <= 90:
            return f"{event_name.strip()} at {time_text} ET"
        if is_medium_impact and delta_minutes <= 60:
            return f"{event_name.strip()} at {time_text} ET"
    return None


def urgent_news_override(embed: Any, created_at: datetime, now: datetime) -> str | None:
    footer = getattr(embed, "footer", None)
    footer_text = str(getattr(footer, "text", "") or "")
    if "Urgency: CRITICAL" not in footer_text and "Urgency: HIGH" not in footer_text:
        return None
    age_minutes = (now - created_at).total_seconds() / 60
    if age_minutes > 60:
        return None
    title = str(getattr(embed, "title", "") or "").strip()
    return title or "High-urgency market news"


def tone_trend(headlines: list[HeadlineSentiment], fallback: str) -> str:
    if len(headlines) < 2:
        return fallback
    ordered = sorted(headlines, key=lambda item: item.created_at)
    previous = ordered[-2].bull_percent - ordered[-2].bear_percent
    current = ordered[-1].bull_percent - ordered[-1].bear_percent
    if current > previous:
        return "improving"
    if current < previous:
        return "worsening"
    return "stable"
