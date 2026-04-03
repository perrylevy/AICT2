from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from aict2.analysis.analysis_service import build_analysis_snapshot
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore

ET = ZoneInfo('America/New_York')
DOWNLOADS = Path(r'C:\Users\Psus\Downloads')


def _memory_store(tmp_path: Path) -> StructuralMemoryStore:
    context_store = ContextStore(tmp_path / 'aict2.db')
    context_store.initialize()
    return StructuralMemoryStore(context_store)


def _existing_paths(paths: list[Path]) -> list[str]:
    missing = [path for path in paths if not path.exists()]
    if missing:
        pytest.skip(f'Missing regression fixture(s): {missing}')
    return [str(path) for path in paths]


def test_regression_2026_04_02_0957_waits_on_timeframe_conflict(tmp_path: Path) -> None:
    file_paths = _existing_paths(
        [
            DOWNLOADS / 'CME_MINI_MNQ1!, 1D (1).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 60 (1).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 5 (1).csv',
        ]
    )
    file_names = [Path(path).name for path in file_paths]

    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=datetime(2026, 4, 2, 9, 57, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.status == 'WAIT'


def test_regression_2026_04_01_1002_waits_on_unconfirmed_reversal(tmp_path: Path) -> None:
    file_paths = _existing_paths(
        [
            DOWNLOADS / 'CME_MINI_MNQ1!, 240.csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 15.csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 1 (7).csv',
        ]
    )
    file_names = [Path(path).name for path in file_paths]

    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=datetime(2026, 4, 1, 10, 2, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.status == 'WAIT'


def test_regression_2026_03_25_0832_waits_on_conflicted_judas_setup(tmp_path: Path) -> None:
    file_paths = _existing_paths(
        [
            DOWNLOADS / 'CME_MINI_MNQ1!, 1D (4) (1).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 60 (5) (1).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 5 (6) (1).csv',
        ]
    )
    file_names = [Path(path).name for path in file_paths]

    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=datetime(2026, 3, 25, 8, 32, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.status == 'WAIT'


def test_regression_2026_03_25_1000_flags_bearish_execution_setup(tmp_path: Path) -> None:
    file_paths = _existing_paths(
        [
            DOWNLOADS / 'CME_MINI_MNQ1!, 240 (1) (1).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 15 (1) (1).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 1 (3) (1).csv',
        ]
    )
    file_names = [Path(path).name for path in file_paths]

    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=datetime(2026, 3, 25, 10, 0, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.thesis.state == 'bearish'
    assert snapshot.status in {'LIVE SETUP', 'WAIT'}


def test_regression_2026_03_26_1014_waits_for_bearish_reengagement(tmp_path: Path) -> None:
    file_paths = _existing_paths(
        [
            DOWNLOADS / 'CME_MINI_MNQ1!, 240 (2).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 15 (2).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 1 (4) (1).csv',
        ]
    )
    file_names = [Path(path).name for path in file_paths]

    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=datetime(2026, 3, 26, 10, 14, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.status == 'WAIT'


def test_regression_2026_03_27_0956_stays_bearish_after_distribution_confirms(
    tmp_path: Path,
) -> None:
    file_paths = _existing_paths(
        [
            DOWNLOADS / 'CME_MINI_MNQ1!, 1D (1) (2).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 60 (4).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 5 (3).csv',
        ]
    )
    file_names = [Path(path).name for path in file_paths]

    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=datetime(2026, 3, 27, 9, 56, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.thesis.state == 'bearish'
    assert snapshot.status in {'LIVE SETUP', 'WAIT'}


def test_regression_2026_03_25_1442_waits_late_in_conflicted_retracement(tmp_path: Path) -> None:
    file_paths = _existing_paths(
        [
            DOWNLOADS / 'CME_MINI_MNQ1!, 1D (9).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 60 (3).csv',
            DOWNLOADS / 'CME_MINI_MNQ1!, 5 (10).csv',
        ]
    )
    file_names = [Path(path).name for path in file_paths]

    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=datetime(2026, 3, 25, 14, 42, tzinfo=ET),
        macro_state='Mixed',
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.status == 'WAIT'
