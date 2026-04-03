from __future__ import annotations

from pathlib import Path

from aict2.context.store import ContextStore
from aict2.reporting.accuracy_report import build_accuracy_report
from aict2.reporting.analysis_records import AnalysisRecord, AnalysisRecordStore


def test_analysis_record_store_round_trips_and_scores(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    record_store = AnalysisRecordStore(context_store)
    record = AnalysisRecord(
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

    record_store.record_analysis(record)
    record_store.score_analysis('msg-1', outcome='TP_HIT', score=1.0)
    loaded = record_store.get_analysis('msg-1')

    assert loaded is not None
    assert loaded.outcome == 'TP_HIT'
    assert loaded.score == 1.0


def test_build_accuracy_report_summarizes_scored_records() -> None:
    report = build_accuracy_report(
        [
            {
                'message_id': 'msg-1',
                'status': 'LIVE SETUP',
                'outcome': 'TP_HIT',
                'score': 1.0,
            },
            {
                'message_id': 'msg-2',
                'status': 'NO TRADE',
                'outcome': 'CORRECT_NO_TRADE',
                'score': 1.0,
            },
            {
                'message_id': 'msg-3',
                'status': 'LIVE SETUP',
                'outcome': None,
                'score': None,
            },
        ]
    )

    assert 'Total analyses: 3' in report
    assert 'Scored: 2' in report
    assert 'Average score: 1.00' in report
