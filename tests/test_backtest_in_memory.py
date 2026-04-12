from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from aict2.analysis.analysis_service import AnalysisSnapshot
from aict2.analysis.risk_gate import RiskGateResult
from aict2.analysis.session_lens import SessionLens
from aict2.analysis.trade_thesis import TradeThesis
from aict2.backtest.engine import run_backtest_case
from aict2.backtest.models import BacktestCase, BacktestTradeReplay
from aict2.io.chart_intake import ChartRequest

ET = ZoneInfo("America/New_York")


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
            source_files=("MNQ1!, 5.csv",),
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


def _frame(time: str, open_: float, high: float, low: float, close: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [time],
            "open": [open_],
            "high": [high],
            "low": [low],
            "close": [close],
        }
    )


def _in_memory_case(tmp_path: Path) -> BacktestCase:
    analysis_frames = {
        "5M": _frame("2026-04-02T09:55:00-04:00", 20000, 20010, 19990, 20005),
    }
    score_frame = _frame("2026-04-02T10:01:00-04:00", 20005, 20040, 20000, 20035)
    return BacktestCase(
        case_id="case-in-memory",
        case_path=tmp_path,
        analysis_paths=(),
        analysis_frames=analysis_frames,
        score_path=None,
        score_frame=score_frame,
        instrument="MNQ1!",
        ordered_timeframes=("5M",),
        execution_timeframe="5M",
        analysis_timestamp=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        validation_error=None,
    )


def test_run_backtest_case_uses_in_memory_analysis_and_score_frames(
    tmp_path: Path, monkeypatch
) -> None:
    case = _in_memory_case(tmp_path)
    captured: dict[str, object] = {}

    def fake_build_analysis_snapshot_from_frames(**kwargs):
        captured["analysis_frames"] = kwargs["analysis_frames"]
        captured["current_time"] = kwargs["current_time"]
        return _snapshot()

    monkeypatch.setattr(
        "aict2.backtest.engine.build_analysis_snapshot_from_frames",
        fake_build_analysis_snapshot_from_frames,
    )

    result = run_backtest_case(case)

    assert result.status == "LIVE SETUP"
    assert result.trade_outcome == "TP_HIT"
    assert result.trade_score == 1.0
    assert captured["analysis_frames"] is case.analysis_frames
    assert captured["current_time"] == case.analysis_timestamp


def test_run_backtest_case_compare_execution_only_uses_frame_subset(
    tmp_path: Path, monkeypatch
) -> None:
    case = BacktestCase(
        case_id="case-compare-in-memory",
        case_path=tmp_path,
        analysis_paths=(),
        analysis_frames={
            "Daily": _frame("2026-04-02T00:00:00-04:00", 20000, 20100, 19950, 20080),
            "1H": _frame("2026-04-02T09:00:00-04:00", 20050, 20090, 20040, 20085),
            "5M": _frame("2026-04-02T09:55:00-04:00", 20000, 20010, 19990, 20005),
        },
        score_path=None,
        score_frame=_frame("2026-04-02T09:56:00-04:00", 20005, 20040, 20000, 20035),
        instrument="MNQ1!",
        ordered_timeframes=("Daily", "1H", "5M"),
        execution_timeframe="5M",
        analysis_timestamp=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        validation_error=None,
    )
    seen_timeframes: list[tuple[str, ...]] = []

    def fake_build_analysis_snapshot_from_frames(**kwargs):
        seen_timeframes.append(tuple(kwargs["analysis_frames"].keys()))
        return _snapshot(status="LIVE SETUP" if len(kwargs["analysis_frames"]) == 1 else "WAIT")

    monkeypatch.setattr(
        "aict2.backtest.engine.build_analysis_snapshot_from_frames",
        fake_build_analysis_snapshot_from_frames,
    )

    result = run_backtest_case(case, compare_execution_only=True)

    assert result.status == "WAIT"
    assert result.comparison is not None
    assert result.comparison.primary_status == "WAIT"
    assert result.comparison.execution_only_status == "LIVE SETUP"
    assert result.comparison.differs is True
    assert seen_timeframes == [("Daily", "1H", "5M"), ("5M",)]
