from pathlib import Path

from aict2.context.store import ContextStore
from aict2.reporting.accuracy_report import build_accuracy_report
from aict2.bot.main import main as bot_main
from aict2.macro.publisher import main as macro_main


def test_bot_main_is_callable() -> None:
    assert callable(bot_main)


def test_macro_main_is_callable() -> None:
    assert callable(macro_main)


def test_context_store_initializes_sqlite_file(tmp_path: Path) -> None:
    db_path = tmp_path / 'aict2.db'

    store = ContextStore(db_path)
    store.initialize()

    assert db_path.exists()
    assert {'analysis_context', 'macro_snapshots'}.issubset(store.table_names())


def test_build_accuracy_report_for_empty_results() -> None:
    assert build_accuracy_report([]) == 'No scored analyses yet.'
