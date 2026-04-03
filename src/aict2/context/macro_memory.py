from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from aict2.context.store import ContextStore


@dataclass(frozen=True, slots=True)
class MacroSnapshot:
    macro_state: str
    vix: float
    volatility_regime: str
    event_risk: str
    override_reason: str | None


class MacroSnapshotStore:
    def __init__(self, context_store: ContextStore) -> None:
        self._context_store = context_store
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._context_store.db_path)

    def _ensure_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS macro_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    macro_state TEXT NOT NULL,
                    vix REAL NOT NULL,
                    volatility_regime TEXT NOT NULL,
                    event_risk TEXT NOT NULL,
                    override_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def save_latest(self, snapshot: MacroSnapshot) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO macro_snapshots (
                    macro_state,
                    vix,
                    volatility_regime,
                    event_risk,
                    override_reason
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot.macro_state,
                    snapshot.vix,
                    snapshot.volatility_regime,
                    snapshot.event_risk,
                    snapshot.override_reason,
                ),
            )
            connection.commit()

    def load_latest(self) -> MacroSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT macro_state, vix, volatility_regime, event_risk, override_reason
                FROM macro_snapshots
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return None

        return MacroSnapshot(
            macro_state=row[0],
            vix=row[1],
            volatility_regime=row[2],
            event_risk=row[3],
            override_reason=row[4],
        )
