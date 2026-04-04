from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aict2.analysis.market_map import ChartDerivedPlan, derive_chart_plan
from aict2.analysis.risk_gate import RiskGateResult, evaluate_risk_gate
from aict2.analysis.session_levels import SessionLevels, derive_session_levels_from_paths
from aict2.analysis.session_lens import SessionLens, build_session_lens
from aict2.analysis.trade_thesis import TradeThesis, derive_trade_thesis
from aict2.context.structural_memory import StructuralMemorySnapshot, StructuralMemoryStore
from aict2.io.chart_intake import ChartRequest, build_chart_request


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    instrument: str
    request: ChartRequest
    thesis: TradeThesis
    session: SessionLens
    risk: RiskGateResult
    status: str
    used_structural_memory: bool
    entry: float
    stop: float
    target: float
    liquidity_summary: str
    reference_context: str
    internal_reference_context: str
    draw_on_liquidity: str
    htf_reference: str
    stop_run_summary: str
    gap_summary: str
    gap_confluence: str
    opening_summary: str
    opening_confluence: str
    pd_array_summary: str
    pd_array_confluence: str
    entry_model: str
    tp_model: str
    target_reason: str
    needs_confirmation: bool
    requires_retrace: bool
    session_levels: SessionLevels | None


def _resolve_bias_and_profile(
    request: ChartRequest,
    bias: str | None,
    daily_profile: str | None,
    memory_store: StructuralMemoryStore | None,
    chart_plan: ChartDerivedPlan | None,
) -> tuple[str, str, bool]:
    if request.has_higher_timeframe_context or memory_store is None:
        resolved_bias = bias or (chart_plan.bias if chart_plan else 'mixed')
        resolved_profile = daily_profile or (
            chart_plan.daily_profile if chart_plan else 'transition'
        )
        return resolved_bias, resolved_profile, False

    memory = memory_store.load_latest(request.instrument)
    if memory is None:
        resolved_bias = bias or (chart_plan.bias if chart_plan else 'mixed')
        resolved_profile = daily_profile or (
            chart_plan.daily_profile if chart_plan else 'transition'
        )
        return resolved_bias, resolved_profile, False

    resolved_bias = bias or memory.thesis_state or (chart_plan.bias if chart_plan else 'mixed')
    resolved_profile = daily_profile or memory.daily_profile or (
        chart_plan.daily_profile if chart_plan else 'transition'
    )
    return resolved_bias, resolved_profile, True


def _resolve_reference_context(
    request: ChartRequest,
    memory_store: StructuralMemoryStore | None,
    chart_plan: ChartDerivedPlan | None,
) -> str:
    if request.has_higher_timeframe_context:
        if chart_plan is not None:
            return chart_plan.reference_context
        return 'Using latest uploaded higher-timeframe structure only'

    if memory_store is not None:
        memory = memory_store.load_latest(request.instrument)
        if memory is not None and memory.reference_context:
            return memory.reference_context

    if chart_plan is not None and chart_plan.reference_context:
        return chart_plan.reference_context
    return 'Awaiting richer prior day / week / 20-day context'


def _derive_status(
    request: ChartRequest,
    thesis: TradeThesis,
    risk: RiskGateResult,
    used_structural_memory: bool,
    needs_confirmation: bool,
    requires_retrace: bool,
    session: SessionLens,
    entry: float,
    stop: float,
    target: float,
) -> str:
    if request.mode == 'multi' and not request.is_canonical_bundle:
        return 'WATCH'
    if not request.has_higher_timeframe_context and not used_structural_memory:
        return 'WATCH'
    if (
        session.session_phase == 'overnight'
        and not risk.clears_min_rr
        and risk.rr < 1.0
    ):
        return 'NO TRADE'
    if (
        thesis.state in {'bullish', 'bearish'}
        and entry == 0.0
        and stop == 0.0
        and target == 0.0
    ):
        return 'WAIT'
    if needs_confirmation:
        return 'WAIT'
    if requires_retrace:
        return 'WAIT'
    if thesis.allowed_business == 'no_trade':
        if thesis.state in {'mixed', 'neutral', 'transition'}:
            return 'WAIT'
        return 'NO TRADE'
    if session.session_phase in {'lunch', 'afternoon'} and not session.active_windows:
        return 'WAIT'
    if not risk.clears_min_rr or risk.max_contracts <= 0:
        return 'NO TRADE'
    return 'LIVE SETUP'


