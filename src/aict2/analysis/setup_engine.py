from __future__ import annotations

import re
from datetime import time

import pandas as pd

from aict2.analysis.gap_levels import derive_gap_confluence, derive_gap_summary
from aict2.analysis.market_frame import ChartFrameFacts, frame_bias, load_chart_frames
from aict2.analysis.opening_levels import derive_opening_levels_summary
from aict2.analysis.pd_arrays import (
    derive_execution_entry_trigger,
    derive_htf_array_reference,
    derive_pd_array_confluence,
    derive_pd_array_summary,
)
from aict2.analysis.trade_planning import (
    ChartDerivedPlan,
    derive_daily_profile,
    derive_reference_context,
    derive_trade_levels,
    needs_confirmation,
    requires_retrace,
    weighted_bias_score,
)
from aict2.analysis.session_levels import select_best_intraday_frame
from aict2.io.filename_parsing import parse_chart_file_name

_TF_ORDER = {
    'Monthly': 0,
    'Weekly': 1,
    'Daily': 2,
    '4H': 3,
    '1H': 4,
    '15M': 5,
    '5M': 6,
    '1M': 7,
    '30S': 8,
}


def _equal_liquidity_label(frame: pd.DataFrame, side: str) -> str | None:
    recent = frame.tail(min(len(frame), 20)).reset_index(drop=True)
    if len(recent) < 3:
        return None
    tolerance = max(0.25, float((recent["high"] - recent["low"]).mean()) * 0.2)
    values = recent["high"].tolist() if side == "high" else recent["low"].tolist()
    label = "EQH" if side == "high" else "EQL"
    for value in values:
        cluster = [candidate for candidate in values if abs(candidate - value) <= tolerance]
        if len(cluster) >= 2:
            level = sum(cluster) / len(cluster)
            return f"{label} {level:.2f}"
    return None


def _previous_session_range(frame: pd.DataFrame) -> tuple[float | None, float | None]:
    enriched = frame.copy()
    et_times = enriched["time"].dt.tz_convert("America/New_York")
    enriched["et_date"] = et_times.dt.date
    enriched["et_clock"] = et_times.dt.time
    trade_date = et_times.iloc[-1].date()
    previous_date = trade_date.fromordinal(trade_date.toordinal() - 1)
    previous_rth = enriched[
        (enriched["et_date"] == previous_date)
        & (enriched["et_clock"] >= time(hour=9, minute=30))
        & (enriched["et_clock"] < time(hour=16, minute=0))
    ]
    if previous_rth.empty:
        return None, None
    return float(previous_rth["high"].max()), float(previous_rth["low"].min())


def _session_liquidity_candidates(frame: pd.DataFrame, bias: str) -> list[tuple[str, float]]:
    enriched = frame.copy()
    et_times = enriched["time"].dt.tz_convert("America/New_York")
    enriched["et_date"] = et_times.dt.date
    enriched["et_clock"] = et_times.dt.time
    trade_date = et_times.iloc[-1].date()
    previous_date = trade_date.fromordinal(trade_date.toordinal() - 1)

    windows = [
        (
            "Asia",
            enriched[
                (enriched["et_date"] == previous_date)
                & (enriched["et_clock"] >= time(hour=18, minute=0))
            ],
        ),
        (
            "London",
            enriched[
                (enriched["et_date"] == trade_date)
                & (enriched["et_clock"] < time(hour=6, minute=0))
            ],
        ),
    ]

    candidates: list[tuple[str, float]] = []
    for name, window in windows:
        if window.empty:
            continue
        if bias == "bullish":
            candidates.append((f"{name} High", float(window["high"].max())))
        elif bias == "bearish":
            candidates.append((f"{name} Low", float(window["low"].min())))
    return candidates


def _nearest_directional_liquidity_label(
    *,
    last_close: float,
    bias: str,
    candidates: list[tuple[str, float]],
) -> str | None:
    if bias == "bullish":
        directional = [(label, level) for label, level in candidates if level > last_close]
        if not directional:
            return None
        label, level = min(directional, key=lambda item: item[1] - last_close)
        return f"{label} {level:.2f}"
    if bias == "bearish":
        directional = [(label, level) for label, level in candidates if level < last_close]
        if not directional:
            return None
        label, level = min(directional, key=lambda item: last_close - item[1])
        return f"{label} {level:.2f}"
    return None


