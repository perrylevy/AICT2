from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aict2.analysis.market_frame import (
    ChartFrameFacts,
    cluster_level,
    format_price,
    liquidity_tolerance,
)


@dataclass(frozen=True, slots=True)
class PDArrayZone:
    timeframe: str
    array_type: str
    bias: str
    lower: float
    upper: float
    source_index: int

    @property
    def ce(self) -> float:
        return (self.lower + self.upper) / 2

    def label(self) -> str:
        bias_prefix = '' if self.array_type in {'IFVG', 'Breaker'} else f'{self.bias.capitalize()} '
        return (
            f'{self.timeframe} {bias_prefix}{self.array_type} '
            f'{format_price(self.lower)}-{format_price(self.upper)} '
            f'(CE {format_price(self.ce)})'
        )


@dataclass(frozen=True, slots=True)
class PDArraySummary:
    public_summary: str
    internal_summary: str


def _recent_window(frame: pd.DataFrame, limit: int = 60) -> pd.DataFrame:
    return frame.tail(min(len(frame), limit)).reset_index(drop=True)


def _detect_fvgs(frame: pd.DataFrame, timeframe: str) -> list[PDArrayZone]:
    recent = _recent_window(frame)
    zones: list[PDArrayZone] = []
    for index in range(2, len(recent)):
        left = recent.iloc[index - 2]
        current = recent.iloc[index]
        left_high = float(left['high'])
        left_low = float(left['low'])
        current_low = float(current['low'])
        current_high = float(current['high'])
        if current_low > left_high:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='FVG',
                    bias='bullish',
                    lower=left_high,
                    upper=current_low,
                    source_index=index,
                )
            )
        if current_high < left_low:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='FVG',
                    bias='bearish',
                    lower=current_high,
                    upper=left_low,
                    source_index=index,
                )
            )
    return zones


def _detect_ifvgs(frame: pd.DataFrame, timeframe: str) -> list[PDArrayZone]:
    recent = _recent_window(frame)
    if recent.empty:
        return []
    last_close = float(recent.iloc[-1]['close'])
    zones: list[PDArrayZone] = []
    for zone in _detect_fvgs(recent, timeframe):
        if zone.bias == 'bullish' and last_close < zone.lower:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='IFVG',
                    bias='bearish',
                    lower=zone.lower,
                    upper=zone.upper,
                    source_index=zone.source_index,
                )
            )
        if zone.bias == 'bearish' and last_close > zone.upper:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='IFVG',
                    bias='bullish',
                    lower=zone.lower,
                    upper=zone.upper,
                    source_index=zone.source_index,
                )
            )
    return zones


def _detect_order_blocks(frame: pd.DataFrame, timeframe: str) -> list[PDArrayZone]:
    recent = _recent_window(frame)
    if len(recent) < 3:
        return []
    average_body = float((recent['close'] - recent['open']).abs().mean())
    if average_body == 0:
        return []

    zones: list[PDArrayZone] = []
    for index in range(1, len(recent)):
        previous = recent.iloc[index - 1]
        current = recent.iloc[index]
        body = abs(float(current['close']) - float(current['open']))
        displacement = body / average_body

        previous_down = float(previous['close']) < float(previous['open'])
        previous_up = float(previous['close']) > float(previous['open'])
        current_up = float(current['close']) > float(current['open'])
        current_down = float(current['close']) < float(current['open'])

        if previous_down and current_up and displacement >= 1.4:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='OB',
                    bias='bullish',
                    lower=float(previous['low']),
                    upper=float(previous['high']),
                    source_index=index - 1,
                )
            )
        if previous_up and current_down and displacement >= 1.4:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='OB',
                    bias='bearish',
                    lower=float(previous['low']),
                    upper=float(previous['high']),
                    source_index=index - 1,
                )
            )
    return zones


def _detect_breakers(frame: pd.DataFrame, timeframe: str) -> list[PDArrayZone]:
    recent = _recent_window(frame)
    if recent.empty:
        return []
    last_close = float(recent.iloc[-1]['close'])
    zones: list[PDArrayZone] = []
    for zone in _detect_order_blocks(recent, timeframe):
        if zone.bias == 'bearish' and last_close > zone.upper:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='Breaker',
                    bias='bullish',
                    lower=zone.lower,
                    upper=zone.upper,
                    source_index=zone.source_index,
                )
            )
        if zone.bias == 'bullish' and last_close < zone.lower:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='Breaker',
                    bias='bearish',
                    lower=zone.lower,
                    upper=zone.upper,
                    source_index=zone.source_index,
                )
            )
    return zones