def build_analysis_snapshot(
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
) -> AnalysisSnapshot:
    request = build_chart_request(file_names)
    chart_plan = derive_chart_plan(file_paths or []) if file_paths else None
    session_levels = (
        derive_session_levels_from_paths(file_paths or [], current_time=current_time)
        if file_paths
        else None
    )
    resolved_bias, resolved_profile, used_structural_memory = _resolve_bias_and_profile(
        request=request,
        bias=bias,
        daily_profile=daily_profile,
        memory_store=memory_store,
        chart_plan=chart_plan,
    )
    resolved_entry = entry if entry > 0 else (chart_plan.entry if chart_plan else 0.0)
    resolved_stop = stop if stop > 0 else (chart_plan.stop if chart_plan else 0.0)
    resolved_target = target if target > 0 else (chart_plan.target if chart_plan else 0.0)
    resolved_liquidity_summary = (
        chart_plan.liquidity_summary
        if chart_plan is not None
        else 'Awaiting cleaner liquidity interaction for this session'
    )
    resolved_reference_context = _resolve_reference_context(
        request=request,
        memory_store=memory_store,
        chart_plan=chart_plan,
    )
    resolved_internal_reference_context = (
        chart_plan.internal_reference_context
        if chart_plan is not None
        else resolved_reference_context
    )
    resolved_gap_summary = (
        chart_plan.gap_summary if chart_plan is not None else 'No active NDOG/NWOG'
    )
    resolved_draw_on_liquidity = (
        chart_plan.draw_on_liquidity
        if chart_plan is not None
        else 'Awaiting clearer draw on liquidity'
    )
    resolved_htf_reference = (
        chart_plan.htf_reference
        if chart_plan is not None
        else 'Awaiting clearer 1H/4H reference'
    )
    resolved_stop_run_summary = (
        chart_plan.stop_run_summary
        if chart_plan is not None
        else 'No confirmed stop run yet'
    )
    resolved_gap_confluence = (
        chart_plan.gap_confluence
        if chart_plan is not None
        else 'No active NDOG/NWOG is shaping the current path.'
    )
    resolved_opening_summary = (
        chart_plan.opening_summary
        if chart_plan is not None
        else 'Opening levels unavailable from current upload'
    )
    resolved_opening_confluence = (
        chart_plan.opening_confluence
        if chart_plan is not None
        else 'Opening prices are informational only right now.'
    )
    resolved_pd_array_summary = (
        chart_plan.pd_array_summary if chart_plan is not None else 'No clear PD array ranked yet'
    )
    resolved_pd_array_confluence = (
        chart_plan.pd_array_confluence
        if chart_plan is not None
        else 'Daily arrays are informational only right now.'
    )
    resolved_entry_model = (
        chart_plan.entry_model if chart_plan is not None else '5M/15M Confirmation'
    )
    resolved_tp_model = (
        chart_plan.tp_model if chart_plan is not None else '2R'
    )
    resolved_target_reason = (
        chart_plan.target_reason
        if chart_plan is not None
        else 'Defaulting to a full 2R objective unless external liquidity is closer.'
    )
    thesis = derive_trade_thesis(
        bias=resolved_bias,
        daily_profile=resolved_profile,
        has_higher_timeframe_context=(
            request.has_higher_timeframe_context or used_structural_memory
        ),
    )
    session = build_session_lens(current_time=current_time, macro_state=macro_state, vix=vix)
    risk = evaluate_risk_gate(entry=resolved_entry, stop=resolved_stop, target=resolved_target)
    needs_confirmation = chart_plan.needs_confirmation if chart_plan is not None else False
    requires_retrace = chart_plan.requires_retrace if chart_plan is not None else False
    status = _derive_status(
        request=request,
        thesis=thesis,
        risk=risk,
        used_structural_memory=used_structural_memory,
        needs_confirmation=needs_confirmation,
        requires_retrace=requires_retrace,
        session=session,
        entry=resolved_entry,
        stop=resolved_stop,
        target=resolved_target,
    )

    if memory_store is not None and request.has_higher_timeframe_context:
        memory_store.save_latest(
            StructuralMemorySnapshot(
                instrument=request.instrument,
                thesis_state=thesis.state,
                daily_profile=thesis.daily_profile,
                source_timeframes=request.ordered_timeframes,
                lookback_days=20,
                reference_context=resolved_reference_context,
            )
        )

    return AnalysisSnapshot(
        instrument=request.instrument,
        request=request,
        thesis=thesis,
        session=session,
        risk=risk,
        status=status,
        used_structural_memory=used_structural_memory,
        entry=resolved_entry,
        stop=resolved_stop,
        target=resolved_target,
        liquidity_summary=resolved_liquidity_summary,
        reference_context=resolved_reference_context,
        internal_reference_context=resolved_internal_reference_context,
        draw_on_liquidity=resolved_draw_on_liquidity,
        htf_reference=resolved_htf_reference,
        stop_run_summary=resolved_stop_run_summary,
        gap_summary=resolved_gap_summary,
        gap_confluence=resolved_gap_confluence,
        opening_summary=resolved_opening_summary,
        opening_confluence=resolved_opening_confluence,
        pd_array_summary=resolved_pd_array_summary,
        pd_array_confluence=resolved_pd_array_confluence,
        entry_model=resolved_entry_model,
        tp_model=resolved_tp_model,
        target_reason=resolved_target_reason,
        needs_confirmation=needs_confirmation,
        requires_retrace=requires_retrace,
        session_levels=session_levels,
    )

