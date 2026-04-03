from __future__ import annotations

import sqlite3
from pathlib import Path

from aict2.context.store import ContextStore
from aict2.reporting.analysis_records import AnalysisRecordStore


def test_context_store_adds_macro_snapshot_columns_to_existing_table(tmp_path: Path) -> None:
    db_path = tmp_path / "aict2.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE macro_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                macro_state TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()

    store = ContextStore(db_path)
    store.initialize()

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("PRAGMA table_info(macro_snapshots)").fetchall()
    columns = {row[1] for row in rows}

    assert "vix" in columns
    assert "volatility_regime" in columns
    assert "event_risk" in columns
    assert "override_reason" in columns


def test_analysis_record_store_adds_scoredata_columns_to_existing_table(tmp_path: Path) -> None:
    db_path = tmp_path / "aict2.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE analysis_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL,
                instrument TEXT NOT NULL,
                status TEXT NOT NULL,
                direction TEXT,
                confidence INTEGER,
                outcome TEXT,
                score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()

    context_store = ContextStore(db_path)
    context_store.initialize()
    AnalysisRecordStore(context_store)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("PRAGMA table_info(analysis_records)").fetchall()
    columns = {row[1] for row in rows}

    assert "analyzed_at" in columns
    assert "entry" in columns
    assert "stop" in columns
    assert "target" in columns
