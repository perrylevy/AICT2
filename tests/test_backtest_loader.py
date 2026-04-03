from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aict2.backtest.loader as loader_module
from aict2.backtest.loader import discover_backtest_cases

ET = ZoneInfo("America/New_York")


def _write_csv(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def test_discover_backtest_cases_reads_three_chart_bundle(tmp_path: Path) -> None:
    case = tmp_path / "2026-03-25-0832"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()

    _write_csv(
        analysis / "CME_MINI_MNQ1!, 1D.csv",
        [("2026-03-24T16:00:00-04:00", 20000, 20100, 19950, 20080)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 60.csv",
        [("2026-03-25T08:00:00-04:00", 20040, 20060, 20010, 20020)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 5.csv",
        [("2026-03-25T08:30:00-04:00", 20015, 20018, 20005, 20010)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 1.csv",
        [("2026-03-25T08:31:00-04:00", 20010, 20012, 20000, 20008)],
    )

    cases = discover_backtest_cases(tmp_path)

    assert len(cases) == 1
    discovered = cases[0]
    assert discovered.case_id == "2026-03-25-0832"
    assert discovered.instrument == "MNQ1!"
    assert discovered.ordered_timeframes == ("Daily", "1H", "5M")
    assert discovered.execution_timeframe == "5M"
    assert discovered.analysis_timestamp == datetime(2026, 3, 25, 8, 30, tzinfo=ET)
    assert discovered.validation_error is None


def test_discover_backtest_cases_reads_single_chart_bundle(tmp_path: Path) -> None:
    case = tmp_path / "2026-04-02-1000"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()

    _write_csv(
        analysis / "CME_MINI_MNQ1!, 5.csv",
        [("2026-04-02T10:00:00-04:00", 20100, 20105, 20095, 20102)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 1.csv",
        [("2026-04-02T10:01:00-04:00", 20102, 20106, 20100, 20105)],
    )

    cases = discover_backtest_cases(tmp_path)

    assert len(cases) == 1
    discovered = cases[0]
    assert discovered.ordered_timeframes == ("5M",)
    assert discovered.execution_timeframe == "5M"
    assert discovered.analysis_timestamp == datetime(2026, 4, 2, 10, 0, tzinfo=ET)
    assert discovered.validation_error is None


def test_discover_backtest_cases_parses_score_filename(tmp_path: Path, monkeypatch) -> None:
    case = tmp_path / "2026-04-02-1000"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()

    _write_csv(
        analysis / "CME_MINI_MNQ1!, 5.csv",
        [("2026-04-02T10:00:00-04:00", 20100, 20105, 20095, 20102)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 1.csv",
        [("2026-04-02T10:01:00-04:00", 20102, 20106, 20100, 20105)],
    )

    parsed_names: list[str] = []
    original_parse = loader_module.parse_chart_file_name

    def wrapped_parse_chart_file_name(file_name: str):
        parsed_names.append(file_name)
        return original_parse(file_name)

    monkeypatch.setattr(loader_module, "parse_chart_file_name", wrapped_parse_chart_file_name)

    discover_backtest_cases(tmp_path)

    assert "CME_MINI_MNQ1!, 1.csv" in parsed_names


def test_discover_backtest_cases_reads_score_csv_content(
    tmp_path: Path, monkeypatch
) -> None:
    case = tmp_path / "2026-04-02-1000"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()

    _write_csv(
        analysis / "CME_MINI_MNQ1!, 5.csv",
        [("2026-04-02T10:00:00-04:00", 20100, 20105, 20095, 20102)],
    )
    score_path = score / "CME_MINI_MNQ1!, 1.csv"
    _write_csv(
        score_path,
        [("2026-04-02T10:01:00-04:00", 20102, 20106, 20100, 20105)],
    )

    called_paths: list[Path] = []
    original_read_csv = loader_module.pd.read_csv

    def wrapped_read_csv(path, *args, **kwargs):
        called_paths.append(Path(path))
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(loader_module.pd, "read_csv", wrapped_read_csv)

    discover_backtest_cases(tmp_path)

    assert score_path in called_paths


def test_discover_backtest_cases_marks_missing_score_folder_invalid(tmp_path: Path) -> None:
    case = tmp_path / "missing-score"
    analysis = case / "analysis"
    analysis.mkdir(parents=True)
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 5.csv",
        [("2026-04-02T10:00:00-04:00", 20100, 20105, 20095, 20102)],
    )

    cases = discover_backtest_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0].validation_error == "Missing score directory"


def test_discover_backtest_cases_marks_multiple_score_csvs_invalid(tmp_path: Path) -> None:
    case = tmp_path / "many-score-files"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 5.csv",
        [("2026-04-02T10:00:00-04:00", 20100, 20105, 20095, 20102)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 1.csv",
        [("2026-04-02T10:01:00-04:00", 20102, 20106, 20100, 20105)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 1 (1).csv",
        [("2026-04-02T10:02:00-04:00", 20105, 20107, 20101, 20106)],
    )

    cases = discover_backtest_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0].validation_error == "Expected exactly one score CSV"


def test_discover_backtest_cases_rejects_non_one_minute_score_chart(tmp_path: Path) -> None:
    case = tmp_path / "bad-score-timeframe"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 240.csv",
        [("2026-04-02T08:00:00-04:00", 20000, 20020, 19980, 20010)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 15.csv",
        [("2026-04-02T09:45:00-04:00", 20010, 20014, 20000, 20012)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 1.csv",
        [("2026-04-02T09:59:00-04:00", 20012, 20013, 20008, 20010)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 5.csv",
        [("2026-04-02T10:00:00-04:00", 20010, 20015, 20005, 20012)],
    )

    cases = discover_backtest_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0].validation_error == "Score chart must be 1M"


def test_discover_backtest_cases_uses_execution_chart_timestamp_for_4h_15m_1m_bundle(
    tmp_path: Path,
) -> None:
    case = tmp_path / "2026-04-02-0959"
    analysis = case / "analysis"
    score = case / "score"
    analysis.mkdir(parents=True)
    score.mkdir()

    _write_csv(
        analysis / "CME_MINI_MNQ1!, 240.csv",
        [("2026-04-02T08:00:00-04:00", 20000, 20020, 19980, 20010)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 15.csv",
        [("2026-04-02T09:45:00-04:00", 20010, 20014, 20000, 20012)],
    )
    _write_csv(
        analysis / "CME_MINI_MNQ1!, 1.csv",
        [("2026-04-02T09:59:00-04:00", 20012, 20013, 20008, 20010)],
    )
    _write_csv(
        score / "CME_MINI_MNQ1!, 1.csv",
        [("2026-04-02T10:00:00-04:00", 20010, 20015, 20005, 20012)],
    )

    cases = discover_backtest_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0].execution_timeframe == "1M"
    assert cases[0].analysis_timestamp == datetime(2026, 4, 2, 9, 59, tzinfo=ET)
