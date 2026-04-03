from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aict2.bot.main import create_analysis_bundle
from aict2.bot.router import RoutedMessage
from aict2.context.structural_memory import StructuralMemoryStore
from aict2.reporting.accuracy_report import build_accuracy_report
from aict2.reporting.analysis_records import AnalysisRecord, AnalysisRecordStore
from aict2.reporting.scoredata import score_csv_against_records


def execute_routed_message(
    routed_message: RoutedMessage,
    message_id: str,
    current_time: datetime,
    macro_state: str,
    vix: float,
    bias: str | None,
    daily_profile: str | None,
    entry: float,
    stop: float,
    target: float,
    memory_store: StructuralMemoryStore,
    record_store: AnalysisRecordStore,
) -> str:
    if routed_message.action == 'accuracy_report':
        return build_accuracy_report(record_store.list_analyses())

    if routed_message.action == 'analyze_upload':
        bundle = create_analysis_bundle(
            file_names=list(routed_message.attachment_names),
            file_paths=list(routed_message.attachment_paths),
            current_time=current_time,
            macro_state=macro_state,
            vix=vix,
            bias=bias,
            daily_profile=daily_profile,
            entry=entry,
            stop=stop,
            target=target,
            memory_store=memory_store,
        )
        record_store.record_analysis(
            AnalysisRecord(
                message_id=message_id,
                instrument=bundle.snapshot.instrument,
                status=bundle.snapshot.status,
                direction=(
                    'LONG'
                    if bundle.snapshot.thesis.state == 'bullish'
                    else 'SHORT'
                    if bundle.snapshot.thesis.state == 'bearish'
                    else None
                ),
                confidence=None,
                outcome=None,
                score=None,
                analyzed_at=current_time.isoformat(),
                entry=bundle.snapshot.entry,
                stop=bundle.snapshot.stop,
                target=bundle.snapshot.target,
            )
        )
        return bundle.output

    if routed_message.action == 'scoredata':
        if not routed_message.attachment_paths:
            return 'Upload a 1-minute CSV with `!scoredata`.'

        csv_path = Path(routed_message.attachment_paths[0])
        pending = record_store.list_pending_live_setups(csv_path.stem.split(',')[0].strip().split('_')[-1])
        scored = score_csv_against_records(csv_path, pending)
        if not scored:
            return f'No pending LIVE SETUP analyses matched {csv_path.name}.'

        lines = [f'Scored {len(scored)} analysis(es) from {csv_path.name}:']
        for result in scored:
            record_store.score_analysis(result.message_id, result.outcome, result.score)
            score_text = 'n/a' if result.score is None else f'{result.score:.2f}'
            lines.append(f'- {result.message_id}: {result.outcome} (score={score_text})')
        return '\n'.join(lines)

    return 'Unsupported action.'
