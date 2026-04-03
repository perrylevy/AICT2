from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ContextStore:
    db_path: Path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_columns(self, table_name: str, columns: dict[str, str]) -> None:
        with self._connect() as connection:
            existing = {
                row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, column_sql in columns.items():
                if column_name not in existing:
                    connection.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
                    )
            connection.commit()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_context (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS macro_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    macro_state TEXT NOT NULL,
                    vix REAL NOT NULL DEFAULT 18.0,
                    volatility_regime TEXT NOT NULL DEFAULT 'normal',
                    event_risk TEXT NOT NULL DEFAULT 'normal',
                    override_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()
        self._ensure_columns(
            'macro_snapshots',
            {
                'vix': "REAL NOT NULL DEFAULT 18.0",
                'volatility_regime': "TEXT NOT NULL DEFAULT 'normal'",
                'event_risk': "TEXT NOT NULL DEFAULT 'normal'",
                'override_reason': 'TEXT',
            },
        )

    def table_names(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        return {row[0] for row in rows}
