from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from aict2.analysis.analysis_service import build_analysis_snapshot
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore
from aict2.reporting.analysis_records import AnalysisRecord
from aict2.reporting.scoredata import score_csv_against_records

ET = ZoneInfo("America/New_York")
DOWNLOADS = Path(r"C:\Users\Psus\Downloads")


@dataclass(frozen=True, slots=True)
class AnalysisAcceptanceCase:
    label: str
    timestamp: datetime
    csv_names: tuple[str, str, str]
    expected_status: str
    expected_bias: str | None = None


@dataclass(frozen=True, slots=True)
class ScoreAcceptanceCase:
    label: str
    csv_name: str
    record: AnalysisRecord
    expected_outcome: str
    expected_score: float | None


ANALYSIS_CASES = (
    AnalysisAcceptanceCase(
        label="2026-03-25 08:32 conflicted Judas short waits",
        timestamp=datetime(2026, 3, 25, 8, 32, tzinfo=ET),
        csv_names=(
            "CME_MINI_MNQ1!, 1D (4) (1).csv",
            "CME_MINI_MNQ1!, 60 (5) (1).csv",
            "CME_MINI_MNQ1!, 5 (6) (1).csv",
        ),
        expected_status="WAIT",
    ),
    AnalysisAcceptanceCase(
        label="2026-03-26 10:14 bearish reengagement still waits",
        timestamp=datetime(2026, 3, 26, 10, 14, tzinfo=ET),
        csv_names=(
            "CME_MINI_MNQ1!, 240 (2).csv",
            "CME_MINI_MNQ1!, 15 (2).csv",
            "CME_MINI_MNQ1!, 1 (4) (1).csv",
        ),
        expected_status="WAIT",
    ),
    AnalysisAcceptanceCase(
        label="2026-03-25 14:42 late retracement waits",
        timestamp=datetime(2026, 3, 25, 14, 42, tzinfo=ET),
        csv_names=(
            "CME_MINI_MNQ1!, 1D (9).csv",
            "CME_MINI_MNQ1!, 60 (3).csv",
            "CME_MINI_MNQ1!, 5 (10).csv",
        ),
        expected_status="WAIT",
    ),
    AnalysisAcceptanceCase(
        label="2026-04-01 10:02 unconfirmed reversal waits",
        timestamp=datetime(2026, 4, 1, 10, 2, tzinfo=ET),
        csv_names=(
            "CME_MINI_MNQ1!, 240.csv",
            "CME_MINI_MNQ1!, 15.csv",
            "CME_MINI_MNQ1!, 1 (7).csv",
        ),
        expected_status="WAIT",
    ),
    AnalysisAcceptanceCase(
        label="2026-04-02 09:57 timeframe conflict waits",
        timestamp=datetime(2026, 4, 2, 9, 57, tzinfo=ET),
        csv_names=(
            "CME_MINI_MNQ1!, 1D (1).csv",
            "CME_MINI_MNQ1!, 60 (1).csv",
            "CME_MINI_MNQ1!, 5 (1).csv",
        ),
        expected_status="WAIT",
    ),
)