def _detect_volume_imbalances(frame: pd.DataFrame, timeframe: str) -> list[PDArrayZone]:
    recent = _recent_window(frame)
    zones: list[PDArrayZone] = []
    for index in range(1, len(recent)):
        previous = recent.iloc[index - 1]
        current = recent.iloc[index]
        previous_body_high = max(float(previous['open']), float(previous['close']))
        previous_body_low = min(float(previous['open']), float(previous['close']))
        current_body_high = max(float(current['open']), float(current['close']))
        current_body_low = min(float(current['open']), float(current['close']))
        if current_body_low > previous_body_high:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='VI',
                    bias='bullish',
                    lower=previous_body_high,
                    upper=current_body_low,
                    source_index=index,
                )
            )
        if current_body_high < previous_body_low:
            zones.append(
                PDArrayZone(
                    timeframe=timeframe,
                    array_type='VI',
                    bias='bearish',
                    lower=current_body_high,
                    upper=previous_body_low,
                    source_index=index,
                )
            )
    return zones


def _detect_timeframe_arrays(frame: pd.DataFrame, timeframe: str) -> list[PDArrayZone]:
    zones = [
        *_detect_ifvgs(frame, timeframe),
        *_detect_breakers(frame, timeframe),
        *_detect_fvgs(frame, timeframe),
        *_detect_order_blocks(frame, timeframe),
        *_detect_volume_imbalances(frame, timeframe),
    ]
    deduped: list[PDArrayZone] = []
    seen: set[tuple[str, str, str, float, float]] = set()
    for zone in zones:
        key = (
            zone.timeframe,
            zone.array_type,
            zone.bias,
            round(zone.lower, 2),
            round(zone.upper, 2),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(zone)
    return deduped


def _find_latest_sweep(frame: pd.DataFrame) -> tuple[int, str] | None:
    recent = _recent_window(frame, limit=20)
    if len(recent) < 4:
        return None
    tolerance = liquidity_tolerance(recent)
    latest: tuple[int, str] | None = None
    for index in range(2, len(recent)):
        prior_lows = recent['low'].iloc[:index].tolist()
        sell_pool = cluster_level(prior_lows, tolerance, 'low')
        if sell_pool is not None:
            candidate_low = float(recent['low'].iloc[index])
            candidate_close = float(recent['close'].iloc[index])
            last_close = float(recent['close'].iloc[-1])
            if (
                candidate_low < sell_pool - (tolerance * 0.25)
                and candidate_close > sell_pool
                and last_close >= sell_pool
            ):
                latest = (index, 'sell-side')

        prior_highs = recent['high'].iloc[:index].tolist()
        buy_pool = cluster_level(prior_highs, tolerance, 'high')
        if buy_pool is not None:
            candidate_high = float(recent['high'].iloc[index])
            candidate_close = float(recent['close'].iloc[index])
            last_close = float(recent['close'].iloc[-1])
            if (
                candidate_high > buy_pool + (tolerance * 0.25)
                and candidate_close < buy_pool
                and last_close <= buy_pool
            ):
                latest = (index, 'buy-side')
    return latest


def _priority(zone: PDArrayZone, intended_bias: str) -> tuple[int, int]:
    type_order = {
        'IFVG': 0,
        'Breaker': 1,
        'VI': 2,
        'FVG': 3,
        'OB': 4,
    }
    directional_penalty = 0 if zone.bias == intended_bias else 1
    return directional_penalty, type_order.get(zone.array_type, 9)


def _select_structure_path(
    zones: list[PDArrayZone],
    *,
    bias: str,
    last_close: float,
) -> str | None:
    if not zones:
        return None

    featured = [zone for zone in zones if zone.array_type in {'IFVG', 'Breaker', 'VI'}]
    current: PDArrayZone
    path_bias = bias
    if featured:
        featured_candidate = min(
            featured,
            key=lambda zone: (abs(last_close - zone.ce),) + _priority(zone, bias),
        )
        distance = abs(last_close - featured_candidate.ce)
        zone_width = max(featured_candidate.upper - featured_candidate.lower, 0.25)
        if featured_candidate.array_type in {'IFVG', 'Breaker'} or distance <= zone_width * 3:
            current = featured_candidate
            path_bias = featured_candidate.bias
        else:
            current = None  # type: ignore[assignment]
    else:
        current = None  # type: ignore[assignment]

    if current is None:
        same_bias = [zone for zone in zones if zone.bias == bias] or zones
        containing = [zone for zone in same_bias if zone.lower <= last_close <= zone.upper]
        if containing:
            current = sorted(containing, key=lambda zone: _priority(zone, bias))[0]
        else:
            if bias == 'bullish':
                below = [zone for zone in same_bias if zone.ce <= last_close]
                pool = below or same_bias
                current = min(pool, key=lambda zone: (abs(last_close - zone.ce),) + _priority(zone, bias))
            else:
                above = [zone for zone in same_bias if zone.ce >= last_close]
                pool = above or same_bias
                current = min(pool, key=lambda zone: (abs(zone.ce - last_close),) + _priority(zone, bias))

    same_bias = [zone for zone in zones if zone.bias == path_bias] or zones
    if path_bias == 'bullish':
        forward = [zone for zone in same_bias if zone.ce > current.ce]
    else:
        forward = [zone for zone in same_bias if zone.ce < current.ce]
    if forward:
        next_zone = min(forward, key=lambda zone: (abs(zone.ce - last_close),) + _priority(zone, path_bias))
        if next_zone.label() != current.label():
            return f'{current.label()} -> {next_zone.label()}'
    return current.label()


def _internal_summary(timeframe: str, zones: list[PDArrayZone]) -> str:
    if not zones:
        return f'{timeframe}: none'
    ordered = sorted(zones, key=lambda zone: (zone.source_index, zone.ce))
    return f'{timeframe}: ' + ' | '.join(zone.label() for zone in ordered[-4:])


def _select_execution_path(
    zones: list[PDArrayZone],
    *,
    bias: str,
    last_close: float,
    sweep: tuple[int, str] | None,
) -> str | None:
    if sweep is not None:
        sweep_index, sweep_side = sweep
        if sweep_side == 'sell-side' and bias == 'bullish':
            pre_sweep = [
                zone
                for zone in zones
                if zone.array_type == 'FVG'
                and zone.bias == 'bullish'
                and zone.source_index <= sweep_index
            ]
            if pre_sweep:
                chosen = min(pre_sweep, key=lambda zone: abs(last_close - zone.ce))
                return chosen.label()
        if sweep_side == 'buy-side' and bias == 'bearish':
            pre_sweep = [
                zone
                for zone in zones
                if zone.array_type == 'FVG'
                and zone.bias == 'bearish'
                and zone.source_index <= sweep_index
            ]
            if pre_sweep:
                chosen = min(pre_sweep, key=lambda zone: abs(last_close - zone.ce))
                return chosen.label()
    return _select_structure_path(zones, bias=bias, last_close=last_close)


def derive_pd_array_summary(
    frames: dict[str, pd.DataFrame],
    facts: dict[str, ChartFrameFacts],
    bias: str,
    execution_timeframe: str,
) -> PDArraySummary:
    structural_timeframe = 'Daily' if 'Daily' in frames else next(
        (timeframe for timeframe in ('4H', '1H') if timeframe in frames),
        None,
    )
    structural_summary: str | None = None
    execution_summary: str | None = None
    internal_parts: list[str] = []

    if structural_timeframe is not None:
        structural_frame = frames[structural_timeframe]
        structural_zones = _detect_timeframe_arrays(structural_frame, structural_timeframe)
        structural_last_close = float(structural_frame.iloc[-1]['close'])
        structural_bias = facts[structural_timeframe].bias
        if structural_bias not in {'bullish', 'bearish'}:
            structural_bias = bias
        structural_summary = _select_structure_path(
            structural_zones,
            bias=structural_bias,
            last_close=structural_last_close,
        )
        internal_parts.append(_internal_summary(structural_timeframe, structural_zones))

    execution_frame = frames[execution_timeframe]
    execution_zones = _detect_timeframe_arrays(execution_frame, execution_timeframe)
    execution_last_close = float(execution_frame.iloc[-1]['close'])
    execution_bias = facts[execution_timeframe].bias
    if execution_bias not in {'bullish', 'bearish'}:
        execution_bias = bias
    execution_summary = _select_execution_path(
        execution_zones,
        bias=execution_bias,
        last_close=execution_last_close,
        sweep=_find_latest_sweep(execution_frame),
    )
    internal_parts.append(_internal_summary(execution_timeframe, execution_zones))

    public_parts: list[str] = []
    if structural_summary is not None:
        public_parts.append(f'Daily Structure: {structural_summary}')
    if execution_summary is not None and execution_timeframe != structural_timeframe:
        public_parts.append(f'Execution: {execution_summary}')
    elif execution_summary is not None and not public_parts:
        public_parts.append(f'Execution: {execution_summary}')

    if not public_parts:
        summary = 'No clear PD array ranked yet'
        return PDArraySummary(public_summary=summary, internal_summary=summary)

    return PDArraySummary(
        public_summary=' | '.join(public_parts),
        internal_summary=' || '.join(internal_parts),
    )


def derive_pd_array_confluence(
    frames: dict[str, pd.DataFrame],
    facts: dict[str, ChartFrameFacts],
    bias: str,
) -> str:
    if bias not in {'bullish', 'bearish'}:
        return 'Daily arrays are informational only right now.'

    structural_timeframe = 'Daily' if 'Daily' in frames else next(
        (timeframe for timeframe in ('4H', '1H') if timeframe in frames),
        None,
    )
    if structural_timeframe is None:
        return 'Daily arrays are informational only right now.'

    structural_frame = frames[structural_timeframe]
    zones = _detect_timeframe_arrays(structural_frame, structural_timeframe)
    if not zones:
        return 'Daily arrays are informational only right now.'

    last_close = float(structural_frame.iloc[-1]['close'])
    nearest = min(zones, key=lambda zone: abs(last_close - zone.ce))
    zone_width = max(nearest.upper - nearest.lower, 0.25)
    distance = abs(last_close - nearest.ce)
    if distance > zone_width * 3:
        return f'{structural_timeframe} arrays are neutral to the {bias} thesis.'

    descriptor = f'{structural_timeframe} {nearest.array_type}'
    if nearest.bias == bias:
        return f'{descriptor} supports the {bias} thesis.'
    return f'{descriptor} conflicts with the {bias} thesis.'


def derive_htf_array_reference(
    frames: dict[str, pd.DataFrame],
    *,
    bias: str,
) -> str | None:
    if bias not in {'bullish', 'bearish'}:
        return None

    for timeframe in ('4H', '1H'):
        frame = frames.get(timeframe)
        if frame is None or frame.empty:
            continue
        zones = [
            zone
            for zone in _detect_timeframe_arrays(frame, timeframe)
            if zone.array_type in {'FVG', 'IFVG'}
        ]
        if not zones:
            continue

        last_close = float(frame.iloc[-1]['close'])
        aligned = [zone for zone in zones if zone.bias == bias]
        pool = aligned or zones
        chosen = min(
            pool,
            key=lambda zone: (abs(last_close - zone.ce),) + _priority(zone, bias),
        )
        return chosen.label()

    return None


def derive_execution_entry_trigger(
    frames: dict[str, pd.DataFrame],
    *,
    bias: str,
    execution_timeframe: str,
) -> str | None:
    if bias not in {'bullish', 'bearish'}:
        return None

    timeframes = [timeframe for timeframe in ('15M', '5M') if timeframe in frames]
    if not timeframes and execution_timeframe in {'15M', '5M'} and execution_timeframe in frames:
        timeframes = [execution_timeframe]

    for timeframe in timeframes:
        frame = frames[timeframe]
        zones = _detect_timeframe_arrays(frame, timeframe)
        aligned_ifvg = [zone for zone in zones if zone.array_type == 'IFVG' and zone.bias == bias]
        if aligned_ifvg:
            chosen = min(
                aligned_ifvg,
                key=lambda zone: (abs(float(frame.iloc[-1]['close']) - zone.ce),) + _priority(zone, bias),
            )
            return f'{timeframe} {chosen.array_type}'

        aligned_breaker = [
            zone for zone in zones if zone.array_type == 'Breaker' and zone.bias == bias
        ]
        if aligned_breaker:
            chosen = min(
                aligned_breaker,
                key=lambda zone: (abs(float(frame.iloc[-1]['close']) - zone.ce),) + _priority(zone, bias),
            )
            return f'{timeframe} {chosen.array_type}'

    return None
