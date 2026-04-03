from __future__ import annotations

from pathlib import Path

from aict2.bot.main import run_discord_bot
from aict2.bot.runtime import build_runtime
from aict2.bot.settings import load_settings


class FakeClient:
    def __init__(self) -> None:
        self.ran_with: str | None = None

    def run(self, token: str) -> None:
        self.ran_with = token


def test_run_discord_bot_uses_client_factory_and_token(tmp_path: Path) -> None:
    observed: dict[str, object] = {}
    fake_client = FakeClient()

    def fake_client_factory(settings, runtime):
        observed["settings"] = settings
        observed["runtime"] = runtime
        return fake_client

    settings = load_settings(
        {
            "AICT2_DISCORD_TOKEN": "token-123",
            "AICT2_WATCH_CHANNELS": "aict2",
            "AICT2_DB_PATH": str(tmp_path / "aict2.db"),
        }
    )
    runtime = build_runtime(settings)

    exit_code = run_discord_bot(
        settings,
        runtime,
        client_factory=fake_client_factory,
    )

    assert exit_code == 0
    assert observed["settings"] == settings
    assert observed["runtime"] == runtime
    assert fake_client.ran_with == "token-123"
