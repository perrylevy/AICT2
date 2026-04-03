from __future__ import annotations

from aict2.macro.dashboard_core import MacroInputs, score_macro_dashboard
from aict2.macro.dashboard_renderer import render_macro_dashboard, build_dashboard_payload


def test_render_macro_dashboard_includes_key_sections() -> None:
    score = score_macro_dashboard(
        MacroInputs(
            bull_percent=35.0,
            bear_percent=65.0,
            fear_greed_score=24.0,
            vix=22.4,
            vix_source="cboe",
            put_call_ratio=0.96,
            tone_trend='worsening',
            major_event_active=False,
            major_event_label=None,
        )
    )

    output = render_macro_dashboard(score)

    assert 'Macro Label: Risk-Off' in output
    assert 'Score:' in output
    assert 'VIX: 22.40 (cboe)' in output
    assert 'Volatility Regime: high' in output
    assert 'Event Risk: normal' in output


def test_build_dashboard_payload_preserves_override_reason() -> None:
    score = score_macro_dashboard(
        MacroInputs(
            bull_percent=55.0,
            bear_percent=45.0,
            fear_greed_score=55.0,
            vix=17.0,
            vix_source="fallback",
            put_call_ratio=0.68,
            tone_trend='stable',
            major_event_active=True,
            major_event_label='CPI release imminent',
        )
    )

    payload = build_dashboard_payload(score)

    assert payload['label'] == 'Transition'
    assert payload['event_risk'] == 'high'
    assert payload['override_reason'] == 'CPI release imminent'
    assert 'CPI release imminent' in payload['body']
