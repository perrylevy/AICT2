from __future__ import annotations

from pathlib import Path

import pandas as pd

from aict2.analysis.setup_engine import (
    _resolve_execution_override_bias,
    _should_relax_retrace_requirement,
    derive_setup_plan,
    derive_setup_plan_from_frames,
    resolve_confirmation_requirement,
    resolve_stop_run_confirmation,
    resolve_target_and_tp_model,
)
from aict2.analysis.market_frame import ChartFrameFacts


def _write_chart(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def test_derive_setup_plan_from_frames_matches_path_variant(tmp_path: Path) -> None:
    daily = pd.DataFrame(
        {
            "time": [
                "2026-03-31T00:00:00-04:00",
                "2026-04-01T00:00:00-04:00",
                "2026-04-02T00:00:00-04:00",
            ],
            "open": [23960.0, 24050.0, 24120.0],
            "high": [24020.0, 24110.0, 24210.0],
            "low": [23920.0, 24000.0, 24090.0],
            "close": [23980.0, 24090.0, 24180.0],
        }
    )
    five = pd.DataFrame(
        {
            "time": [
                "2026-04-02T09:30:00-04:00",
                "2026-04-02T09:35:00-04:00",
                "2026-04-02T09:40:00-04:00",
                "2026-04-02T09:45:00-04:00",
                "2026-04-02T09:50:00-04:00",
                "2026-04-02T09:55:00-04:00",
                "2026-04-02T10:00:00-04:00",
            ],
            "open": [100.0, 99.2, 98.9, 98.1, 97.6, 99.1, 100.7],
            "high": [100.5, 99.8, 99.0, 98.5, 99.2, 100.8, 102.4],
            "low": [99.0, 98.7, 97.8, 97.2, 97.5, 99.0, 100.6],
            "close": [99.2, 98.9, 98.1, 97.6, 99.1, 100.7, 102.1],
        }
    )

    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(chart_daily, list(daily.itertuples(index=False, name=None)))
    _write_chart(chart_5, list(five.itertuples(index=False, name=None)))

    path_plan = derive_setup_plan([str(chart_daily), str(chart_5)])
    plan = derive_setup_plan_from_frames({"Daily": daily, "5M": five})

    assert plan is not None
    assert path_plan is not None
    assert plan.bias == path_plan.bias
    assert plan.entry == path_plan.entry
    assert plan.stop == path_plan.stop
    assert plan.target == path_plan.target
    assert plan.entry > 0.0
    assert plan.stop > 0.0
    assert plan.target > 0.0


def test_derive_setup_plan_builds_deterministic_plan_from_charts(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-31T00:00:00-04:00", 23960.0, 24020.0, 23920.0, 23980.0),
            ("2026-04-01T00:00:00-04:00", 24050.0, 24110.0, 24000.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24120.0, 24210.0, 24090.0, 24180.0),
        ],
    )
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

    plan = derive_setup_plan([str(chart_daily), str(chart_5)])

    assert plan is not None
    assert plan.liquidity_summary
    assert plan.reference_context
    assert plan.gap_summary
    assert plan.opening_summary
    assert plan.pd_array_summary
    assert plan.draw_on_liquidity
    assert plan.htf_reference
    assert plan.stop_run_summary
    assert plan.entry_model
    assert plan.tp_model
    assert plan.stop < plan.entry < plan.target


def test_derive_setup_plan_prioritizes_pdh_over_other_bullish_liquidity_targets(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_1h = tmp_path / "CME_MINI_MNQ1!, 60.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-31T00:00:00-04:00", 23960.0, 24020.0, 23920.0, 23980.0),
            ("2026-04-01T00:00:00-04:00", 24050.0, 24110.0, 24000.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24120.0, 24210.0, 24090.0, 24180.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ("2026-04-01T20:00:00-04:00", 24080.0, 24100.0, 24040.0, 24090.0),
            ("2026-04-02T09:00:00-04:00", 24090.0, 24180.0, 24070.0, 24170.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-01T15:30:00-04:00", 24010.0, 24060.0, 23980.0, 24040.0),
            ("2026-04-01T15:55:00-04:00", 24040.0, 24090.0, 24020.0, 24080.0),
            ("2026-04-02T09:30:00-04:00", 24080.0, 24110.0, 23990.0, 24020.0),
            ("2026-04-02T09:35:00-04:00", 24020.0, 24040.0, 23980.0, 24010.0),
            ("2026-04-02T09:40:00-04:00", 24010.0, 24120.0, 24000.0, 24100.0),
            ("2026-04-02T09:45:00-04:00", 24100.0, 24120.0, 24060.0, 24070.0),
        ],
    )

    plan = derive_setup_plan([str(chart_daily), str(chart_1h), str(chart_5)])

    assert plan is not None
    assert plan.draw_on_liquidity.startswith("PDH ")