SCORE_CASES = (
    ScoreAcceptanceCase(
        label="2026-03-25 10:00 HTF short stops out",
        csv_name="CME_MINI_MNQ1!, 1 (11).csv",
        record=AnalysisRecord(
            message_id="acceptance-0325-1000-htf",
            instrument="MNQ1!",
            status="LIVE SETUP",
            direction="SHORT",
            confidence=70,
            outcome=None,
            score=None,
            analyzed_at=datetime(2026, 3, 25, 10, 0, tzinfo=ET).isoformat(),
            entry=24403.0,
            stop=24460.0,
            target=24320.0,
        ),
        expected_outcome="SL_HIT",
        expected_score=0.0,
    ),
    ScoreAcceptanceCase(
        label="2026-03-26 10:14 HTF short never enters",
        csv_name="CME_MINI_MNQ1!, 1 (15).csv",
        record=AnalysisRecord(
            message_id="acceptance-0326-1014-htf",
            instrument="MNQ1!",
            status="LIVE SETUP",
            direction="SHORT",
            confidence=60,
            outcome=None,
            score=None,
            analyzed_at=datetime(2026, 3, 26, 10, 14, tzinfo=ET).isoformat(),
            entry=24302.0,
            stop=24380.0,
            target=24108.0,
        ),
        expected_outcome="NO_ENTRY",
        expected_score=None,
    ),
    ScoreAcceptanceCase(
        label="2026-03-27 09:56 LTF short hits TP",
        csv_name="CME_MINI_MNQ1!, 1 (4).csv",
        record=AnalysisRecord(
            message_id="acceptance-0327-0956-ltf",
            instrument="MNQ1!",
            status="LIVE SETUP",
            direction="SHORT",
            confidence=82,
            outcome=None,
            score=None,
            analyzed_at=datetime(2026, 3, 27, 9, 56, tzinfo=ET).isoformat(),
            entry=23591.0,
            stop=23656.0,
            target=23531.0,
        ),
        expected_outcome="TP_HIT",
        expected_score=1.0,
    ),
    ScoreAcceptanceCase(
        label="2026-04-02 08:44 short stops out",
        csv_name="CME_MINI_MNQ1!, 1 (14).csv",
        record=AnalysisRecord(
            message_id="acceptance-0402-0844",
            instrument="MNQ1!",
            status="LIVE SETUP",
            direction="SHORT",
            confidence=60,
            outcome=None,
            score=None,
            analyzed_at=datetime(2026, 4, 2, 8, 44, tzinfo=ET).isoformat(),
            entry=23832.8,
            stop=23858.0,
            target=23717.0,
        ),
        expected_outcome="SL_HIT",
        expected_score=0.0,
    ),
    ScoreAcceptanceCase(
        label="2026-04-02 10:15 short stops out",
        csv_name="CME_MINI_MNQ1!, 1 (14).csv",
        record=AnalysisRecord(
            message_id="acceptance-0402-1015",
            instrument="MNQ1!",
            status="LIVE SETUP",
            direction="SHORT",
            confidence=55,
            outcome=None,
            score=None,
            analyzed_at=datetime(2026, 4, 2, 10, 15, tzinfo=ET).isoformat(),
            entry=23940.0,
            stop=24000.0,
            target=23800.0,
        ),
        expected_outcome="SL_HIT",
        expected_score=0.0,
    ),
)


def _memory_store(tmp_path: Path) -> StructuralMemoryStore:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    return StructuralMemoryStore(context_store)


def _require_paths(paths: tuple[str, ...]) -> list[str]:
    full_paths = [DOWNLOADS / name for name in paths]
    missing = [path for path in full_paths if not path.exists()]
    if missing:
        pytest.skip(f"Missing historical acceptance fixtures: {missing}")
    return [str(path) for path in full_paths]


@pytest.mark.parametrize("case", ANALYSIS_CASES, ids=lambda case: case.label)
def test_historical_analysis_acceptance(tmp_path: Path, case: AnalysisAcceptanceCase) -> None:
    file_paths = _require_paths(case.csv_names)
    snapshot = build_analysis_snapshot(
        file_names=list(case.csv_names),
        file_paths=file_paths,
        current_time=case.timestamp,
        macro_state="Mixed",
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=_memory_store(tmp_path),
    )

    assert snapshot.status == case.expected_status
    if case.expected_bias is not None:
        assert snapshot.thesis.state == case.expected_bias


@pytest.mark.parametrize("case", SCORE_CASES, ids=lambda case: case.label)
def test_historical_score_acceptance(case: ScoreAcceptanceCase) -> None:
    csv_path = DOWNLOADS / case.csv_name
    if not csv_path.exists():
        pytest.skip(f"Missing historical acceptance fixture: {csv_path}")

    scored = score_csv_against_records(csv_path, [case.record])

    assert len(scored) == 1
    assert scored[0].outcome == case.expected_outcome
    assert scored[0].score == case.expected_score
