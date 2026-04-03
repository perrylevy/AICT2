from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.analysis.analysis_service import build_analysis_snapshot
from aict2.analysis.mark_douglas import build_mark_douglas_verdict
from aict2.analysis.plan_writer import render_analysis_output
from aict2.analysis.risk_gate import evaluate_risk_gate
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore

ET = ZoneInfo('America/New_York')


def _make_snapshot(
    tmp_path: Path,
    *,
    target: float,
    bias: str = 'bullish',
    file_names: list[str] | None = None,
):
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    return build_analysis_snapshot(
        file_names=file_names
        or [
            'CME_MINI_MNQ1!, 15.csv',
            'CME_MINI_MNQ1!, 5.csv',
            'CME_MINI_MNQ1!, 1.csv',
        ],
        current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        macro_state='Risk-Off',
        vix=22.4,
        bias=bias,
        daily_profile='continuation',
        entry=20000,
        stop=19990,
        target=target,
        memory_store=memory_store,
    )


def test_render_analysis_output_includes_v2_sections(tmp_path: Path) -> None:
    snapshot = _make_snapshot(tmp_path, target=20035)

    output = render_analysis_output(snapshot)

    assert 'Status: LIVE SETUP - Market-ready now if price respects the plan.' in output
    assert 'Trade Thesis' in output
    assert 'Entry Plan' in output
    assert 'Risk Gate' in output
    assert 'Session Awareness' in output
    assert 'Mark Douglas Verdict' in output
    assert 'TP1: 20035' in output
    assert 'Bundle Profile: execution' in output
    assert 'Entry Trigger:' in output
    assert 'Entry Mode: Market-Ready Entry' in output
    assert 'Analysis Window: Open Check (ideal)' in output
    assert 'Allowed Business: Look for Longs' in output
    assert 'Draw on Liquidity:' in output
    assert 'HTF Reference:' in output
    assert 'Stop Run:' in output
    assert 'Confluence:' in output
    assert 'Opening Context:' in output
    assert 'Gap Context:' in output
    assert 'Session Interaction:' in output
    assert 'Session Levels:' in output
    assert 'PD Arrays:' in output
    assert 'TP Model:' in output


def test_render_analysis_output_explains_when_liquidity_caps_tp(tmp_path: Path) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20018),
        tp_model='Draw on Liquidity',
        draw_on_liquidity='PDH 20018.00',
        target_reason='External liquidity caps the trade before a full 2R expansion.',
    )

    output = render_analysis_output(snapshot)

    assert 'TP Model: Draw on Liquidity' in output
    assert 'Target Reason: External liquidity caps the trade before a full 2R expansion.' in output


def test_mark_douglas_verdict_encourages_discipline_on_valid_setup(tmp_path: Path) -> None:
    snapshot = _make_snapshot(tmp_path, target=20035)

    verdict = build_mark_douglas_verdict(snapshot)

    assert 'edge' in verdict.lower()
    assert 'predefined risk' in verdict.lower()
    assert 'take' in verdict.lower()


def test_mark_douglas_verdict_tells_you_to_stand_aside_on_no_trade(tmp_path: Path) -> None:
    snapshot = _make_snapshot(tmp_path, target=20015)

    verdict = build_mark_douglas_verdict(snapshot)

    assert snapshot.status == 'NO TRADE'
    assert 'stand aside' in verdict.lower()
    assert 'predefined risk' in verdict.lower()


def test_mark_douglas_verdict_respects_valid_wait_thesis(tmp_path: Path) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20035),
        status='WAIT',
        needs_confirmation=True,
        requires_retrace=False,
    )

    verdict = build_mark_douglas_verdict(snapshot)

    assert 'wait' in verdict.lower()
    assert 'not dismissing the idea' in verdict.lower()
    assert 'predefined risk' in verdict.lower()


def test_mark_douglas_verdict_warns_on_micro_bundle(tmp_path: Path) -> None:
    snapshot = _make_snapshot(
        tmp_path,
        target=20035,
        file_names=[
            'CME_MINI_MNQ1!, 60.csv',
            'CME_MINI_MNQ1!, 5.csv',
            'CME_MINI_MNQ1!, 30S.csv',
        ],
    )

    verdict = build_mark_douglas_verdict(snapshot)

    assert snapshot.request.bundle_profile == 'micro'
    assert 'micro' in verdict.lower()
    assert 'noise' in verdict.lower()


