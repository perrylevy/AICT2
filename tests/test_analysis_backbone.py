from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from aict2.analysis.market_map import summarize_timeframe_context
from aict2.analysis.analysis_service import _derive_status
from aict2.analysis.risk_gate import evaluate_risk_gate
from aict2.analysis.session_lens import build_session_lens
from aict2.analysis.trade_thesis import derive_trade_thesis
from aict2.io.chart_intake import build_chart_request

ET = ZoneInfo('America/New_York')


def test_summarize_timeframe_context_sorts_and_detects_htf() -> None:
    summary = summarize_timeframe_context(['1M', '15M', '5M'])

    assert summary.ordered_timeframes == ('15M', '5M', '1M')
    assert summary.execution_timeframe == '1M'
    assert summary.has_higher_timeframe_context is True


def test_summarize_timeframe_context_ignores_duplicates_for_htf_flag() -> None:
    summary = summarize_timeframe_context(['1M', '1M'])

    assert summary.ordered_timeframes == ('1M',)
    assert summary.has_higher_timeframe_context is False


def test_summarize_timeframe_context_rejects_unknown_timeframes() -> None:
    with pytest.raises(ValueError, match='Unknown timeframe'):
        summarize_timeframe_context(['1M', '2M'])


def test_build_session_lens_tags_ny_open_macro_and_high_vol() -> None:
    lens = build_session_lens(
        current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        macro_state='Risk-Off',
        vix=22.4,
    )

    assert 'ny_open_macro' in lens.active_windows
    assert lens.volatility_regime == 'high'
    assert lens.macro_state == 'Risk-Off'
    assert lens.session_phase == 'rth_morning'
    assert lens.analysis_window == 'Open Check (ideal)'


def test_build_session_lens_tags_london_close_macro() -> None:
    lens = build_session_lens(
        current_time=datetime(2026, 4, 2, 10, 55, tzinfo=ET),
        macro_state='Mixed',
        vix=18.2,
    )

    assert 'london_close_macro' in lens.active_windows
    assert lens.volatility_regime == 'normal'
    assert lens.session_phase == 'rth_morning'
    assert lens.analysis_window == 'Standard Session Read'


def test_build_session_lens_labels_overnight_phase_before_premarket() -> None:
    lens = build_session_lens(
        current_time=datetime(2026, 4, 2, 1, 13, tzinfo=ET),
        macro_state='Mixed',
        vix=22.0,
    )

    assert lens.session_phase == 'overnight'
    assert lens.analysis_window == 'Standard Session Read'


def test_build_session_lens_labels_premarket_map_window() -> None:
    lens = build_session_lens(
        current_time=datetime(2026, 4, 2, 8, 30, tzinfo=ET),
        macro_state='Mixed',
        vix=18.2,
    )

    assert lens.session_phase == 'premarket'
    assert lens.analysis_window == 'Premarket Map (early)'


def test_build_session_lens_marks_afternoon_phase() -> None:
    lens = build_session_lens(
        current_time=datetime(2026, 4, 2, 14, 42, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
    )

    assert lens.active_windows == ()
    assert lens.session_phase == 'afternoon'
    assert lens.analysis_window == 'Standard Session Read'


def test_derive_trade_thesis_maps_bullish_bias_to_long_only() -> None:
    thesis = derive_trade_thesis(
        bias='bullish',
        daily_profile='continuation',
        has_higher_timeframe_context=True,
    )

    assert thesis.state == 'bullish'
    assert thesis.allowed_business == 'long_only'
    assert thesis.daily_profile == 'continuation'


def test_derive_trade_thesis_stands_down_on_mixed_bias() -> None:
    thesis = derive_trade_thesis(
        bias='mixed',
        daily_profile='seek_and_destroy',
        has_higher_timeframe_context=False,
    )

    assert thesis.state == 'mixed'
    assert thesis.allowed_business == 'no_trade'


def test_evaluate_risk_gate_computes_contracts_and_rr() -> None:
    gate = evaluate_risk_gate(
        entry=20_000,
        stop=19_990,
        target=20_035,
        point_value=2.0,
        risk_per_trade=120.0,
        min_rr=1.75,
    )

    assert gate.stop_distance == 10
    assert gate.rr == 3.5
    assert gate.max_contracts == 6
    assert gate.clears_min_rr is True


def test_evaluate_risk_gate_rejects_low_rr_setup() -> None:
    gate = evaluate_risk_gate(
        entry=20_000,
        stop=19_990,
        target=20_015,
        point_value=2.0,
        risk_per_trade=120.0,
        min_rr=1.75,
    )

    assert gate.rr == 1.5
    assert gate.clears_min_rr is False

def test_derive_status_keeps_bad_rr_waits_during_premarket() -> None:
    request = build_chart_request(
        ['CME_MINI_MNQ1!, 240.csv', 'CME_MINI_MNQ1!, 15.csv', 'CME_MINI_MNQ1!, 1.csv']
    )
    thesis = derive_trade_thesis(
        bias='bullish',
        daily_profile='reversal',
        has_higher_timeframe_context=True,
    )
    session = build_session_lens(
        current_time=datetime(2026, 4, 3, 8, 32, tzinfo=ET),
        macro_state='Transition',
        vix=22.0,
    )
    risk = evaluate_risk_gate(entry=23846.0, stop=23695.0, target=23882.0)

    status = _derive_status(
        request=request,
        thesis=thesis,
        risk=risk,
        used_structural_memory=False,
        needs_confirmation=True,
        requires_retrace=True,
        session=session,
    )

    assert session.session_phase == 'premarket'
    assert risk.rr < 1.0
    assert status == 'WAIT'
def test_derive_status_prioritizes_severely_bad_rr_only_overnight() -> None:
    request = build_chart_request(
        ['CME_MINI_MNQ1!, 240.csv', 'CME_MINI_MNQ1!, 15.csv', 'CME_MINI_MNQ1!, 1.csv']
    )
    thesis = derive_trade_thesis(
        bias='bullish',
        daily_profile='reversal',
        has_higher_timeframe_context=True,
    )
    session = build_session_lens(
        current_time=datetime(2026, 4, 3, 1, 13, tzinfo=ET),
        macro_state='Transition',
        vix=22.0,
    )
    risk = evaluate_risk_gate(entry=23846.0, stop=23695.0, target=23882.0)

    status = _derive_status(
        request=request,
        thesis=thesis,
        risk=risk,
        used_structural_memory=False,
        needs_confirmation=True,
        requires_retrace=True,
        session=session,
    )

    assert session.session_phase == 'overnight'
    assert risk.rr < 1.0
    assert status == 'NO TRADE'

