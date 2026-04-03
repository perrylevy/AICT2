from __future__ import annotations

import re
from collections.abc import Callable
from urllib.request import Request, urlopen

DEFAULT_VIX_URL = "https://www.cboe.com/tradable_products/vix/"

HtmlLoader = Callable[[str], str]
TickerFactory = Callable[[str], object]


def parse_vix_from_html(html: str) -> float | None:
    text = re.sub(r"<[^>]+>", " ", html)
    compact = re.sub(r"\s+", " ", text)
    patterns = (
        r"\$([0-9]+(?:\.[0-9]+)?)\s+VIX Spot Price",
        r"VIX Spot Price.{0,80}?\$([0-9]+(?:\.[0-9]+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if match is None:
            continue
        value = float(match.group(1))
        if 5.0 <= value <= 100.0:
            return value
    return None


def _default_html_loader(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "AICT2 Macro Publisher/1.0",
        },
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="ignore")


def _default_yfinance_ticker_factory(symbol: str) -> object:
    import yfinance

    return yfinance.Ticker(symbol)


def _fetch_vix_from_yfinance(
    *,
    ticker_factory: TickerFactory = _default_yfinance_ticker_factory,
) -> float | None:
    try:
        ticker = ticker_factory("^VIX")
        history = ticker.history(period="1d", interval="1m")
    except Exception:
        return None

    close_series = getattr(history, "get", lambda key, default=None: default)("Close", None)
    if close_series is None:
        return None
    try:
        last_value = close_series[-1]
    except Exception:
        return None
    try:
        value = float(last_value)
    except Exception:
        return None
    if 5.0 <= value <= 100.0:
        return value
    return None


def fetch_live_vix(
    *,
    url: str = DEFAULT_VIX_URL,
    html_loader: HtmlLoader = _default_html_loader,
    yfinance_ticker_factory: TickerFactory = _default_yfinance_ticker_factory,
) -> float | None:
    try:
        html = html_loader(url)
    except Exception:
        html = ""
    parsed = parse_vix_from_html(html)
    if parsed is not None:
        return parsed
    return _fetch_vix_from_yfinance(ticker_factory=yfinance_ticker_factory)