def test_derive_setup_plan_uses_previous_session_high_before_eqh_when_no_daily(tmp_path: Path) -> None:
    chart_1h = tmp_path / "CME_MINI_MNQ1!, 60.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_1h,
        [
            ("2026-04-01T20:00:00-04:00", 24080.0, 24100.0, 24040.0, 24090.0),
            ("2026-04-02T09:00:00-04:00", 24090.0, 24180.0, 24070.0, 24170.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-01T14:30:00-04:00", 24010.0, 24080.0, 23990.0, 24050.0),
            ("2026-04-01T15:00:00-04:00", 24050.0, 24082.0, 24020.0, 24060.0),
            ("2026-04-01T15:55:00-04:00", 24060.0, 24090.0, 24040.0, 24080.0),
            ("2026-04-02T09:30:00-04:00", 24080.0, 24110.0, 23990.0, 24020.0),
            ("2026-04-02T09:35:00-04:00", 24020.0, 24040.0, 23980.0, 24010.0),
            ("2026-04-02T09:40:00-04:00", 24010.0, 24120.0, 24000.0, 24100.0),
            ("2026-04-02T09:45:00-04:00", 24100.0, 24120.0, 24060.0, 24070.0),
        ],
    )

    plan = derive_setup_plan([str(chart_1h), str(chart_5)])

    assert plan is not None
    assert plan.draw_on_liquidity.startswith("EQH ")


def test_derive_setup_plan_prefers_nearer_london_high_over_farther_previous_session_high(
    tmp_path: Path,
) -> None:
    chart_1h = tmp_path / "CME_MINI_MNQ1!, 60.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_1h,
        [
            ("2026-04-01T20:00:00-04:00", 24010.0, 24040.0, 23980.0, 24020.0),
            ("2026-04-02T01:00:00-04:00", 24020.0, 24110.0, 24000.0, 24100.0),
            ("2026-04-02T09:00:00-04:00", 24100.0, 24180.0, 24090.0, 24170.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-01T15:30:00-04:00", 24010.0, 24060.0, 23980.0, 24040.0),
            ("2026-04-01T15:55:00-04:00", 24040.0, 24180.0, 24020.0, 24120.0),
            ("2026-04-02T00:30:00-04:00", 24030.0, 24070.0, 24020.0, 24060.0),
            ("2026-04-02T05:30:00-04:00", 24060.0, 24110.0, 24040.0, 24090.0),
            ("2026-04-02T09:30:00-04:00", 24090.0, 24100.0, 24030.0, 24040.0),
            ("2026-04-02T09:35:00-04:00", 24040.0, 24080.0, 24020.0, 24030.0),
            ("2026-04-02T09:40:00-04:00", 24030.0, 24120.0, 24020.0, 24100.0),
            ("2026-04-02T09:45:00-04:00", 24100.0, 24110.0, 24080.0, 24095.0),
        ],
    )

    plan = derive_setup_plan([str(chart_1h), str(chart_5)])

    assert plan is not None
    assert plan.draw_on_liquidity.startswith("London High ")


