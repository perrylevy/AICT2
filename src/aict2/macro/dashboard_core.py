from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MacroInputs:
    bull_percent: float
    bear_percent: float
    fear_greed_score: float
    vix: float
    put_call_ratio: float
    tone_trend: str
    major_event_active: bool
    major_event_label: str | None
    vix_source: str = 'fallback'


@dataclass(frozen=True, slots=True)
class MacroScore:
    score: int
    label: str
    vix: float
    vix_source: str
    volatility_regime: str
    event_risk: str
    override_reason: str | None


def _volatility_regime(vix: float) -> str:
    if vix > 20:
        return 'high'
    if vix >= 19:
        return 'elevated'
    return 'normal'


def score_macro_dashboard(inputs: MacroInputs) -> MacroScore:
    score = 50

    bear_spread = inputs.bear_percent - inputs.bull_percent
    if bear_spread >= 20:
        score += 12
    elif bear_spread >= 5:
        score += 6
    elif bear_spread <= -20:
        score -= 12
    elif bear_spread <= -5:
        score -= 6

    if inputs.fear_greed_score < 30:
        score += 12
    elif inputs.fear_greed_score < 45:
        score += 4
    elif inputs.fear_greed_score > 60:
        score -= 8

    if inputs.vix > 20:
        score += 12
    elif inputs.vix >= 19:
        score += 5

    if inputs.put_call_ratio >= 0.9:
        score += 10
    elif inputs.put_call_ratio >= 0.75:
        score += 3
    elif inputs.put_call_ratio < 0.65:
        score -= 5

    if inputs.tone_trend == 'worsening':
        score += 8
    elif inputs.tone_trend == 'improving':
        score -= 8

    score = max(0, min(100, score))
    volatility_regime = _volatility_regime(inputs.vix)
    event_risk = 'high' if inputs.major_event_active else 'normal'
    override_reason = inputs.major_event_label if inputs.major_event_active else None

    if inputs.major_event_active:
        label = 'Transition'
    elif abs(score - 50) <= 8 and inputs.tone_trend == 'improving':
        label = 'Transition'
    elif score >= 60:
        label = 'Risk-Off'
    elif score <= 40:
        label = 'Risk-On'
    else:
        label = 'Mixed'

    return MacroScore(
        score=score,
        label=label,
        vix=inputs.vix,
        vix_source=inputs.vix_source,
        volatility_regime=volatility_regime,
        event_risk=event_risk,
        override_reason=override_reason,
    )
