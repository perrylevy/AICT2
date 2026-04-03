from __future__ import annotations

from aict2.macro.dashboard_core import MacroInputs
from aict2.macro.live_cycle import with_live_vix
from aict2.macro.vix_source import fetch_live_vix, parse_vix_from_html


def test_parse_vix_from_html_reads_spot_price_when_number_precedes_label() -> None:
    html = """
    <section>
      <h2>$23.87 VIX Spot Price</h2>
    </section>
    """

    value = parse_vix_from_html(html)

    assert value == 23.87


def test_parse_vix_from_html_reads_spot_price_across_html_tags() -> None:
    html = """
    <section>
      <h2><span>$23.87</span></h2>
      <div><strong>VIX</strong> <em>Spot Price</em></div>
    </section>
    """

    value = parse_vix_from_html(html)

    assert value == 23.87


def test_with_live_vix_overrides_existing_input_when_fetch_succeeds() -> None:
    inputs = MacroInputs(
        bull_percent=50.0,
        bear_percent=50.0,
        fear_greed_score=50.0,
        vix=18.0,
        put_call_ratio=0.75,
        tone_trend="stable",
        major_event_active=False,
        major_event_label=None,
    )

    updated = with_live_vix(inputs, vix_fetcher=lambda: 24.6)

    assert updated.vix == 24.6
    assert updated.bull_percent == 50.0


def test_with_live_vix_keeps_existing_value_when_fetch_fails() -> None:
    inputs = MacroInputs(
        bull_percent=50.0,
        bear_percent=50.0,
        fear_greed_score=50.0,
        vix=18.0,
        put_call_ratio=0.75,
        tone_trend="stable",
        major_event_active=False,
        major_event_label=None,
    )

    updated = with_live_vix(inputs, vix_fetcher=lambda: None)

    assert updated.vix == 18.0


def test_fetch_live_vix_uses_yfinance_fallback_when_cboe_parse_fails() -> None:
    class FakeTicker:
        def history(self, period: str = "1d", interval: str = "1m"):
            _ = period, interval
            return {"Close": [24.6]}

    def fake_ticker(symbol: str):
        assert symbol == "^VIX"
        return FakeTicker()

    value = fetch_live_vix(
        html_loader=lambda url: "<html>No spot price here</html>",
        yfinance_ticker_factory=fake_ticker,
    )

    assert value == 24.6
