from __future__ import annotations

import sqlite3

from aict2.context.store import ContextStore
from aict2.reporting.analysis_record_model import (
    AnalysisRecord,
    row_to_analysis_dict,
    row_to_analysis_record,
)
from aict2.reporting.analysis_record_schema import (
    ANALYSIS_RECORD_COLUMNS,
    ANALYSIS_RECORD_SELECT,
    ensure_analysis_record_table,
)


class AnalysisRecordStore:
    def __init__(self, context_store: ContextStore) -> None:
        self._context_store = context_store
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._context_store.db_path)

    def _ensure_table(self) -> None:
        with self._connect() as connection:
            ensure_analysis_record_table(connection)
            connection.commit()

    def record_analysis(self, record: AnalysisRecord) -> None:
        placeholders = ', '.join('?' for _ in ANALYSIS_RECORD_COLUMNS)
        columns = ', '.join(ANALYSIS_RECORD_COLUMNS)
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT OR REPLACE INTO analysis_records ({columns})
                VALUES ({placeholders})
                """,
                (
                    record.message_id,
                    record.instrument,
                    record.status,
                    record.direction,
                    record.confidence,
                    record.outcome,
                    record.score,
                    record.analyzed_at,
                    record.entry,
                    record.stop,
                    record.target,
                ),
            )
            connection.commit()

    def score_analysis(self, message_id: str, outcome: str, score: float | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE analysis_records SET outcome = ?, score = ? WHERE message_id = ?",
                (outcome, score, message_id),
            )
            connection.commit()

    def get_analysis(self, message_id: str) -> AnalysisRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                {ANALYSIS_RECORD_SELECT}
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return row_to_analysis_record(row)

    def list_analyses(self) -> list[dict[str, object | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {ANALYSIS_RECORD_SELECT}
                ORDER BY id ASC
                """
            ).fetchall()
        return [row_to_analysis_dict(row) for row in rows]

    def list_pending_live_setups(self, instrument: str) -> list[AnalysisRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {ANALYSIS_RECORD_SELECT}
                WHERE instrument = ? AND status = 'LIVE SETUP' AND outcome IS NULL
                ORDER BY id ASC
                """,
                (instrument,),
            ).fetchall()
        return [row_to_analysis_record(row) for row in rows]
