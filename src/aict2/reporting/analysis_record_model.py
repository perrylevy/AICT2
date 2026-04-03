from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    message_id: str
    instrument: str
    status: str
    direction: str | None
    confidence: int | None
    outcome: str | None
    score: float | None
    analyzed_at: str
    entry: float | None
    stop: float | None
    target: float | None


_ROW_KEYS = (
    'message_id',
    'instrument',
    'status',
    'direction',
    'confidence',
    'outcome',
    'score',
    'analyzed_at',
    'entry',
    'stop',
    'target',
)


def row_to_analysis_record(row: tuple[object, ...]) -> AnalysisRecord:
    return AnalysisRecord(
        message_id=row[0],
        instrument=row[1],
        status=row[2],
        direction=row[3],
        confidence=row[4],
        outcome=row[5],
        score=row[6],
        analyzed_at=row[7],
        entry=row[8],
        stop=row[9],
        target=row[10],
    )


def row_to_analysis_dict(row: tuple[object, ...]) -> dict[str, object | None]:
    return dict(zip(_ROW_KEYS, row, strict=True))
