from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from aict2.io.env_files import load_env_file


@dataclass(frozen=True, slots=True)
class MacroPublishSettings:
    discord_token: str
    dashboard_channel: str
    dashboard_channel_id: int | None
    market_news_channel: str
    market_news_channel_id: int | None
    db_path: Path


def _repo_env_path() -> Path:
    return Path(__file__).resolve().parents[3] / '.env'


def _effective_env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    if env is not None:
        return env
    return {**load_env_file(_repo_env_path()), **os.environ}


def load_macro_publish_settings(
    env: Mapping[str, str] | None = None,
) -> MacroPublishSettings:
    source = _effective_env(env)
    return MacroPublishSettings(
        discord_token=source.get('AICT2_DISCORD_TOKEN', ''),
        dashboard_channel=source.get('MACRO_DASHBOARD_CHANNEL', 'macro-dashboard'),
        dashboard_channel_id=(
            int(source['MACRO_DASHBOARD_CHANNEL_ID'])
            if source.get('MACRO_DASHBOARD_CHANNEL_ID')
            else None
        ),
        market_news_channel=source.get('MARKET_NEWS_CHANNEL', 'market-news'),
        market_news_channel_id=(
            int(source['MARKET_NEWS_CHANNEL_ID'])
            if source.get('MARKET_NEWS_CHANNEL_ID')
            else None
        ),
        db_path=Path(source.get('AICT2_DB_PATH', '.data/aict2.db')),
    )
