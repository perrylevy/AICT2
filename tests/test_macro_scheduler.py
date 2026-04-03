from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aict2.macro.publisher import should_publish_macro_dashboard, seconds_until_next_macro_publish

ET = ZoneInfo("America/New_York")


def test_should_publish_macro_dashboard_allows_hourly_window_on_weekday() -> None:
    assert should_publish_macro_dashboard(datetime(2026, 4, 3, 8, 0, tzinfo=ET)) is True
    assert should_publish_macro_dashboard(datetime(2026, 4, 3, 12, 0, tzinfo=ET)) is True
    assert should_publish_macro_dashboard(datetime(2026, 4, 3, 17, 0, tzinfo=ET)) is True


def test_should_publish_macro_dashboard_blocks_outside_window_and_weekends() -> None:
    assert should_publish_macro_dashboard(datetime(2026, 4, 3, 7, 59, tzinfo=ET)) is False
    assert should_publish_macro_dashboard(datetime(2026, 4, 3, 17, 1, tzinfo=ET)) is False
    assert should_publish_macro_dashboard(datetime(2026, 4, 4, 8, 0, tzinfo=ET)) is False


def test_seconds_until_next_macro_publish_rounds_to_next_hour_inside_window() -> None:
    seconds = seconds_until_next_macro_publish(datetime(2026, 4, 3, 8, 23, 10, tzinfo=ET))

    assert seconds == 37 * 60


def test_seconds_until_next_macro_publish_rolls_to_next_trading_day_open() -> None:
    seconds = seconds_until_next_macro_publish(datetime(2026, 4, 3, 17, 5, tzinfo=ET))

    assert seconds == ((62 * 60) + 55) * 60
