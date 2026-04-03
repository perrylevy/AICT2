from __future__ import annotations

from aict2.analysis.analysis_service import AnalysisSnapshot
from aict2.analysis.mark_douglas import build_mark_douglas_verdict


def _bundle_note(snapshot: AnalysisSnapshot) -> str:
    profile = snapshot.request.bundle_profile
    if profile == 'micro':
        return 'Micro bundle active; expect more noise and manage execution discipline tightly.'
    if profile == 'custom':
        return 'Custom bundle in use; trust the setup only if the HTF story is still obvious.'
    if profile == 'structural':
        return 'Structural bundle active; prioritize thesis quality over forcing immediate execution.'
    if profile == 'balanced':
        return 'Balanced bundle active; context and execution are aligned for standard intraday reads.'
    return 'Execution bundle active; lean on confirmation and let the lower timeframe refine the entry.'


def _entry_mode(snapshot: AnalysisSnapshot) -> str:
    if snapshot.requires_retrace:
        return 'Retrace Entry'
    if snapshot.needs_confirmation:
        return 'Confirmation Entry'
    return 'Market-Ready Entry'


def _allowed_business_label(snapshot: AnalysisSnapshot) -> str:
    mapping = {
        'long_only': 'Look for Longs',
        'short_only': 'Look for Shorts',
        'both': 'Both Sides in Play',
        'no_trade': 'Stand Aside',
    }
    return mapping.get(snapshot.thesis.allowed_business, snapshot.thesis.allowed_business)


def _setup_reason(snapshot: AnalysisSnapshot) -> str:
    if (
        snapshot.status == 'LIVE SETUP'
        and snapshot.stop_run_summary.startswith('No stop run required; continuation structure')
    ):
        return 'Continuation structure is confirmed and market-ready.'
    if snapshot.status == 'WAIT':
        if snapshot.requires_retrace:
            return 'Stretched move, retrace needed before entry.'
        if snapshot.needs_confirmation:
            return 'Liquidity shift not confirmed yet.'
        if snapshot.thesis.allowed_business == 'no_trade':
            return 'Bias is mixed, neutral, or transitional right now.'
        if snapshot.session.session_phase in {'lunch', 'afternoon'} and not snapshot.session.active_windows:
            return 'Session timing is weak for a fresh entry.'
        return 'Patience is still the higher-quality decision here.'
    if snapshot.status == 'WATCH':
        return 'Context is useful, but execution quality is not there yet.'
    if snapshot.status == 'NO TRADE':
        if not snapshot.risk.clears_min_rr or snapshot.risk.max_contracts <= 0:
            return 'Risk-to-reward or sizing does not fit the plan.'
        return 'Current structure does not justify a trade.'
    return 'Market-ready now if price respects the plan.'


def _current_posture(snapshot: AnalysisSnapshot) -> str:
    if snapshot.requires_retrace:
        return 'Waiting for retrace into the entry zone.'
    if snapshot.needs_confirmation:
        return 'Waiting for displacement and confirmation.'
    if snapshot.status == 'LIVE SETUP':
        return 'Executable now if price respects the stated levels.'
    if snapshot.status == 'WATCH':
        return 'Context is useful, but higher-quality confirmation is still needed.'
    return 'Stand aside until the market offers a cleaner edge.'


def _has_executable_plan(snapshot: AnalysisSnapshot) -> bool:
    return snapshot.entry > 0 and snapshot.stop > 0 and snapshot.target > 0


def _confluence_line(snapshot: AnalysisSnapshot) -> str:
    return (
        f'{snapshot.gap_confluence} '
        f'{snapshot.opening_confluence} '
        f'{snapshot.pd_array_confluence}'
    )


def _account_fit_line(snapshot: AnalysisSnapshot) -> str:
    if snapshot.risk.max_contracts <= 0:
        return 'Account Fit: Not executable at the current $120 risk budget.'
    contract_label = 'contract' if snapshot.risk.max_contracts == 1 else 'contracts'
    return f'Account Fit: Executable with up to {snapshot.risk.max_contracts} {contract_label} at the current $120 risk budget.'


