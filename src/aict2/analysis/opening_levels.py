from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from aict2.analysis.market_frame import format_price

ET = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class OpeningLevelsSummary:
    public_summary: str
    internal_summary: str
    confluence: str


def _select_intraday_frame(frames: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    for timeframe in ("30S", "1M", "5M", "15M", "1H", "4H"):
        frame = frames.get(timeframe)
        if frame is not None and not frame.empty:
            return frame
    return None


def _prepare_intraday(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    et_times = enriched["time"].dt.tz_convert(ET)
    enriched["et_time"] = et_times
    enriched["et_date"] = et_times.dt.date
    enriched["et_clock"] = et_times.dt.time
    enriched["iso_year"] = et_times.dt.isocalendar().year
    enriched["iso_week"] = et_times.dt.isocalendar().week
    enriched["month"] = et_times.dt.month
    enriched["quarter"] = ((et_times.dt.month - 1) // 3) + 1
    return enriched


def _current_session_date(frame: pd.DataFrame):
    latest = frame.iloc[-1]["et_time"]
    if latest.hour >= 18:
        return latest.date() + timedelta(days=1)
    return latest.date()


def _true_day_open(frame: pd.DataFrame, trade_date) -> float | None:
    session_start = datetime.combine(trade_date, time(hour=18, minute=0), tzinfo=ET) - timedelta(days=1)
    session_rows = frame[frame["et_time"] >= session_start]
    if session_rows.empty:
        return None
    return float(session_rows.iloc[0]["open"])


def _midnight_open(frame: pd.DataFrame, trade_date) -> float | None:
    rows = frame[
        (frame["et_date"] == trade_date)
        & (frame["et_clock"] >= time(hour=0, minute=0))
    ]
    if rows.empty:
        return None
    return float(rows.iloc[0]["open"])


def _rth_open(frame: pd.DataFrame, trade_date) -> float | None:
    rows = frame[
        (frame["et_date"] == trade_date)
        & (frame["et_clock"] >= time(hour=9, minute=30))
    ]
    if rows.empty:
        return None
    return float(rows.iloc[0]["open"])


def _daily_open_for_group(daily: pd.DataFrame, mask: pd.Series) -> float | None:
    rows = daily[mask]
    if rows.empty:
        return None
    return float(rows.iloc[0]["open"])


def _is_public_open_relevant(label: str, value: float, latest_price: float) -> bool:
    if label != "Monthly Open":
        return True
    if latest_price <= 0:
        return False
    return abs(value - latest_price) / latest_price <= 0.12


def derive_opening_levels_summary(
    frames: dict[str, pd.DataFrame],
    *,
    bias: str,
) -> OpeningLevelsSummary:
    intraday = _select_intraday_frame(frames)
    daily = frames.get("Daily")
    if intraday is None:
        summary = "Opening levels unavailable from current upload"
        return OpeningLevelsSummary(public_summary=summary, internal_summary=summary, confluence=summary)

    prepared_intraday = _prepare_intraday(intraday)
    latest_price = float(prepared_intraday.iloc[-1]["close"])
    trade_date = _current_session_date(prepared_intraday)

    lines: list[str] = []
    internal_lines: list[str] = []
    comparison_levels: list[tuple[str, float]] = []

    true_day_open = _true_day_open(prepared_intraday, trade_date)
    midnight_open = _midnight_open(prepared_intraday, trade_date)
    rth_open = _rth_open(prepared_intraday, trade_date)
    for label, value in (
        ("True Day Open", true_day_open),
        ("Midnight Open", midnight_open),
        ("RTH Open", rth_open),
    ):
        if value is not None:
            lines.append(f"{label} {format_price(value)}")
            internal_lines.append(f"{label} {format_price(value)}")
            comparison_levels.append((label, value))

    if daily is not None and not daily.empty:
        prepared_daily = daily.copy()
        daily_et = prepared_daily["time"].dt.tz_convert(ET)
        prepared_daily["trade_date"] = daily_et.dt.date
        prepared_daily["iso_year"] = daily_et.dt.isocalendar().year
        prepared_daily["iso_week"] = daily_et.dt.isocalendar().week
        prepared_daily["month"] = daily_et.dt.month
        prepared_daily["quarter"] = ((daily_et.dt.month - 1) // 3) + 1

        latest_row = prepared_daily.iloc[-1]
        weekly_open = _daily_open_for_group(
            prepared_daily,
            (prepared_daily["iso_year"] == latest_row["iso_year"])
            & (prepared_daily["iso_week"] == latest_row["iso_week"]),
        )
        monthly_open = _daily_open_for_group(
            prepared_daily,
            prepared_daily["month"] == latest_row["month"],
        )
        quarterly_open = _daily_open_for_group(
            prepared_daily,
            prepared_daily["quarter"] == latest_row["quarter"],
        )

        for label, value in (
            ("Weekly Open", weekly_open),
            ("Monthly Open", monthly_open),
        ):
            if value is not None:
                internal_lines.append(f"{label} {format_price(value)}")
                if _is_public_open_relevant(label, value, latest_price):
                    lines.append(f"{label} {format_price(value)}")
                comparison_levels.append((label, value))
        if quarterly_open is not None:
            internal_lines.append(f"Quarterly Open {format_price(quarterly_open)}")
            comparison_levels.append(("Quarterly Open", quarterly_open))

    if not lines:
        summary = "Opening levels unavailable from current upload"
        return OpeningLevelsSummary(public_summary=summary, internal_summary=summary, confluence=summary)

    if bias in {"bullish", "bearish"} and comparison_levels:
        supportive = 0
        conflicting = 0
        for _, level in comparison_levels:
            if latest_price > level and bias == "bullish":
                supportive += 1
            elif latest_price < level and bias == "bearish":
                supportive += 1
            elif latest_price < level and bias == "bullish":
                conflicting += 1
            elif latest_price > level and bias == "bearish":
                conflicting += 1
        if supportive >= conflicting + 2:
            confluence = f"Opening prices support the {bias} thesis."
        elif conflicting >= supportive + 2:
            confluence = f"Opening prices conflict with the {bias} thesis."
        else:
            confluence = f"Opening prices are neutral to the {bias} thesis."
    else:
        confluence = "Opening prices are informational only right now."

    return OpeningLevelsSummary(
        public_summary=" | ".join(lines),
        internal_summary=" | ".join(internal_lines),
        confluence=confluence,
    )