def _derive_draw_on_liquidity(
    *,
    frames: dict[str, pd.DataFrame],
    bias: str,
) -> str:
    daily = frames.get("Daily")
    intraday = select_best_intraday_frame(frames)
    daily_candidate: str | None = None
    if daily is not None and len(daily) >= 2:
        prior_day = daily.iloc[-2]
        if bias == "bullish":
            daily_candidate = f"PDH {float(prior_day['high']):.2f}"
        elif bias == "bearish":
            daily_candidate = f"PDL {float(prior_day['low']):.2f}"
    if daily_candidate is not None:
        return daily_candidate
    if intraday is not None:
        last_close = float(intraday.iloc[-1]["close"])
        session_candidates = _session_liquidity_candidates(intraday, bias)
        directional_label = _nearest_directional_liquidity_label(
            last_close=last_close,
            bias=bias,
            candidates=session_candidates,
        )
        if directional_label is not None:
            return directional_label
        equal_level = _equal_liquidity_label(intraday, "high" if bias == "bullish" else "low")
        if equal_level is not None:
            return equal_level
        if session_candidates:
            label, level = session_candidates[0]
            return f"{label} {level:.2f}"
    return "Awaiting clearer draw on liquidity"


def _derive_htf_reference(
    *,
    frames: dict[str, pd.DataFrame],
    facts: dict[str, ChartFrameFacts],
    bias: str,
) -> str:
    htf_array_reference = derive_htf_array_reference(frames, bias=bias)
    if htf_array_reference is not None:
        return htf_array_reference

    for timeframe in ("4H", "1H", "Daily"):
        frame = frames.get(timeframe)
        fact = facts.get(timeframe)
        if frame is None or fact is None:
            continue
        if bias == "bullish":
            if fact.latest_swing_high is not None:
                return f"{timeframe} High {fact.latest_swing_high:.2f}"
            if fact.latest_swing_low is not None:
                return f"{timeframe} Low {fact.latest_swing_low:.2f}"
        if bias == "bearish":
            if fact.latest_swing_low is not None:
                return f"{timeframe} Low {fact.latest_swing_low:.2f}"
            if fact.latest_swing_high is not None:
                return f"{timeframe} High {fact.latest_swing_high:.2f}"
    return "Awaiting clearer 1H/4H reference"


def _has_confirmed_stop_run(liquidity_summary: str) -> bool:
    summary = liquidity_summary.lower()
    return summary.startswith('sell-side liquidity sweep') or summary.startswith(
        'buy-side liquidity sweep'
    )


def _has_named_execution_trigger(
    *,
    execution_timeframe: str,
    entry_model: str,
    liquidity_summary: str,
    execution_displacement: float,
) -> bool:
    if execution_timeframe != "5M":
        return False
    normalized_entry_model = entry_model.lower()
    if "ifvg" in normalized_entry_model or "breaker" in normalized_entry_model:
        return True
    normalized_liquidity = liquidity_summary.lower()
    return (
        _has_confirmed_stop_run(liquidity_summary)
        or (
            execution_displacement >= 1.2
            and (
                normalized_liquidity.startswith("buy-side reclaim")
                or normalized_liquidity.startswith("sell-side pressure")
            )
        )
    )


def _has_execution_confirmation_signal(
    *,
    bias: str,
    entry_model: str,
    execution_reclaimed_high: bool,
    execution_broke_low: bool,
    liquidity_summary: str,
) -> bool:
    normalized_entry_model = entry_model.lower()
    if "ifvg" in normalized_entry_model or "breaker" in normalized_entry_model:
        return True
    if _has_confirmed_stop_run(liquidity_summary):
        return True
    if bias == "bullish":
        return execution_reclaimed_high
    if bias == "bearish":
        return execution_broke_low
    return False


def _resolve_execution_override_bias(
    *,
    raw_bias: str,
    execution_timeframe: str,
    execution_bias: str,
    execution_entry_model: str,
    execution_fact: ChartFrameFacts,
) -> str:
    if raw_bias != "mixed":
        return raw_bias
    if execution_bias not in {"bullish", "bearish"}:
        return raw_bias
    if requires_retrace(execution_bias, execution_fact):
        return raw_bias
    if not _has_named_execution_trigger(
        execution_timeframe=execution_timeframe,
        entry_model=execution_entry_model,
        liquidity_summary=execution_fact.liquidity_summary,
        execution_displacement=execution_fact.displacement,
    ):
        return raw_bias
    if not _has_execution_confirmation_signal(
        bias=execution_bias,
        entry_model=execution_entry_model,
        execution_reclaimed_high=execution_fact.reclaimed_high,
        execution_broke_low=execution_fact.broke_low,
        liquidity_summary=execution_fact.liquidity_summary,
    ):
        return raw_bias
    return execution_bias


