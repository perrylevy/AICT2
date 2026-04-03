from __future__ import annotations

from pathlib import Path

from aict2.context.macro_memory import MacroSnapshot
from aict2.macro.dashboard_core import MacroInputs
from aict2.macro.live_cycle import run_live_macro_cycle, with_stored_vix
from aict2.macro.settings import load_macro_publish_settings


class FakeClient:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code
        self.ran_with: str | None = None

    def run(self, token: str) -> None:
        self.ran_with = token


def test_run_live_macro_cycle_uses_client_factory_and_exit_code(tmp_path: Path) -> None:
    observed: dict[str, object] = {}
    fake_client = FakeClient(exit_code=0)

    def fake_client_factory(settings, fallback_inputs):
        observed["settings"] = settings
        observed["fallback_inputs"] = fallback_inputs
        return fake_client

    settings = load_macro_publish_settings(
        {
            "AICT2_DISCORD_TOKEN": "token-123",
            "MACRO_DASHBOARD_CHANNEL": "macro-dashboard",
            "MARKET_NEWS_CHANNEL": "market-news",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        }
    )

    exit_code = run_live_macro_cycle(
        settings,
        MacroInputs(
            bull_percent=50.0,
            bear_percent=50.0,
            fear_greed_score=50.0,
            vix=18.0,
            vix_source="fallback",
            put_call_ratio=0.75,
            tone_trend="stable",
            major_event_active=False,
            major_event_label=None,
        ),
        client_factory=fake_client_factory,
    )

    assert exit_code == 0
    assert observed["settings"] == settings
    assert fake_client.ran_with == "token-123"


def test_with_stored_vix_prefers_latest_snapshot_over_plain_fallback() -> None:
    inputs = MacroInputs(
        bull_percent=50.0,
        bear_percent=50.0,
        fear_greed_score=50.0,
        vix=18.0,
        vix_source="fallback",
        put_call_ratio=0.75,
        tone_trend="stable",
        major_event_active=False,
        major_event_label=None,
    )

    updated = with_stored_vix(
        inputs,
        MacroSnapshot(
            macro_state="Transition",
            vix=23.87,
            volatility_regime="high",
            event_risk="high",
            override_reason=None,
        ),
    )

    assert updated.vix == 23.87
    assert updated.vix_source == "stored"
