from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from aict2.io.env_files import load_env_file


@dataclass(frozen=True, slots=True)
class BotSettings:
    discord_token: str
    watch_channels: tuple[str, ...]
    db_path: Path


def _repo_env_path() -> Path:
    return Path(__file__).resolve().parents[3] / '.env'


def _effective_env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    if env is not None:
        return env
    return {**load_env_file(_repo_env_path()), **os.environ}


def load_settings(env: Mapping[str, str] | None = None) -> BotSettings:
    source = _effective_env(env)
    token = source.get('AICT2_DISCORD_TOKEN', '')
    watch_channels = tuple(
        channel.strip()
        for channel in source.get('AICT2_WATCH_CHANNELS', 'aict2').split(',')
        if channel.strip()
    )
    db_path = Path(source.get('AICT2_DB_PATH', '.data/aict2.db'))
    return BotSettings(
        discord_token=token,
        watch_channels=watch_channels,
        db_path=db_path,
    )
