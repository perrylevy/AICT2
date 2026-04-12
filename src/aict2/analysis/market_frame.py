from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_SWING_LOOKBACK_BY_TF = {
    '30S': 2,
    '1M': 2,
    '5M': 2,
    '15M': 3,
    '1H': 3,
    '4H': 4,
    'Daily': 5,
}


@dataclass(frozen=True, slots=True)
class ChartFrameFacts:
    timeframe: str
    last_close: float
    last_open: float
    last_high: float
    last_low: float
    anchor_close: float
    range_high: float
    range_low: float
    range_position: float
    bias: str
    displacement: float
    latest_swing_high: float | None
    latest_swing_low: float | None
    reclaimed_high: bool
    broke_low: bool
    buy_side_sweep: bool
    sell_side_sweep: bool
    liquidity_summary: str


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.rename(columns={column: column.lower() for column in frame.columns})
    required = {'time', 'open', 'high', 'low', 'close'}
    if not required.issubset(normalized.columns):
        missing = ', '.join(sorted(required - set(normalized.columns)))
        raise ValueError(f'Missing required OHLC columns: {missing}')
    normalized = normalized[list(required)]
    normalized['time'] = pd.to_datetime(normalized['time'], utc=True)
    normalized = normalized.sort_values('time').reset_index(drop=True)
    for column in ['open', 'high', 'low', 'close']:
        normalized[column] = normalized[column].astype(float)
    return normalized


def swing_lookback(timeframe: str) -> int:
    return _SWING_LOOKBACK_BY_TF.get(timeframe, 2)


def find_swings(frame: pd.DataFrame, timeframe: str) -> tuple[list[float], list[float]]:
    lookback = swing_lookback(timeframe)
    if len(frame) < (lookback * 2) + 1:
        return [], []

    highs = frame['high'].tolist()
    lows = frame['low'].tolist()
    swing_highs: list[float] = []
    swing_lows: list[float] = []
    for index in range(lookback, len(frame) - lookback):
        high_window = highs[index - lookback : index + lookback + 1]
        low_window = lows[index - lookback : index + lookback + 1]
        if highs[index] == max(high_window):
            swing_highs.append(float(highs[index]))
        if lows[index] == min(low_window):
            swing_lows.append(float(lows[index]))
    return swing_highs, swing_lows


def liquidity_tolerance(frame: pd.DataFrame) -> float:
    recent = frame.tail(max(6, min(len(frame), 16)))
    average_bar = float((recent['high'] - recent['low']).mean()) if not recent.empty else 0.0
    return max(0.25, average_bar * 0.2)


def cluster_level(values: list[float], tolerance: float, side: str) -> float | None:
    if len(values) < 2:
        return None

    cluster_levels: list[float] = []
    for value in values:
        cluster = [candidate for candidate in values if abs(candidate - value) <= tolerance]
        if len(cluster) >= 2:
            cluster_levels.append(sum(cluster) / len(cluster))

    if not cluster_levels:
        return None

    return min(cluster_levels) if side == 'low' else max(cluster_levels)


def format_price(price: float) -> str:
    return f'{_round_tick(price):.2f}'


def _round_tick(price: float) -> float:
    return round(price * 4) / 4


def detect_liquidity_behavior(
    frame: pd.DataFrame,
    latest_swing_high: float | None,
    latest_swing_low: float | None,
) -> tuple[bool, bool, str]:
    recent = frame.tail(max(6, min(len(frame), 12))).reset_index(drop=True)
    if len(recent) < 4:
        return False, False, 'No clear liquidity sweep; insufficient recent history'

    tolerance = liquidity_tolerance(frame)
    last_close = float(recent['close'].iloc[-1])
    latest_event: tuple[int, str, float] | None = None

    for index in range(2, len(recent)):
        prior_lows = recent['low'].iloc[:index].tolist()
        sell_pool = cluster_level(prior_lows, tolerance, 'low')
        if sell_pool is not None:
            candidate_low = float(recent['low'].iloc[index])
            candidate_close = float(recent['close'].iloc[index])
            if (
                candidate_low < sell_pool - (tolerance * 0.25)
                and candidate_close > sell_pool
                and last_close >= sell_pool
            ):
                latest_event = (index, 'sell-side', sell_pool)

        prior_highs = recent['high'].iloc[:index].tolist()
        buy_pool = cluster_level(prior_highs, tolerance, 'high')
        if buy_pool is not None:
            candidate_high = float(recent['high'].iloc[index])
            candidate_close = float(recent['close'].iloc[index])
            if (
                candidate_high > buy_pool + (tolerance * 0.25)
                and candidate_close < buy_pool
                and last_close <= buy_pool
            ):
                latest_event = (index, 'buy-side', buy_pool)

    if latest_event is not None:
        _, side, level = latest_event
        if side == 'sell-side':
            return True, False, f'Sell-side liquidity sweep below {format_price(level)} with bullish reclaim'
        return False, True, f'Buy-side liquidity sweep above {format_price(level)} with bearish close-back-in'

    if latest_swing_high is not None and last_close > latest_swing_high:
        return False, False, f'Buy-side reclaim through recent swing high {format_price(latest_swing_high)}'
    if latest_swing_low is not None and last_close < latest_swing_low:
        return False, False, f'Sell-side pressure through recent swing low {format_price(latest_swing_low)}'
    return False, False, 'No clear liquidity sweep; waiting for cleaner pool interaction'


