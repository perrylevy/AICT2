from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.analysis.analysis_service import AnalysisSnapshot
from aict2.analysis.risk_gate import RiskGateResult
from aict2.analysis.session_lens import SessionLens
from aict2.analysis.trade_thesis import TradeThesis
from aict2.backtest.engine import run_backtest_case, run_backtest_cases, summarize_results
from aict2.backtest.models import BacktestCase, BacktestCaseResult, BacktestTradeReplay
from aict2.backtest.scoring import replay_live_setup
from aict2.io.chart_intake import ChartRequest

ET = ZoneInfo("America/New_York")


def _write_csv(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def _case(tmp_path: Path) -> BacktestCase:
    analysis = tmp_path / "analysis"
    score = tmp_path / "score"
    analysis.mkdir(parents=True)
    score.mkdir()
    execution = analysis / "CME_MINI_MNQ1!, 5.csv"
    _write_csv(
        execution,
        [("2026-04-02T09:55:00-04:00", 20000, 20010, 19990, 20005)],
    )
    score_path = score / "CME_MINI_MNQ1!, 1.csv"
    _write_csv(
        score_path,
        [("2026-04-02T09:56:00-04:00", 20005, 20040, 20000, 20035)],
    )
    return BacktestCase(
        case_id="case-1",
        case_path=tmp_path,
        analysis_paths=(execution,),
        score_path=score_path,
        instrument="MNQ1!",
        ordered_timeframes=("5M",),
        execution_timeframe="5M",
        analysis_timestamp=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        validation_error=None,
    )


def _multi_case(tmp_path: Path) -> BacktestCase:
    analysis = tmp_path / "analysis"
    score = tmp_path / "score"
    analysis.mkdir(parents=True)
    score.mkdir()
    daily = analysis / "CME_MINI_MNQ1!, 1D.csv"
    hourly = analysis / "CME_MINI_MNQ1!, 60.csv"
    execution = analysis / "CME_MINI_MNQ1!, 5.csv"
    _write_csv(
        daily,
        [("2026-04-02T00:00:00-04:00", 20000, 20100, 19950, 20080)],
    )
    _write_csv(
        hourly,
        [("2026-04-02T09:00:00-04:00", 20050, 20090, 20040, 20085)],
    )
    _write_csv(
        execution,
        [("2026-04-02T09:55:00-04:00", 20000, 20010, 19990, 20005)],
    )
    score_path = score / "CME_MINI_MNQ1!, 1.csv"
    _write_csv(
        score_path,
        [("2026-04-02T09:56:00-04:00", 20005, 20040, 20000, 20035)],
    )
    return BacktestCase(
        case_id="case-compare",
        case_path=tmp_path,
        analysis_paths=(daily, hourly, execution),
        score_path=score_path,
        instrument="MNQ1!",
        ordered_timeframes=("Daily", "1H", "5M"),
        execution_timeframe="5M",
        analysis_timestamp=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        validation_error=None,
    )


def _snapshot(status: str = "LIVE SETUP", state: str = "bullish") -> AnalysisSnapshot:
    return AnalysisSnapshot(
        instrument="MNQ1!",
        request=ChartRequest(
            instrument="MNQ1!",
            mode="single",
            ordered_timeframes=("5M",),
            execution_timeframe="5M",
            has_higher_timeframe_context=False,
            bundle_profile="custom",
            is_canonical_bundle=False,
            source_files=("CME_MINI_MNQ1!, 5.csv",),
        ),
        thesis=TradeThesis(
            state=state,
            allowed_business="long_only",
            daily_profile="continuation",
            has_higher_timeframe_context=False,
        ),
        session=SessionLens(
            macro_state="Mixed",
            volatility_regime="normal",
            active_windows=("ny_open_macro",),
            session_phase="rth_morning",
            analysis_window="Open Check (ideal)",
        ),
        risk=RiskGateResult(
            stop_distance=10.0,
            rr=2.0,
            max_contracts=1,
            clears_min_rr=True,
        ),
        status=status,
        used_structural_memory=False,
        entry=20000.0,
        stop=19990.0,
        target=20035.0,
        liquidity_summary="PDH nearby",
        reference_context="PDH 20040",
        internal_reference_context="PDH 20040",
        draw_on_liquidity="PDH 20040",
        htf_reference="1H High 20040",
        stop_run_summary="No confirmed stop run yet",
        gap_summary="No active NDOG/NWOG",
        gap_confluence="No gap confluence",
        opening_summary="Opening levels unavailable from current upload",
        opening_confluence="Opening prices are informational only right now.",
        pd_array_summary="No clear PD array ranked yet",
        pd_array_confluence="Daily arrays are informational only right now.",
        entry_model="5M Confirmation",
        tp_model="2R",
        target_reason="Defaulting to a full 2R objective unless external liquidity is closer.",
        needs_confirmation=False,
        requires_retrace=False,
        session_levels=None,
    )


def test_run_backtest_case_passes_only_analysis_paths_to_snapshot_builder(
    tmp_path: Path, monkeypatch
) -> None:
    case = _case(tmp_path)
    captured: dict[str, object] = {}

    def fake_build_analysis_snapshot(**kwargs):
        captured["file_paths"] = kwargs["file_paths"]
        captured["current_time"] = kwargs["current_time"]
        return _snapshot()

    monkeypatch.setattr("aict2.backtest.engine.build_analysis_snapshot", fake_build_analysis_snapshot)
    monkeypatch.setattr(
        "aict2.backtest.engine.replay_live_setup",
        lambda case_arg, snapshot_arg: BacktestTradeReplay(outcome="TP_HIT", score=1.0),
    )

    result = run_backtest_case(case)

    assert result.status == "LIVE SETUP"
    assert result.trade_outcome == "TP_HIT"
    assert captured["file_paths"] == [str(path) for path in case.analysis_paths]
    assert str(case.score_path) not in captured["file_paths"]
    assert captured["current_time"] == case.analysis_timestamp


def test_run_backtest_case_skips_replay_for_wait_status(tmp_path: Path, monkeypatch) -> None:
    case = _case(tmp_path)

    monkeypatch.setattr(
        "aict2.backtest.engine.build_analysis_snapshot",
        lambda **kwargs: _snapshot(status="WAIT", state="mixed"),
    )

    def fail_replay(case_arg, snapshot_arg):
        raise AssertionError("replay should not run for WAIT")

    monkeypatch.setattr("aict2.backtest.engine.replay_live_setup", fail_replay)

    result = run_backtest_case(case)

    assert result.status == "WAIT"
    assert result.trade_outcome is None


def test_run_backtest_case_can_compare_three_chart_and_execution_only(
    tmp_path: Path, monkeypatch
) -> None:
    case = _multi_case(tmp_path)

    def fake_build_analysis_snapshot(**kwargs):
        return _snapshot(status="LIVE SETUP" if len(kwargs["file_names"]) == 1 else "WAIT")

    monkeypatch.setattr("aict2.backtest.engine.build_analysis_snapshot", fake_build_analysis_snapshot)

    result = run_backtest_case(case, compare_execution_only=True)

    assert result.status == "WAIT"
    assert result.comparison is not None
    assert result.comparison.primary_status == "WAIT"
    assert result.comparison.execution_only_status == "LIVE SETUP"
    assert result.comparison.differs is True


def test_run_backtest_case_reuses_memory_store_for_execution_only_comparison(
    tmp_path: Path, monkeypatch
) -> None:
    case = _multi_case(tmp_path)
    seen_memory_store: list[object] = []

    def fake_build_analysis_snapshot(**kwargs):
        seen_memory_store.append(kwargs["memory_store"])
        return _snapshot(status="WAIT")

    monkeypatch.setattr("aict2.backtest.engine.build_analysis_snapshot", fake_build_analysis_snapshot)

    result = run_backtest_case(case, compare_execution_only=True)

    assert result.comparison is not None
    assert len(seen_memory_store) == 2
    assert seen_memory_store[0] is not None
    assert seen_memory_store[0] is seen_memory_store[1]


def test_run_backtest_case_returns_failed_result_when_analysis_raises(
    tmp_path: Path, monkeypatch
) -> None:
    case = _case(tmp_path)

    def boom(**kwargs):
        raise RuntimeError("snapshot failed")

    monkeypatch.setattr("aict2.backtest.engine.build_analysis_snapshot", boom)

    result = run_backtest_case(case)

    assert result.status is None
    assert result.trade_outcome is None
    assert result.validation_error == "snapshot failed"


def test_run_backtest_cases_reuses_shared_memory_store(tmp_path: Path, monkeypatch) -> None:
    first = _case(tmp_path / "first")
    second = BacktestCase(
        case_id="case-2",
        case_path=tmp_path / "second",
        analysis_paths=first.analysis_paths,
        score_path=first.score_path,
        instrument="MNQ1!",
        ordered_timeframes=("1M",),
        execution_timeframe="1M",
        analysis_timestamp=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
        validation_error=None,
    )
    seen_memory_store: list[object] = []

    def fake_build_analysis_snapshot(**kwargs):
        seen_memory_store.append(kwargs["memory_store"])
        return _snapshot(status="WATCH" if len(seen_memory_store) == 2 else "LIVE SETUP")

    monkeypatch.setattr("aict2.backtest.engine.build_analysis_snapshot", fake_build_analysis_snapshot)
    monkeypatch.setattr(
        "aict2.backtest.engine.replay_live_setup",
        lambda case_arg, snapshot_arg: BacktestTradeReplay(outcome="TP_HIT", score=1.0),
    )

    results = run_backtest_cases([first, second])

    assert len(results) == 2
    assert all(memory_store is not None for memory_store in seen_memory_store)
    assert seen_memory_store[0] is seen_memory_store[1]


def test_run_backtest_cases_orders_cases_by_analysis_timestamp(tmp_path: Path, monkeypatch) -> None:
    late_case = _case(tmp_path / "late")
    early_case = BacktestCase(
        case_id="early",
        case_path=tmp_path / "early",
        analysis_paths=late_case.analysis_paths,
        score_path=late_case.score_path,
        instrument="MNQ1!",
        ordered_timeframes=("5M",),
        execution_timeframe="5M",
        analysis_timestamp=datetime(2026, 4, 2, 9, 50, tzinfo=ET),
        validation_error=None,
    )
    seen_case_times: list[datetime] = []

    def fake_run_backtest_case(case, memory_store=None, compare_execution_only=False):
        seen_case_times.append(case.analysis_timestamp)
        return BacktestCaseResult(
            case_id=case.case_id,
            instrument=case.instrument,
            ordered_timeframes=case.ordered_timeframes,
            execution_timeframe=case.execution_timeframe,
            analysis_timestamp=case.analysis_timestamp,
            status="WATCH",
            thesis_state="mixed",
            entry=None,
            stop=None,
            target=None,
            trade_outcome=None,
            trade_score=None,
        )

    monkeypatch.setattr("aict2.backtest.engine.run_backtest_case", fake_run_backtest_case)

    run_backtest_cases([late_case, early_case])

    assert seen_case_times == [
        datetime(2026, 4, 2, 9, 50, tzinfo=ET),
        datetime(2026, 4, 2, 9, 55, tzinfo=ET),
    ]


def test_replay_live_setup_starts_after_execution_timeframe(tmp_path: Path, monkeypatch) -> None:
    case = _case(tmp_path)
    captured: dict[str, object] = {}

    def fake_score_csv_against_records(csv_path, records):
        captured["analyzed_at"] = records[0].analyzed_at
        return []

    monkeypatch.setattr("aict2.backtest.scoring.score_csv_against_records", fake_score_csv_against_records)

    replay = replay_live_setup(case, _snapshot())

    assert replay.outcome == "NO_SETUP"
    assert captured["analyzed_at"] == datetime(2026, 4, 2, 10, 0, tzinfo=ET).isoformat()


def test_summarize_results_tracks_status_and_trade_outcomes() -> None:
    summary = summarize_results(
        [
            BacktestCaseResult(
                case_id="wait",
                instrument="MNQ1!",
                ordered_timeframes=("5M",),
                execution_timeframe="5M",
                analysis_timestamp=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
                status="WAIT",
                thesis_state="mixed",
                entry=None,
                stop=None,
                target=None,
                trade_outcome=None,
                trade_score=None,
            ),
            BacktestCaseResult(
                case_id="live-win",
                instrument="MNQ1!",
                ordered_timeframes=("5M",),
                execution_timeframe="5M",
                analysis_timestamp=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
                status="LIVE SETUP",
                thesis_state="bullish",
                entry=20000.0,
                stop=19990.0,
                target=20035.0,
                trade_outcome="TP_HIT",
                trade_score=1.0,
            ),
            BacktestCaseResult(
                case_id="watch",
                instrument="MNQ1!",
                ordered_timeframes=("5M",),
                execution_timeframe="5M",
                analysis_timestamp=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
                status="WATCH",
                thesis_state="bullish",
                entry=20000.0,
                stop=19990.0,
                target=20035.0,
                trade_outcome=None,
                trade_score=None,
            ),
            BacktestCaseResult(
                case_id="invalid",
                instrument=None,
                ordered_timeframes=(),
                execution_timeframe=None,
                analysis_timestamp=None,
                status=None,
                thesis_state=None,
                entry=None,
                stop=None,
                target=None,
                trade_outcome=None,
                trade_score=None,
                validation_error="Missing score directory",
            ),
        ]
    )

    assert summary.total_cases == 4
    assert summary.valid_cases == 3
    assert summary.invalid_cases == 1
    assert summary.wait_count == 1
    assert summary.live_setup_count == 1
    assert summary.watch_count == 1
    assert summary.tp_hit_count == 1