def test_derive_setup_plan_uses_same_london_level_as_session_levels_when_intraday_frames_disagree(
    tmp_path: Path,
) -> None:
    chart_4h = tmp_path / "CME_MINI_MNQ1!, 240.csv"
    chart_15 = tmp_path / "CME_MINI_MNQ1!, 15.csv"
    chart_1 = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_chart(
        chart_4h,
        [
            ("2026-04-02T02:00:00-04:00", 24080.0, 24160.0, 24020.0, 24140.0),
            ("2026-04-02T06:00:00-04:00", 24140.0, 24170.0, 24080.0, 24120.0),
            ("2026-04-02T10:00:00-04:00", 24120.0, 24190.0, 24090.0, 24130.0),
        ],
    )
    _write_chart(
        chart_15,
        [
            ("2026-04-01T18:00:00-04:00", 24110.0, 24140.0, 24100.0, 24120.0),
            ("2026-04-02T00:15:00-04:00", 24120.0, 24184.25, 24105.0, 24160.0),
            ("2026-04-02T05:45:00-04:00", 24160.0, 24180.0, 24120.0, 24140.0),
            ("2026-04-02T08:45:00-04:00", 24140.0, 24155.0, 24105.0, 24120.0),
            ("2026-04-02T09:00:00-04:00", 24120.0, 24135.0, 24105.0, 24115.0),
        ],
    )
    _write_chart(
        chart_1,
        [
            ("2026-04-01T18:00:00-04:00", 24110.0, 24140.0, 24110.0, 24120.0),
            ("2026-04-02T00:05:00-04:00", 24120.0, 24170.0, 24112.0, 24140.0),
            ("2026-04-02T01:02:00-04:00", 24140.0, 24193.50, 24120.0, 24180.0),
            ("2026-04-02T05:50:00-04:00", 24180.0, 24182.0, 24130.0, 24145.0),
            ("2026-04-02T08:55:00-04:00", 24145.0, 24155.0, 24110.0, 24118.0),
            ("2026-04-02T09:01:00-04:00", 24118.0, 24128.0, 24112.0, 24124.0),
        ],
    )

    plan = derive_setup_plan([str(chart_4h), str(chart_15), str(chart_1)])

    assert plan is not None
    assert plan.draw_on_liquidity == "London Low 24112.00"


def test_derive_setup_plan_prefers_nearer_asia_low_over_farther_previous_session_low(
    tmp_path: Path,
) -> None:
    chart_1h = tmp_path / "CME_MINI_MNQ1!, 60.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_1h,
        [
            ("2026-04-01T20:00:00-04:00", 24180.0, 24210.0, 24080.0, 24100.0),
            ("2026-04-02T01:00:00-04:00", 24100.0, 24120.0, 24040.0, 24060.0),
            ("2026-04-02T09:00:00-04:00", 24060.0, 24080.0, 23940.0, 23960.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-01T15:30:00-04:00", 24180.0, 24200.0, 24020.0, 24060.0),
            ("2026-04-01T15:55:00-04:00", 24060.0, 24080.0, 23940.0, 23960.0),
            ("2026-04-02T00:30:00-04:00", 24090.0, 24100.0, 24070.0, 24080.0),
            ("2026-04-02T05:30:00-04:00", 24080.0, 24090.0, 24040.0, 24060.0),
            ("2026-04-02T09:30:00-04:00", 24060.0, 24070.0, 23990.0, 24040.0),
            ("2026-04-02T09:35:00-04:00", 24040.0, 24050.0, 23970.0, 24000.0),
            ("2026-04-02T09:40:00-04:00", 24000.0, 24010.0, 23920.0, 23940.0),
            ("2026-04-02T09:45:00-04:00", 23940.0, 23980.0, 23930.0, 24050.0),
        ],
    )

    plan = derive_setup_plan([str(chart_1h), str(chart_5)])

    assert plan is not None
    assert plan.draw_on_liquidity.startswith("London Low ")


def test_resolve_confirmation_requirement_allows_clean_bullish_continuation_without_stop_run() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=False,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.5,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="15M IFVG",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
        )
        is False
    )


def test_resolve_confirmation_requirement_still_requires_confirmation_for_weak_continuation() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=False,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.05,
            execution_reclaimed_high=False,
            execution_broke_low=False,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M/15M Confirmation",
            liquidity_summary="No clear liquidity sweep; waiting for cleaner pool interaction",
            requires_retrace=False,
        )
        is True
    )


def test_resolve_confirmation_requirement_allows_mixed_context_ifvg_override() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.6,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=True,
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
        )
        is False
    )


def test_resolve_confirmation_requirement_keeps_mixed_context_wait_without_named_trigger() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.8,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=True,
            execution_timeframe="5M",
            entry_model="5M/15M Confirmation",
            liquidity_summary="No clear liquidity sweep; waiting for cleaner pool interaction",
            requires_retrace=False,
        )
        is True
    )


