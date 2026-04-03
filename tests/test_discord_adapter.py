from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aict2.bot.discord_adapter import handle_discord_message
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore
from aict2.reporting.analysis_records import AnalysisRecord, AnalysisRecordStore

ET = ZoneInfo("America/New_York")


@dataclass
class FakeAuthor:
    bot: bool = False


@dataclass
class FakeChannel:
    name: str


@dataclass
class FakeAttachment:
    filename: str
    local_path: str | None = None


@dataclass
class FakeMessage:
    channel: FakeChannel
    content: str
    attachments: list[FakeAttachment]
    author: FakeAuthor = field(default_factory=FakeAuthor)
    replies: list[str] = field(default_factory=list)

    async def reply(self, content: str) -> None:
        self.replies.append(content)


def test_handle_discord_message_replies_to_csv_upload(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    message = FakeMessage(
        channel=FakeChannel(name="aict2"),
        content="",
        attachments=[
            FakeAttachment("CME_MINI_MNQ1!, 15.csv"),
            FakeAttachment("CME_MINI_MNQ1!, 5.csv"),
            FakeAttachment("CME_MINI_MNQ1!, 1.csv"),
        ],
    )

    response = asyncio.run(
        handle_discord_message(
            message=message,
            watch_channels=("aict2",),
            current_time=datetime(2026, 4, 2, 9, 55, tzinfo=ET),
            macro_state="Risk-Off",
            vix=22.4,
            bias="bullish",
            daily_profile="continuation",
            entry=20000,
            stop=19990,
            target=20035,
            memory_store=memory_store,
            record_store=record_store,
            message_id="msg-1",
        )
    )

    assert response is not None
    assert "Status: LIVE SETUP" in response
    assert message.replies == [response]


def test_handle_discord_message_ignores_bot_authors(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    message = FakeMessage(
        channel=FakeChannel(name="aict2"),
        content="!accuracy report",
        attachments=[],
        author=FakeAuthor(bot=True),
    )

    response = asyncio.run(
        handle_discord_message(
            message=message,
            watch_channels=("aict2",),
            current_time=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
            macro_state="Mixed",
            vix=18.0,
            bias=None,
            daily_profile=None,
            entry=20000,
            stop=19990,
            target=20025,
            memory_store=memory_store,
            record_store=record_store,
            message_id="msg-2",
        )
    )

    assert response is None
    assert message.replies == []


def test_handle_discord_message_routes_accuracy_report(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    record_store.record_analysis(
        AnalysisRecord(
            message_id="msg-1",
            instrument="MNQ1!",
            status="LIVE SETUP",
            direction="LONG",
            confidence=65,
            outcome="TP_HIT",
            score=1.0,
            analyzed_at="2026-04-02T09:55:00-04:00",
            entry=20000.0,
            stop=19990.0,
            target=20035.0,
        )
    )
    message = FakeMessage(
        channel=FakeChannel(name="aict2"),
        content="!accuracy report",
        attachments=[],
    )

    response = asyncio.run(
        handle_discord_message(
            message=message,
            watch_channels=("aict2",),
            current_time=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
            macro_state="Mixed",
            vix=18.0,
            bias=None,
            daily_profile=None,
            entry=20000,
            stop=19990,
            target=20025,
            memory_store=memory_store,
            record_store=record_store,
            message_id="msg-3",
        )
    )

    assert response is not None
    assert "Total analyses: 1" in response
    assert message.replies == [response]


def test_handle_discord_message_routes_scoredata_with_local_attachment(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    record_store.record_analysis(
        AnalysisRecord(
            message_id="msg-1",
            instrument="MNQ1!",
            status="LIVE SETUP",
            direction="LONG",
            confidence=65,
            outcome=None,
            score=None,
            analyzed_at="2026-04-02T09:55:00-04:00",
            entry=20000.0,
            stop=19990.0,
            target=20035.0,
        )
    )
    csv_path = tmp_path / "CME_MINI_MNQ1!, 1.csv"
    csv_path.write_text(
        "Time,Open,High,Low,Close\n"
        "2026-04-02T13:56:00Z,20002,20004,19998,20001\n"
        "2026-04-02T13:57:00Z,20001,20036,19999,20030\n",
        encoding="utf-8",
    )
    message = FakeMessage(
        channel=FakeChannel(name="aict2"),
        content="!scoredata",
        attachments=[FakeAttachment("CME_MINI_MNQ1!, 1.csv", local_path=str(csv_path))],
    )

    response = asyncio.run(
        handle_discord_message(
            message=message,
            watch_channels=("aict2",),
            current_time=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
            macro_state="Mixed",
            vix=18.0,
            bias=None,
            daily_profile=None,
            entry=0,
            stop=0,
            target=0,
            memory_store=memory_store,
            record_store=record_store,
            message_id="msg-4",
        )
    )

    updated = record_store.get_analysis("msg-1")

    assert response is not None
    assert "TP_HIT" in response
    assert message.replies == [response]
    assert updated is not None
    assert updated.outcome == "TP_HIT"


def test_handle_discord_message_splits_long_responses(tmp_path: Path) -> None:
    context_store = ContextStore(tmp_path / "aict2.db")
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    message = FakeMessage(
        channel=FakeChannel(name="aict2"),
        content="!accuracy report",
        attachments=[],
    )
    long_response = ("A" * 1990) + "\n" + ("B" * 1990)

    async def run() -> str | None:
        from unittest.mock import patch

        with patch(
            "aict2.bot.discord_adapter.execute_routed_message",
            return_value=long_response,
        ):
            return await handle_discord_message(
                message=message,
                watch_channels=("aict2",),
                current_time=datetime(2026, 4, 2, 10, 0, tzinfo=ET),
                macro_state="Mixed",
                vix=18.0,
                bias=None,
                daily_profile=None,
                entry=0,
                stop=0,
                target=0,
                memory_store=memory_store,
                record_store=record_store,
                message_id="msg-5",
            )

    response = asyncio.run(run())

    assert response == long_response
    assert len(message.replies) == 2
    assert all(len(part) <= 2000 for part in message.replies)
    assert message.replies[0].endswith("\n")