def body_displacement(frame: pd.DataFrame) -> float:
    recent = frame.tail(max(4, min(len(frame), 14)))
    if recent.empty:
        return 0.0
    last_body = abs(float(recent['close'].iloc[-1]) - float(recent['open'].iloc[-1]))
    average_body = float((recent['close'] - recent['open']).abs().mean())
    if average_body == 0:
        return 0.0
    return last_body / average_body


def load_chart_frames(
    file_paths: list[str],
    parse_chart_file_name: callable,
) -> dict[str, pd.DataFrame]:
    from pathlib import Path

    raw_frames: dict[str, pd.DataFrame] = {}
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            continue
        _, timeframe = parse_chart_file_name(path.name)
        raw_frames[timeframe] = pd.read_csv(path)
    return load_chart_frames_from_mapping(raw_frames)


def load_chart_frames_from_mapping(
    frames_by_timeframe: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    return {
        timeframe: normalize_frame(frame)
        for timeframe, frame in frames_by_timeframe.items()
        if frame is not None and not frame.empty
    }


def frame_bias(frame: pd.DataFrame, timeframe: str) -> ChartFrameFacts:
    lookback = max(3, min(len(frame), 20))
    recent = frame.tail(lookback)
    last_close = float(recent['close'].iloc[-1])
    last_open = float(recent['open'].iloc[-1])
    last_high = float(recent['high'].iloc[-1])
    last_low = float(recent['low'].iloc[-1])
    anchor_close = float(recent['close'].iloc[0])
    range_high = float(recent['high'].max())
    range_low = float(recent['low'].min())
    span = max(range_high - range_low, 0.25)
    midpoint = (range_high + range_low) / 2
    range_position = (last_close - range_low) / span
    swing_highs, swing_lows = find_swings(frame, timeframe)
    latest_swing_high = swing_highs[-1] if swing_highs else None
    latest_swing_low = swing_lows[-1] if swing_lows else None
    displacement = body_displacement(frame)
    reclaimed_high = latest_swing_high is not None and last_close > latest_swing_high
    broke_low = latest_swing_low is not None and last_close < latest_swing_low
    sell_side_sweep, buy_side_sweep, liquidity_summary = detect_liquidity_behavior(
        frame=frame,
        latest_swing_high=latest_swing_high,
        latest_swing_low=latest_swing_low,
    )

    if sell_side_sweep:
        bias = 'bullish'
    elif buy_side_sweep:
        bias = 'bearish'
    elif reclaimed_high and displacement >= 1.2:
        bias = 'bullish'
    elif broke_low and displacement >= 1.2:
        bias = 'bearish'
    elif last_close > anchor_close and last_close >= midpoint:
        bias = 'bullish'
    elif last_close < anchor_close and last_close <= midpoint:
        bias = 'bearish'
    else:
        bias = 'neutral'
    return ChartFrameFacts(
        timeframe=timeframe,
        last_close=last_close,
        last_open=last_open,
        last_high=last_high,
        last_low=last_low,
        anchor_close=anchor_close,
        range_high=range_high,
        range_low=range_low,
        range_position=range_position,
        bias=bias,
        displacement=displacement,
        latest_swing_high=latest_swing_high,
        latest_swing_low=latest_swing_low,
        reclaimed_high=reclaimed_high,
        broke_low=broke_low,
        buy_side_sweep=buy_side_sweep,
        sell_side_sweep=sell_side_sweep,
        liquidity_summary=liquidity_summary,
    )
