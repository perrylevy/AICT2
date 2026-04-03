from __future__ import annotations

from aict2.macro.dashboard_core import MacroInputs, score_macro_dashboard


def test_score_macro_dashboard_flags_risk_off_with_high_vol_and_bearish_inputs() -> None:
    result = score_macro_dashboard(
        MacroInputs(
            bull_percent=35.0,
            bear_percent=65.0,
            fear_greed_score=24.0,
            vix=22.4,
            put_call_ratio=0.96,
            tone_trend='worsening',
            major_event_active=False,
            major_event_label=None,
        )
    )

    assert result.label == 'Risk-Off'
    assert result.volatility_regime == 'high'
    assert result.override_reason is None
    assert result.score > 60


def test_score_macro_dashboard_can_return_transition_when_inputs_improve() -> None:
    result = score_macro_dashboard(
        MacroInputs(
            bull_percent=49.0,
            bear_percent=51.0,
            fear_greed_score=42.0,
            vix=19.4,
            put_call_ratio=0.78,
            tone_trend='improving',
            major_event_active=False,
            major_event_label=None,
        )
    )

    assert result.label == 'Transition'
    assert result.volatility_regime == 'elevated'


def test_score_macro_dashboard_uses_override_for_major_event() -> None:
    result = score_macro_dashboard(
        MacroInputs(
            bull_percent=55.0,
            bear_percent=45.0,
            fear_greed_score=55.0,
            vix=17.0,
            put_call_ratio=0.68,
            tone_trend='stable',
            major_event_active=True,
            major_event_label='CPI release imminent',
        )
    )

    assert result.override_reason == 'CPI release imminent'
    assert result.event_risk == 'high'
    assert result.label == 'Transition'