def resolve_stop_run_confirmation(
    *,
    liquidity_summary: str,
    draw_on_liquidity: str,
    htf_reference: str,
) -> tuple[bool, str]:
    if not _has_confirmed_stop_run(liquidity_summary):
        return False, "No confirmed stop run at the selected draw on liquidity yet"

    sweep_level = _extract_price(liquidity_summary)
    if sweep_level is None:
        return False, "No confirmed stop run at the selected draw on liquidity yet"

    reference_levels = [
        level
        for level in (_extract_price(draw_on_liquidity), _extract_price(htf_reference))
        if level is not None
    ]
    tolerance = 8.0
    if any(abs(sweep_level - level) <= tolerance for level in reference_levels):
        return True, f"Confirmed stop run: {liquidity_summary}"
    return False, "No confirmed stop run at the selected draw on liquidity yet"


def resolve_confirmation_requirement(
    *,
    base_needs_confirmation: bool,
    stop_run_confirmed: bool,
    daily_profile: str,
    bias: str,
    execution_bias: str,
    execution_displacement: float,
    execution_reclaimed_high: bool,
    execution_broke_low: bool,
    execution_bias_override_active: bool,
    execution_timeframe: str,
    entry_model: str,
    liquidity_summary: str,
    requires_retrace: bool,
) -> bool:
    if stop_run_confirmed:
        return False

    named_trigger = _has_named_execution_trigger(
        execution_timeframe=execution_timeframe,
        entry_model=entry_model,
        liquidity_summary=liquidity_summary,
        execution_displacement=execution_displacement,
    )
    directional_execution = execution_bias in {"bullish", "bearish"} and execution_bias == bias
    execution_signal = _has_execution_confirmation_signal(
        bias=bias,
        entry_model=entry_model,
        execution_reclaimed_high=execution_reclaimed_high,
        execution_broke_low=execution_broke_low,
        liquidity_summary=liquidity_summary,
    )

    reversal_trigger = (
        daily_profile == "reversal"
        and directional_execution
        and named_trigger
        and execution_signal
        and not requires_retrace
    )
    if reversal_trigger:
        return False

    mixed_context_override = (
        execution_bias_override_active
        and base_needs_confirmation
        and directional_execution
        and named_trigger
        and execution_signal
        and not requires_retrace
    )
    if mixed_context_override:
        return False

    continuation_trigger = (
        execution_timeframe == "5M"
        and
        daily_profile == "continuation"
        and directional_execution
        and execution_displacement >= 1.2
        and (
            "IFVG" in entry_model
            or "Breaker" in entry_model
            or "Pullback" in entry_model
            or _has_confirmed_stop_run(liquidity_summary)
        )
    )
    if bias == "bullish" and continuation_trigger and execution_reclaimed_high:
        return False
    if bias == "bearish" and continuation_trigger and execution_broke_low:
        return False
    return True


def _derive_entry_model(
    *,
    frames: dict[str, pd.DataFrame],
    bias: str,
    execution_timeframe: str,
    requires_retrace: bool,
) -> str:
    trigger = derive_execution_entry_trigger(
        frames,
        bias=bias,
        execution_timeframe=execution_timeframe,
    )
    if trigger is not None:
        return trigger

    execution_label = execution_timeframe if execution_timeframe in {"5M", "15M"} else "5M/15M"
    if requires_retrace:
        return f"{execution_label} Pullback"
    return f"{execution_label} Confirmation"


def _derive_tp_model(*, entry: float, stop: float, target: float) -> str:
    risk = abs(entry - stop)
    if risk <= 0:
        return "2R"
    if abs(target - entry) >= risk * 1.95 and abs(target - entry) <= risk * 2.05:
        return "2R"
    return "Draw on Liquidity"


def _extract_price(label: str) -> float | None:
    matches = re.findall(r'(-?\d+(?:\.\d+)?)', label)
    if not matches:
        return None
    return float(matches[-1])


def resolve_target_and_tp_model(
    *,
    entry: float,
    stop: float,
    bias: str,
    draw_on_liquidity: str,
) -> tuple[float, str, str]:
    risk = abs(entry - stop)
    if risk <= 0 or bias not in {"bullish", "bearish"}:
        return entry, "2R", "Defaulting to a full 2R objective unless external liquidity is closer."

    two_r_target = entry + (risk * 2.0) if bias == "bullish" else entry - (risk * 2.0)
    liquidity_target = _extract_price(draw_on_liquidity)
    if liquidity_target is None:
        return (
            two_r_target,
            "2R",
            "Defaulting to a full 2R objective unless external liquidity is closer.",
        )

    if bias == "bullish" and entry < liquidity_target < two_r_target:
        return (
            liquidity_target,
            "Draw on Liquidity",
            "External liquidity caps the trade before a full 2R expansion.",
        )
    if bias == "bearish" and entry > liquidity_target > two_r_target:
        return (
            liquidity_target,
            "Draw on Liquidity",
            "External liquidity caps the trade before a full 2R expansion.",
        )
    return (
        two_r_target,
        "2R",
        "A full 2R objective comes before the next meaningful external liquidity target.",
    )


