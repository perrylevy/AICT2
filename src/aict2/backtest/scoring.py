from __future__ import annotations

from datetime import timedelta

from aict2.analysis.analysis_service import AnalysisSnapshot
from aict2.backtest.models import BacktestCase, BacktestTradeReplay
from aict2.reporting.analysis_record_model import AnalysisRecord
from aict2.reporting.scoredata import score_csv_against_records

_TIMEFRAME_DELTAS = {
    "30S": timedelta(seconds=30),
    "1M": timedelta(minutes=1),
    "5M": timedelta(minutes=5),
    "15M": timedelta(minutes=15),
    "1H": timedelta(hours=1),
    "4H": timedelta(hours=4),
    "Daily": timedelta(days=1),
    "Weekly": timedelta(days=7),
}


def _effective_analysis_time(case: BacktestCase) -> str:
    if case.analysis_timestamp is None:
        raise ValueError("Backtest case is missing analysis timestamp")
    delta = _TIMEFRAME_DELTAS.get(case.execution_timeframe or "", timedelta())
    return (case.analysis_timestamp + delta).isoformat()


def replay_live_setup(case: BacktestCase, snapshot: AnalysisSnapshot) -> BacktestTradeReplay:
    direction = (
        "LONG"
        if snapshot.thesis.state == "bullish"
        else "SHORT"
        if snapshot.thesis.state == "bearish"
        else None
    )
    record = AnalysisRecord(
        message_id=case.case_id,
        instrument=snapshot.instrument,
        status=snapshot.status,
        direction=direction,
        confidence=None,
        outcome=None,
        score=None,
        analyzed_at=_effective_analysis_time(case),
        entry=snapshot.entry,
        stop=snapshot.stop,
        target=snapshot.target,
    )
    scored = score_csv_against_records(case.score_path, [record]) if case.score_path else []
    if not scored:
        return BacktestTradeReplay(outcome="NO_SETUP", score=None)
    return BacktestTradeReplay(outcome=scored[0].outcome, score=scored[0].score)
