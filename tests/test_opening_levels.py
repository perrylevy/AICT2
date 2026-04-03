from __future__ import annotations

from pathlib import Path

from aict2.analysis.market_frame import load_chart_frames
from aict2.analysis.opening_levels import derive_opening_levels_summary
from aict2.io.filename_parsing import parse_chart_file_name


def _write_chart(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def test_derive_opening_levels_summary_includes_key_opens(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-30T00:00:00-04:00", 23900.0, 24000.0, 23880.0, 23960.0),
            ("2026-03-31T00:00:00-04:00", 23960.0, 24020.0, 23920.0, 23980.0),
            ("2026-04-01T00:00:00-04:00", 24050.0, 24110.0, 24000.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24120.0, 24210.0, 24090.0, 24180.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-01T18:00:00-04:00", 24080.0, 24095.0, 24060.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24110.0, 24120.0, 24100.0, 24115.0),
            ("2026-04-02T09:30:00-04:00", 24160.0, 24190.0, 24155.0, 24185.0),
            ("2026-04-02T10:00:00-04:00", 24185.0, 24210.0, 24180.0, 24205.0),
        ],
    )

    frames = load_chart_frames([str(chart_daily), str(chart_5)], parse_chart_file_name)
    summary = derive_opening_levels_summary(frames, bias="bullish")

    assert "Weekly Open" in summary.public_summary
    assert "Monthly Open" in summary.public_summary
    assert "Quarterly Open" in summary.internal_summary
    assert "True Day Open" in summary.public_summary
    assert "Midnight Open" in summary.public_summary
    assert "RTH Open" in summary.public_summary


def test_derive_opening_levels_summary_reports_support_or_conflict(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-30T00:00:00-04:00", 23900.0, 24000.0, 23880.0, 23960.0),
            ("2026-03-31T00:00:00-04:00", 23960.0, 24020.0, 23920.0, 23980.0),
            ("2026-04-01T00:00:00-04:00", 24050.0, 24110.0, 24000.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24120.0, 24210.0, 24090.0, 24180.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-01T18:00:00-04:00", 24080.0, 24095.0, 24060.0, 24070.0),
            ("2026-04-02T00:00:00-04:00", 24060.0, 24065.0, 24020.0, 24030.0),
            ("2026-04-02T09:30:00-04:00", 24020.0, 24030.0, 23990.0, 24000.0),
            ("2026-04-02T10:00:00-04:00", 24000.0, 24005.0, 23970.0, 23980.0),
        ],
    )

    frames = load_chart_frames([str(chart_daily), str(chart_5)], parse_chart_file_name)
    summary = derive_opening_levels_summary(frames, bias="bullish")

    assert "conflict" in summary.confluence.lower() or "neutral" in summary.confluence.lower()


def test_derive_opening_levels_summary_hides_stale_monthly_open_from_public_output(
    tmp_path: Path,
) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-30T00:00:00-04:00", 23900.0, 24000.0, 23880.0, 23960.0),
            ("2026-03-31T00:00:00-04:00", 23960.0, 24020.0, 23920.0, 23980.0),
            ("2026-04-01T00:00:00-04:00", 8376.25, 24110.0, 24000.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24120.0, 24210.0, 24090.0, 24180.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-01T18:00:00-04:00", 24080.0, 24095.0, 24060.0, 24090.0),
            ("2026-04-02T00:00:00-04:00", 24110.0, 24120.0, 24100.0, 24115.0),
            ("2026-04-02T09:30:00-04:00", 24160.0, 24190.0, 24155.0, 24185.0),
            ("2026-04-02T10:00:00-04:00", 24185.0, 24210.0, 24180.0, 24205.0),
        ],
    )

    frames = load_chart_frames([str(chart_daily), str(chart_5)], parse_chart_file_name)
    summary = derive_opening_levels_summary(frames, bias="bullish")

    assert "Monthly Open" not in summary.public_summary
    assert "Monthly Open" in summary.internal_summary
