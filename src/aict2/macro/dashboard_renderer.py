from __future__ import annotations

from aict2.macro.dashboard_core import MacroScore


def render_macro_dashboard(score: MacroScore) -> str:
    lines = [
        f'Macro Label: {score.label}',
        f'Score: {score.score}',
        f'VIX: {score.vix:.2f} ({score.vix_source})',
        f'Volatility Regime: {score.volatility_regime}',
        f'Event Risk: {score.event_risk}',
    ]
    if score.override_reason:
        lines.append(f'Override: {score.override_reason}')
    return '\n'.join(lines)


def build_dashboard_payload(score: MacroScore) -> dict[str, str | int | None]:
    return {
        'label': score.label,
        'score': score.score,
        'event_risk': score.event_risk,
        'override_reason': score.override_reason,
        'body': render_macro_dashboard(score),
    }
