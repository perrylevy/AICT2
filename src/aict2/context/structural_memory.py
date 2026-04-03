from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from aict2.context.store import ContextStore


@dataclass(frozen=True, slots=True)
class StructuralMemorySnapshot:
    instrument: str
    thesis_state: str
    daily_profile: str
    source_timeframes: tuple[str, ...]
    lookback_days: int
    reference_context: str = ''


class StructuralMemoryStore:
    def __init__(self, context_store: ContextStore) -> None:
        self._context_store = context_store
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._context_store.db_path)

    def _ensure_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS structural_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instrument TEXT NOT NULL,
                    thesis_state TEXT NOT NULL,
                    daily_profile TEXT NOT NULL,
                    source_timeframes TEXT NOT NULL,
                    lookback_days INTEGER NOT NULL,
                    reference_context TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            existing = {
                row[1] for row in connection.execute("PRAGMA table_info(structural_memory)").fetchall()
            }
            if 'reference_context' not in existing:
                connection.execute(
                    "ALTER TABLE structural_memory ADD COLUMN reference_context TEXT NOT NULL DEFAULT ''"
                )
            connection.commit()

    def save_latest(self, snapshot: StructuralMemorySnapshot) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO structural_memory (
                    instrument,
                    thesis_state,
                    daily_profile,
                    source_timeframes,
                    lookback_days,
                    reference_context
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.instrument,
                    snapshot.thesis_state,
                    snapshot.daily_profile,
                    ','.join(snapshot.source_timeframes),
                    snapshot.lookback_days,
                    snapshot.reference_context,
                ),
            )
            connection.commit()

    def load_latest(self, instrument: str) -> StructuralMemorySnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT instrument, thesis_state, daily_profile, source_timeframes, lookback_days, reference_context
                FROM structural_memory
                WHERE instrument = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (instrument,),
            ).fetchone()

        if row is None:
            return None

        return StructuralMemorySnapshot(
            instrument=row[0],
            thesis_state=row[1],
            daily_profile=row[2],
            source_timeframes=tuple(filter(None, row[3].split(','))),
            lookback_days=row[4],
            reference_context=row[5] or '',
        )
