from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aict2.context.macro_memory import MacroSnapshot, MacroSnapshotStore
from aict2.context.store import ContextStore
from aict2.macro.client import publish_dashboard_message
from aict2.macro.dashboard_core import MacroInputs, MacroScore, score_macro_dashboard
from aict2.macro.dashboard_renderer import build_dashboard_payload
from aict2.macro.live_cycle import run_live_macro_cycle
from aict2.macro.settings import MacroPublishSettings, load_macro_publish_settings

InputLoader = Callable[[Mapping[str, str]], MacroInputs]
DashboardPublisher = Callable[[MacroPublishSettings, dict[str, object]], int]
LiveCycleRunner = Callable[[MacroPublishSettings, MacroInputs], int]
NowProvider = Callable[[], datetime]
SleepFn = Callable[[float], None]

ET = ZoneInfo("America/New_York")


def create_hourly_dashboard_payload(
    bull_percent: float,
    bear_percent: float,
    fear_greed_score: float,
    vix: float,
    put_call_ratio: float,
    tone_trend: str,
    major_event_active: bool,
    major_event_label: str | None,
) -> dict[str, str | int | None]:
    score = score_macro_dashboard(
        MacroInputs(
            bull_percent=bull_percent,
            bear_percent=bear_percent,
            fear_greed_score=fear_greed_score,
            vix=vix,
            put_call_ratio=put_call_ratio,
            tone_trend=tone_trend,
            major_event_active=major_event_active,
            major_event_label=major_event_label,
        )
    )
    return build_dashboard_payload(score)


def create_hourly_dashboard_score(inputs: MacroInputs) -> MacroScore:
    return score_macro_dashboard(inputs)


def load_macro_inputs(env: Mapping[str, str] | None = None) -> MacroInputs:
    source = env if env is not None else os.environ
    return MacroInputs(
        bull_percent=float(source.get('AICT2_MACRO_BULL_PERCENT', '50')),
        bear_percent=float(source.get('AICT2_MACRO_BEAR_PERCENT', '50')),
        fear_greed_score=float(source.get('AICT2_MACRO_FEAR_GREED', '50')),
        vix=float(source.get('AICT2_MACRO_VIX', '18')),
        vix_source='fallback',
        put_call_ratio=float(source.get('AICT2_MACRO_PUT_CALL', '0.75')),
        tone_trend=source.get('AICT2_MACRO_TONE_TREND', 'stable'),
        major_event_active=source.get('AICT2_MAJOR_EVENT_ACTIVE', '').strip().lower()
        in {'1', 'true', 'yes', 'on'},
        major_event_label=source.get('AICT2_MAJOR_EVENT_LABEL') or None,
    )


def should_publish_macro_dashboard(now: datetime) -> bool:
    et_now = now.astimezone(ET)
    if et_now.weekday() >= 5:
        return False
    if et_now.hour < 8:
        return False
    if et_now.hour > 17:
        return False
    return et_now.minute == 0


def seconds_until_next_macro_publish(now: datetime) -> int:
    et_now = now.astimezone(ET).replace(second=0, microsecond=0)
    candidate = et_now + timedelta(hours=1)
    candidate = candidate.replace(minute=0)

    if et_now.weekday() >= 5:
        days_until_monday = 7 - et_now.weekday()
        candidate = (et_now + timedelta(days=days_until_monday)).replace(
            hour=8, minute=0
        )
    elif et_now.hour < 8:
        candidate = et_now.replace(hour=8, minute=0)
    elif et_now.hour >= 17:
        next_day = et_now + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        candidate = next_day.replace(hour=8, minute=0)

    return max(1, int((candidate - et_now).total_seconds()))


def run_macro_scheduler(
    settings: MacroPublishSettings,
    fallback_inputs: MacroInputs,
    *,
    run_live_cycle: LiveCycleRunner = run_live_macro_cycle,
    now_provider: NowProvider | None = None,
    sleep_fn: SleepFn = time.sleep,
) -> int:
    now_fn = now_provider or (lambda: datetime.now(ET))
    while True:
        now = now_fn()
        if should_publish_macro_dashboard(now):
            run_live_cycle(settings, fallback_inputs)
            sleep_fn(60)
            continue
        sleep_fn(seconds_until_next_macro_publish(now))


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    load_inputs: InputLoader | None = None,
    publish_dashboard: DashboardPublisher | None = None,
    run_live_cycle: LiveCycleRunner | None = None,
) -> int:
    _ = argv
    settings = load_macro_publish_settings(env)
    if not settings.discord_token:
        print('AICT2_DISCORD_TOKEN is not set.', file=sys.stderr)
        return 1

    source = env if env is not None else os.environ
    fallback_inputs = load_macro_inputs(source)
    if load_inputs is None and publish_dashboard is None:
        if source.get("AICT2_MACRO_SCHEDULED", "").strip().lower() in {"1", "true", "yes", "on"}:
            return run_macro_scheduler(
                settings,
                fallback_inputs,
                run_live_cycle=run_live_cycle or run_live_macro_cycle,
            )
        live_runner = run_live_cycle or run_live_macro_cycle
        return live_runner(settings, fallback_inputs)

    inputs = (load_inputs or load_macro_inputs)(source)
    score = create_hourly_dashboard_score(inputs)
    payload = build_dashboard_payload(score)
    publisher = publish_dashboard or publish_dashboard_message
    exit_code = publisher(settings, payload)
    if exit_code == 0:
        context_store = ContextStore(settings.db_path)
        context_store.initialize()
        macro_store = MacroSnapshotStore(context_store)
        macro_store.save_latest(
            MacroSnapshot(
                macro_state=score.label,
                vix=inputs.vix,
                volatility_regime=score.volatility_regime,
                event_risk=score.event_risk,
                override_reason=score.override_reason,
            )
        )
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