def test_resolve_confirmation_requirement_allows_aligned_reversal_ifvg_without_stop_run() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=False,
            stop_run_confirmed=False,
            daily_profile="reversal",
            bias="bearish",
            execution_bias="bearish",
            execution_displacement=1.5,
            execution_reclaimed_high=False,
            execution_broke_low=True,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Sell-side pressure through recent swing low 23910.00",
            requires_retrace=False,
        )
        is False
    )


def test_resolve_confirmation_requirement_allows_clear_5m_reclaim_without_ifvg() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.2,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=True,
            execution_timeframe="5M",
            entry_model="5M/15M Confirmation",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
        )
        is False
    )


def test_resolve_confirmation_requirement_allows_aligned_5m_displacement_plus_hold_without_stop_run() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.45,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M/15M Confirmation",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
            higher_timeframe_bias="bullish",
            target_distance=45.0,
        )
        is False
    )


def test_resolve_confirmation_requirement_allows_mixed_htf_aligned_5m_ifvg_without_opposing_draw() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.6,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
            higher_timeframe_bias="mixed",
            target_distance=45.0,
        )
        is False
    )


def test_resolve_confirmation_requirement_allows_weak_htf_conflict_reversal_ifvg_when_raw_bias_is_mixed() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="reversal",
            raw_bias="mixed",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.8,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
            higher_timeframe_bias="bearish",
            target_distance=45.0,
        )
        is False
    )


def test_resolve_confirmation_requirement_keeps_weak_reclaim_waiting_without_ifvg() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.05,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=True,
            execution_timeframe="5M",
            entry_model="5M/15M Confirmation",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
        )
        is True
    )


def test_resolve_confirmation_requirement_blocks_counter_draw_if_reversal_lacks_sweep() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=False,
            stop_run_confirmed=False,
            daily_profile="reversal",
            bias="bearish",
            execution_bias="bearish",
            execution_displacement=1.65,
            execution_reclaimed_high=False,
            execution_broke_low=True,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Sell-side pressure through recent swing low 23910.00",
            requires_retrace=False,
            higher_timeframe_bias="bullish",
            target_distance=80.0,
        )
        is True
    )


def test_resolve_confirmation_requirement_blocks_counter_draw_without_60_point_runway() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=False,
            stop_run_confirmed=False,
            daily_profile="reversal",
            bias="bearish",
            execution_bias="bearish",
            execution_displacement=1.8,
            execution_reclaimed_high=False,
            execution_broke_low=True,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side liquidity sweep above 24090.00 with bearish close-back-in",
            requires_retrace=False,
            higher_timeframe_bias="bullish",
            target_distance=45.0,
        )
        is True
    )


def test_resolve_confirmation_requirement_allows_counter_draw_with_full_exception() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=False,
            stop_run_confirmed=False,
            daily_profile="reversal",
            bias="bearish",
            execution_bias="bearish",
            execution_displacement=1.8,
            execution_reclaimed_high=False,
            execution_broke_low=True,
            execution_bias_override_active=False,
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side liquidity sweep above 24090.00 with bearish close-back-in",
            requires_retrace=False,
            higher_timeframe_bias="bullish",
            target_distance=75.0,
        )
        is False
    )


def test_resolve_confirmation_requirement_keeps_override_scoped_to_5m() -> None:
    assert (
        resolve_confirmation_requirement(
            base_needs_confirmation=True,
            stop_run_confirmed=False,
            daily_profile="continuation",
            bias="bullish",
            execution_bias="bullish",
            execution_displacement=1.6,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            execution_bias_override_active=False,
            execution_timeframe="15M",
            entry_model="15M IFVG",
            liquidity_summary="Buy-side reclaim through recent swing high 24090.00",
            requires_retrace=False,
        )
        is True
    )


def test_resolve_execution_override_bias_allows_strong_mixed_reclaim_despite_extended_range() -> None:
    execution_fact = ChartFrameFacts(
        timeframe="5M",
        last_close=25140.0,
        last_open=25080.0,
        last_high=25145.0,
        last_low=25020.0,
        anchor_close=25060.0,
        range_high=25145.0,
        range_low=25020.0,
        range_position=0.96,
        bias="bullish",
        displacement=1.75,
        latest_swing_high=25110.0,
        latest_swing_low=25040.0,
        reclaimed_high=True,
        broke_low=False,
        buy_side_sweep=False,
        sell_side_sweep=True,
        liquidity_summary="Sell-side liquidity sweep below 25040.00 with bullish reclaim",
    )

    bias = _resolve_execution_override_bias(
        raw_bias="mixed",
        execution_timeframe="5M",
        execution_bias="bullish",
        execution_entry_model="5M Confirmation",
        execution_fact=execution_fact,
    )

    assert bias == "bullish"


