from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.bot.main import create_analysis_bundle, create_analysis_response
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemorySnapshot, StructuralMemoryStore

ET = ZoneInfo('America/New_York')


def test_create_analysis_response_for_multi_chart_request(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    response = create_analysis_response(
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

    assert 'Status: LIVE SETUP' in response
    assert 'Bias: bullish' in response
    assert 'Bundle Profile: execution' in response
    assert 'Macro State: Risk-Off' in response
    assert 'TP1: 20035' in response


def test_create_analysis_bundle_returns_snapshot_and_rendered_output(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    bundle = create_analysis_bundle(
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

    assert bundle.snapshot.status == 'LIVE SETUP'
    assert 'Status: LIVE SETUP' in bundle.output


def test_create_analysis_response_for_single_chart_reuses_memory(tmp_path: Path) -> None:
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
        )
    )

    response = create_analysis_response(
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

    assert 'Bias: bullish' in response
    assert 'Daily Profile: continuation' in response
    assert 'Active Windows: london_close_macro' in response
