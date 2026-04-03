from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from aict2.analysis.market_frame import format_price

_LARGE_GAP_POINTS = 100.0
_NDOG_VALID_DAYS = 5
_NWOG_VALID_DAYS = 20


@dataclass(frozen=True, slots=True)
class GapSummary:
    public_summary: str
    internal_summary: str
    nwog: GapLevel | None = None
    ndog: GapLevel | None = None


@dataclass(frozen=True, slots=True)
class GapLevel:
    gap_type: str
    created_at: datetime
    lower: float
    upper: float
    ce: float
    age_days: int
    is_large: bool

    def quadrant_label(self, current_price: float) -> str | None:
        if not self.is_large:
            return None
        span = self.upper - self.lower
        quarter_25 = self.lower + (span * 0.25)
        quarter_50 = self.ce
        quarter_75 = self.lower + (span * 0.75)
        if current_price <= quarter_25:
            return f'below 25% ({format_price(quarter_25)})'
        if current_price <= quarter_50:
            return f'between 25% and 50% ({format_price(quarter_50)})'
        if current_price <= quarter_75:
            return f'between 50% and 75% ({format_price(quarter_75)})'
        if current_price <= self.upper:
            return f'between 75% and high ({format_price(self.upper)})'
        return f'above high ({format_price(self.upper)})'

    def quadrant_summary(self) -> str | None:
        if not self.is_large:
            return None
        span = self.upper - self.lower
        quarter_25 = self.lower + (span * 0.25)
        quarter_50 = self.ce
        quarter_75 = self.lower + (span * 0.75)
        return (
            f'25% {format_price(quarter_25)} / '
            f'50% {format_price(quarter_50)} / '
            f'75% {format_price(quarter_75)}'
        )

    def label(self) -> str:
        return (
            f'{self.gap_type} {format_price(self.lower)}-{format_price(self.upper)} '
            f'(CE {format_price(self.ce)})'
        )


def _prepare_daily(daily: pd.DataFrame) -> pd.DataFrame:
    prepared = daily.copy()
    prepared['trade_date'] = prepared['time'].dt.tz_convert('America/New_York').dt.date
    prepared['iso_year'] = prepared['time'].dt.tz_convert('America/New_York').dt.isocalendar().year
    prepared['iso_week'] = prepared['time'].dt.tz_convert('America/New_York').dt.isocalendar().week
    return prepared.reset_index(drop=True)


def _detect_ndogs(prepared: pd.DataFrame) -> list[GapLevel]:
    gaps: list[GapLevel] = []
    for index in range(1, len(prepared)):
        previous = prepared.iloc[index - 1]
        current = prepared.iloc[index]
        previous_close = float(previous['close'])
        current_open = float(current['open'])
        if abs(current_open - previous_close) < 0.25:
            continue
        lower = min(previous_close, current_open)
        upper = max(previous_close, current_open)
        gaps.append(
            GapLevel(
                gap_type='NDOG',
                created_at=current['time'].to_pydatetime(),
                lower=lower,
                upper=upper,
                ce=(lower + upper) / 2,
                age_days=(len(prepared) - 1) - index,
                is_large=(upper - lower) >= _LARGE_GAP_POINTS,
            )
        )
    return gaps


def _detect_nwogs(prepared: pd.DataFrame) -> list[GapLevel]:
    gaps: list[GapLevel] = []
    grouped = prepared.groupby(['iso_year', 'iso_week'], sort=False)
    weeks = list(grouped)
    for week_index in range(1, len(weeks)):
        (_, _), previous_week = weeks[week_index - 1]
        (_, _), current_week = weeks[week_index]
        previous_close = float(previous_week.iloc[-1]['close'])
        current_open = float(current_week.iloc[0]['open'])
        if abs(current_open - previous_close) < 0.25:
            continue
        lower = min(previous_close, current_open)
        upper = max(previous_close, current_open)
        created_row_index = int(current_week.index[0])
        age_days = (len(prepared) - 1) - created_row_index
        gaps.append(
            GapLevel(
                gap_type='NWOG',
                created_at=current_week.iloc[0]['time'].to_pydatetime(),
                lower=lower,
                upper=upper,
                ce=(lower + upper) / 2,
                age_days=age_days,
                is_large=(upper - lower) >= _LARGE_GAP_POINTS,
            )
        )
    return gaps


