from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradeThesis:
    state: str
    allowed_business: str
    daily_profile: str
    has_higher_timeframe_context: bool


def derive_trade_thesis(
    bias: str,
    daily_profile: str,
    has_higher_timeframe_context: bool,
) -> TradeThesis:
    if bias == 'bullish':
        allowed_business = 'long_only'
    elif bias == 'bearish':
        allowed_business = 'short_only'
    elif bias == 'neutral':
        allowed_business = 'both'
    else:
        allowed_business = 'no_trade'

    return TradeThesis(
        state=bias,
        allowed_business=allowed_business,
        daily_profile=daily_profile,
        has_higher_timeframe_context=has_higher_timeframe_context,
    )
