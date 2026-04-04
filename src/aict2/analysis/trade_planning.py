from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aict2.analysis.market_frame import ChartFrameFacts, format_price

SCALP_EXECUTION_TIMEFRAMES = {'5M', '1M'}
SCALP_STOP_FLOOR = 12.0
SCALP_STOP_CEILING = 60.0
SCALP_TARGET_MIN = 40.0
SCALP_TARGET_MAX = 50.0
SCALP_TARGET_DEFAULT = 45.0


@dataclass(frozen=True, slots=True)
class ChartDerivedPlan:
    bias: str
    daily_profile: str
    entry: float
    stop: float
    target: float
    liquidity_summary: str
    reference_context: str
    internal_reference_context: str
    draw_on_liquidity: str
    htf_reference: str
    stop_run_summary: str
    gap_summary: str
    gap_confluence: str
    opening_summary: str
    opening_confluence: str
    pd_array_summary: str
    pd_array_confluence: str
    entry_model: str
    tp_model: str
    target_reason: str
    needs_confirmation: bool
    requires_retrace: bool


def weighted_bias_score(facts: dict[str, ChartFrameFacts]) -> str:
    weights = {
        'Daily': 5,
        '4H': 4,
        '1H': 3,
        '15M': 2,
        '5M': 1,
        '1M': 1,
    }
    score = 0
    for timeframe, fact in facts.items():
        weight = weights.get(timeframe, 1)
        if fact.bias == 'bullish':
            score += weight
        elif fact.bias == 'bearish':
            score -= weight
    threshold = 1 if len(facts) == 1 else 2
    if score >= threshold:
        return 'bullish'
    if score <= -threshold:
        return 'bearish'
    return 'mixed'


def needs_confirmation(
    facts: dict[str, ChartFrameFacts],
    bias: str,
    execution_timeframe: str,
) -> bool:
    directional_biases = {fact.bias for fact in facts.values() if fact.bias in {'bullish', 'bearish'}}
    timeframe_conflict = len(directional_biases) > 1
    execution_bias = facts[execution_timeframe].bias
    execution_disagrees = execution_bias in {'bullish', 'bearish'} and execution_bias != bias
    unresolved_execution = (
        execution_timeframe in {'30S', '1M', '5M', '15M'}
        and facts[execution_timeframe].liquidity_summary.startswith('No clear liquidity sweep')
    )
    return timeframe_conflict or bias == 'mixed' or execution_disagrees or unresolved_execution


def requires_retrace(bias: str, execution_fact: ChartFrameFacts) -> bool:
    if bias == 'bearish':
        return execution_fact.range_position <= 0.15
    if bias == 'bullish':
        return execution_fact.range_position >= 0.85
    return False


def derive_daily_profile(execution_frame: pd.DataFrame, bias: str, fact: ChartFrameFacts) -> str:
    lookback = max(3, min(len(execution_frame), 20))
    recent = execution_frame.tail(lookback)
    first_close = float(recent['close'].iloc[0])
    last_close = float(recent['close'].iloc[-1])
    range_high = float(recent['high'].max())
    range_low = float(recent['low'].min())
    span = max(range_high - range_low, 0.25)
    midpoint = (range_high + range_low) / 2
    close_position = (last_close - range_low) / span

    if abs(last_close - first_close) <= span * 0.2:
        return 'consolidation'

    if bias == 'bullish':
        if fact.sell_side_sweep:
            return 'reversal'
        if fact.reclaimed_high and first_close < midpoint:
            return 'reversal'
        return 'reversal' if first_close < midpoint and close_position >= 0.65 else 'continuation'
    if bias == 'bearish':
        if fact.buy_side_sweep:
            return 'reversal'
        if fact.broke_low and first_close > midpoint:
            return 'reversal'
        return 'reversal' if first_close > midpoint and close_position <= 0.35 else 'continuation'
    return 'transition'


def round_tick(price: float) -> float:
    return round(price * 4) / 4


def _is_scalp_execution_timeframe(execution_timeframe: str) -> bool:
    return execution_timeframe in SCALP_EXECUTION_TIMEFRAMES


def _extract_price(label: str) -> float | None:
    import re

    matches = re.findall(r'(-?\d+(?:\.\d+)?)', label)
    if not matches:
        return None
    return float(matches[-1])