def test_should_relax_retrace_requirement_for_aligned_reversal_ifvg() -> None:
    assert (
        _should_relax_retrace_requirement(
            raw_bias="bullish",
            bias="bullish",
            higher_timeframe_bias="bullish",
            execution_bias="bullish",
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side reclaim through recent swing high 25546.75",
            execution_displacement=0.99,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            daily_profile="reversal",
        )
        is True
    )


def test_should_not_relax_retrace_requirement_for_weak_mixed_extension() -> None:
    assert (
        _should_relax_retrace_requirement(
            raw_bias="mixed",
            bias="bullish",
            higher_timeframe_bias="mixed",
            execution_bias="bullish",
            execution_timeframe="5M",
            entry_model="5M Confirmation",
            liquidity_summary="Sell-side liquidity sweep below 24780.00 with bullish reclaim",
            execution_displacement=0.69,
            execution_reclaimed_high=True,
            execution_broke_low=False,
            daily_profile="transition",
        )
        is False
    )


def test_should_not_relax_retrace_requirement_for_mixed_ifvg_extension() -> None:
    assert (
        _should_relax_retrace_requirement(
            raw_bias="mixed",
            bias="bearish",
            higher_timeframe_bias="mixed",
            execution_bias="bearish",
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Sell-side pressure through recent swing low 24440.50",
            execution_displacement=1.95,
            execution_reclaimed_high=False,
            execution_broke_low=True,
            daily_profile="continuation",
        )
        is False
    )


def test_should_relax_retrace_requirement_for_confirmed_stop_run_reversal_with_aligned_htf() -> None:
    assert (
        _should_relax_retrace_requirement(
            raw_bias="bearish",
            bias="bearish",
            higher_timeframe_bias="bearish",
            execution_bias="bearish",
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side liquidity sweep above 23621.25 with bearish close-back-in",
            execution_displacement=3.14,
            execution_reclaimed_high=False,
            execution_broke_low=True,
            daily_profile="reversal",
        )
        is True
    )


def test_should_not_relax_retrace_requirement_for_confirmed_stop_run_reversal_against_htf() -> None:
    assert (
        _should_relax_retrace_requirement(
            raw_bias="bearish",
            bias="bearish",
            higher_timeframe_bias="bullish",
            execution_bias="bearish",
            execution_timeframe="5M",
            entry_model="5M IFVG",
            liquidity_summary="Buy-side liquidity sweep above 23621.25 with bearish close-back-in",
            execution_displacement=3.14,
            execution_reclaimed_high=False,
            execution_broke_low=True,
            daily_profile="reversal",
        )
        is False
    )


def test_derive_setup_plan_prefers_4h_fvg_as_htf_reference_before_swing_levels(
    tmp_path: Path,
) -> None:
    chart_4h = tmp_path / "CME_MINI_MNQ1!, 240.csv"
    chart_15 = tmp_path / "CME_MINI_MNQ1!, 15.csv"
    chart_1 = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_chart(
        chart_4h,
        [
            ("2026-04-01T18:00:00-04:00", 23920.0, 23980.0, 23890.0, 23970.0),
            ("2026-04-01T22:00:00-04:00", 23970.0, 24010.0, 23940.0, 23990.0),
            ("2026-04-02T02:00:00-04:00", 24060.0, 24120.0, 24050.0, 24100.0),
            ("2026-04-02T06:00:00-04:00", 24100.0, 24140.0, 24080.0, 24110.0),
        ],
    )
    _write_chart(
        chart_15,
        [
            ("2026-04-02T09:15:00-04:00", 24092.0, 24102.0, 24080.0, 24086.0),
            ("2026-04-02T09:30:00-04:00", 24086.0, 24088.0, 24040.0, 24048.0),
            ("2026-04-02T09:45:00-04:00", 24048.0, 24070.0, 24042.0, 24066.0),
            ("2026-04-02T10:00:00-04:00", 24066.0, 24096.0, 24060.0, 24090.0),
        ],
    )
    _write_chart(
        chart_1,
        [
            ("2026-04-02T09:58:00-04:00", 24068.0, 24070.0, 24060.0, 24062.0),
            ("2026-04-02T09:59:00-04:00", 24062.0, 24064.0, 24052.0, 24056.0),
            ("2026-04-02T10:00:00-04:00", 24056.0, 24075.0, 24054.0, 24072.0),
            ("2026-04-02T10:01:00-04:00", 24072.0, 24092.0, 24070.0, 24090.0),
        ],
    )

    plan = derive_setup_plan([str(chart_4h), str(chart_15), str(chart_1)])

    assert plan is not None
    assert plan.bias == "bullish"
    assert plan.htf_reference.startswith("4H Bullish FVG ")


