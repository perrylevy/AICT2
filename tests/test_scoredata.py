from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from aict2.reporting.analysis_records import AnalysisRecord
from aict2.reporting.scoredata import score_csv_against_records

ET = ZoneInfo("America/New_York")
DOWNLOADS = Path(r"C:\Users\Psus\Downloads")


def _write_csv(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "Time,Open,High,Low,Close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def test_score_csv_against_records_marks_tp_hit(tmp_path: Path) -> None:
    csv_path = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_csv(
        csv_path,
        [
            ("2026-04-02T13:56:00Z", 20002, 20004, 19998, 20001),
            ("2026-04-02T13:57:00Z", 20001, 20036, 19999, 20030),
        ],
    )
    record = AnalysisRecord(
        message_id="msg-1",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="LONG",
        confidence=65,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 4, 2, 9, 55, tzinfo=ET).isoformat(),
        entry=20000.0,
        stop=19990.0,
        target=20035.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].message_id == "msg-1"
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_records_marks_sl_hit(tmp_path: Path) -> None:
    csv_path = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_csv(
        csv_path,
        [
            ("2026-04-02T13:56:00Z", 20002, 20004, 19998, 20001),
            ("2026-04-02T13:57:00Z", 20001, 20005, 19988, 19990),
        ],
    )
    record = AnalysisRecord(
        message_id="msg-1",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="LONG",
        confidence=65,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 4, 2, 9, 55, tzinfo=ET).isoformat(),
        entry=20000.0,
        stop=19990.0,
        target=20035.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "SL_HIT"
    assert scored[0].score == 0.0


def test_score_csv_against_records_returns_no_entry_when_zone_not_touched(tmp_path: Path) -> None:
    csv_path = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_csv(
        csv_path,
        [
            ("2026-04-02T13:56:00Z", 20010, 20014, 20006, 20012),
            ("2026-04-02T14:10:00Z", 20020, 20025, 20018, 20024),
        ],
    )
    record = AnalysisRecord(
        message_id="msg-1",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="LONG",
        confidence=65,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 4, 2, 9, 55, tzinfo=ET).isoformat(),
        entry=20000.0,
        stop=19990.0,
        target=20035.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "NO_ENTRY"
    assert scored[0].score is None


def test_score_csv_against_records_supports_lowercase_tradingview_columns(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "CME_MINI_MNQ1!, 1 (7).csv"
    csv_path.write_text(
        "time,open,high,low,close\n"
        "2026-04-02T13:56:00Z,20002,20004,19998,20001\n"
        "2026-04-02T13:57:00Z,20001,20036,19999,20030\n",
        encoding="utf-8",
    )
    record = AnalysisRecord(
        message_id="msg-1",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="LONG",
        confidence=65,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 4, 2, 9, 55, tzinfo=ET).isoformat(),
        entry=20000.0,
        stop=19990.0,
        target=20035.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_records_supports_sanitized_discord_filename(tmp_path: Path) -> None:
    csv_path = tmp_path / "CME_MINI_MNQ1_1_14.csv"
    _write_csv(
        csv_path,
        [
            ("2026-04-02T13:56:00Z", 20002, 20004, 19998, 20001),
            ("2026-04-02T13:57:00Z", 20001, 20036, 19999, 20030),
        ],
    )
    record = AnalysisRecord(
        message_id="msg-sanitized",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="LONG",
        confidence=65,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 4, 2, 9, 55, tzinfo=ET).isoformat(),
        entry=20000.0,
        stop=19990.0,
        target=20035.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_real_march_25_chart_marks_no_entry() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (11).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0325-no-entry",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="SHORT",
        confidence=60,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 3, 25, 14, 42, tzinfo=ET).isoformat(),
        entry=24443.0,
        stop=24548.0,
        target=24287.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "NO_ENTRY"
    assert scored[0].score is None


def test_score_csv_against_real_march_25_chart_marks_1000_ltf_tp_hit() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (11).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0325-1000-ltf",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="SHORT",
        confidence=65,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 3, 25, 10, 0, tzinfo=ET).isoformat(),
        entry=24460.0,
        stop=24528.0,
        target=24391.7,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_real_march_25_chart_marks_1000_htf_stopout() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (11).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0325-1000-htf",
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
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "SL_HIT"
    assert scored[0].score == 0.0


def test_score_csv_against_real_march_27_chart_marks_tp_hit() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (4).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0327-tp",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="SHORT",
        confidence=75,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 3, 27, 9, 56, tzinfo=ET).isoformat(),
        entry=23609.0,
        stop=23680.0,
        target=23430.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_real_march_27_chart_marks_ltf_tp_hit() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (4).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0327-ltf-tp",
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
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_real_march_26_chart_marks_0827_htf_tp_hit() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (15).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0326-0827-htf",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="SHORT",
        confidence=75,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 3, 26, 8, 27, tzinfo=ET).isoformat(),
        entry=24209.0,
        stop=24295.0,
        target=24081.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_real_march_26_chart_marks_1014_htf_no_entry() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (15).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0326-1014-htf",
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
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "NO_ENTRY"
    assert scored[0].score is None


def test_score_csv_against_real_march_26_chart_marks_1014_ltf_tp_hit() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (15).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0326-1014-ltf",
        instrument="MNQ1!",
        status="LIVE SETUP",
        direction="SHORT",
        confidence=68,
        outcome=None,
        score=None,
        analyzed_at=datetime(2026, 3, 26, 10, 14, tzinfo=ET).isoformat(),
        entry=24193.0,
        stop=24244.0,
        target=24123.0,
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "TP_HIT"
    assert scored[0].score == 1.0


def test_score_csv_against_real_april_2_chart_marks_844_short_stopout() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (14).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0402-0844",
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
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "SL_HIT"
    assert scored[0].score == 0.0


def test_score_csv_against_real_april_2_chart_marks_1015_short_stopout() -> None:
    csv_path = DOWNLOADS / "CME_MINI_MNQ1!, 1 (14).csv"
    if not csv_path.exists():
        pytest.skip(f"Missing real score fixture: {csv_path}")

    record = AnalysisRecord(
        message_id="msg-real-0402-1015",
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
    )

    scored = score_csv_against_records(csv_path, [record])

    assert len(scored) == 1
    assert scored[0].outcome == "SL_HIT"
    assert scored[0].score == 0.0
