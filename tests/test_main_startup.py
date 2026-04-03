from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from aict2.bot import settings as bot_settings_module
from aict2.bot.main import main


def test_main_returns_error_when_token_missing(tmp_path, capsys) -> None:
    exit_code = main(
        env={
            "AICT2_DISCORD_TOKEN": "",
            "AICT2_WATCH_CHANNELS": "aict2",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        }
    )

    assert exit_code == 1
    assert "AICT2_DISCORD_TOKEN is not set" in capsys.readouterr().err


def test_main_calls_runner_when_token_present(tmp_path) -> None:
    observed: dict[str, object] = {}

    def fake_runner(settings, runtime) -> int:
        observed["settings"] = settings
        observed["runtime"] = runtime
        return 0

    exit_code = main(
        env={
            "AICT2_DISCORD_TOKEN": "token-123",
            "AICT2_WATCH_CHANNELS": "aict2",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        },
        run_bot=fake_runner,
    )

    assert exit_code == 0
    assert observed["settings"].discord_token == "token-123"
    assert observed["runtime"].settings == observed["settings"]


def test_module_entrypoint_invokes_main(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / '.env'
    monkeypatch.setattr(bot_settings_module, '_repo_env_path', lambda: env_file)
    monkeypatch.delenv('AICT2_DISCORD_TOKEN', raising=False)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module('aict2.bot.main', run_name='__main__')

    assert exc_info.value.code == 1
