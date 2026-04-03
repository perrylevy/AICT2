from __future__ import annotations

from pathlib import Path

from aict2.analysis.market_map import derive_chart_plan


def _write_chart(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def test_derive_chart_plan_detects_bullish_reclaim_and_uses_swing_stop(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 100.0, 100.5, 99.0, 99.2),
            ("2026-04-02T09:35:00-04:00", 99.2, 99.8, 98.7, 98.9),
            ("2026-04-02T09:40:00-04:00", 98.9, 99.0, 97.8, 98.1),
            ("2026-04-02T09:45:00-04:00", 98.1, 98.5, 97.2, 97.6),
            ("2026-04-02T09:50:00-04:00", 97.6, 99.2, 97.5, 99.1),
            ("2026-04-02T09:55:00-04:00", 99.1, 100.8, 99.0, 100.7),
            ("2026-04-02T10:00:00-04:00", 100.7, 102.4, 100.6, 102.1),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert plan.bias == "bullish"
    assert plan.daily_profile in {"reversal", "continuation"}
    assert plan.stop < plan.entry < plan.target


def test_derive_chart_plan_marks_extended_bullish_move_as_retrace_entry(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 100.0, 100.5, 99.8, 100.4),
            ("2026-04-02T09:35:00-04:00", 100.4, 100.9, 100.3, 100.8),
            ("2026-04-02T09:40:00-04:00", 100.8, 101.2, 100.7, 101.1),
            ("2026-04-02T09:45:00-04:00", 101.1, 101.8, 101.0, 101.7),
            ("2026-04-02T09:50:00-04:00", 101.7, 102.4, 101.6, 102.3),
            ("2026-04-02T09:55:00-04:00", 102.3, 103.0, 102.2, 102.9),
            ("2026-04-02T10:00:00-04:00", 102.9, 103.8, 102.8, 103.7),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert plan.bias == "bullish"
    assert plan.requires_retrace is True
    assert plan.entry < 103.7
    assert plan.stop < plan.entry < plan.target


def test_derive_chart_plan_detects_bearish_break_and_uses_swing_stop(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T10:00:00-04:00", 104.0, 104.5, 103.5, 104.2),
            ("2026-04-02T10:05:00-04:00", 104.2, 105.1, 104.0, 104.9),
            ("2026-04-02T10:10:00-04:00", 104.9, 105.4, 104.4, 105.2),
            ("2026-04-02T10:15:00-04:00", 105.2, 105.3, 104.2, 104.4),
            ("2026-04-02T10:20:00-04:00", 104.4, 104.5, 103.0, 103.2),
            ("2026-04-02T10:25:00-04:00", 103.2, 103.3, 101.9, 102.0),
            ("2026-04-02T10:30:00-04:00", 102.0, 102.2, 100.8, 101.1),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert plan.bias == "bearish"
    assert plan.stop > plan.entry > plan.target


def test_derive_chart_plan_marks_extended_bearish_move_as_retrace_entry(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T10:00:00-04:00", 104.0, 104.2, 103.6, 103.8),
            ("2026-04-02T10:05:00-04:00", 103.8, 103.9, 103.0, 103.1),
            ("2026-04-02T10:10:00-04:00", 103.1, 103.2, 102.3, 102.4),
            ("2026-04-02T10:15:00-04:00", 102.4, 102.5, 101.5, 101.6),
            ("2026-04-02T10:20:00-04:00", 101.6, 101.7, 100.8, 100.9),
            ("2026-04-02T10:25:00-04:00", 100.9, 101.0, 100.1, 100.2),
            ("2026-04-02T10:30:00-04:00", 100.2, 100.3, 99.4, 99.5),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert plan.bias == "bearish"
    assert plan.requires_retrace is True
    assert plan.entry > 99.5
    assert plan.stop > plan.entry > plan.target


def test_derive_chart_plan_detects_sell_side_sweep_as_bullish_liquidity(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 100.0, 100.7, 99.8, 100.4),
            ("2026-04-02T09:35:00-04:00", 100.4, 100.6, 99.1, 99.4),
            ("2026-04-02T09:40:00-04:00", 99.4, 100.1, 99.3, 99.8),
            ("2026-04-02T09:45:00-04:00", 99.8, 100.0, 99.05, 99.2),
            ("2026-04-02T09:50:00-04:00", 99.2, 100.2, 98.8, 100.1),
            ("2026-04-02T09:55:00-04:00", 100.1, 101.0, 100.0, 100.9),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert plan.bias == "bullish"
    assert "sell-side" in plan.liquidity_summary.lower()
    assert "sweep" in plan.liquidity_summary.lower()


def test_derive_chart_plan_surfaces_pd_arrays_on_bullish_displacement(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 100.0, 100.4, 99.7, 99.8),
            ("2026-04-02T09:35:00-04:00", 99.8, 100.0, 99.2, 99.3),
            ("2026-04-02T09:40:00-04:00", 99.3, 101.0, 99.2, 100.9),
            ("2026-04-02T09:45:00-04:00", 100.9, 102.2, 100.8, 102.0),
            ("2026-04-02T09:50:00-04:00", 102.0, 102.4, 101.7, 102.2),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert 'FVG' in plan.pd_array_summary or 'OB' in plan.pd_array_summary or 'VI' in plan.pd_array_summary


def test_derive_chart_plan_prioritizes_daily_structure_in_pd_array_summary(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-27T00:00:00-04:00", 100.0, 110.0, 95.0, 98.0),
            ("2026-03-30T00:00:00-04:00", 98.0, 102.0, 90.0, 92.0),
            ("2026-03-31T00:00:00-04:00", 112.0, 121.0, 111.0, 119.0),
            ("2026-04-01T00:00:00-04:00", 119.0, 123.0, 113.0, 114.0),
            ("2026-04-02T00:00:00-04:00", 114.0, 118.0, 112.5, 117.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 114.0, 114.5, 113.2, 113.5),
            ("2026-04-02T09:35:00-04:00", 113.5, 113.7, 112.8, 113.0),
            ("2026-04-02T09:40:00-04:00", 113.0, 114.8, 112.9, 114.6),
            ("2026-04-02T09:45:00-04:00", 114.6, 115.9, 114.5, 115.6),
            ("2026-04-02T09:50:00-04:00", 115.6, 116.0, 115.1, 115.8),
        ],
    )

    plan = derive_chart_plan([str(chart_daily), str(chart_5)])

    assert plan is not None
    assert "Daily Structure:" in plan.pd_array_summary
    assert "Daily" in plan.pd_array_summary
    assert "Execution:" in plan.pd_array_summary


def test_derive_chart_plan_detects_daily_ifvg_in_pd_array_summary(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-25T00:00:00-04:00", 100.0, 110.0, 95.0, 105.0),
            ("2026-03-26T00:00:00-04:00", 105.0, 107.0, 101.0, 106.0),
            ("2026-03-27T00:00:00-04:00", 112.0, 120.0, 111.5, 118.0),
            ("2026-03-30T00:00:00-04:00", 118.0, 119.0, 108.0, 109.0),
            ("2026-03-31T00:00:00-04:00", 109.0, 111.0, 104.0, 105.0),
            ("2026-04-01T00:00:00-04:00", 105.0, 108.0, 102.0, 103.0),
            ("2026-04-02T00:00:00-04:00", 103.0, 106.0, 101.0, 102.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 103.0, 103.2, 102.2, 102.4),
            ("2026-04-02T09:35:00-04:00", 102.4, 102.6, 101.9, 102.1),
            ("2026-04-02T09:40:00-04:00", 102.1, 102.3, 101.2, 101.4),
            ("2026-04-02T09:45:00-04:00", 101.4, 101.8, 100.8, 101.0),
            ("2026-04-02T09:50:00-04:00", 101.0, 101.4, 100.5, 100.8),
        ],
    )

    plan = derive_chart_plan([str(chart_daily), str(chart_5)])

    assert plan is not None
    assert "IFVG" in plan.pd_array_summary
    assert "conflicts" in plan.pd_array_confluence.lower() or "neutral" in plan.pd_array_confluence.lower()


def test_derive_chart_plan_detects_execution_breaker_or_vi(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 100.0, 100.8, 99.7, 100.7),
            ("2026-04-02T09:35:00-04:00", 100.7, 101.2, 100.5, 101.0),
            ("2026-04-02T09:40:00-04:00", 101.0, 101.1, 99.6, 99.8),
            ("2026-04-02T09:45:00-04:00", 99.8, 100.0, 99.1, 99.3),
            ("2026-04-02T09:50:00-04:00", 99.3, 101.8, 99.2, 101.7),
            ("2026-04-02T09:55:00-04:00", 101.5, 102.8, 101.4, 102.6),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert (
        "Breaker" in plan.pd_array_summary
        or "VI" in plan.pd_array_summary
        or "IFVG" in plan.pd_array_summary
    )


def test_derive_chart_plan_prioritizes_pre_sweep_execution_fvg(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:30:00-04:00", 101.0, 102.0, 100.0, 101.2),
            ("2026-04-02T09:35:00-04:00", 101.2, 102.2, 100.2, 101.5),
            ("2026-04-02T09:40:00-04:00", 103.2, 104.8, 103.0, 104.6),
            ("2026-04-02T09:45:00-04:00", 104.6, 104.9, 100.1, 100.4),
            ("2026-04-02T09:50:00-04:00", 100.4, 104.6, 99.3, 103.9),
            ("2026-04-02T09:55:00-04:00", 103.9, 105.2, 103.7, 105.0),
            ("2026-04-02T10:00:00-04:00", 105.0, 106.0, 104.9, 105.8),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert "102.00-103.00" in plan.pd_array_summary


def test_derive_chart_plan_detects_buy_side_sweep_as_bearish_liquidity(tmp_path: Path) -> None:
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_5,
        [
            ("2026-04-02T10:00:00-04:00", 104.0, 104.2, 103.4, 103.8),
            ("2026-04-02T10:05:00-04:00", 103.8, 105.1, 103.7, 104.9),
            ("2026-04-02T10:10:00-04:00", 104.9, 105.0, 104.2, 104.4),
            ("2026-04-02T10:15:00-04:00", 104.4, 105.15, 104.3, 104.8),
            ("2026-04-02T10:20:00-04:00", 104.8, 104.9, 103.5, 103.7),
            ("2026-04-02T10:25:00-04:00", 103.7, 103.8, 102.8, 102.9),
        ],
    )

    plan = derive_chart_plan([str(chart_5)])

    assert plan is not None
    assert plan.bias == "bearish"
    assert "buy-side" in plan.liquidity_summary.lower()
    assert "sweep" in plan.liquidity_summary.lower()