def _resolve_scalp_invalidation_price(
    execution_frame: pd.DataFrame,
    fact: ChartFrameFacts,
    *,
    bias: str,
    entry_model: str,
) -> float:
    recent = execution_frame.tail(max(3, min(len(execution_frame), 6))).reset_index(drop=True)
    if recent.empty:
        return fact.anchor_close

    latest = recent.iloc[-1]
    prior = recent.iloc[-2] if len(recent) >= 2 else latest
    normalized_entry_model = entry_model.lower()

    if 'ifvg' in normalized_entry_model:
        if bias == 'bullish':
            return max(float(prior['high']), min(float(latest['open']), float(latest['close'])))
        if bias == 'bearish':
            return min(float(prior['low']), max(float(latest['open']), float(latest['close'])))

    if 'breaker' in normalized_entry_model:
        if bias == 'bullish':
            return max(float(prior['open']), float(prior['close']))
        if bias == 'bearish':
            return min(float(prior['open']), float(prior['close']))

    if bias == 'bullish':
        return (
            fact.latest_swing_low
            if fact.latest_swing_low is not None
            else float(recent['low'].min())
        )
    if bias == 'bearish':
        return (
            fact.latest_swing_high
            if fact.latest_swing_high is not None
            else float(recent['high'].max())
        )
    return fact.anchor_close


def _place_scalp_stop(
    *,
    entry: float,
    invalidation: float,
    bias: str,
    floor_points: float = SCALP_STOP_FLOOR,
) -> float:
    if bias == 'bullish':
        distance = max(entry - invalidation, floor_points)
        return round_tick(entry - distance)
    if bias == 'bearish':
        distance = max(invalidation - entry, floor_points)
        return round_tick(entry + distance)
    return entry


def _resolve_scalp_target(
    *,
    entry: float,
    stop: float,
    bias: str,
    draw_on_liquidity: str,
) -> float | None:
    risk = abs(entry - stop)
    if risk <= 0 or bias not in {'bullish', 'bearish'}:
        return None

    directional_sign = 1.0 if bias == 'bullish' else -1.0
    liquidity_target = _extract_price(draw_on_liquidity)
    min_target = entry + (directional_sign * SCALP_TARGET_MIN)
    max_target = entry + (directional_sign * SCALP_TARGET_MAX)
    default_target = entry + (directional_sign * SCALP_TARGET_DEFAULT)

    if liquidity_target is None:
        return round_tick(default_target)

    distance = abs(liquidity_target - entry)
    if (bias == 'bullish' and liquidity_target <= entry) or (
        bias == 'bearish' and liquidity_target >= entry
    ):
        return None
    if distance < max(SCALP_TARGET_MIN, risk * 1.75):
        return None
    if SCALP_TARGET_MIN <= distance <= SCALP_TARGET_MAX:
        return round_tick(liquidity_target)
    if distance > SCALP_TARGET_MAX:
        return round_tick(default_target)
    return None


def _derive_structure_trade_levels(
    execution_frame: pd.DataFrame,
    bias: str,
    fact: ChartFrameFacts,
) -> tuple[float, float, float]:
    recent = execution_frame.tail(max(4, min(len(execution_frame), 12)))
    last_close = float(execution_frame['close'].iloc[-1])
    entry = last_close
    average_bar = float((recent['high'] - recent['low']).mean()) if not recent.empty else 5.0
    min_risk = max(average_bar * 0.8, 5.0)
    tick_buffer = max(0.25, average_bar * 0.1)
    recent_high = float(recent['high'].max())
    recent_low = float(recent['low'].min())
    midpoint = (recent_high + recent_low) / 2
    retrace_required = requires_retrace(bias, fact)

    if bias == 'bullish':
        if retrace_required:
            retrace_anchor = max(
                midpoint,
                fact.latest_swing_high or midpoint,
                fact.anchor_close,
            )
            entry = min(last_close - tick_buffer, retrace_anchor)
        swing_stop = (
            fact.latest_swing_low - tick_buffer if fact.latest_swing_low is not None else recent_low
        )
        stop = min(recent_low, swing_stop, entry - min_risk)
        risk = max(entry - stop, min_risk)
        stop = entry - risk
        structure_target = max(fact.latest_swing_high or entry, recent_high) + tick_buffer
        target = max(entry + (risk * 2.0), structure_target)
    elif bias == 'bearish':
        if retrace_required:
            broken_level = fact.latest_swing_low if fact.broke_low else None
            retrace_anchor = max(
                midpoint,
                broken_level or midpoint,
                min(fact.anchor_close, recent_high - tick_buffer),
            )
            entry = max(last_close + tick_buffer, retrace_anchor)
        swing_stop = (
            fact.latest_swing_high + tick_buffer
            if fact.latest_swing_high is not None
            else recent_high
        )
        stop = max(recent_high, swing_stop, entry + min_risk)
        risk = max(stop - entry, min_risk)
        stop = entry + risk
        structure_target = min(fact.latest_swing_low or entry, recent_low) - tick_buffer
        target = min(entry - (risk * 2.0), structure_target)
    else:
        return 0.0, 0.0, 0.0

    return round_tick(entry), round_tick(stop), round_tick(target)


