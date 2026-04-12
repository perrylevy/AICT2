from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from aict2.analysis.analysis_service import (
    _derive_status,
    build_analysis_snapshot,
    build_analysis_snapshot_from_frames,
)
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemorySnapshot, StructuralMemoryStore
from aict2.analysis.risk_gate import evaluate_risk_gate
from aict2.analysis.session_lens import build_session_lens
from aict2.analysis.trade_thesis import derive_trade_thesis
from aict2.io.chart_intake import build_chart_request

ET = ZoneInfo('America/New_York')


def _write_chart(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        'time,open,high,low,close\n'
        + '\n'.join(
            f'{timestamp},{open_},{high},{low},{close}'
            for timestamp, open_, high, low, close in rows
        ),
        encoding='utf-8',
    )


def _tradingview_frame(
    rows: list[tuple[str, float, float, float, float, int]]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            'time': [row[0] for row in rows],
            'open': [row[1] for row in rows],
            'high': [row[2] for row in rows],
            'low': [row[3] for row in rows],
            'close': [row[4] for row in rows],
            'volume': [row[5] for row in rows],
        }
    )


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


def test_build_analysis_snapshot_from_frames_matches_file_based_parity(
    tmp_path: Path,
) -> None:
    chart_15 = tmp_path / 'CME_MINI_MNQ1!, 15.csv'
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'
    chart_1 = tmp_path / 'CME_MINI_MNQ1!, 1.csv'

    _write_chart(
        chart_15,
        [
            ('2026-04-01T00:00:00-04:00', 19940.0, 20010.0, 19920.0, 19988.0),
            ('2026-04-02T00:00:00-04:00', 19988.0, 20042.0, 19970.0, 20018.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ('2026-04-02T09:30:00-04:00', 20000.0, 20008.0, 19996.0, 20005.0),
            ('2026-04-02T09:35:00-04:00', 20005.0, 20018.0, 20003.0, 20015.0),
            ('2026-04-02T09:40:00-04:00', 20015.0, 20028.0, 20012.0, 20024.0),
            ('2026-04-02T09:45:00-04:00', 20024.0, 20040.0, 20020.0, 20036.0),
        ],
    )
    _write_chart(
        chart_1,
        [
            ('2026-04-02T09:30:00-04:00', 20000.0, 20009.0, 19997.0, 20006.0),
            ('2026-04-02T09:31:00-04:00', 20006.0, 20012.0, 20004.0, 20010.0),
            ('2026-04-02T09:32:00-04:00', 20010.0, 20016.0, 20008.0, 20014.0),
            ('2026-04-02T09:33:00-04:00', 20014.0, 20022.0, 20012.0, 20020.0),
            ('2026-04-02T09:34:00-04:00', 20020.0, 20030.0, 20018.0, 20028.0),
            ('2026-04-02T09:35:00-04:00', 20028.0, 20036.0, 20024.0, 20034.0),
            ('2026-04-02T09:36:00-04:00', 20034.0, 20042.0, 20030.0, 20040.0),
            ('2026-04-02T09:37:00-04:00', 20040.0, 20046.0, 20036.0, 20044.0),
            ('2026-04-02T09:38:00-04:00', 20044.0, 20050.0, 20040.0, 20048.0),
            ('2026-04-02T09:39:00-04:00', 20048.0, 20056.0, 20044.0, 20052.0),
        ],
    )

    file_context_store = ContextStore(tmp_path / 'files.db')
    file_context_store.initialize()
    file_memory_store = StructuralMemoryStore(file_context_store)
    frame_context_store = ContextStore(tmp_path / 'frames.db')
    frame_context_store.initialize()
    frame_memory_store = StructuralMemoryStore(frame_context_store)

    file_based = build_analysis_snapshot(
        file_names=[
            chart_15.name,
            chart_5.name,
            chart_1.name,
        ],
        file_paths=[str(chart_15), str(chart_5), str(chart_1)],
        current_time=datetime(2026, 4, 2, 9, 40, tzinfo=ET),
        macro_state='Risk-On',
        vix=17.8,
        bias='bullish',
        daily_profile='continuation',
        entry=20000.0,
        stop=19990.0,
        target=20020.0,
        memory_store=file_memory_store,
    )

    frame_based = build_analysis_snapshot_from_frames(
        instrument='MNQ1!',
        analysis_frames={
            '15M': _tradingview_frame(
                [
                    ('2026-04-01T00:00:00-04:00', 19940.0, 20010.0, 19920.0, 19988.0, 2200),
                    ('2026-04-02T00:00:00-04:00', 19988.0, 20042.0, 19970.0, 20018.0, 2450),
                ]
            ),
            '5M': _tradingview_frame(
                [
                    ('2026-04-02T09:30:00-04:00', 20000.0, 20008.0, 19996.0, 20005.0, 5100),
                    ('2026-04-02T09:35:00-04:00', 20005.0, 20018.0, 20003.0, 20015.0, 4875),
                    ('2026-04-02T09:40:00-04:00', 20015.0, 20028.0, 20012.0, 20024.0, 5325),
                    ('2026-04-02T09:45:00-04:00', 20024.0, 20040.0, 20020.0, 20036.0, 5780),
                ]
            ),
            '1M': _tradingview_frame(
                [
                    ('2026-04-02T09:30:00-04:00', 20000.0, 20009.0, 19997.0, 20006.0, 1200),
                    ('2026-04-02T09:31:00-04:00', 20006.0, 20012.0, 20004.0, 20010.0, 1250),
                    ('2026-04-02T09:32:00-04:00', 20010.0, 20016.0, 20008.0, 20014.0, 1325),
                    ('2026-04-02T09:33:00-04:00', 20014.0, 20022.0, 20012.0, 20020.0, 1400),
                    ('2026-04-02T09:34:00-04:00', 20020.0, 20030.0, 20018.0, 20028.0, 1450),
                    ('2026-04-02T09:35:00-04:00', 20028.0, 20036.0, 20024.0, 20034.0, 1500),
                    ('2026-04-02T09:36:00-04:00', 20034.0, 20042.0, 20030.0, 20040.0, 1525),
                    ('2026-04-02T09:37:00-04:00', 20040.0, 20046.0, 20036.0, 20044.0, 1550),
                    ('2026-04-02T09:38:00-04:00', 20044.0, 20050.0, 20040.0, 20048.0, 1600),
                    ('2026-04-02T09:39:00-04:00', 20048.0, 20056.0, 20044.0, 20052.0, 1625),
                ]
            ),
        },
        current_time=datetime(2026, 4, 2, 9, 40, tzinfo=ET),
        macro_state='Risk-On',
        vix=17.8,
        bias='bullish',
        daily_profile='continuation',
        entry=20000.0,
        stop=19990.0,
        target=20020.0,
        memory_store=frame_memory_store,
    )

    assert frame_based.status == file_based.status
    assert frame_based.thesis == file_based.thesis
    assert frame_based.session == file_based.session
    assert frame_based.risk == file_based.risk
    assert frame_based.entry == file_based.entry
    assert frame_based.stop == file_based.stop
    assert frame_based.target == file_based.target
    assert frame_based.liquidity_summary == file_based.liquidity_summary
    assert frame_based.reference_context == file_based.reference_context
    assert frame_based.internal_reference_context == file_based.internal_reference_context
    assert frame_based.draw_on_liquidity == file_based.draw_on_liquidity
    assert frame_based.htf_reference == file_based.htf_reference
    assert frame_based.stop_run_summary == file_based.stop_run_summary
    assert frame_based.gap_summary == file_based.gap_summary
    assert frame_based.gap_confluence == file_based.gap_confluence
    assert frame_based.opening_summary == file_based.opening_summary
    assert frame_based.opening_confluence == file_based.opening_confluence
    assert frame_based.pd_array_summary == file_based.pd_array_summary
    assert frame_based.pd_array_confluence == file_based.pd_array_confluence
    assert frame_based.entry_model == file_based.entry_model
    assert frame_based.tp_model == file_based.tp_model
    assert frame_based.target_reason == file_based.target_reason
    assert frame_based.needs_confirmation == file_based.needs_confirmation
    assert frame_based.requires_retrace == file_based.requires_retrace
    assert frame_based.session_levels == file_based.session_levels
    assert frame_based.request.instrument == file_based.request.instrument
    assert frame_based.request.mode == file_based.request.mode
    assert frame_based.request.ordered_timeframes == file_based.request.ordered_timeframes
    assert frame_based.request.execution_timeframe == file_based.request.execution_timeframe
    assert frame_based.request.has_higher_timeframe_context == file_based.request.has_higher_timeframe_context
    assert frame_based.request.bundle_profile == file_based.request.bundle_profile
    assert frame_based.request.is_canonical_bundle == file_based.request.is_canonical_bundle
    assert frame_based.request.source_files == ('MNQ1!:15M', 'MNQ1!:5M', 'MNQ1!:1M')


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


def test_derive_status_marks_mature_zero_geometry_as_no_trade() -> None:
    request = build_chart_request(
        [
            'CME_MINI_MNQ1!, 1D.csv',
            'CME_MINI_MNQ1!, 60.csv',
            'CME_MINI_MNQ1!, 5.csv',
        ]
    )
    thesis = derive_trade_thesis(
        bias='bearish',
        daily_profile='reversal',
        has_higher_timeframe_context=True,
    )
    session = build_session_lens(
        current_time=datetime(2026, 2, 13, 9, 40, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
    )
    risk = evaluate_risk_gate(entry=0.0, stop=0.0, target=0.0)

    status = _derive_status(
        request=request,
        thesis=thesis,
        risk=risk,
        used_structural_memory=False,
        needs_confirmation=False,
        requires_retrace=False,
        session=session,
        entry=0.0,
        stop=0.0,
        target=0.0,
    )

    assert status == 'NO TRADE'


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
        entry=23846.0,
        stop=23695.0,
        target=23882.0,
    )

    assert risk.rr < 1.0
    assert status == 'NO TRADE'


def test_build_analysis_snapshot_allows_aligned_reversal_ifvg_live_setup_after_confirmation_tuning(
    tmp_path: Path,
) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    chart_daily = tmp_path / 'CME_MINI_MNQ1!, 1D.csv'
    chart_1h = tmp_path / 'CME_MINI_MNQ1!, 60.csv'
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'

    _write_chart(
        chart_daily,
        [
            ('2026-03-31T00:00:00-04:00', 23960.0, 24020.0, 23920.0, 23980.0),
            ('2026-04-01T00:00:00-04:00', 24050.0, 24240.0, 24000.0, 24090.0),
            ('2026-04-02T00:00:00-04:00', 24120.0, 24210.0, 24090.0, 24180.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ('2026-04-02T07:00:00-04:00', 24080.0, 24100.0, 24040.0, 24090.0),
            ('2026-04-02T08:00:00-04:00', 24090.0, 24140.0, 24070.0, 24120.0),
            ('2026-04-02T09:00:00-04:00', 24120.0, 24200.0, 24100.0, 24190.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ('2026-04-02T09:10:00-04:00', 24080.0, 24084.0, 24074.0, 24078.0),
            ('2026-04-02T09:15:00-04:00', 24078.0, 24080.0, 24070.0, 24072.0),
            ('2026-04-02T09:20:00-04:00', 24072.0, 24074.0, 24064.0, 24066.0),
            ('2026-04-02T09:25:00-04:00', 24066.0, 24068.0, 24058.0, 24060.0),
            ('2026-04-02T09:30:00-04:00', 24060.0, 24056.0, 24050.0, 24052.0),
            ('2026-04-02T09:35:00-04:00', 24052.0, 24078.0, 24050.0, 24074.0),
            ('2026-04-02T09:40:00-04:00', 24074.0, 24108.0, 24072.0, 24092.0),
        ],
    )

    snapshot = build_analysis_snapshot(
        file_names=[chart_daily.name, chart_1h.name, chart_5.name],
        file_paths=[str(chart_daily), str(chart_1h), str(chart_5)],
        current_time=datetime(2026, 4, 2, 9, 40, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=memory_store,
    )

    assert snapshot.entry_model == '5M IFVG'
    assert snapshot.thesis.state == 'bullish'
    assert snapshot.requires_retrace is False
    assert snapshot.needs_confirmation is False
    assert snapshot.status == 'LIVE SETUP'


def test_build_analysis_snapshot_allows_mixed_htf_5m_ifvg_when_no_opposing_draw_exists(
    tmp_path: Path,
) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    chart_daily = tmp_path / 'CME_MINI_MNQ1!, 1D.csv'
    chart_1h = tmp_path / 'CME_MINI_MNQ1!, 60.csv'
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'

    _write_chart(
        chart_daily,
        [
            ('2026-03-31T00:00:00-04:00', 130.0, 148.0, 118.0, 130.0),
            ('2026-04-01T00:00:00-04:00', 130.0, 146.0, 120.0, 129.0),
            ('2026-04-02T00:00:00-04:00', 129.0, 145.0, 121.0, 131.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ('2026-04-02T07:00:00-04:00', 140.0, 144.0, 138.0, 140.0),
            ('2026-04-02T08:00:00-04:00', 140.0, 146.0, 139.0, 141.0),
            ('2026-04-02T09:00:00-04:00', 141.0, 145.0, 140.0, 141.75),
        ],
    )
    _write_chart(
        chart_5,
        [
            ('2026-04-02T09:10:00-04:00', 99.8, 100.0, 99.7, 99.9),
            ('2026-04-02T09:15:00-04:00', 99.9, 100.2, 99.8, 100.0),
            ('2026-04-02T09:20:00-04:00', 100.0, 100.5, 99.9, 100.3),
            ('2026-04-02T09:25:00-04:00', 100.3, 100.4, 99.9, 99.95),
            ('2026-04-02T09:30:00-04:00', 99.95, 100.0, 99.7, 99.8),
            ('2026-04-02T09:35:00-04:00', 99.8, 100.0, 99.75, 99.9),
            ('2026-04-02T09:40:00-04:00', 99.9, 101.0, 99.9, 100.8),
        ],
    )

    snapshot = build_analysis_snapshot(
        file_names=[chart_daily.name, chart_1h.name, chart_5.name],
        file_paths=[str(chart_daily), str(chart_1h), str(chart_5)],
        current_time=datetime(2026, 4, 2, 9, 40, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=memory_store,
    )

    assert snapshot.entry_model == '5M Confirmation'
    assert snapshot.thesis.state == 'bullish'
    assert snapshot.requires_retrace is False
    assert snapshot.needs_confirmation is False
    assert snapshot.status == 'LIVE SETUP'


def test_build_analysis_snapshot_marks_aligned_displacement_hold_scalp_as_live_setup(
    tmp_path: Path,
) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    chart_daily = tmp_path / 'CME_MINI_MNQ1!, 1D.csv'
    chart_1h = tmp_path / 'CME_MINI_MNQ1!, 60.csv'
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'

    _write_chart(
        chart_daily,
        [
            ('2026-03-31T00:00:00-04:00', 120.0, 132.0, 118.0, 130.0),
            ('2026-04-01T00:00:00-04:00', 130.0, 148.0, 128.0, 146.0),
            ('2026-04-02T00:00:00-04:00', 146.0, 155.0, 140.0, 150.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ('2026-04-02T07:00:00-04:00', 138.0, 141.0, 136.0, 140.0),
            ('2026-04-02T08:00:00-04:00', 140.0, 143.0, 139.0, 142.0),
            ('2026-04-02T09:00:00-04:00', 142.0, 146.0, 141.0, 145.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ('2026-04-02T09:10:00-04:00', 99.8, 100.0, 99.7, 99.9),
            ('2026-04-02T09:15:00-04:00', 99.9, 100.2, 99.8, 100.0),
            ('2026-04-02T09:20:00-04:00', 100.0, 100.5, 99.9, 100.3),
            ('2026-04-02T09:25:00-04:00', 100.3, 100.4, 99.9, 99.95),
            ('2026-04-02T09:30:00-04:00', 99.95, 100.0, 99.7, 99.8),
            ('2026-04-02T09:35:00-04:00', 99.8, 100.0, 99.75, 99.9),
            ('2026-04-02T09:40:00-04:00', 99.9, 101.0, 99.9, 100.8),
        ],
    )

    snapshot = build_analysis_snapshot(
        file_names=[
            chart_daily.name,
            chart_1h.name,
            chart_5.name,
        ],
        file_paths=[str(chart_daily), str(chart_1h), str(chart_5)],
        current_time=datetime(2026, 4, 2, 9, 40, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=memory_store,
    )

    assert snapshot.status == 'LIVE SETUP'
    assert snapshot.entry_model == '5M Confirmation'
    assert snapshot.entry > snapshot.stop
    assert snapshot.entry - snapshot.stop == 12.0
    assert 40.0 <= snapshot.target - snapshot.entry <= 50.0


def test_build_analysis_snapshot_waits_when_scalp_geometry_is_still_invalid(
    tmp_path: Path,
) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    chart_daily = tmp_path / 'CME_MINI_MNQ1!, 1D.csv'
    chart_1h = tmp_path / 'CME_MINI_MNQ1!, 60.csv'
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'

    _write_chart(
        chart_daily,
        [
            ('2026-02-01T00:00:00-05:00', 25520.0, 26019.0, 25180.0, 25640.0),
            ('2026-02-02T00:00:00-05:00', 25640.0, 25688.0, 25596.0, 25613.0),
        ],
    )
    _write_chart(
        chart_1h,
        [
            ('2026-02-02T08:00:00-05:00', 25505.0, 25560.0, 25495.0, 25556.0),
            ('2026-02-02T09:00:00-05:00', 25556.0, 25613.0, 25544.0, 25613.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ('2026-02-02T08:45:00-05:00', 25498.0, 25520.0, 25492.25, 25505.0),
            ('2026-02-02T08:50:00-05:00', 25505.0, 25530.0, 25498.0, 25518.0),
            ('2026-02-02T08:55:00-05:00', 25518.0, 25544.0, 25510.0, 25540.0),
            ('2026-02-02T09:00:00-05:00', 25540.0, 25552.0, 25530.0, 25536.0),
            ('2026-02-02T09:05:00-05:00', 25536.0, 25544.0, 25520.0, 25528.0),
            ('2026-02-02T09:10:00-05:00', 25528.0, 25536.0, 25514.0, 25518.0),
            ('2026-02-02T09:15:00-05:00', 25518.0, 25534.0, 25510.0, 25530.0),
            ('2026-02-02T09:20:00-05:00', 25530.0, 25548.0, 25522.0, 25542.0),
            ('2026-02-02T09:25:00-05:00', 25542.0, 25570.0, 25538.0, 25564.0),
            ('2026-02-02T09:30:00-05:00', 25564.0, 25588.0, 25542.0, 25584.0),
            ('2026-02-02T09:35:00-05:00', 25584.0, 25613.0, 25580.0, 25613.0),
            ('2026-02-02T09:40:00-05:00', 25613.0, 25616.0, 25596.0, 25613.0),
        ],
    )

    snapshot = build_analysis_snapshot(
        file_names=[
            chart_daily.name,
            chart_1h.name,
            chart_5.name,
        ],
        file_paths=[str(chart_daily), str(chart_1h), str(chart_5)],
        current_time=datetime(2026, 2, 2, 9, 40, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=memory_store,
    )

    assert snapshot.status == 'WAIT'
    assert snapshot.needs_confirmation is True
    assert snapshot.requires_retrace is True
    assert snapshot.entry > 0.0
    assert snapshot.stop > 0.0
    assert snapshot.target > 0.0
