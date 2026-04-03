from __future__ import annotations

from pathlib import Path

import pytest

from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemorySnapshot, StructuralMemoryStore
from aict2.io.chart_intake import build_chart_request


def test_build_chart_request_for_multi_timeframe_upload() -> None:
    request = build_chart_request(
        [
            "CME_MINI_MNQ1!, 1.csv",
            "CME_MINI_MNQ1!, 15.csv",
            "CME_MINI_MNQ1!, 5.csv",
        ]
    )

    assert request.instrument == "MNQ1!"
    assert request.mode == "multi"
    assert request.ordered_timeframes == ("15M", "5M", "1M")
    assert request.execution_timeframe == "1M"
    assert request.bundle_profile == "execution"
    assert request.is_canonical_bundle is True


def test_build_chart_request_supports_daily_hourly_five_minute_bundle() -> None:
    request = build_chart_request(
        [
            "CME_MINI_MNQ1!, 1D.csv",
            "CME_MINI_MNQ1!, 60.csv",
            "CME_MINI_MNQ1!, 5.csv",
        ]
    )

    assert request.ordered_timeframes == ("Daily", "1H", "5M")
    assert request.execution_timeframe == "5M"
    assert request.bundle_profile == "balanced"
    assert request.is_canonical_bundle is True


def test_build_chart_request_supports_weekly_daily_hourly_bundle() -> None:
    request = build_chart_request(
        [
            "CME_MINI_MNQ1!, 1W.csv",
            "CME_MINI_MNQ1!, 1D.csv",
            "CME_MINI_MNQ1!, 60.csv",
        ]
    )

    assert request.ordered_timeframes == ("Weekly", "Daily", "1H")
    assert request.execution_timeframe == "1H"
    assert request.bundle_profile == "structural"
    assert request.is_canonical_bundle is True


def test_build_chart_request_supports_micro_execution_bundle() -> None:
    request = build_chart_request(
        [
            "CME_MINI_MNQ1!, 60.csv",
            "CME_MINI_MNQ1!, 5.csv",
            "CME_MINI_MNQ1!, 30S.csv",
        ]
    )

    assert request.ordered_timeframes == ("1H", "5M", "30S")
    assert request.execution_timeframe == "30S"
    assert request.bundle_profile == "micro"
    assert request.is_canonical_bundle is True


def test_build_chart_request_supports_sanitized_discord_filenames() -> None:
    request = build_chart_request(
        [
            "CME_MINI_MNQ1_1D_4_1.csv",
            "CME_MINI_MNQ1_60_5_1.csv",
            "CME_MINI_MNQ1_5_6_1.csv",
        ]
    )

    assert request.instrument == "MNQ1!"
    assert request.ordered_timeframes == ("Daily", "1H", "5M")
    assert request.bundle_profile == "balanced"
    assert request.is_canonical_bundle is True


def test_build_chart_request_marks_noncanonical_bundle() -> None:
    request = build_chart_request(
        [
            "CME_MINI_MNQ1!, 1D.csv",
            "CME_MINI_MNQ1!, 15.csv",
            "CME_MINI_MNQ1!, 1.csv",
        ]
    )

    assert request.ordered_timeframes == ("Daily", "15M", "1M")
    assert request.bundle_profile == "custom"
    assert request.is_canonical_bundle is False


def test_build_chart_request_rejects_mixed_instruments() -> None:
    with pytest.raises(ValueError, match="Mixed instruments"):
        build_chart_request(
            [
                "CME_MINI_MNQ1!, 1.csv",
                "CME_MINI_MNQ1!, 5.csv",
                "CME_MINI_NQ1!, 15.csv",
            ]
        )


def test_build_chart_request_rejects_unsupported_chart_counts() -> None:
    with pytest.raises(ValueError, match="Expected 1 or 3 charts"):
        build_chart_request(
            [
                "CME_MINI_MNQ1!, 1.csv",
                "CME_MINI_MNQ1!, 5.csv",
            ]
        )


def test_structural_memory_store_round_trips_latest_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "aict2.db"
    context_store = ContextStore(db_path)
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    snapshot = StructuralMemorySnapshot(
        instrument="MNQ1!",
        thesis_state="bullish",
        daily_profile="continuation",
        source_timeframes=("15M", "5M", "1M"),
        lookback_days=20,
        reference_context="PDH 20050.00 / PDL 19880.00",
    )

    memory_store.save_latest(snapshot)
    loaded = memory_store.load_latest("MNQ1!")

    assert loaded == snapshot


def test_structural_memory_store_returns_none_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "aict2.db"
    context_store = ContextStore(db_path)
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    assert memory_store.load_latest("MNQ1!") is None
