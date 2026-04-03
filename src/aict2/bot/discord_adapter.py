from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from aict2.bot.execution import execute_routed_message
from aict2.bot.router import route_message
from aict2.context.structural_memory import StructuralMemoryStore
from aict2.reporting.analysis_records import AnalysisRecordStore

_DISCORD_MESSAGE_LIMIT = 2000


async def _resolve_attachment_paths(attachments: list[Any]) -> list[str]:
    resolved: list[str] = []
    base_dir = Path(tempfile.gettempdir()) / 'aict2_uploads'
    base_dir.mkdir(parents=True, exist_ok=True)
    for attachment in attachments:
        local_path = getattr(attachment, 'local_path', None)
        if local_path:
            resolved.append(str(local_path))
            continue
        saver = getattr(attachment, 'save', None)
        if callable(saver):
            destination = base_dir / attachment.filename
            await saver(destination)
            resolved.append(str(destination))
            continue
        resolved.append(attachment.filename)
    return resolved


def _chunk_response(content: str, *, limit: int = _DISCORD_MESSAGE_LIMIT) -> list[str]:
    if len(content) <= limit:
        return [content]

    chunks: list[str] = []
    remaining = content
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        chunk = remaining[:split_at]
        if split_at < len(remaining) and remaining[split_at] == "\n":
            chunk += "\n"
            remaining = remaining[split_at + 1 :]
        else:
            remaining = remaining[split_at:]
        chunks.append(chunk)
    if remaining:
        chunks.append(remaining)
    return chunks


async def handle_discord_message(
    message: Any,
    watch_channels: tuple[str, ...],
    current_time: datetime,
    macro_state: str,
    vix: float,
    bias: str | None,
    daily_profile: str | None,
    entry: float,
    stop: float,
    target: float,
    memory_store: StructuralMemoryStore,
    record_store: AnalysisRecordStore,
    message_id: str,
) -> str | None:
    if getattr(getattr(message, 'author', None), 'bot', False):
        return None

    routed = route_message(
        channel_name=message.channel.name,
        content=message.content,
        attachment_names=[attachment.filename for attachment in message.attachments],
        attachment_paths=await _resolve_attachment_paths(list(message.attachments)),
        watch_channels=watch_channels,
    )
    if routed is None:
        return None

    response = execute_routed_message(
        routed_message=routed,
        message_id=message_id,
        current_time=current_time,
        macro_state=macro_state,
        vix=vix,
        bias=bias,
        daily_profile=daily_profile,
        entry=entry,
        stop=stop,
        target=target,
        memory_store=memory_store,
        record_store=record_store,
    )
    for chunk in _chunk_response(response):
        await message.reply(chunk)
    return response