def test_derive_setup_plan_keeps_confirmation_required_without_real_stop_run(
    tmp_path: Path,
) -> None:
    chart_4h = tmp_path / "CME_MINI_MNQ1!, 240.csv"
    chart_15 = tmp_path / "CME_MINI_MNQ1!, 15.csv"
    chart_1 = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_chart(
        chart_4h,
        [
            ("2026-04-01T18:00:00-04:00", 23920.0, 23980.0, 23890.0, 23970.0),
            ("2026-04-01T22:00:00-04:00", 23970.0, 24010.0, 23940.0, 23990.0),
            ("2026-04-02T02:00:00-04:00", 24060.0, 24120.0, 24050.0, 24100.0),
            ("2026-04-02T06:00:00-04:00", 24100.0, 24140.0, 24080.0, 24110.0),
        ],
    )
    _write_chart(
        chart_15,
        [
            ("2026-04-02T09:15:00-04:00", 24092.0, 24102.0, 24080.0, 24086.0),
            ("2026-04-02T09:30:00-04:00", 24086.0, 24088.0, 24040.0, 24048.0),
            ("2026-04-02T09:45:00-04:00", 24048.0, 24070.0, 24042.0, 24066.0),
            ("2026-04-02T10:00:00-04:00", 24066.0, 24096.0, 24060.0, 24090.0),
        ],
    )
    _write_chart(
        chart_1,
        [
            ("2026-04-02T09:57:00-04:00", 24060.0, 24066.0, 24058.0, 24064.0),
            ("2026-04-02T09:58:00-04:00", 24064.0, 24068.0, 24062.0, 24066.0),
            ("2026-04-02T09:59:00-04:00", 24066.0, 24070.0, 24064.0, 24069.0),
            ("2026-04-02T10:00:00-04:00", 24069.0, 24076.0, 24068.0, 24075.0),
            ("2026-04-02T10:01:00-04:00", 24075.0, 24082.0, 24074.0, 24081.0),
        ],
    )

    plan = derive_setup_plan([str(chart_4h), str(chart_15), str(chart_1)])

    assert plan is not None
    assert plan.bias == "bullish"
    assert plan.stop_run_summary.startswith("No confirmed stop run")
    assert plan.needs_confirmation is True


def test_derive_setup_plan_promotes_mixed_htf_5m_ifvg_when_no_opposing_draw_exists(
    tmp_path: Path,
) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_1h = tmp_path / "CME_MINI_MNQ1!, 60.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-31T00:00:00-04:00", 130.0, 148.0, 118.0, 130.0),
            ("2026-04-01T00:00:00-04:00", 130.0, 146.0, 120.0, 129.0),
            ("2026-04-02T00:00:00-04:00", 129.0, 145.0, 121.0, 131.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ("2026-04-02T07:00:00-04:00", 140.0, 144.0, 138.0, 140.0),
            ("2026-04-02T08:00:00-04:00", 140.0, 146.0, 139.0, 141.0),
            ("2026-04-02T09:00:00-04:00", 141.0, 145.0, 140.0, 141.75),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:10:00-04:00", 99.8, 100.0, 99.7, 99.9),
            ("2026-04-02T09:15:00-04:00", 99.9, 100.2, 99.8, 100.0),
            ("2026-04-02T09:20:00-04:00", 100.0, 100.5, 99.9, 100.3),
            ("2026-04-02T09:25:00-04:00", 100.3, 100.4, 99.9, 99.95),
            ("2026-04-02T09:30:00-04:00", 99.95, 100.0, 99.7, 99.8),
            ("2026-04-02T09:35:00-04:00", 99.8, 100.0, 99.75, 99.9),
            ("2026-04-02T09:40:00-04:00", 99.9, 101.0, 99.9, 100.8),
        ],
    )

    plan = derive_setup_plan([str(chart_daily), str(chart_1h), str(chart_5)])

    assert plan is not None
    assert plan.bias == "bullish"
    assert plan.entry_model == "5M Confirmation"
    assert plan.requires_retrace is False
    assert plan.needs_confirmation is False


