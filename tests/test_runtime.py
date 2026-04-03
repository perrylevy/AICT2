from __future__ import annotations

from pathlib import Path

from aict2.bot import settings as bot_settings_module
from aict2.bot.runtime import build_runtime
from aict2.bot.settings import load_settings


def test_load_settings_reads_env_values(monkeypatch) -> None:
    monkeypatch.setenv("AICT2_DISCORD_TOKEN", "token-123")
    monkeypatch.setenv("AICT2_WATCH_CHANNELS", "aict2,charts")
    monkeypatch.setenv("AICT2_DB_PATH", "C:/tmp/aict2.db")

    settings = load_settings()

    assert settings.discord_token == "token-123"
    assert settings.watch_channels == ("aict2", "charts")
    assert settings.db_path == Path("C:/tmp/aict2.db")


def test_load_settings_uses_explicit_empty_env_without_fallback() -> None:
    settings = load_settings({})

    assert settings.discord_token == ""
    assert settings.watch_channels == ("aict2",)
    assert settings.db_path == Path(".data/aict2.db")


def test_load_settings_reads_repo_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / '.env'
    env_file.write_text(
        '\n'.join(
            [
                'AICT2_DISCORD_TOKEN=token-from-file',
                'AICT2_WATCH_CHANNELS=aict2,macro-dashboard',
                'AICT2_DB_PATH=.data/local-test.db',
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(bot_settings_module, '_repo_env_path', lambda: env_file)
    monkeypatch.delenv('AICT2_DISCORD_TOKEN', raising=False)
    monkeypatch.delenv('AICT2_WATCH_CHANNELS', raising=False)
    monkeypatch.delenv('AICT2_DB_PATH', raising=False)

    settings = load_settings()

    assert settings.discord_token == 'token-from-file'
    assert settings.watch_channels == ('aict2', 'macro-dashboard')
    assert settings.db_path == Path('.data/local-test.db')


def test_build_runtime_creates_stores(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "AICT2_DISCORD_TOKEN": "token-123",
            "AICT2_WATCH_CHANNELS": "aict2",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        }
    )

    runtime = build_runtime(settings)

    assert runtime.settings == settings
    assert runtime.context_store.db_path == settings.db_path
    assert runtime.record_store.get_analysis("missing") is None
