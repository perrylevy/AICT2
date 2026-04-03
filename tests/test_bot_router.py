from __future__ import annotations

from aict2.bot.router import route_message


def test_route_message_detects_auto_analysis_csv_upload() -> None:
    routed = route_message(
        channel_name="aict2",
        content="",
        attachment_names=["CME_MINI_MNQ1!, 1.csv"],
        watch_channels=("aict2",),
    )

    assert routed is not None
    assert routed.action == "analyze_upload"
    assert routed.attachment_names == ("CME_MINI_MNQ1!, 1.csv",)


def test_route_message_detects_scoredata_command() -> None:
    routed = route_message(
        channel_name="aict2",
        content="!scoredata",
        attachment_names=["CME_MINI_MNQ1!, 1.csv"],
        attachment_paths=["C:/tmp/CME_MINI_MNQ1!, 1.csv"],
        watch_channels=("aict2",),
    )

    assert routed is not None
    assert routed.action == "scoredata"
    assert routed.attachment_paths == ("C:/tmp/CME_MINI_MNQ1!, 1.csv",)


def test_route_message_detects_accuracy_report_command() -> None:
    routed = route_message(
        channel_name="aict2",
        content="!accuracy report",
        attachment_names=[],
        watch_channels=("aict2",),
    )

    assert routed is not None
    assert routed.action == "accuracy_report"


def test_route_message_ignores_other_channels() -> None:
    routed = route_message(
        channel_name="general",
        content="!scoredata",
        attachment_names=["CME_MINI_MNQ1!, 1.csv"],
        watch_channels=("aict2",),
    )

    assert routed is None
