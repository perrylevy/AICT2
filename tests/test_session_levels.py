from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.analysis.session_levels import derive_session_levels_from_paths

ET = ZoneInfo('America/New_York')


def _write_chart(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        'time,open,high,low,close\n'
        + '\n'.join(
            f'{timestamp},{open_},{high},{low},{close}'
            for timestamp, open_, high, low, close in rows
        ),
        encoding='utf-8',
    )


def test_derive_session_levels_from_paths_extracts_named_ranges_and_gap(tmp_path: Path) -> None:
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'
    _write_chart(
        chart_5,
        [
            ('2026-04-01T18:00:00-04:00', 23990.0, 24010.0, 23980.0, 24005.0),
            ('2026-04-01T21:00:00-04:00', 24005.0, 24040.0, 23970.0, 24020.0),
            ('2026-04-01T23:55:00-04:00', 24020.0, 24035.0, 24000.0, 24015.0),
            ('2026-04-02T00:30:00-04:00', 24015.0, 24070.0, 24005.0, 24060.0),
            ('2026-04-02T05:30:00-04:00', 24060.0, 24080.0, 24010.0, 24020.0),
            ('2026-04-01T15:55:00-04:00', 23940.0, 23960.0, 23920.0, 23950.0),
            ('2026-04-02T09:30:00-04:00', 24010.0, 24040.0, 23995.0, 24035.0),
            ('2026-04-02T10:15:00-04:00', 24035.0, 24110.0, 24025.0, 24095.0),
            ('2026-04-02T11:45:00-04:00', 24095.0, 24120.0, 24050.0, 24070.0),
            ('2026-04-02T13:15:00-04:00', 24070.0, 24140.0, 24060.0, 24120.0),
            ('2026-04-02T15:30:00-04:00', 24120.0, 24155.0, 24090.0, 24100.0),
        ],
    )

    levels = derive_session_levels_from_paths(
        [str(chart_5)],
        current_time=datetime(2026, 4, 2, 15, 30, tzinfo=ET),
    )

    assert levels is not None
    assert levels.asia == 'Asia H 24040.00 / L 23970.00'
    assert levels.london == 'London H 24080.00 / L 24005.00'
    assert levels.ny_am == 'NY AM H 24120.00 / L 23995.00'
    assert levels.ny_pm == 'NY PM H 24155.00 / L 24060.00'
    assert levels.rth_gap == 'RTH Gap H 24010.00 / L 23950.00 / CE 23980.00'
    assert levels.interaction == 'Swept NY AM high and closed back below | Holding above RTH Gap high'


def test_derive_session_levels_from_paths_returns_none_without_intraday_data(tmp_path: Path) -> None:
    chart_daily = tmp_path / 'CME_MINI_MNQ1!, 1D.csv'
    _write_chart(
        chart_daily,
        [
            ('2026-04-01T00:00:00-04:00', 23900.0, 24100.0, 23800.0, 24050.0),
            ('2026-04-02T00:00:00-04:00', 24050.0, 24200.0, 23950.0, 24120.0),
        ],
    )

    levels = derive_session_levels_from_paths(
        [str(chart_daily)],
        current_time=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
    )

    assert levels is None


def test_derive_session_levels_prefers_intraday_frame_with_better_session_coverage(
    tmp_path: Path,
) -> None:
    chart_1h = tmp_path / 'CME_MINI_MNQ1!, 60.csv'
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'
    _write_chart(
        chart_1h,
        [
            ('2026-04-01T15:00:00-04:00', 23920.0, 23960.0, 23910.0, 23940.0),
            ('2026-04-01T18:00:00-04:00', 23990.0, 24010.0, 23980.0, 24005.0),
            ('2026-04-01T21:00:00-04:00', 24005.0, 24040.0, 23970.0, 24020.0),
            ('2026-04-02T00:00:00-04:00', 24020.0, 24070.0, 24005.0, 24060.0),
            ('2026-04-02T05:00:00-04:00', 24060.0, 24080.0, 24010.0, 24020.0),
            ('2026-04-02T09:00:00-04:00', 24020.0, 24030.0, 23995.0, 24010.0),
            ('2026-04-02T10:00:00-04:00', 24010.0, 24110.0, 24005.0, 24095.0),
        ],
    )
    _write_chart(
        chart_5,
        [
            ('2026-04-02T09:30:00-04:00', 24010.0, 24040.0, 23995.0, 24035.0),
            ('2026-04-02T10:15:00-04:00', 24035.0, 24110.0, 24025.0, 24095.0),
            ('2026-04-02T11:45:00-04:00', 24095.0, 24120.0, 24050.0, 24070.0),
        ],
    )

    levels = derive_session_levels_from_paths(
        [str(chart_1h), str(chart_5)],
        current_time=datetime(2026, 4, 2, 11, 45, tzinfo=ET),
    )

    assert levels is not None
    assert levels.asia != 'Asia unavailable'
    assert levels.london != 'London unavailable'
    assert levels.rth_gap != 'RTH Gap unavailable'


def test_derive_session_levels_uses_chart_trade_date_not_upload_time(tmp_path: Path) -> None:
    chart_5 = tmp_path / 'CME_MINI_MNQ1!, 5.csv'
    _write_chart(
        chart_5,
        [
            ('2026-04-01T15:55:00-04:00', 24159.0, 24253.75, 24154.0, 24199.75),
            ('2026-04-01T18:00:00-04:00', 24181.5, 24204.5, 24174.5, 24197.5),
            ('2026-04-01T21:00:00-04:00', 24236.5, 24240.0, 24109.5, 24150.0),
            ('2026-04-02T00:00:00-04:00', 23821.25, 23837.75, 23821.0, 23827.25),
            ('2026-04-02T05:00:00-04:00', 23835.25, 23848.25, 23828.5, 23836.5),
            ('2026-04-02T09:30:00-04:00', 23763.25, 23819.0, 23762.75, 23789.0),
            ('2026-04-02T10:10:00-04:00', 23930.5, 23964.75, 23912.75, 23934.75),
        ],
    )

    levels = derive_session_levels_from_paths(
        [str(chart_5)],
        current_time=datetime(2026, 4, 3, 1, 36, tzinfo=ET),
    )

    assert levels is not None
    assert levels.asia != 'Asia unavailable'
    assert levels.london != 'London unavailable'
    assert levels.rth_gap != 'RTH Gap unavailable'
