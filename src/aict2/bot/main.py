from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import sys

from aict2.analysis.analysis_service import AnalysisSnapshot, build_analysis_snapshot
from aict2.analysis.plan_writer import render_analysis_output
from aict2.bot.runtime import BotRuntime, build_runtime
from aict2.bot.settings import BotSettings, load_settings
from aict2.context.structural_memory import StructuralMemoryStore


@dataclass(frozen=True, slots=True)
class AnalysisBundle:
    snapshot: AnalysisSnapshot
    output: str


DiscordClientFactory = Callable[[BotSettings, BotRuntime], object]
BotRunner = Callable[[BotSettings, BotRuntime], int]


def create_analysis_bundle(
    file_names: list[str],
    current_time: datetime,
    macro_state: str,
    vix: float,
    bias: str | None,
    daily_profile: str | None,
    entry: float,
    stop: float,
    target: float,
    file_paths: list[str] | None = None,
    memory_store: StructuralMemoryStore | None = None,
) -> AnalysisBundle:
    snapshot = build_analysis_snapshot(
        file_names=file_names,
        file_paths=file_paths,
        current_time=current_time,
        macro_state=macro_state,
        vix=vix,
        bias=bias,
        daily_profile=daily_profile,
        entry=entry,
        stop=stop,
        target=target,
        memory_store=memory_store,
    )
    return AnalysisBundle(snapshot=snapshot, output=render_analysis_output(snapshot))


def create_analysis_response(
    file_names: list[str],
    current_time: datetime,
    macro_state: str,
    vix: float,
    bias: str | None,
    daily_profile: str | None,
    entry: float,
    stop: float,
    target: float,
    file_paths: list[str] | None = None,
    memory_store: StructuralMemoryStore | None = None,
) -> str:
    return create_analysis_bundle(
        file_names=file_names,
        file_paths=file_paths,
        current_time=current_time,
        macro_state=macro_state,
        vix=vix,
        bias=bias,
        daily_profile=daily_profile,
        entry=entry,
        stop=stop,
        target=target,
        memory_store=memory_store,
    ).output


def run_discord_bot(
    settings: BotSettings,
    runtime: BotRuntime,
    *,
    client_factory: DiscordClientFactory | None = None,
) -> int:
    factory = client_factory
    if factory is None:
        from aict2.bot.client import create_discord_client

        factory = create_discord_client
    client = factory(settings, runtime)
    client.run(settings.discord_token)
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    run_bot: BotRunner | None = None,
) -> int:
    _ = argv
    settings = load_settings(env)
    if not settings.discord_token:
        print('AICT2_DISCORD_TOKEN is not set.', file=sys.stderr)
        return 1

    runtime = build_runtime(settings)
    runner = run_bot or run_discord_bot
    return runner(settings, runtime)


if __name__ == '__main__':
    raise SystemExit(main())