def test_derive_setup_plan_uses_15m_ifvg_as_entry_trigger_when_available(
    tmp_path: Path,
) -> None:
    chart_4h = tmp_path / "CME_MINI_MNQ1!, 240.csv"
    chart_15 = tmp_path / "CME_MINI_MNQ1!, 15.csv"
    chart_1 = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_chart(
        chart_4h,
        [
            ("2026-04-01T18:00:00-04:00", 23920.0, 23980.0, 23890.0, 23970.0),
            ("2026-04-01T22:00:00-04:00", 23970.0, 24010.0, 23940.0, 23990.0),
            ("2026-04-02T02:00:00-04:00", 24060.0, 24120.0, 24050.0, 24100.0),
            ("2026-04-02T06:00:00-04:00", 24100.0, 24140.0, 24080.0, 24110.0),
        ],
    )
    _write_chart(
        chart_15,
        [
            ("2026-04-02T09:15:00-04:00", 24102.0, 24106.0, 24088.0, 24090.0),
            ("2026-04-02T09:30:00-04:00", 24090.0, 24092.0, 24046.0, 24050.0),
            ("2026-04-02T09:45:00-04:00", 24050.0, 24052.0, 24020.0, 24026.0),
            ("2026-04-02T10:00:00-04:00", 24026.0, 24094.0, 24024.0, 24090.0),
        ],
    )
    _write_chart(
        chart_1,
        [
            ("2026-04-02T09:58:00-04:00", 24042.0, 24046.0, 24038.0, 24044.0),
            ("2026-04-02T09:59:00-04:00", 24044.0, 24048.0, 24040.0, 24046.0),
            ("2026-04-02T10:00:00-04:00", 24046.0, 24056.0, 24044.0, 24054.0),
            ("2026-04-02T10:01:00-04:00", 24054.0, 24066.0, 24052.0, 24064.0),
        ],
    )

    plan = derive_setup_plan([str(chart_4h), str(chart_15), str(chart_1)])

    assert plan is not None
    assert plan.entry_model.startswith("15M IFVG")


def test_resolve_target_and_tp_model_prefers_nearer_draw_on_liquidity_before_2r() -> None:
    target, tp_model, target_reason = resolve_target_and_tp_model(
        entry=100.0,
        stop=96.0,
        bias="bullish",
        draw_on_liquidity="PDH 106.00",
    )

    assert target == 106.0
    assert tp_model == "Draw on Liquidity"
    assert target_reason == "External liquidity caps the trade before a full 2R expansion."


def test_resolve_target_and_tp_model_keeps_2r_when_draw_on_liquidity_is_beyond_it() -> None:
    target, tp_model, target_reason = resolve_target_and_tp_model(
        entry=100.0,
        stop=96.0,
        bias="bullish",
        draw_on_liquidity="PDH 110.00",
    )

    assert target == 108.0
    assert tp_model == "2R"
    assert target_reason == "A full 2R objective comes before the next meaningful external liquidity target."


def test_resolve_stop_run_confirmation_confirms_raid_at_selected_draw_on_liquidity() -> None:
    confirmed, summary = resolve_stop_run_confirmation(
        liquidity_summary="Sell-side liquidity sweep below 24050.50 with bullish reclaim",
        draw_on_liquidity="PDL 24050.00",
        htf_reference="4H Bullish FVG 24042.00-24058.00 (CE 24050.00)",
    )

    assert confirmed is True
    assert summary.startswith("Confirmed stop run")


def test_resolve_stop_run_confirmation_rejects_raid_far_from_selected_levels() -> None:
    confirmed, summary = resolve_stop_run_confirmation(
        liquidity_summary="Sell-side liquidity sweep below 23920.50 with bullish reclaim",
        draw_on_liquidity="PDL 24050.00",
        htf_reference="4H Bullish FVG 24042.00-24058.00 (CE 24050.00)",
    )

    assert confirmed is False
    assert summary.startswith("No confirmed stop run at the selected draw on liquidity yet")


