from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoutedMessage:
    action: str
    channel_name: str
    content: str
    attachment_names: tuple[str, ...]
    attachment_paths: tuple[str, ...] = ()


def _normalize_content(content: str) -> str:
    return content.strip().lower()


def _csv_attachments(attachment_names: list[str]) -> tuple[str, ...]:
    return tuple(name for name in attachment_names if name.lower().endswith('.csv'))


def route_message(
    channel_name: str,
    content: str,
    attachment_names: list[str],
    watch_channels: tuple[str, ...],
    attachment_paths: list[str] | None = None,
) -> RoutedMessage | None:
    if channel_name not in watch_channels:
        return None

    normalized = _normalize_content(content)
    csv_attachments = _csv_attachments(attachment_names)
    resolved_paths = tuple(attachment_paths or ())

    if normalized == '!accuracy report':
        return RoutedMessage(
            action='accuracy_report',
            channel_name=channel_name,
            content=content,
            attachment_names=csv_attachments,
            attachment_paths=resolved_paths,
        )

    if normalized == '!scoredata':
        return RoutedMessage(
            action='scoredata',
            channel_name=channel_name,
            content=content,
            attachment_names=csv_attachments,
            attachment_paths=resolved_paths,
        )

    if csv_attachments:
        return RoutedMessage(
            action='analyze_upload',
            channel_name=channel_name,
            content=content,
            attachment_names=csv_attachments,
            attachment_paths=resolved_paths,
        )

    return None
