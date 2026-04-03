from __future__ import annotations

from pathlib import Path

from aict2.analysis.gap_levels import derive_gap_confluence, derive_gap_summary
from aict2.analysis.market_frame import load_chart_frames
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


def test_derive_gap_summary_detects_active_ndog_and_nwog(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-16T00:00:00-04:00", 23920.0, 23980.0, 23880.0, 23910.0),
            ("2026-03-17T00:00:00-04:00", 23910.0, 23960.0, 23890.0, 23940.0),
            ("2026-03-18T00:00:00-04:00", 23940.0, 23990.0, 23910.0, 23970.0),
            ("2026-03-19T00:00:00-04:00", 23970.0, 24010.0, 23930.0, 23980.0),
            ("2026-03-20T00:00:00-04:00", 23980.0, 24030.0, 23960.0, 24000.0),
            ("2026-03-23T00:00:00-04:00", 24120.0, 24240.0, 24090.0, 24190.0),
            ("2026-03-24T00:00:00-04:00", 24220.0, 24260.0, 24140.0, 24180.0),
            ("2026-03-25T00:00:00-04:00", 24180.0, 24220.0, 24080.0, 24110.0),
            ("2026-03-26T00:00:00-04:00", 24110.0, 24180.0, 24060.0, 24090.0),
            ("2026-03-27T00:00:00-04:00", 24090.0, 24140.0, 24020.0, 24080.0),
            ("2026-03-30T00:00:00-04:00", 24190.0, 24250.0, 24120.0, 24210.0),
            ("2026-03-31T00:00:00-04:00", 24210.0, 24280.0, 24170.0, 24240.0),
            ("2026-04-01T00:00:00-04:00", 24240.0, 24290.0, 24190.0, 24230.0),
            ("2026-04-02T00:00:00-04:00", 24230.0, 24270.0, 24180.0, 24220.0),
        ],
    )

    frames = load_chart_frames([str(chart_daily)], parse_chart_file_name)
    summary = derive_gap_summary(frames)

    assert "NWOG" in summary.public_summary
    assert "NDOG" in summary.public_summary


def test_derive_gap_summary_uses_quadrants_for_large_weekly_gap(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-16T00:00:00-04:00", 23920.0, 23980.0, 23880.0, 23910.0),
            ("2026-03-17T00:00:00-04:00", 23910.0, 23960.0, 23890.0, 23940.0),
            ("2026-03-18T00:00:00-04:00", 23940.0, 23990.0, 23910.0, 23970.0),
            ("2026-03-19T00:00:00-04:00", 23970.0, 24010.0, 23930.0, 23980.0),
            ("2026-03-20T00:00:00-04:00", 23980.0, 24030.0, 23960.0, 24000.0),
            ("2026-03-23T00:00:00-04:00", 24120.0, 24240.0, 24090.0, 24190.0),
            ("2026-03-24T00:00:00-04:00", 24190.0, 24260.0, 24140.0, 24210.0),
            ("2026-03-25T00:00:00-04:00", 24210.0, 24240.0, 24100.0, 24150.0),
            ("2026-03-26T00:00:00-04:00", 24150.0, 24200.0, 24090.0, 24140.0),
            ("2026-03-27T00:00:00-04:00", 24140.0, 24190.0, 24080.0, 24130.0),
            ("2026-03-30T00:00:00-04:00", 24110.0, 24180.0, 24090.0, 24150.0),
        ],
    )

    frames = load_chart_frames([str(chart_daily)], parse_chart_file_name)
    summary = derive_gap_summary(frames)

    assert "50%" in summary.public_summary or "75%" in summary.public_summary or "25%" in summary.public_summary


def test_derive_gap_confluence_treats_large_nwog_as_pathing_not_bias_override(tmp_path: Path) -> None:
    chart_daily = tmp_path / "CME_MINI_MNQ1!, 1D.csv"
    _write_chart(
        chart_daily,
        [
            ("2026-03-16T00:00:00-04:00", 23920.0, 23980.0, 23880.0, 23910.0),
            ("2026-03-17T00:00:00-04:00", 23910.0, 23960.0, 23890.0, 23940.0),
            ("2026-03-18T00:00:00-04:00", 23940.0, 23990.0, 23910.0, 23970.0),
            ("2026-03-19T00:00:00-04:00", 23970.0, 24010.0, 23930.0, 23980.0),
            ("2026-03-20T00:00:00-04:00", 23980.0, 24030.0, 23960.0, 24000.0),
            ("2026-03-23T00:00:00-04:00", 24120.0, 24240.0, 24090.0, 24190.0),
            ("2026-03-24T00:00:00-04:00", 24190.0, 24260.0, 24140.0, 24210.0),
            ("2026-03-25T00:00:00-04:00", 24210.0, 24240.0, 24100.0, 24150.0),
            ("2026-03-26T00:00:00-04:00", 24150.0, 24200.0, 24090.0, 24140.0),
            ("2026-03-27T00:00:00-04:00", 24140.0, 24190.0, 24080.0, 24130.0),
            ("2026-03-30T00:00:00-04:00", 24040.0, 24180.0, 24010.0, 24060.0),
        ],
    )

    frames = load_chart_frames([str(chart_daily)], parse_chart_file_name)
    summary = derive_gap_summary(frames)
    confluence = derive_gap_confluence(summary, bias="bullish", current_price=24060.0)

    assert "supports bullish path" in confluence.lower()
    assert "NWOG" in confluence