def test_derive_setup_plan_targets_scalp_style_5m_ifvg_levels(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_1h = tmp_path / "CME_MINI_MNQ1!, 60.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-31T00:00:00-04:00", 23960.0, 24020.0, 23920.0, 23980.0),
            ("2026-04-01T00:00:00-04:00", 24050.0, 24240.0, 24000.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24120.0, 24210.0, 24090.0, 24180.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ("2026-04-02T07:00:00-04:00", 24080.0, 24100.0, 24040.0, 24090.0),
            ("2026-04-02T08:00:00-04:00", 24090.0, 24140.0, 24070.0, 24120.0),
            ("2026-04-02T09:00:00-04:00", 24120.0, 24200.0, 24100.0, 24190.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:10:00-04:00", 24080.0, 24084.0, 24074.0, 24078.0),
            ("2026-04-02T09:15:00-04:00", 24078.0, 24080.0, 24070.0, 24072.0),
            ("2026-04-02T09:20:00-04:00", 24072.0, 24074.0, 24064.0, 24066.0),
            ("2026-04-02T09:25:00-04:00", 24066.0, 24068.0, 24058.0, 24060.0),
            ("2026-04-02T09:30:00-04:00", 24060.0, 24056.0, 24050.0, 24052.0),
            ("2026-04-02T09:35:00-04:00", 24052.0, 24078.0, 24050.0, 24074.0),
            ("2026-04-02T09:40:00-04:00", 24074.0, 24108.0, 24072.0, 24092.0),
        ],
    )

    plan = derive_setup_plan([str(chart_daily), str(chart_1h), str(chart_5)])

    assert plan is not None
    assert plan.entry_model == "5M IFVG"
    assert plan.entry > plan.stop
    assert plan.entry - plan.stop <= 15.0
    assert 40.0 <= plan.target - plan.entry <= 50.0


def test_derive_setup_plan_rejects_scalp_when_only_wide_stop_is_available(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_1h = tmp_path / "CME_MINI_MNQ1!, 60.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-02-01T00:00:00-05:00", 25520.0, 26019.0, 25180.0, 25640.0),
            ("2026-02-02T00:00:00-05:00", 25640.0, 25688.0, 25596.0, 25613.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ("2026-02-02T08:00:00-05:00", 25505.0, 25560.0, 25495.0, 25556.0),
            ("2026-02-02T09:00:00-05:00", 25556.0, 25613.0, 25544.0, 25613.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-02-02T08:45:00-05:00", 25498.0, 25520.0, 25492.25, 25505.0),
            ("2026-02-02T08:50:00-05:00", 25505.0, 25530.0, 25498.0, 25518.0),
            ("2026-02-02T08:55:00-05:00", 25518.0, 25544.0, 25510.0, 25540.0),
            ("2026-02-02T09:00:00-05:00", 25540.0, 25552.0, 25530.0, 25536.0),
            ("2026-02-02T09:05:00-05:00", 25536.0, 25544.0, 25520.0, 25528.0),
            ("2026-02-02T09:10:00-05:00", 25528.0, 25536.0, 25514.0, 25518.0),
            ("2026-02-02T09:15:00-05:00", 25518.0, 25534.0, 25510.0, 25530.0),
            ("2026-02-02T09:20:00-05:00", 25530.0, 25548.0, 25522.0, 25542.0),
            ("2026-02-02T09:25:00-05:00", 25542.0, 25570.0, 25538.0, 25564.0),
            ("2026-02-02T09:30:00-05:00", 25564.0, 25588.0, 25542.0, 25584.0),
            ("2026-02-02T09:35:00-05:00", 25584.0, 25613.0, 25580.0, 25613.0),
            ("2026-02-02T09:40:00-05:00", 25613.0, 25616.0, 25596.0, 25613.0),
        ],
    )

    plan = derive_setup_plan([str(chart_daily), str(chart_1h), str(chart_5)])

    assert plan is not None
    assert plan.entry > 0.0
    assert plan.stop > 0.0
    assert plan.target > 0.0
    assert plan.needs_confirmation is True
    assert plan.requires_retrace is True