def derive_setup_plan(file_paths: list[str]) -> ChartDerivedPlan | None:
    if not file_paths:
        return None
    frames = load_chart_frames(file_paths, parse_chart_file_name)
    if not frames:
        return None

    facts: dict[str, ChartFrameFacts] = {
        timeframe: frame_bias(frame, timeframe) for timeframe, frame in frames.items()
    }
    ordered_timeframes = sorted(facts, key=lambda tf: _TF_ORDER[tf])
    execution_timeframe = ordered_timeframes[-1]
    execution_frame = frames[execution_timeframe]
    execution_fact = facts[execution_timeframe]
    raw_bias = weighted_bias_score(facts)
    execution_entry_model = derive_execution_entry_trigger(
        frames,
        bias=execution_fact.bias,
        execution_timeframe=execution_timeframe,
    )
    bias = _resolve_execution_override_bias(
        raw_bias=raw_bias,
        execution_timeframe=execution_timeframe,
        execution_bias=execution_fact.bias,
        execution_entry_model=execution_entry_model or "",
        execution_fact=execution_fact,
    )
    execution_bias_override_active = raw_bias != bias
    draw_on_liquidity = _derive_draw_on_liquidity(frames=frames, bias=bias)
    htf_reference = _derive_htf_reference(frames=frames, facts=facts, bias=bias)
    confirmation_needed = needs_confirmation(facts, bias, execution_timeframe)
    retrace_required = requires_retrace(bias, execution_fact)
    daily_profile = derive_daily_profile(execution_frame, bias, execution_fact)
    entry, stop, target = derive_trade_levels(execution_frame, bias, execution_fact)
    reference_context, internal_reference_context = derive_reference_context(frames)
    gap_summary = derive_gap_summary(frames)
    gap_confluence = derive_gap_confluence(
        gap_summary,
        bias=bias,
        current_price=float(execution_frame.iloc[-1]['close']),
    )
    opening_summary = derive_opening_levels_summary(frames, bias=bias)
    pd_array_summary = derive_pd_array_summary(frames, facts, bias, execution_timeframe)
    pd_array_confluence = derive_pd_array_confluence(frames, facts, bias)
    stop_run_confirmed, stop_run_summary = resolve_stop_run_confirmation(
        liquidity_summary=execution_fact.liquidity_summary,
        draw_on_liquidity=draw_on_liquidity,
        htf_reference=htf_reference,
    )
    entry_model = _derive_entry_model(
        frames=frames,
        bias=bias,
        execution_timeframe=execution_timeframe,
        requires_retrace=retrace_required,
    )
    confirmation_needed = resolve_confirmation_requirement(
        base_needs_confirmation=confirmation_needed,
        stop_run_confirmed=stop_run_confirmed,
        daily_profile=daily_profile,
        bias=bias,
        execution_bias=execution_fact.bias,
        execution_displacement=execution_fact.displacement,
        execution_reclaimed_high=execution_fact.reclaimed_high,
        execution_broke_low=execution_fact.broke_low,
        execution_bias_override_active=execution_bias_override_active,
        execution_timeframe=execution_timeframe,
        entry_model=entry_model,
        liquidity_summary=execution_fact.liquidity_summary,
        requires_retrace=retrace_required,
    )
    if (
        not stop_run_confirmed
        and not confirmation_needed
        and daily_profile == "continuation"
    ):
        stop_run_summary = "No stop run required; continuation structure is already confirmed."
    target, tp_model, target_reason = resolve_target_and_tp_model(
        entry=entry,
        stop=stop,
        bias=bias,
        draw_on_liquidity=draw_on_liquidity,
    )
    return ChartDerivedPlan(
        bias=bias,
        daily_profile=daily_profile,
        entry=entry,
        stop=stop,
        target=target,
        liquidity_summary=execution_fact.liquidity_summary,
        reference_context=reference_context,
        internal_reference_context=internal_reference_context,
        draw_on_liquidity=draw_on_liquidity,
        htf_reference=htf_reference,
        stop_run_summary=stop_run_summary,
        gap_summary=gap_summary.public_summary,
        gap_confluence=gap_confluence,
        opening_summary=opening_summary.public_summary,
        opening_confluence=opening_summary.confluence,
        pd_array_summary=pd_array_summary.public_summary,
        pd_array_confluence=pd_array_confluence,
        entry_model=entry_model,
        tp_model=tp_model,
        target_reason=target_reason,
        needs_confirmation=confirmation_needed,
        requires_retrace=retrace_required,
    )
