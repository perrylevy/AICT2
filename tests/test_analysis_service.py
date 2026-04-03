from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.analysis.analysis_service import _derive_status, build_analysis_snapshot
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemorySnapshot, StructuralMemoryStore
from aict2.analysis.risk_gate import evaluate_risk_gate
from aict2.analysis.session_lens import build_session_lens
from aict2.analysis.trade_thesis import derive_trade_thesis
from aict2.io.chart_intake import build_chart_request

ET = ZoneInfo('America/New_York')


def test_build_analysis_snapshot_for_multi_chart_setup_saves_memory(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    snapshot = build_analysis_snapshot(
        file_names=[
            'CME_MINI_MNQ1!, 15.csv',
            'CME_MINI_MNQ1!, 5.csv',
            'CME_MINI_MNQ1!, 1.csv',
        ],
        current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        macro_state='Risk-Off',
        vix=22.4,
        bias='bullish',
        daily_profile='continuation',
        entry=20000,
        stop=19990,
        target=20035,
        memory_store=memory_store,
    )

    assert snapshot.instrument == 'MNQ1!'
    assert snapshot.status == 'LIVE SETUP'
    assert snapshot.thesis.allowed_business == 'long_only'
    assert snapshot.session.active_windows == ('ny_open_macro',)
    assert snapshot.used_structural_memory is False

    stored = memory_store.load_latest('MNQ1!')
    assert stored == StructuralMemorySnapshot(
        instrument='MNQ1!',
        thesis_state='bullish',
        daily_profile='continuation',
        source_timeframes=('15M', '5M', '1M'),
        lookback_days=20,
        reference_context='Using latest uploaded higher-timeframe structure only',
    )


def test_build_analysis_snapshot_for_single_chart_reuses_memory_context(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    memory_store.save_latest(
        StructuralMemorySnapshot(
            instrument='MNQ1!',
            thesis_state='bullish',
            daily_profile='continuation',
            source_timeframes=('15M', '5M', '1M'),
            lookback_days=20,
            reference_context='PDH 20050.00 / PDL 19880.00',
        )
    )

    snapshot = build_analysis_snapshot(
        file_names=['CME_MINI_MNQ1!, 1.csv'],
        current_time=datetime(2026, 4, 2, 10, 55, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=20000,
        stop=19990,
        target=20025,
        memory_store=memory_store,
    )

    assert snapshot.used_structural_memory is True
    assert snapshot.thesis.state == 'bullish'
    assert snapshot.thesis.daily_profile == 'continuation'
    assert snapshot.reference_context == 'PDH 20050.00 / PDL 19880.00'
    assert snapshot.session.active_windows == ('london_close_macro',)
    assert snapshot.status == 'LIVE SETUP'


def test_build_analysis_snapshot_blocks_low_rr_setup(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    snapshot = build_analysis_snapshot(
        file_names=[
            'CME_MINI_MNQ1!, 15.csv',
            'CME_MINI_MNQ1!, 5.csv',
            'CME_MINI_MNQ1!, 1.csv',
        ],
        current_time=datetime(2026, 4, 2, 9, 40, tzinfo=ET),
        macro_state='Risk-On',
        vix=17.5,
        bias='bullish',
        daily_profile='continuation',
        entry=20000,
        stop=19990,
        target=20015,
        memory_store=memory_store,
    )

    assert snapshot.risk.clears_min_rr is False
    assert snapshot.status == 'NO TRADE'


def test_build_analysis_snapshot_marks_mixed_bias_as_wait(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    snapshot = build_analysis_snapshot(
        file_names=[
            'CME_MINI_MNQ1!, 15.csv',
            'CME_MINI_MNQ1!, 5.csv',
            'CME_MINI_MNQ1!, 1.csv',
        ],
        current_time=datetime(2026, 4, 2, 10, 2, tzinfo=ET),
        macro_state='Mixed',
        vix=19.2,
        bias='mixed',
        daily_profile='transition',
        entry=20000,
        stop=19990,
        target=20020,
        memory_store=memory_store,
    )

    assert snapshot.risk.clears_min_rr is True
    assert snapshot.status == 'WAIT'
    assert snapshot.needs_confirmation is False
    assert snapshot.requires_retrace is False


def test_build_analysis_snapshot_marks_single_chart_without_memory_as_watch(
    tmp_path: Path,
) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    snapshot = build_analysis_snapshot(
        file_names=['CME_MINI_MNQ1!, 1.csv'],
        current_time=datetime(2026, 4, 2, 10, 55, tzinfo=ET),
        macro_state='Risk-On',
        vix=17.8,
        bias='bullish',
        daily_profile='continuation',
        entry=20000,
        stop=19990,
        target=20025,
        memory_store=memory_store,
    )

    assert snapshot.used_structural_memory is False
    assert snapshot.status == 'WATCH'


def test_build_analysis_snapshot_marks_noncanonical_multi_chart_as_watch(
    tmp_path: Path,
) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    snapshot = build_analysis_snapshot(
        file_names=[
            'CME_MINI_MNQ1!, 1D.csv',
            'CME_MINI_MNQ1!, 15.csv',
            'CME_MINI_MNQ1!, 1.csv',
        ],
        current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        macro_state='Risk-On',
        vix=18.4,
        bias='bullish',
        daily_profile='continuation',
        entry=20000,
        stop=19990,
        target=20025,
        memory_store=memory_store,
    )

    assert snapshot.request.is_canonical_bundle is False
    assert snapshot.status == 'WATCH'


def test_build_analysis_snapshot_tracks_retrace_requirement_from_chart_plan(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'
    chart_5.write_text(
        '\n'.join(
            [
                'time,open,high,low,close',
                '2026-04-02T09:30:00-04:00,100.0,100.5,99.8,100.4',
                '2026-04-02T09:35:00-04:00,100.4,100.9,100.3,100.8',
                '2026-04-02T09:40:00-04:00,100.8,101.2,100.7,101.1',
                '2026-04-02T09:45:00-04:00,101.1,101.8,101.0,101.7',
                '2026-04-02T09:50:00-04:00,101.7,102.4,101.6,102.3',
                '2026-04-02T09:55:00-04:00,102.3,103.0,102.2,102.9',
                '2026-04-02T10:00:00-04:00,102.9,103.8,102.8,103.7',
            ]
        ),
        encoding='utf-8',
    )

    snapshot = build_analysis_snapshot(
        file_names=[chart_5.name],
        file_paths=[str(chart_5)],
        current_time=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
        macro_state='Mixed',
        vix=18.5,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=memory_store,
    )

    assert snapshot.requires_retrace is True
    assert snapshot.status == 'WATCH'


def test_derive_status_prioritizes_severely_bad_rr_over_wait_conditions() -> None:
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

    assert risk.rr < 1.0
    assert status == 'NO TRADE'
