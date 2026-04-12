from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from aict2.io.filename_parsing import parse_chart_file_name
from aict2.reporting.analysis_records import AnalysisRecord

ET = ZoneInfo('America/New_York')


@dataclass(frozen=True, slots=True)
class ScoredTrade:
    message_id: str
    outcome: str
    score: float | None


def _parse_instrument_from_csv_path(csv_path: Path) -> str:
    instrument, _ = parse_chart_file_name(csv_path.name)
    return instrument


def _normalize_ohlc_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame = frame.rename(columns={column: column.capitalize() for column in frame.columns})
    required = {'Time', 'Open', 'High', 'Low', 'Close'}
    if not required.issubset(frame.columns):
        missing = ', '.join(sorted(required - set(frame.columns)))
        raise ValueError(f'Missing required OHLC columns: {missing}')
    frame['Time'] = pd.to_datetime(frame['Time'], utc=True)
    frame = frame.set_index('Time').sort_index()
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize('UTC')
    else:
        frame.index = frame.index.tz_convert('UTC')
    return frame


def _load_ohlc(csv_path: Path) -> pd.DataFrame:
    return _normalize_ohlc_frame(pd.read_csv(csv_path))


def _end_of_trade_day_utc(posted_at: datetime) -> datetime:
    posted_et = posted_at.astimezone(ET)
    eod_et = datetime.combine(posted_et.date(), time(hour=17, minute=0), tzinfo=ET)
    return eod_et.astimezone(timezone.utc)


def _resolve_outcome(frame: pd.DataFrame, record: AnalysisRecord) -> ScoredTrade:
    if record.direction not in {'LONG', 'SHORT'}:
        return ScoredTrade(record.message_id, 'NO_SETUP', None)
    if record.entry is None or record.stop is None or record.target is None:
        return ScoredTrade(record.message_id, 'NO_SETUP', None)

    posted_at = datetime.fromisoformat(record.analyzed_at)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    else:
        posted_at = posted_at.astimezone(timezone.utc)
    eod_utc = _end_of_trade_day_utc(posted_at)
    window = frame[(frame.index >= posted_at) & (frame.index < eod_utc)]
    if window.empty:
        return ScoredTrade(record.message_id, 'NO_ENTRY', None)

    entry_time: datetime | None = None
    for candle in window.itertuples():
        high = float(candle.High)
        low = float(candle.Low)
        if record.direction == 'LONG' and low <= record.entry:
            entry_time = candle.Index
            break
        if record.direction == 'SHORT' and high >= record.entry:
            entry_time = candle.Index
            break

    if entry_time is None:
        return ScoredTrade(record.message_id, 'NO_ENTRY', None)

    post_entry = window[window.index >= entry_time]
    for candle in post_entry.itertuples():
        high = float(candle.High)
        low = float(candle.Low)
        if record.direction == 'LONG':
            if low <= float(record.stop):
                return ScoredTrade(record.message_id, 'SL_HIT', 0.0)
            if high >= float(record.target):
                return ScoredTrade(record.message_id, 'TP_HIT', 1.0)
        else:
            if high >= float(record.stop):
                return ScoredTrade(record.message_id, 'SL_HIT', 0.0)
            if low <= float(record.target):
                return ScoredTrade(record.message_id, 'TP_HIT', 1.0)

    return ScoredTrade(record.message_id, 'ENTRY_NO_RESOLUTION', None)


def score_csv_against_records(csv_path: Path, records: list[AnalysisRecord]) -> list[ScoredTrade]:
    instrument = _parse_instrument_from_csv_path(csv_path)
    matching = [record for record in records if record.instrument == instrument]
    if not matching:
        return []
    frame = _load_ohlc(csv_path)
    return [_resolve_outcome(frame, record) for record in matching]


def score_frame_against_records(
    frame: pd.DataFrame, *, instrument: str, records: list[AnalysisRecord]
) -> list[ScoredTrade]:
    matching = [record for record in records if record.instrument == instrument]
    if not matching:
        return []
    normalized = _normalize_ohlc_frame(frame)
    return [_resolve_outcome(normalized, record) for record in matching]
