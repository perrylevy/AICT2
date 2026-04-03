from __future__ import annotations

import sqlite3


ANALYSIS_RECORD_COLUMNS = (
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

ANALYSIS_RECORD_SELECT = """
SELECT message_id, instrument, status, direction, confidence, outcome, score,
       analyzed_at, entry, stop, target
FROM analysis_records
"""


def ensure_analysis_record_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE NOT NULL,
            instrument TEXT NOT NULL,
            status TEXT NOT NULL,
            direction TEXT,
            confidence INTEGER,
            outcome TEXT,
            score REAL,
            analyzed_at TEXT NOT NULL,
            entry REAL,
            stop REAL,
            target REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    existing = {row[1] for row in connection.execute("PRAGMA table_info(analysis_records)").fetchall()}
    missing_columns = {
        'analyzed_at': "TEXT NOT NULL DEFAULT ''",
        'entry': 'REAL',
        'stop': 'REAL',
        'target': 'REAL',
    }
    for column_name, column_sql in missing_columns.items():
        if column_name not in existing:
            connection.execute(f"ALTER TABLE analysis_records ADD COLUMN {column_name} {column_sql}")
