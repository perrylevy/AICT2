from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from aict2.analysis.market_frame import format_price, load_chart_frames
from aict2.io.filename_parsing import parse_chart_file_name

ET = ZoneInfo('America/New_York')
_INTRADAY_PRIORITY = ('30S', '1M', '5M', '15M', '1H', '4H')


@dataclass(frozen=True, slots=True)
class SessionLevels:
    asia: str
    london: str
    ny_am: str
    ny_pm: str
    rth_gap: str
    interaction: str

    def summary(self) -> str:
        return ' | '.join([self.asia, self.london, self.ny_am, self.ny_pm, self.rth_gap])


def _select_intraday_frame(frames: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    for timeframe in _INTRADAY_PRIORITY:
        frame = frames.get(timeframe)
        if frame is not None and not frame.empty:
            return frame
    return None


def _frame_with_et_columns(frame: pd.DataFrame) -> pd.DataFrame:
    et_times = frame['time'].dt.tz_convert(ET)
    enriched = frame.copy()
    enriched['et_time'] = et_times
    enriched['et_date'] = et_times.dt.date
    enriched['et_clock'] = et_times.dt.time
    return enriched


def _trade_date_from_frame(frame: pd.DataFrame) -> datetime.date:
    latest = frame.iloc[-1]['et_time']
    if latest.hour >= 18:
        return latest.date() + timedelta(days=1)
    return latest.date()


def _session_coverage_score(frame: pd.DataFrame) -> tuple[int, int]:
    trade_date = _trade_date_from_frame(frame)
    previous_date = trade_date - timedelta(days=1)
    checks = [
        (
            (frame['et_date'] == previous_date)
            & (frame['et_clock'] >= time(hour=18, minute=0))
        ),
        (
            (frame['et_date'] == trade_date)
            & (frame['et_clock'] < time(hour=6, minute=0))
        ),
        (
            (frame['et_date'] == previous_date)
            & (frame['et_clock'] >= time(hour=9, minute=30))
            & (frame['et_clock'] < time(hour=16, minute=0))
        ),
        (
            (frame['et_date'] == trade_date)
            & (frame['et_clock'] >= time(hour=9, minute=30))
            & (frame['et_clock'] < time(hour=16, minute=0))
        ),
    ]
    score = sum(1 for mask in checks if not frame[mask].empty)
    return score, len(frame)


def select_best_intraday_frame(frames: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    candidates: list[tuple[tuple[int, int, int], pd.DataFrame]] = []
    for index, timeframe in enumerate(_INTRADAY_PRIORITY):
        frame = frames.get(timeframe)
        if frame is None or frame.empty:
            continue
        enriched = _frame_with_et_columns(frame)
        coverage_score, row_count = _session_coverage_score(enriched)
        priority_score = len(_INTRADAY_PRIORITY) - index
        candidates.append(((coverage_score, row_count, priority_score), enriched))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _range_line(name: str, window: pd.DataFrame) -> str:
    if window.empty:
        return f'{name} unavailable'
    high = float(window['high'].max())
    low = float(window['low'].min())
    return f'{name} H {format_price(high)} / L {format_price(low)}'


def _range_bounds(window: pd.DataFrame) -> tuple[float, float] | None:
    if window.empty:
        return None
    return float(window['high'].max()), float(window['low'].min())


def _rth_gap_line(frame: pd.DataFrame, trade_date) -> str:
    previous_date = trade_date - timedelta(days=1)
    previous_rth = frame[
        (frame['et_date'] == previous_date)
        & (frame['et_clock'] >= time(hour=9, minute=30))
        & (frame['et_clock'] < time(hour=16, minute=0))
    ]
    current_rth = frame[
        (frame['et_date'] == trade_date)
        & (frame['et_clock'] >= time(hour=9, minute=30))
        & (frame['et_clock'] < time(hour=16, minute=0))
    ]
    if previous_rth.empty or current_rth.empty:
        return 'RTH Gap unavailable'

    previous_close = float(previous_rth.iloc[-1]['close'])
    current_open = float(current_rth.iloc[0]['open'])
    gap_high = max(previous_close, current_open)
    gap_low = min(previous_close, current_open)
    gap_ce = (gap_high + gap_low) / 2
    return (
        f'RTH Gap H {format_price(gap_high)} / '
        f'L {format_price(gap_low)} / '
        f'CE {format_price(gap_ce)}'
    )


def _range_interaction(
    *,
    name: str,
    bounds: tuple[float, float] | None,
    last_high: float,
    last_low: float,
    last_close: float,
) -> str | None:
    if bounds is None:
        return None
    high, low = bounds
    if last_low < low and last_close > low:
        return f'Swept {name} low and reclaimed'
    if last_high > high and last_close < high:
        return f'Swept {name} high and closed back below'
    if last_close > high:
        return f'Holding above {name} high'
    if last_close < low:
        return f'Holding below {name} low'
    return None


def _gap_interaction(
    *,
    gap_high: float | None,
    gap_low: float | None,
    gap_ce: float | None,
    last_high: float,
    last_low: float,
    last_close: float,
) -> str | None:
    if gap_high is None or gap_low is None or gap_ce is None:
        return None
    if last_low <= gap_ce <= last_high:
        return 'Interacting with RTH Gap CE'
    if gap_low <= last_close <= gap_high:
        return 'Trading inside the RTH gap'
    if last_close > gap_high:
        return 'Holding above RTH Gap high'
    if last_close < gap_low:
        return 'Holding below RTH Gap low'
    return None


def _derive_interaction_summary(
    *,
    frame: pd.DataFrame,
    asia_bounds: tuple[float, float] | None,
    london_bounds: tuple[float, float] | None,
    ny_am_bounds: tuple[float, float] | None,
    ny_pm_bounds: tuple[float, float] | None,
    gap_high: float | None,
    gap_low: float | None,
    gap_ce: float | None,
) -> str:
    last_row = frame.iloc[-1]
    last_high = float(last_row['high'])
    last_low = float(last_row['low'])
    last_close = float(last_row['close'])

    candidates = [
        _range_interaction(
            name='NY PM',
            bounds=ny_pm_bounds,
            last_high=last_high,
            last_low=last_low,
            last_close=last_close,
        ),
        _range_interaction(
            name='NY AM',
            bounds=ny_am_bounds,
            last_high=last_high,
            last_low=last_low,
            last_close=last_close,
        ),
        _gap_interaction(
            gap_high=gap_high,
            gap_low=gap_low,
            gap_ce=gap_ce,
            last_high=last_high,
            last_low=last_low,
            last_close=last_close,
        ),
        _range_interaction(
            name='London',
            bounds=london_bounds,
            last_high=last_high,
            last_low=last_low,
            last_close=last_close,
        ),
        _range_interaction(
            name='Asia',
            bounds=asia_bounds,
            last_high=last_high,
            last_low=last_low,
            last_close=last_close,
        ),
    ]
    interactions = [candidate for candidate in candidates if candidate]
    if not interactions:
        return 'No clear session interaction yet'
    return ' | '.join(interactions[:2])


def derive_session_levels_from_paths(
    file_paths: list[str],
    *,
    current_time: datetime,
) -> SessionLevels | None:
    frames = load_chart_frames(file_paths, parse_chart_file_name)
    frame = select_best_intraday_frame(frames)
    if frame is None:
        return None
    trade_date = _trade_date_from_frame(frame)
    previous_date = trade_date - timedelta(days=1)

    asia_window = frame[
        (frame['et_date'] == previous_date) & (frame['et_clock'] >= time(hour=18, minute=0))
    ]
    london_window = frame[
        (frame['et_date'] == trade_date) & (frame['et_clock'] < time(hour=6, minute=0))
    ]
    ny_am_window = frame[
        (frame['et_date'] == trade_date)
        & (frame['et_clock'] >= time(hour=9, minute=30))
        & (frame['et_clock'] < time(hour=12, minute=0))
    ]
    ny_pm_window = frame[
        (frame['et_date'] == trade_date)
        & (frame['et_clock'] >= time(hour=13, minute=0))
        & (frame['et_clock'] < time(hour=16, minute=0))
    ]
    asia_bounds = _range_bounds(asia_window)
    london_bounds = _range_bounds(london_window)
    ny_am_bounds = _range_bounds(ny_am_window)
    ny_pm_bounds = _range_bounds(ny_pm_window)

    previous_rth = frame[
        (frame['et_date'] == previous_date)
        & (frame['et_clock'] >= time(hour=9, minute=30))
        & (frame['et_clock'] < time(hour=16, minute=0))
    ]
    current_rth = frame[
        (frame['et_date'] == trade_date)
        & (frame['et_clock'] >= time(hour=9, minute=30))
        & (frame['et_clock'] < time(hour=16, minute=0))
    ]
    gap_high = gap_low = gap_ce = None
    if not previous_rth.empty and not current_rth.empty:
        previous_close = float(previous_rth.iloc[-1]['close'])
        current_open = float(current_rth.iloc[0]['open'])
        gap_high = max(previous_close, current_open)
        gap_low = min(previous_close, current_open)
        gap_ce = (gap_high + gap_low) / 2

    interaction = _derive_interaction_summary(
        frame=frame,
        asia_bounds=asia_bounds,
        london_bounds=london_bounds,
        ny_am_bounds=ny_am_bounds,
        ny_pm_bounds=ny_pm_bounds,
        gap_high=gap_high,
        gap_low=gap_low,
        gap_ce=gap_ce,
    )

    return SessionLevels(
        asia=_range_line('Asia', asia_window),
        london=_range_line('London', london_window),
        ny_am=_range_line('NY AM', ny_am_window),
        ny_pm=_range_line('NY PM', ny_pm_window),
        rth_gap=_rth_gap_line(frame, trade_date),
        interaction=interaction,
    )
