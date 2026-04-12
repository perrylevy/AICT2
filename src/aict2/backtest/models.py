from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd


@dataclass(frozen=True, slots=True)
class BacktestCase:
    case_id: str
    case_path: Path
    analysis_paths: tuple[Path, ...]
    score_path: Path | None
    instrument: str | None
    ordered_timeframes: tuple[str, ...]
    execution_timeframe: str | None
    analysis_timestamp: datetime | None
    validation_error: str | None = None
    analysis_frames: dict[str, pd.DataFrame] | None = None
    score_frame: pd.DataFrame | None = None
    source_labels: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class BacktestTradeReplay:
    outcome: str
    score: float | None


@dataclass(frozen=True, slots=True)
class BacktestComparison:
    primary_status: str | None
    execution_only_status: str | None
    differs: bool
    primary_entry: float | None
    execution_only_entry: float | None
    primary_stop: float | None
    execution_only_stop: float | None
    primary_target: float | None
    execution_only_target: float | None


@dataclass(frozen=True, slots=True)
class BacktestCaseResult:
    case_id: str
    instrument: str | None
    ordered_timeframes: tuple[str, ...]
    execution_timeframe: str | None
    analysis_timestamp: datetime | None
    status: str | None
    thesis_state: str | None
    entry: float | None
    stop: float | None
    target: float | None
    trade_outcome: str | None
    trade_score: float | None
    validation_error: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)
    comparison: BacktestComparison | None = None


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    total_cases: int
    valid_cases: int
    invalid_cases: int
    watch_count: int
    wait_count: int
    no_trade_count: int
    live_setup_count: int
    tp_hit_count: int
    sl_hit_count: int
    no_entry_count: int
    unresolved_count: int
    no_setup_count: int
