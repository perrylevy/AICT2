from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.request import Request, urlopen

DEFAULT_VIX_URL = "https://www.cboe.com/tradable_products/vix/"
DEFAULT_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?range=1d&interval=1m"

HtmlLoader = Callable[[str], str]
TickerFactory = Callable[[str], object]
JsonLoader = Callable[[str], object]


class VixReading(tuple):
    __slots__ = ()

    def __new__(cls, value: float, source: str):
        return super().__new__(cls, (value, source))

    @property
    def value(self) -> float:
        return self[0]

    @property
    def source(self) -> str:
        return self[1]


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


def _default_json_loader(url: str) -> object:
    request = Request(
        url,
        headers={
            "User-Agent": "AICT2 Macro Publisher/1.0",
        },
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def _fetch_vix_from_yahoo_chart(
    *,
    url: str = DEFAULT_YAHOO_CHART_URL,
    json_loader: JsonLoader = _default_json_loader,
) -> VixReading | None:
    try:
        payload = json_loader(url)
        result = payload["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    except Exception:
        return None
    try:
        values = [float(value) for value in result if value is not None]
    except Exception:
        return None
    if not values:
        return None
    value = values[-1]
    if 5.0 <= value <= 100.0:
        return VixReading(value=value, source="yahoo-chart")
    return None


def _fetch_vix_from_yfinance(
    *,
    ticker_factory: TickerFactory = _default_yfinance_ticker_factory,
) -> VixReading | None:
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
        return VixReading(value=value, source="yfinance")
    return None


def fetch_live_vix(
    *,
    url: str = DEFAULT_VIX_URL,
    html_loader: HtmlLoader = _default_html_loader,
    yahoo_chart_loader: JsonLoader = _default_json_loader,
    yfinance_ticker_factory: TickerFactory = _default_yfinance_ticker_factory,
) -> VixReading | None:
    try:
        html = html_loader(url)
    except Exception:
        html = ""
    parsed = parse_vix_from_html(html)
    if parsed is not None:
        return VixReading(value=parsed, source="cboe")
    yahoo_chart = _fetch_vix_from_yahoo_chart(json_loader=yahoo_chart_loader)
    if yahoo_chart is not None:
        return yahoo_chart
    return _fetch_vix_from_yfinance(ticker_factory=yfinance_ticker_factory)
