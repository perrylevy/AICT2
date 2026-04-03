from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.bot.execution import execute_routed_message
from aict2.bot.router import RoutedMessage
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore
from aict2.reporting.analysis_records import AnalysisRecord, AnalysisRecordStore

ET = ZoneInfo('America/New_York')


def _write_csv(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "Time,Open,High,Low,Close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def test_execute_routed_message_analyze_upload_records_analysis(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    routed = RoutedMessage(
        action='analyze_upload',
        channel_name='aict2',
        content='',
        attachment_names=(
            'CME_MINI_MNQ1!, 15.csv',
            'CME_MINI_MNQ1!, 5.csv',
            'CME_MINI_MNQ1!, 1.csv',
        ),
    )

    response = execute_routed_message(
        routed_message=routed,
        message_id='msg-1',
        current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        macro_state='Risk-Off',
        vix=22.4,
        bias='bullish',
        daily_profile='continuation',
        entry=20000,
        stop=19990,
        target=20035,
        memory_store=memory_store,
        record_store=record_store,
    )

    assert 'Status: LIVE SETUP' in response
    stored = record_store.get_analysis('msg-1')
    assert stored is not None
    assert stored.instrument == 'MNQ1!'
    assert stored.status == 'LIVE SETUP'


def test_execute_routed_message_accuracy_report_uses_record_store(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    record_store.record_analysis(
        AnalysisRecord(
            message_id='msg-1',
            instrument='MNQ1!',
            status='LIVE SETUP',
            direction='LONG',
            confidence=65,
            outcome='TP_HIT',
            score=1.0,
            analyzed_at='2026-04-02T09:55:00-04:00',
            entry=20000.0,
            stop=19990.0,
            target=20035.0,
        )
    )
    routed = RoutedMessage(
        action='accuracy_report',
        channel_name='aict2',
        content='!accuracy report',
        attachment_names=(),
    )

    response = execute_routed_message(
        routed_message=routed,
        message_id='report-1',
        current_time=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=20000,
        stop=19990,
        target=20025,
        memory_store=memory_store,
        record_store=record_store,
    )

    assert 'Total analyses: 1' in response
    assert 'Scored: 1' in response


def test_execute_routed_message_scoredata_updates_matching_pending_trade(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    record_store.record_analysis(
        AnalysisRecord(
            message_id='msg-1',
            instrument='MNQ1!',
            status='LIVE SETUP',
            direction='LONG',
            confidence=65,
            outcome=None,
            score=None,
            analyzed_at='2026-04-02T09:55:00-04:00',
            entry=20000.0,
            stop=19990.0,
            target=20035.0,
        )
    )
    csv_path = tmp_path / 'CME_MINI_MNQ1!, 1.csv'
    _write_csv(
        csv_path,
        [
            ('2026-04-02T13:56:00Z', 20002, 20004, 19998, 20001),
            ('2026-04-02T13:57:00Z', 20001, 20036, 19999, 20030),
        ],
    )
    routed = RoutedMessage(
        action='scoredata',
        channel_name='aict2',
        content='!scoredata',
        attachment_names=('CME_MINI_MNQ1!, 1.csv',),
        attachment_paths=(str(csv_path),),
    )

    response = execute_routed_message(
        routed_message=routed,
        message_id='score-1',
        current_time=datetime(2026, 4, 2, 10, 30, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0,
        stop=0,
        target=0,
        memory_store=memory_store,
        record_store=record_store,
    )

    updated = record_store.get_analysis('msg-1')

    assert 'Scored 1 analysis(es)' in response
    assert 'TP_HIT' in response
    assert updated is not None
    assert updated.outcome == 'TP_HIT'
    assert updated.score == 1.0
