from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')


@dataclass(frozen=True, slots=True)
class SessionLens:
    macro_state: str
    volatility_regime: str
    active_windows: tuple[str, ...]
    session_phase: str
    analysis_window: str


def _volatility_regime(vix: float) -> str:
    if vix > 20:
        return 'high'
    if vix >= 19:
        return 'elevated'
    return 'normal'


def build_session_lens(current_time: datetime, macro_state: str, vix: float) -> SessionLens:
    et_time = current_time.astimezone(ET)
    minute_of_day = et_time.hour * 60 + et_time.minute
    active_windows: list[str] = []

    if 590 <= minute_of_day <= 610:
        active_windows.append('ny_open_macro')
    if 650 <= minute_of_day <= 670:
        active_windows.append('london_close_macro')

    if minute_of_day < 300:
        session_phase = 'overnight'
    elif minute_of_day < 570:
        session_phase = 'premarket'
    elif minute_of_day < 720:
        session_phase = 'rth_morning'
    elif minute_of_day < 780:
        session_phase = 'lunch'
    else:
        session_phase = 'afternoon'

    if 500 <= minute_of_day <= 514:
        analysis_window = 'Premarket Map (early)'
    elif 515 <= minute_of_day <= 530:
        analysis_window = 'Premarket Map (ideal)'
    elif 531 <= minute_of_day <= 550:
        analysis_window = 'Premarket Map (late)'
    elif 575 <= minute_of_day <= 584:
        analysis_window = 'Open Check (early)'
    elif 585 <= minute_of_day <= 605:
        analysis_window = 'Open Check (ideal)'
    elif 606 <= minute_of_day <= 610:
        analysis_window = 'Open Check (late)'
    else:
        analysis_window = 'Standard Session Read'

    return SessionLens(
        macro_state=macro_state,
        volatility_regime=_volatility_regime(vix),
        active_windows=tuple(active_windows),
        session_phase=session_phase,
        analysis_window=analysis_window,
    )