def _active_gap(gaps: list[GapLevel], *, validity_days: int, current_price: float) -> GapLevel | None:
    active = [gap for gap in gaps if gap.age_days < validity_days]
    if not active:
        return None
    large_relevant = [
        gap
        for gap in active
        if gap.is_large
        and current_price >= gap.lower - (gap.upper - gap.lower)
        and current_price <= gap.upper + (gap.upper - gap.lower)
    ]
    if large_relevant:
        return min(large_relevant, key=lambda gap: abs(current_price - gap.ce))
    return min(active, key=lambda gap: abs(current_price - gap.ce))


def _public_gap_line(gap: GapLevel, current_price: float) -> str:
    relationship: str
    if gap.lower <= current_price <= gap.upper:
        relationship = 'trading inside'
    elif current_price > gap.upper:
        relationship = 'holding above'
    else:
        relationship = 'holding below'
    quadrant = gap.quadrant_label(current_price)
    quadrant_levels = gap.quadrant_summary()
    parts = [f'{gap.label()} {relationship}']
    if quadrant is not None and relationship == 'trading inside':
        parts.append(quadrant)
    if quadrant_levels is not None:
        parts.append(quadrant_levels)
    return '; '.join(parts)


def derive_gap_summary(frames: dict[str, pd.DataFrame]) -> GapSummary:
    daily = frames.get('Daily')
    if daily is None or daily.empty or len(daily) < 2:
        summary = 'No active NDOG/NWOG'
        return GapSummary(public_summary=summary, internal_summary=summary)

    prepared = _prepare_daily(daily)
    current_price = float(prepared.iloc[-1]['close'])
    ndog = _active_gap(_detect_ndogs(prepared), validity_days=_NDOG_VALID_DAYS, current_price=current_price)
    nwog = _active_gap(_detect_nwogs(prepared), validity_days=_NWOG_VALID_DAYS, current_price=current_price)

    public_parts: list[str] = []
    internal_parts: list[str] = []
    if nwog is not None:
        public_parts.append(_public_gap_line(nwog, current_price))
        internal_parts.append(_public_gap_line(nwog, current_price))
    if ndog is not None:
        public_parts.append(_public_gap_line(ndog, current_price))
        internal_parts.append(_public_gap_line(ndog, current_price))

    if not public_parts:
        summary = 'No active NDOG/NWOG'
        return GapSummary(public_summary=summary, internal_summary=summary)

    return GapSummary(
        public_summary=' | '.join(public_parts),
        internal_summary=' | '.join(internal_parts),
        nwog=nwog,
        ndog=ndog,
    )


def _next_level_for_bias(gap: GapLevel, *, bias: str, current_price: float) -> float | None:
    levels = [gap.lower, gap.ce, gap.upper]
    if gap.is_large:
        span = gap.upper - gap.lower
        levels = [
            gap.lower,
            gap.lower + (span * 0.25),
            gap.ce,
            gap.lower + (span * 0.75),
            gap.upper,
        ]
    rounded = sorted({round(level, 2): level for level in levels}.values())
    if bias == 'bullish':
        for level in rounded:
            if level > current_price:
                return level
        return None
    if bias == 'bearish':
        for level in reversed(rounded):
            if level < current_price:
                return level
        return None
    return None


def derive_gap_confluence(summary: GapSummary, *, bias: str, current_price: float) -> str:
    if bias not in {'bullish', 'bearish'}:
        return 'Gap structure is informational only right now.'

    candidates = [gap for gap in (summary.nwog, summary.ndog) if gap is not None]
    if not candidates:
        return 'No active NDOG/NWOG is shaping the current path.'

    chosen = min(candidates, key=lambda gap: abs(current_price - gap.ce))
    next_level = _next_level_for_bias(chosen, bias=bias, current_price=current_price)
    if next_level is None:
        return f'{chosen.gap_type} is noted, but it is not adding meaningful pathing right now.'

    return (
        f'{chosen.gap_type} supports {bias} pathing toward '
        f'{format_price(next_level)} without overriding the main thesis.'
    )
