from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.analysis.analysis_service import build_analysis_snapshot
from aict2.bot.main import create_analysis_bundle
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore

ET = ZoneInfo("America/New_York")


def _write_chart(path: Path, rows: list[tuple[str, float, float, float, float]]) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        + "\n".join(
            f"{timestamp},{open_},{high},{low},{close}"
            for timestamp, open_, high, low, close in rows
        ),
        encoding="utf-8",
    )


def test_build_analysis_snapshot_can_derive_setup_from_csv_paths(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    chart_15 = tmp_path / "CME_MINI_MNQ1!, 15.csv"
    chart_5 = tmp_path / "CME_MINI_MNQ1!, 5.csv"
    chart_1 = tmp_path / "CME_MINI_MNQ1!, 1.csv"

    _write_chart(
        chart_15,
        [
            ("2026-04-02T09:00:00-04:00", 20000, 20020, 19995, 20018),
            ("2026-04-02T09:15:00-04:00", 20018, 20040, 20010, 20034),
            ("2026-04-02T09:30:00-04:00", 20034, 20058, 20028, 20052),
            ("2026-04-02T09:45:00-04:00", 20052, 20076, 20048, 20072),
        ],
    )
    _write_chart(
        chart_5,
        [
            ("2026-04-02T09:40:00-04:00", 20038, 20045, 20035, 20044),
            ("2026-04-02T09:45:00-04:00", 20044, 20052, 20042, 20050),
            ("2026-04-02T09:50:00-04:00", 20050, 20059, 20048, 20057),
            ("2026-04-02T09:55:00-04:00", 20057, 20066, 20055, 20064),
        ],
    )
    _write_chart(
        chart_1,
        [
            ("2026-04-02T09:52:00-04:00", 20055, 20057, 20053, 20056),
            ("2026-04-02T09:53:00-04:00", 20056, 20059, 20055, 20058),
            ("2026-04-02T09:54:00-04:00", 20058, 20061, 20057, 20060),
            ("2026-04-02T09:55:00-04:00", 20060, 20064, 20059, 20063),
        ],
    )

    snapshot = build_analysis_snapshot(
        file_names=[chart_15.name, chart_5.name, chart_1.name],
        file_paths=[str(chart_15), str(chart_5), str(chart_1)],
        current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
        macro_state="Mixed",
        vix=18.0,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=memory_store,
    )

    assert snapshot.thesis.state == "bullish"
    assert snapshot.thesis.daily_profile in {"continuation", "reversal"}
    assert snapshot.reference_context
    assert '20D' not in snapshot.reference_context
    assert snapshot.internal_reference_context
    assert snapshot.draw_on_liquidity
    assert snapshot.htf_reference
    assert snapshot.stop_run_summary
    assert snapshot.gap_summary
    assert snapshot.opening_summary
    assert snapshot.liquidity_summary
    assert snapshot.pd_array_summary
    assert snapshot.entry_model
    assert snapshot.tp_model
    assert snapshot.entry > 0
    assert snapshot.stop < snapshot.entry
    assert snapshot.target > snapshot.entry
    assert snapshot.risk.max_contracts >= 1


def test_create_analysis_bundle_uses_csv_paths_for_rendered_output(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)

    chart_1 = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    _write_chart(
        chart_1,
        [
            ("2026-04-02T10:52:00-04:00", 19980, 19981, 19970, 19972),
            ("2026-04-02T10:53:00-04:00", 19972, 19974, 19965, 19967),
            ("2026-04-02T10:54:00-04:00", 19967, 19968, 19960, 19961),
            ("2026-04-02T10:55:00-04:00", 19961, 19962, 19954, 19955),
        ],
    )

    bundle = create_analysis_bundle(
        file_names=[chart_1.name],
        file_paths=[str(chart_1)],
        current_time=datetime(2026, 4, 2, 10, 55, tzinfo=ET),
        macro_state="Risk-Off",
        vix=22.4,
        bias=None,
        daily_profile=None,
        entry=0.0,
        stop=0.0,
        target=0.0,
        memory_store=memory_store,
    )

    assert bundle.snapshot.entry > 0
    assert bundle.snapshot.reference_context
    assert bundle.snapshot.draw_on_liquidity
    assert bundle.snapshot.gap_summary
    assert bundle.snapshot.opening_summary
    assert bundle.snapshot.liquidity_summary
    assert bundle.snapshot.entry_model
    assert "HTF Context:" in bundle.output
    assert "Draw on Liquidity:" in bundle.output
    assert "HTF Reference:" in bundle.output
    assert "Stop Run:" in bundle.output
    assert "Opening Context:" in bundle.output
    assert "Gap Context:" in bundle.output
    assert "Liquidity:" in bundle.output
    assert "Entry Trigger:" in bundle.output
    assert "Entry:" in bundle.output
    assert "Stop:" in bundle.output
    assert "TP1:" in bundle.output
