from __future__ import annotations

import pandas as pd

from aict2.analysis.market_frame import load_chart_frames_from_mapping
from aict2.io.chart_bundle import ChartFrameBundle
from aict2.io.chart_intake import (
    build_chart_request,
    build_chart_request_from_bundle,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": ["2026-04-11T09:40:00-04:00"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.5],
            "close": [100.5],
        }
    )


def _tradingview_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": ["2026-04-11T09:40:00-04:00", "2026-04-11T09:45:00-04:00"],
            "open": [100.0, 100.5],
            "high": [101.0, 101.4],
            "low": [99.5, 100.1],
            "close": [100.5, 101.0],
            "volume": [1500, 1725],
        }
    )


def test_build_chart_request_from_bundle_matches_filename_path() -> None:
    request = build_chart_request(
        ["CME_MINI_MNQ1!, 1D.csv", "CME_MINI_MNQ1!, 60.csv", "CME_MINI_MNQ1!, 5.csv"]
    )
    bundle = ChartFrameBundle(
        instrument="MNQ1!",
        analysis_frames={"Daily": _frame(), "1H": _frame(), "5M": _frame()},
    )

    from_bundle = build_chart_request_from_bundle(bundle)

    assert from_bundle.instrument == request.instrument
    assert from_bundle.ordered_timeframes == request.ordered_timeframes
    assert from_bundle.execution_timeframe == request.execution_timeframe
    assert from_bundle.bundle_profile == request.bundle_profile


def test_load_chart_frames_from_mapping_trims_tradingview_payload_columns() -> None:
    normalized = load_chart_frames_from_mapping({"5M": _tradingview_frame()})

    assert set(normalized["5M"].columns) == {"time", "open", "high", "low", "close"}
    assert "volume" not in normalized["5M"].columns
    assert len(normalized["5M"]) == 2


def test_build_chart_request_from_bundle_rejects_mixed_or_empty_frames() -> None:
    empty = ChartFrameBundle(instrument="MNQ1!", analysis_frames={})

    try:
        build_chart_request_from_bundle(empty)
    except ValueError as exc:
        assert "Expected 1 or 3 charts" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty bundle")
