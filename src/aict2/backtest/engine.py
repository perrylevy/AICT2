from __future__ import annotations

import gc
from pathlib import Path
from tempfile import TemporaryDirectory

from aict2.analysis.analysis_service import build_analysis_snapshot
from aict2.analysis.analysis_service import build_analysis_snapshot_from_frames
from aict2.backtest.models import (
    BacktestCase,
    BacktestCaseResult,
    BacktestComparison,
    BacktestSummary,
)
from aict2.backtest.scoring import replay_live_setup
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore
from aict2.io.filename_parsing import parse_chart_file_name


def _invalid_case_result(case: BacktestCase) -> BacktestCaseResult:
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


def _runtime_failure_result(case: BacktestCase, exc: Exception) -> BacktestCaseResult:
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
        validation_error=str(exc),
        notes=("runtime_failure",),
    )


def _analyze_case(
    case: BacktestCase, memory_store: StructuralMemoryStore | None = None
):
    if case.analysis_frames is not None:
        if case.instrument is None:
            raise ValueError("Backtest case is missing instrument for in-memory analysis")
        return build_analysis_snapshot_from_frames(
            instrument=case.instrument,
            analysis_frames=case.analysis_frames,
            current_time=case.analysis_timestamp,
            macro_state="Mixed",
            vix=18.0,
            bias=None,
            daily_profile=None,
            entry=0.0,
            stop=0.0,
            target=0.0,
            memory_store=memory_store,
        )
    return build_analysis_snapshot(
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
        memory_store=memory_store,
    )


def _execution_only_case(case: BacktestCase) -> BacktestCase:
    if case.analysis_frames is not None:
        if case.execution_timeframe is None:
            raise ValueError("Missing execution timeframe chart for comparison")
        execution_frames = {
            timeframe: frame
            for timeframe, frame in case.analysis_frames.items()
            if timeframe == case.execution_timeframe
        }
        if len(execution_frames) != 1:
            raise ValueError("Missing execution timeframe chart for comparison")
        return BacktestCase(
            case_id=case.case_id,
            case_path=case.case_path,
            analysis_paths=(),
            score_path=case.score_path,
            instrument=case.instrument,
            ordered_timeframes=(case.execution_timeframe,),
            execution_timeframe=case.execution_timeframe,
            analysis_timestamp=case.analysis_timestamp,
            validation_error=case.validation_error,
            analysis_frames=execution_frames,
            score_frame=case.score_frame,
        )
    execution_paths = tuple(
        path
        for path in case.analysis_paths
        if case.execution_timeframe
        and parse_chart_file_name(path.name)[1] == case.execution_timeframe
    )
    if len(execution_paths) != 1:
        raise ValueError("Missing execution timeframe chart for comparison")
    return BacktestCase(
        case_id=case.case_id,
        case_path=case.case_path,
        analysis_paths=execution_paths,
        score_path=case.score_path,
        instrument=case.instrument,
        ordered_timeframes=(case.execution_timeframe,),
        execution_timeframe=case.execution_timeframe,
        analysis_timestamp=case.analysis_timestamp,
        validation_error=case.validation_error,
    )


def _build_comparison(
    case: BacktestCase,
    snapshot,
    memory_store: StructuralMemoryStore | None = None,
) -> BacktestComparison | None:
    analysis_count = (
        len(case.analysis_frames) if case.analysis_frames is not None else len(case.analysis_paths)
    )
    if analysis_count <= 1 or case.execution_timeframe is None:
        return None
    execution_only_snapshot = _analyze_case(_execution_only_case(case), memory_store=memory_store)
    return BacktestComparison(
        primary_status=snapshot.status,
        execution_only_status=execution_only_snapshot.status,
        differs=snapshot.status != execution_only_snapshot.status,
        primary_entry=snapshot.entry,
        execution_only_entry=execution_only_snapshot.entry,
        primary_stop=snapshot.stop,
        execution_only_stop=execution_only_snapshot.stop,
        primary_target=snapshot.target,
        execution_only_target=execution_only_snapshot.target,
    )


def run_backtest_case(
    case: BacktestCase,
    memory_store: StructuralMemoryStore | None = None,
    compare_execution_only: bool = False,
) -> BacktestCaseResult:
    if case.validation_error is not None:
        return _invalid_case_result(case)

    try:
        comparison_memory_store = memory_store
        temp_dir: TemporaryDirectory[str] | None = None
        temp_context_store: ContextStore | None = None
        if compare_execution_only and comparison_memory_store is None:
            temp_dir = TemporaryDirectory()
            temp_context_store = ContextStore(db_path=(Path(temp_dir.name) / "backtest.db"))
            temp_context_store.initialize()
            comparison_memory_store = StructuralMemoryStore(temp_context_store)

        snapshot = _analyze_case(case, memory_store=comparison_memory_store)
        replay = replay_live_setup(case, snapshot) if snapshot.status == "LIVE SETUP" else None
        comparison = (
            _build_comparison(case, snapshot, memory_store=comparison_memory_store)
            if compare_execution_only
            else None
        )

        result = BacktestCaseResult(
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
            comparison=comparison,
        )
        comparison_memory_store = None
        temp_context_store = None
        gc.collect()
        if temp_dir is not None:
            temp_dir.cleanup()
        return result
    except Exception as exc:
        return _runtime_failure_result(case, exc)


def run_backtest_cases(
    cases: list[BacktestCase], compare_execution_only: bool = False
) -> list[BacktestCaseResult]:
    ordered_cases = sorted(
        cases,
        key=lambda case: (case.analysis_timestamp is None, case.analysis_timestamp, case.case_id),
    )
    with TemporaryDirectory() as temp_dir:
        context_store = ContextStore(db_path=(Path(temp_dir) / "backtest.db"))
        context_store.initialize()
        memory_store = StructuralMemoryStore(context_store)
        results = [
            run_backtest_case(
                case,
                memory_store=memory_store,
                compare_execution_only=compare_execution_only,
            )
            for case in ordered_cases
        ]
        memory_store = None
        context_store = None
        gc.collect()
        return results


def summarize_results(results: list[BacktestCaseResult]) -> BacktestSummary:
    valid = [result for result in results if result.validation_error is None]
    invalid = [result for result in results if result.validation_error is not None]
    return BacktestSummary(
        total_cases=len(results),
        valid_cases=len(valid),
        invalid_cases=len(invalid),
        watch_count=sum(result.status == "WATCH" for result in valid),
        wait_count=sum(result.status == "WAIT" for result in valid),
        no_trade_count=sum(result.status == "NO TRADE" for result in valid),
        live_setup_count=sum(result.status == "LIVE SETUP" for result in valid),
        tp_hit_count=sum(result.trade_outcome == "TP_HIT" for result in valid),
        sl_hit_count=sum(result.trade_outcome == "SL_HIT" for result in valid),
        no_entry_count=sum(result.trade_outcome == "NO_ENTRY" for result in valid),
        unresolved_count=sum(result.trade_outcome == "ENTRY_NO_RESOLUTION" for result in valid),
        no_setup_count=sum(result.trade_outcome == "NO_SETUP" for result in valid),
    )
