from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from aict2.backtest.models import BacktestCase
from aict2.io.chart_intake import build_chart_request
from aict2.io.filename_parsing import parse_chart_file_name


def _load_last_timestamp(csv_path: Path) -> datetime:
    frame = pd.read_csv(csv_path)
    if frame.empty:
        raise ValueError(f"Empty analysis chart: {csv_path.name}")
    time_column = next((column for column in frame.columns if column.lower() == "time"), None)
    if time_column is None:
        raise ValueError(f"Missing time column: {csv_path.name}")
    timestamp = pd.to_datetime(frame[time_column].iloc[-1])
    return timestamp.to_pydatetime()


def _discover_case(case_path: Path) -> BacktestCase:
    analysis_dir = case_path / "analysis"
    score_dir = case_path / "score"
    analysis_paths = tuple(sorted(analysis_dir.glob("*.csv")))
    score_paths = tuple(sorted(score_dir.glob("*.csv")))
    request = build_chart_request([path.name for path in analysis_paths])
    execution_path = next(
        path
        for path in analysis_paths
        if parse_chart_file_name(path.name)[1] == request.execution_timeframe
    )
    return BacktestCase(
        case_id=case_path.name,
        case_path=case_path,
        analysis_paths=analysis_paths,
        score_path=score_paths[0] if score_paths else None,
        instrument=request.instrument,
        ordered_timeframes=request.ordered_timeframes,
        execution_timeframe=request.execution_timeframe,
        analysis_timestamp=_load_last_timestamp(execution_path),
    )


def discover_backtest_cases(root: Path) -> list[BacktestCase]:
    return [_discover_case(path) for path in sorted(root.iterdir()) if path.is_dir()]
