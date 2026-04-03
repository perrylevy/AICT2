from __future__ import annotations

from aict2.macro.publisher import create_hourly_dashboard_payload


def test_create_hourly_dashboard_payload_composes_score_and_body() -> None:
    payload = create_hourly_dashboard_payload(
        bull_percent=35.0,
        bear_percent=65.0,
        fear_greed_score=24.0,
        vix=22.4,
        put_call_ratio=0.96,
        tone_trend='worsening',
        major_event_active=False,
        major_event_label=None,
    )

    assert payload['label'] == 'Risk-Off'
    assert payload['event_risk'] == 'normal'
    assert 'Macro Label: Risk-Off' in payload['body']


def test_create_hourly_dashboard_payload_preserves_major_event_override() -> None:
    payload = create_hourly_dashboard_payload(
        bull_percent=55.0,
        bear_percent=45.0,
        fear_greed_score=55.0,
        vix=17.0,
        put_call_ratio=0.68,
        tone_trend='stable',
        major_event_active=True,
        major_event_label='Powell speech imminent',
    )

    assert payload['label'] == 'Transition'
    assert payload['override_reason'] == 'Powell speech imminent'
    assert 'Powell speech imminent' in payload['body']
