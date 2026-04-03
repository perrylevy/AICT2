from __future__ import annotations

from aict2.analysis.analysis_service import build_analysis_snapshot
from aict2.backtest.models import BacktestCase, BacktestCaseResult, BacktestSummary
from aict2.backtest.scoring import replay_live_setup


def run_backtest_case(case: BacktestCase) -> BacktestCaseResult:
    if case.validation_error is not None:
        return BacktestCaseResult(
            case_id=case.case_id,
            instrument=case.instrument,
            ordered_timeframes=case.ordered_timeframes,
            execution_timeframe=case.execution_timeframe,
            analysis_timestamp=case.analysis_timestamp,
            status=None,
            thesis_state=None,
            entry=None,
            stop=None,
            target=None,
            trade_outcome=None,
            trade_score=None,
            validation_error=case.validation_error,
        )

    snapshot = build_analysis_snapshot(
        file_names=[path.name for path in case.analysis_paths],
        file_paths=[str(path) for path in case.analysis_paths],
        current_time=case.analysis_timestamp,
        macro_state="Mixed",
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=None,
    )

    replay = replay_live_setup(case, snapshot) if snapshot.status == "LIVE SETUP" else None

    return BacktestCaseResult(
        case_id=case.case_id,
        instrument=snapshot.instrument,
        ordered_timeframes=case.ordered_timeframes,
        execution_timeframe=case.execution_timeframe,
        analysis_timestamp=case.analysis_timestamp,
        status=snapshot.status,
        thesis_state=snapshot.thesis.state,
        entry=snapshot.entry,
        stop=snapshot.stop,
        target=snapshot.target,
        trade_outcome=replay.outcome if replay else None,
        trade_score=replay.score if replay else None,
        validation_error=None,
    )


def summarize_results(results: list[BacktestCaseResult]) -> BacktestSummary:
    valid = [result for result in results if result.validation_error is None]
    invalid = [result for result in results if result.validation_error is not None]
    return BacktestSummary(
        total_cases=len(results),
        valid_cases=len(valid),
        invalid_cases=len(invalid),
        wait_count=sum(result.status == "WAIT" for result in valid),
        no_trade_count=sum(result.status == "NO TRADE" for result in valid),
        live_setup_count=sum(result.status == "LIVE SETUP" for result in valid),
        tp_hit_count=sum(result.trade_outcome == "TP_HIT" for result in valid),
        sl_hit_count=sum(result.trade_outcome == "SL_HIT" for result in valid),
        no_entry_count=sum(result.trade_outcome == "NO_ENTRY" for result in valid),
        unresolved_count=sum(result.trade_outcome == "ENTRY_NO_RESOLUTION" for result in valid),
        no_setup_count=sum(result.trade_outcome == "NO_SETUP" for result in valid),
    )
