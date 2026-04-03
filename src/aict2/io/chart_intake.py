from __future__ import annotations

from dataclasses import dataclass

from aict2.analysis.market_map import summarize_timeframe_context
from aict2.io.filename_parsing import parse_chart_file_name

_CANONICAL_BUNDLES: dict[tuple[str, ...], str] = {
    ('Weekly', 'Daily', '1H'): 'structural',
    ('Daily', '1H', '5M'): 'balanced',
    ('4H', '15M', '1M'): 'execution',
    ('15M', '5M', '1M'): 'execution',
    ('1H', '5M', '30S'): 'micro',
}


@dataclass(frozen=True, slots=True)
class ChartRequest:
    instrument: str
    mode: str
    ordered_timeframes: tuple[str, ...]
    execution_timeframe: str
    has_higher_timeframe_context: bool
    bundle_profile: str
    is_canonical_bundle: bool
    source_files: tuple[str, ...]

def build_chart_request(file_names: list[str]) -> ChartRequest:
    if len(file_names) not in {1, 3}:
        raise ValueError('Expected 1 or 3 charts')

    instruments: list[str] = []
    timeframes: list[str] = []
    source_files = tuple(file_names)

    for file_name in file_names:
        instrument, timeframe = parse_chart_file_name(file_name)
        instruments.append(instrument)
        timeframes.append(timeframe)

    unique_instruments = set(instruments)
    if len(unique_instruments) != 1:
        raise ValueError('Mixed instruments are not supported')

    timeframe_summary = summarize_timeframe_context(timeframes)
    bundle_profile = _CANONICAL_BUNDLES.get(timeframe_summary.ordered_timeframes, 'custom')
    is_canonical_bundle = timeframe_summary.ordered_timeframes in _CANONICAL_BUNDLES
    return ChartRequest(
        instrument=instruments[0],
        mode='single' if len(file_names) == 1 else 'multi',
        ordered_timeframes=timeframe_summary.ordered_timeframes,
        execution_timeframe=timeframe_summary.execution_timeframe,
        has_higher_timeframe_context=timeframe_summary.has_higher_timeframe_context,
        bundle_profile=bundle_profile,
        is_canonical_bundle=is_canonical_bundle,
        source_files=source_files,
    )