def _entry_plan_lines(snapshot: AnalysisSnapshot) -> list[str]:
    base_lines = [
        'Entry Plan',
        f'- Bundle Profile: {snapshot.request.bundle_profile}',
        f'- Execution Timeframe: {snapshot.request.execution_timeframe}',
        f'- Entry Trigger: {snapshot.entry_model}',
        f'- Entry Mode: {_entry_mode(snapshot)}',
        f'- Current Posture: {_current_posture(snapshot)}',
    ]
    if not _has_executable_plan(snapshot):
        return base_lines + [
            '- Entry: No executable levels yet',
            '- Stop: No executable levels yet',
            '- TP1: No executable levels yet',
            '',
        ]
    return base_lines + [
        f'- Entry: {snapshot.entry:.0f}',
        f'- Stop: {snapshot.stop:.0f}',
        f'- TP1: {snapshot.target:.0f}',
        '',
    ]


def _risk_gate_lines(snapshot: AnalysisSnapshot) -> list[str]:
    wait_not_executable = (
        snapshot.status == 'WAIT'
        and _has_executable_plan(snapshot)
        and snapshot.risk.max_contracts <= 0
    )
    if not _has_executable_plan(snapshot):
        return [
            'Risk Gate',
            f'- {_account_fit_line(snapshot)}',
            '- Stop Distance: Not applicable until an executable plan forms',
            '- R:R: Not applicable until an executable plan forms',
            '- TP Model: Awaiting executable plan',
            '- Target Reason: A valid target is only set once entry and invalidation are defined.',
            f'- Max Contracts @ $120 risk: {snapshot.risk.max_contracts}',
            '',
        ]
    return [
        'Risk Gate',
        f'- {_account_fit_line(snapshot)}',
        *(
            [
                '- Execution Note: The idea is valid, but it needs a tighter retrace or smaller invalidation to fit the account.'
            ]
            if wait_not_executable
            else []
        ),
        f'- Stop Distance: {snapshot.risk.stop_distance}',
        f'- R:R: {snapshot.risk.rr:.2f}',
        f'- TP Model: {snapshot.tp_model}',
        f'- Target Reason: {snapshot.target_reason}',
        f'- Max Contracts @ $120 risk: {snapshot.risk.max_contracts}',
        '',
    ]


def render_analysis_output(snapshot: AnalysisSnapshot) -> str:
    session_levels = (
        snapshot.session_levels.summary() if snapshot.session_levels else 'Unavailable from current upload'
    )
    session_interaction = (
        snapshot.session_levels.interaction
        if snapshot.session_levels
        else 'Unavailable from current upload'
    )
    lines = [
        f'Status: {snapshot.status} - {_setup_reason(snapshot)}',
        '',
        'Trade Thesis',
        f'- Setup Reason: {_setup_reason(snapshot)}',
        f'- Bias: {snapshot.thesis.state}',
        f'- Daily Profile: {snapshot.thesis.daily_profile}',
        f'- Draw on Liquidity: {snapshot.draw_on_liquidity}',
        f'- HTF Reference: {snapshot.htf_reference}',
        f'- Stop Run: {snapshot.stop_run_summary}',
        f'- HTF Context: {snapshot.reference_context}',
        f'- Confluence: {_confluence_line(snapshot)}',
        f'- Opening Context: {snapshot.opening_summary}',
        f'- Gap Context: {snapshot.gap_summary}',
        f'- Liquidity: {snapshot.liquidity_summary}',
        f'- PD Arrays: {snapshot.pd_array_summary}',
        f'- Allowed Business: {_allowed_business_label(snapshot)}',
        '',
        *_entry_plan_lines(snapshot),
        *_risk_gate_lines(snapshot),
        'Session Awareness',
        f'- Analysis Window: {snapshot.session.analysis_window}',
        f'- Macro State: {snapshot.session.macro_state}',
        f'- Volatility Regime: {snapshot.session.volatility_regime}',
        f'- Active Windows: {", ".join(snapshot.session.active_windows) if snapshot.session.active_windows else "none"}',
        f'- Session Interaction: {session_interaction}',
        f'- Session Levels: {session_levels}',
        f'- Bundle Note: {_bundle_note(snapshot)}',
        '',
        'Mark Douglas Verdict',
        build_mark_douglas_verdict(snapshot),
    ]
    return '\n'.join(lines)
