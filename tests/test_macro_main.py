from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from aict2.context.macro_memory import MacroSnapshotStore
from aict2.context.store import ContextStore
from aict2.macro.dashboard_core import MacroInputs
from aict2.macro import settings as macro_settings_module
from aict2.macro.publisher import MacroPublishSettings, main
from aict2.macro.settings import load_macro_publish_settings


def test_macro_main_returns_error_when_token_missing() -> None:
    exit_code = main(env={"AICT2_DISCORD_TOKEN": "", "MACRO_DASHBOARD_CHANNEL": "macro-dashboard"})
    assert exit_code == 1


def test_macro_main_calls_runner_with_payload_when_token_present() -> None:
    observed: dict[str, object] = {}

    def fake_inputs_loader(env):
        observed["env"] = dict(env)
        return MacroInputs(
            bull_percent=42.0,
            bear_percent=58.0,
            fear_greed_score=31.0,
            vix=21.1,
            put_call_ratio=0.92,
            tone_trend="worsening",
            major_event_active=True,
            major_event_label="CPI release imminent",
        )

    def fake_runner(settings: MacroPublishSettings, payload: dict[str, object]) -> int:
        observed["settings"] = settings
        observed["payload"] = payload
        return 0

    exit_code = main(
        env={
            "AICT2_DISCORD_TOKEN": "token-123",
            "MACRO_DASHBOARD_CHANNEL": "macro-dashboard",
        },
        load_inputs=fake_inputs_loader,
        publish_dashboard=fake_runner,
    )

    assert exit_code == 0
    assert observed["settings"].discord_token == "token-123"
    assert observed["settings"].dashboard_channel == "macro-dashboard"
    assert observed["payload"]["label"] == "Transition"
    assert observed["payload"]["override_reason"] == "CPI release imminent"


def test_macro_main_persists_snapshot_after_successful_publish(tmp_path: Path) -> None:
    db_path = tmp_path / "aict2.db"

    def fake_runner(settings: MacroPublishSettings, payload: dict[str, object]) -> int:
        _ = settings, payload
        return 0

    exit_code = main(
        env={
            "AICT2_DISCORD_TOKEN": "token-123",
            "MACRO_DASHBOARD_CHANNEL": "macro-dashboard",
            "AICT2_DB_PATH": str(db_path),
            "AICT2_MACRO_BULL_PERCENT": "40",
            "AICT2_MACRO_BEAR_PERCENT": "60",
            "AICT2_MACRO_FEAR_GREED": "25",
            "AICT2_MACRO_VIX": "22.4",
            "AICT2_MACRO_PUT_CALL": "0.95",
            "AICT2_MACRO_TONE_TREND": "worsening",
        },
        publish_dashboard=fake_runner,
    )

    store = ContextStore(db_path)
    store.initialize()
    macro_store = MacroSnapshotStore(store)
    snapshot = macro_store.load_latest()

    assert exit_code == 0
    assert snapshot is not None
    assert snapshot.macro_state == "Risk-Off"
    assert snapshot.vix == 22.4


def test_macro_main_defaults_to_live_cycle_when_not_injected(tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    def fake_run_live_cycle(settings: MacroPublishSettings, fallback_inputs: MacroInputs) -> int:
        observed["settings"] = settings
        observed["fallback_inputs"] = fallback_inputs
        return 0

    exit_code = main(
        env={
            "AICT2_DISCORD_TOKEN": "token-123",
            "MACRO_DASHBOARD_CHANNEL": "macro-dashboard",
            "MARKET_NEWS_CHANNEL": "market-news",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        },
        run_live_cycle=fake_run_live_cycle,
    )

    assert exit_code == 0
    assert observed["settings"].dashboard_channel == "macro-dashboard"
    assert observed["settings"].market_news_channel == "market-news"
    assert observed["fallback_inputs"].vix == 18.0


def test_load_macro_publish_settings_reads_repo_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / '.env'
    env_file.write_text(
        '\n'.join(
            [
                'AICT2_DISCORD_TOKEN=token-from-file',
                'MACRO_DASHBOARD_CHANNEL=macro-dashboard',
                'MACRO_DASHBOARD_CHANNEL_ID=1489458056554086583',
                'MARKET_NEWS_CHANNEL=market-news',
                'MARKET_NEWS_CHANNEL_ID=1476791483225870397',
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(macro_settings_module, '_repo_env_path', lambda: env_file)
    monkeypatch.delenv('AICT2_DISCORD_TOKEN', raising=False)
    monkeypatch.delenv('MACRO_DASHBOARD_CHANNEL', raising=False)
    monkeypatch.delenv('MACRO_DASHBOARD_CHANNEL_ID', raising=False)
    monkeypatch.delenv('MARKET_NEWS_CHANNEL', raising=False)
    monkeypatch.delenv('MARKET_NEWS_CHANNEL_ID', raising=False)

    settings = load_macro_publish_settings()

    assert settings.discord_token == 'token-from-file'
    assert settings.dashboard_channel == 'macro-dashboard'
    assert settings.dashboard_channel_id == 1489458056554086583
    assert settings.market_news_channel_id == 1476791483225870397


def test_macro_module_entrypoint_invokes_main(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / '.env'
    monkeypatch.setattr(macro_settings_module, '_repo_env_path', lambda: env_file)
    monkeypatch.delenv('AICT2_DISCORD_TOKEN', raising=False)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module('aict2.macro.publisher', run_name='__main__')

    assert exc_info.value.code == 1
