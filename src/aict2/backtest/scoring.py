from __future__ import annotations

from aict2.analysis.analysis_service import AnalysisSnapshot
from aict2.backtest.models import BacktestCase, BacktestTradeReplay
from aict2.reporting.analysis_record_model import AnalysisRecord
from aict2.reporting.scoredata import score_csv_against_records


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
        analyzed_at=case.analysis_timestamp.isoformat(),
        entry=snapshot.entry,
        stop=snapshot.stop,
        target=snapshot.target,
    )
    scored = score_csv_against_records(case.score_path, [record]) if case.score_path else []
    if not scored:
        return BacktestTradeReplay(outcome="NO_SETUP", score=None)
    return BacktestTradeReplay(outcome=scored[0].outcome, score=scored[0].score)
