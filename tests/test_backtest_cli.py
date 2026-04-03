from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aict2.analysis.analysis_service import AnalysisSnapshot
from aict2.analysis.risk_gate import RiskGateResult
from aict2.analysis.session_lens import SessionLens
from aict2.analysis.trade_thesis import TradeThesis
from aict2.backtest.cli import main
from aict2.backtest.models import BacktestTradeReplay
from aict2.io.chart_intake import ChartRequest


def _write_csv(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def _snapshot(status: str = "LIVE SETUP", state: str = "bullish") -> AnalysisSnapshot:
    return AnalysisSnapshot(
        instrument="MNQ1!",
        request=ChartRequest(
            instrument="MNQ1!",
            mode="multi",
            ordered_timeframes=("4H", "15M", "1M"),
            execution_timeframe="1M",
            has_higher_timeframe_context=True,
            bundle_profile="execution",
            is_canonical_bundle=True,
            source_files=(
                "CME_MINI_MNQ1!, 240.csv",
                "CME_MINI_MNQ1!, 15.csv",
                "CME_MINI_MNQ1!, 1.csv",
            ),
        ),
        thesis=TradeThesis(
            state=state,
            allowed_business="long_only",
            daily_profile="continuation",
            has_higher_timeframe_context=True,
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
        entry_model="1M Confirmation",
        tp_model="2R",
        target_reason="Defaulting to a full 2R objective unless external liquidity is closer.",
        needs_confirmation=False,
        requires_retrace=False,
        session_levels=None,
    )


def test_backtest_cli_prints_case_and_summary_lines(tmp_path: Path, capsys, monkeypatch) -> None:
    case = tmp_path / "2026-04-02-0955"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()

    _write_csv(
        analysis / "CME_MINI_MNQ1!, 240.csv",
        [("2026-04-02T08:00:00-04:00", 20000, 20020, 19980, 20010)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 15.csv",
        [("2026-04-02T09:45:00-04:00", 20010, 20014, 20000, 20012)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 1.csv",
        [("2026-04-02T09:55:00-04:00", 20012, 20016, 20008, 20015)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 1.csv",
        [
            ("2026-04-02T09:56:00-04:00", 20015, 20020, 20012, 20018),
            ("2026-04-02T09:57:00-04:00", 20018, 20040, 20017, 20035),
        ],
    )

    monkeypatch.setattr("aict2.backtest.engine.build_analysis_snapshot", lambda **kwargs: _snapshot())
    monkeypatch.setattr(
        "aict2.backtest.engine.replay_live_setup",
        lambda case_arg, snapshot_arg: BacktestTradeReplay(outcome="TP_HIT", score=1.0),
    )

    exit_code = main([str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "2026-04-02-0955" in output
    assert "LIVE SETUP" in output
    assert "TP_HIT" in output
    assert "SUMMARY" in output
    assert "total_cases=1" in output


def test_backtest_cli_reports_invalid_cases_without_crashing(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    bad_case = tmp_path / "bad-case"
    (bad_case / "analysis").mkdir(parents=True)

    _write_csv(
        bad_case / "analysis" / "CME_MINI_MNQ1!, 5.csv",
        [("2026-04-02T10:00:00-04:00", 20100, 20105, 20095, 20102)],
    )

    monkeypatch.setattr("aict2.backtest.engine.build_analysis_snapshot", lambda **kwargs: _snapshot())
    monkeypatch.setattr(
        "aict2.backtest.engine.replay_live_setup",
        lambda case_arg, snapshot_arg: BacktestTradeReplay(outcome="TP_HIT", score=1.0),
    )

    exit_code = main([str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "bad-case" in output
    assert "Missing score directory" in output
