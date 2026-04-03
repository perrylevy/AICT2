from __future__ import annotations

from pathlib import Path

from aict2.macro.client import publish_dashboard_message
from aict2.macro.publisher import MacroPublishSettings


class FakeClient:
    def __init__(self) -> None:
        self.ran_with: str | None = None

    def run(self, token: str) -> None:
        self.ran_with = token


class FailingClient:
    def run(self, token: str) -> None:
        _ = token
        raise RuntimeError("channel not found")


def test_publish_dashboard_message_uses_client_factory_and_token() -> None:
    observed: dict[str, object] = {}
    fake_client = FakeClient()

    def fake_client_factory(settings, payload):
        observed["settings"] = settings
        observed["payload"] = payload
        return fake_client

    exit_code = publish_dashboard_message(
        MacroPublishSettings(
            discord_token="token-123",
            dashboard_channel="macro-dashboard",
            dashboard_channel_id=None,
            market_news_channel="market-news",
            market_news_channel_id=None,
            db_path=Path("unused"),
        ),
        {"body": "Macro Label: Mixed"},
        client_factory=fake_client_factory,
    )

    assert exit_code == 0
    assert observed["settings"].dashboard_channel == "macro-dashboard"
    assert observed["payload"]["body"] == "Macro Label: Mixed"
    assert fake_client.ran_with == "token-123"


def test_publish_dashboard_message_returns_error_when_client_run_fails() -> None:
    def fake_client_factory(settings, payload):
        _ = settings, payload
        return FailingClient()

    exit_code = publish_dashboard_message(
        MacroPublishSettings(
            discord_token="token-123",
            dashboard_channel="macro-dashboard",
            dashboard_channel_id=None,
            market_news_channel="market-news",
            market_news_channel_id=None,
            db_path=Path("unused"),
        ),
        {"body": "Macro Label: Mixed"},
        client_factory=fake_client_factory,
    )

    assert exit_code == 1