def derive_scalp_trade_levels(
    execution_frame: pd.DataFrame,
    bias: str,
    fact: ChartFrameFacts,
    *,
    execution_timeframe: str,
    entry_model: str,
    draw_on_liquidity: str,
) -> tuple[float, float, float, str, str]:
    if bias not in {'bullish', 'bearish'}:
        return 0.0, 0.0, 0.0, 'Scalp Liquidity', 'Scalp construction needs directional bias.'

    entry = round_tick(float(execution_frame['close'].iloc[-1]))
    invalidation = _resolve_scalp_invalidation_price(
        execution_frame,
        fact,
        bias=bias,
        entry_model=entry_model,
    )
    stop = _place_scalp_stop(entry=entry, invalidation=invalidation, bias=bias)
    if abs(entry - stop) > SCALP_STOP_CEILING:
        return (
            0.0,
            0.0,
            0.0,
            'Scalp Liquidity',
            'Scalp invalidation exceeds the allowed stop envelope.',
        )

    target = _resolve_scalp_target(
        entry=entry,
        stop=stop,
        bias=bias,
        draw_on_liquidity=draw_on_liquidity,
    )
    if target is None:
        return (
            0.0,
            0.0,
            0.0,
            'Scalp Liquidity',
            'Nearest execution liquidity cannot support a 40-50 point scalp.',
        )

    return (
        entry,
        stop,
        target,
        'Scalp Liquidity',
        'Nearest execution liquidity fits the 40-50 point scalp band.',
    )


def derive_trade_levels(
    execution_frame: pd.DataFrame,
    bias: str,
    fact: ChartFrameFacts,
    *,
    execution_timeframe: str,
    entry_model: str,
    draw_on_liquidity: str,
) -> tuple[float, float, float, str, str]:
    if _is_scalp_execution_timeframe(execution_timeframe):
        return derive_scalp_trade_levels(
            execution_frame,
            bias,
            fact,
            execution_timeframe=execution_timeframe,
            entry_model=entry_model,
            draw_on_liquidity=draw_on_liquidity,
        )

    entry, stop, target = _derive_structure_trade_levels(execution_frame, bias, fact)
    risk = abs(entry - stop)
    if risk <= 0:
        return (
            entry,
            stop,
            target,
            '2R',
            'Defaulting to a full 2R objective unless external liquidity is closer.',
        )
    if abs(target - entry) >= risk * 1.95 and abs(target - entry) <= risk * 2.05:
        return (
            entry,
            stop,
            target,
            '2R',
            'A full 2R objective comes before the next meaningful external liquidity target.',
        )
    return (
        entry,
        stop,
        target,
        'Draw on Liquidity',
        'External liquidity caps the trade before a full 2R expansion.',
    )


def derive_reference_context(frames: dict[str, pd.DataFrame]) -> tuple[str, str]:
    daily = frames.get('Daily')
    if daily is None or daily.empty:
        summary = 'Using latest uploaded higher-timeframe structure only'
        return summary, summary

    public_lines: list[str] = []
    internal_lines: list[str] = []
    if len(daily) >= 2:
        prior_day = daily.iloc[-2]
        line = (
            f"PDH {format_price(float(prior_day['high']))} / PDL {format_price(float(prior_day['low']))}"
        )
        public_lines.append(line)
        internal_lines.append(line)

    prior_week = daily.iloc[max(0, len(daily) - 6) : len(daily) - 1]
    if not prior_week.empty:
        line = (
            'PWH '
            f"{format_price(float(prior_week['high'].max()))} / PWL {format_price(float(prior_week['low'].min()))}"
        )
        public_lines.append(line)
        internal_lines.append(line)

    prior_month = daily.iloc[max(0, len(daily) - 21) : len(daily) - 1]
    if not prior_month.empty:
        internal_lines.append(
            '20D high '
            f"{format_price(float(prior_month['high'].max()))} / 20D low {format_price(float(prior_month['low'].min()))}"
        )

    public_summary = (
        ' | '.join(public_lines) if public_lines else 'Using latest uploaded higher-timeframe structure only'
    )
    internal_summary = ' | '.join(internal_lines) if internal_lines else public_summary
    return public_summary, internal_summary