def test_render_analysis_output_includes_custom_bundle_caution(tmp_path: Path) -> None:
    snapshot = _make_snapshot(
        tmp_path,
        target=20035,
        file_names=[
            'CME_MINI_MNQ1!, 1D.csv',
            'CME_MINI_MNQ1!, 15.csv',
            'CME_MINI_MNQ1!, 1.csv',
        ],
    )

    output = render_analysis_output(snapshot)

    assert snapshot.request.bundle_profile == 'custom'
    assert 'Bundle Note:' in output
    assert 'custom bundle' in output.lower()


def test_render_analysis_output_calls_out_retrace_wait(tmp_path: Path) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20035),
        status='WAIT',
        requires_retrace=True,
        needs_confirmation=False,
    )

    output = render_analysis_output(snapshot)

    assert 'Status: WAIT - Stretched move, retrace needed before entry.' in output
    assert 'Setup Reason: Stretched move, retrace needed before entry.' in output
    assert 'Entry Mode: Retrace Entry' in output
    assert 'Current Posture: Waiting for retrace into the entry zone.' in output


def test_render_analysis_output_calls_out_confirmation_wait(tmp_path: Path) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20035),
        status='WAIT',
        requires_retrace=False,
        needs_confirmation=True,
    )

    output = render_analysis_output(snapshot)

    assert 'Status: WAIT - Liquidity shift not confirmed yet.' in output
    assert 'Setup Reason: Liquidity shift not confirmed yet.' in output
    assert 'Entry Mode: Confirmation Entry' in output
    assert 'Current Posture: Waiting for displacement and confirmation.' in output


def test_render_analysis_output_calls_out_watch_reason(tmp_path: Path) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20035),
        status='WATCH',
        requires_retrace=False,
        needs_confirmation=False,
    )

    output = render_analysis_output(snapshot)

    assert 'Status: WATCH - Context is useful, but execution quality is not there yet.' in output
    assert 'Setup Reason: Context is useful, but execution quality is not there yet.' in output


def test_render_analysis_output_describes_live_continuation_without_stop_run(tmp_path: Path) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20035),
        status='LIVE SETUP',
        needs_confirmation=False,
        requires_retrace=False,
        stop_run_summary='No stop run required; continuation structure is already confirmed.',
    )

    output = render_analysis_output(snapshot)

    assert 'Status: LIVE SETUP - Continuation structure is confirmed and market-ready.' in output
    assert 'Setup Reason: Continuation structure is confirmed and market-ready.' in output
    assert 'Stop Run: No stop run required; continuation structure is already confirmed.' in output
def test_render_analysis_output_hides_zero_levels_for_no_trade(tmp_path: Path) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20015),
        entry=0.0,
        stop=0.0,
        target=0.0,
    )

    output = render_analysis_output(snapshot)

    assert 'Entry: No executable levels yet' in output
    assert 'Stop: No executable levels yet' in output
    assert 'TP1: No executable levels yet' in output
    assert 'Stop Distance: Not applicable until an executable plan forms' in output
    assert 'TP Model: Awaiting executable plan' in output
    assert 'Entry: 0' not in output
    assert 'Stop: 0' not in output
    assert 'TP1: 0' not in output


def test_render_analysis_output_calls_out_when_wait_setup_is_not_executable(
    tmp_path: Path,
) -> None:
    snapshot = replace(
        _make_snapshot(tmp_path, target=20035),
        status='WAIT',
        needs_confirmation=True,
        requires_retrace=False,
        entry=24140.0,
        stop=24036.0,
        target=24347.0,
        risk=evaluate_risk_gate(entry=24140.0, stop=24036.0, target=24347.0),
    )

    output = render_analysis_output(snapshot)

    assert 'Account Fit: Not executable at the current $120 risk budget.' in output
    assert (
        'Execution Note: The idea is valid, but it needs a tighter retrace or smaller invalidation to fit the account.'
        in output
    )

