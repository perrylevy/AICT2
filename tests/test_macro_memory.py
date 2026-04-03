from __future__ import annotations

from pathlib import Path

from aict2.context.macro_memory import MacroSnapshot, MacroSnapshotStore
from aict2.context.store import ContextStore


def test_macro_snapshot_store_saves_and_loads_latest_snapshot(tmp_path: Path) -> None:
    store = ContextStore(tmp_path / 'aict2.db')
    store.initialize()
    macro_store = MacroSnapshotStore(store)

    macro_store.save_latest(
        MacroSnapshot(
            macro_state='Risk-Off',
            vix=22.4,
            volatility_regime='high',
            event_risk='high',
            override_reason='CPI release imminent',
        )
    )

    snapshot = macro_store.load_latest()

    assert snapshot is not None
    assert snapshot.macro_state == 'Risk-Off'
    assert snapshot.vix == 22.4
    assert snapshot.override_reason == 'CPI release imminent'
