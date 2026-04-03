from __future__ import annotations

import re
from pathlib import Path

TIMEFRAME_MAP = {
    '30S': '30S',
    '1': '1M',
    '5': '5M',
    '15': '15M',
    '60': '1H',
    '240': '4H',
    '1D': 'Daily',
    '1W': 'Weekly',
    'W': 'Weekly',
}

RAW_FILENAME_RE = re.compile(r'^(?P<instrument>.+?),\s*(?P<timeframe>[^.]+)\.csv$', re.IGNORECASE)
TIMEFRAME_SUFFIX_RE = re.compile(r'(?:\s*\(\d+\))+\s*$')
CONTRACT_TOKEN_RE = re.compile(r'^[A-Z]+[0-9]+!?$', re.IGNORECASE)


def normalize_instrument(raw_instrument: str) -> str:
    parts = [part for part in raw_instrument.split('_') if part]
    instrument = parts[-1].upper() if parts else raw_instrument.upper()
    if instrument.endswith('!'):
        return instrument
    if CONTRACT_TOKEN_RE.match(instrument):
        return f'{instrument}!'
    return instrument


def normalize_timeframe(raw_timeframe: str) -> str:
    timeframe = TIMEFRAME_SUFFIX_RE.sub('', raw_timeframe.strip().upper())
    if timeframe not in TIMEFRAME_MAP:
        raise ValueError(f'Unknown timeframe: {raw_timeframe}')
    return TIMEFRAME_MAP[timeframe]


def parse_chart_file_name(file_name: str) -> tuple[str, str]:
    name = Path(file_name).name
    match = RAW_FILENAME_RE.match(name)
    if match is not None:
        return normalize_instrument(match.group('instrument')), normalize_timeframe(
            match.group('timeframe')
        )

    stem = Path(name).stem
    parts = [part for part in stem.split('_') if part]
    if len(parts) < 2:
        raise ValueError(f'Unsupported filename: {file_name}')

    timeframe_index: int | None = None
    timeframe_token: str | None = None
    for index in range(len(parts)):
        candidate = parts[index].upper()
        suffix_tokens = parts[index + 1 :]
        if candidate in TIMEFRAME_MAP and all(token.isdigit() for token in suffix_tokens):
            timeframe_index = index
            timeframe_token = candidate
            break

    if timeframe_index is None or timeframe_token is None or timeframe_index == 0:
        raise ValueError(f'Unsupported filename: {file_name}')

    instrument_raw = '_'.join(parts[:timeframe_index])
    return normalize_instrument(instrument_raw), TIMEFRAME_MAP[timeframe_token]
