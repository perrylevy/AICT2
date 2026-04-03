from __future__ import annotations

from dataclasses import dataclass

from aict2.analysis.setup_engine import derive_setup_plan
from aict2.analysis.trade_planning import ChartDerivedPlan

_TF_ORDER = {
    'Monthly': 0,
    'Weekly': 1,
    'Daily': 2,
    '4H': 3,
    '1H': 4,
    '15M': 5,
    '5M': 6,
    '1M': 7,
    '30S': 8,
}

@dataclass(frozen=True, slots=True)
class TimeframeSummary:
    ordered_timeframes: tuple[str, ...]
    execution_timeframe: str
    has_higher_timeframe_context: bool

def summarize_timeframe_context(timeframes: list[str]) -> TimeframeSummary:
    unique_timeframes = tuple(dict.fromkeys(timeframes))
    unknown = [timeframe for timeframe in unique_timeframes if timeframe not in _TF_ORDER]
    if unknown:
        unknown_label = ', '.join(unknown)
        raise ValueError(f'Unknown timeframe: {unknown_label}')

    ordered = tuple(sorted(unique_timeframes, key=lambda tf: _TF_ORDER[tf]))
    execution_timeframe = ordered[-1] if ordered else 'UNKNOWN'
    has_higher_timeframe_context = len(ordered) > 1
    return TimeframeSummary(
        ordered_timeframes=ordered,
        execution_timeframe=execution_timeframe,
        has_higher_timeframe_context=has_higher_timeframe_context,
    )


def derive_chart_plan(file_paths: list[str]) -> ChartDerivedPlan | None:
    return derive_setup_plan(file_paths)
