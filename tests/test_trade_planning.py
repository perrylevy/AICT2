from __future__ import annotations

import pandas as pd

from aict2.analysis.market_frame import frame_bias, normalize_frame
from aict2.analysis.risk_gate import evaluate_risk_gate
from aict2.analysis.trade_planning import derive_scalp_trade_levels


def _frame(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    return normalize_frame(
        pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close'])
    )


def test_derive_scalp_trade_levels_falls_back_to_named_trigger_when_sweep_is_too_wide() -> None:
    execution_frame = _frame(
        [
            ('2026-02-10T08:25:00-05:00', 25328.75, 25337.50, 25324.25, 25332.00),
            ('2026-02-10T08:30:00-05:00', 25330.75, 25355.75, 25301.50, 25349.00),
            ('2026-02-10T08:35:00-05:00', 25349.00, 25353.00, 25329.25, 25337.50),
            ('2026-02-10T08:40:00-05:00', 25337.25, 25355.50, 25336.25, 25350.00),
            ('2026-02-10T08:45:00-05:00', 25350.50, 25369.00, 25348.00, 25353.75),
            ('2026-02-10T08:50:00-05:00', 25354.25, 25368.25, 25349.00, 25360.50),
            ('2026-02-10T08:55:00-05:00', 25360.75, 25374.50, 25358.50, 25372.75),
            ('2026-02-10T09:00:00-05:00', 25372.50, 25383.25, 25367.25, 25378.50),
            ('2026-02-10T09:05:00-05:00', 25378.25, 25384.75, 25373.75, 25383.75),
            ('2026-02-10T09:10:00-05:00', 25384.00, 25386.00, 25373.25, 25382.75),
            ('2026-02-10T09:15:00-05:00', 25383.25, 25397.50, 25382.00, 25393.50),
            ('2026-02-10T09:20:00-05:00', 25393.00, 25398.00, 25388.25, 25392.25),
            ('2026-02-10T09:25:00-05:00', 25392.25, 25398.00, 25375.75, 25375.75),
            ('2026-02-10T09:30:00-05:00', 25376.25, 25410.25, 25346.25, 25362.25),
            ('2026-02-10T09:35:00-05:00', 25362.25, 25377.75, 25300.00, 25326.50),
            ('2026-02-10T09:40:00-05:00', 25327.25, 25334.75, 25265.25, 25309.75),
        ]
    )
    fact = frame_bias(execution_frame, '5M')

    entry, stop, target, tp_model, target_reason = derive_scalp_trade_levels(
        execution_frame,
        'bearish',
        fact,
        execution_timeframe='5M',
        entry_model='5M IFVG',
        draw_on_liquidity='PDL 24955.50',
        has_higher_timeframe_context=True,
    )
    risk = evaluate_risk_gate(entry=entry, stop=stop, target=target)

    assert entry > 0.0
    assert stop > entry
    assert stop - entry <= 60.0
    assert target < entry
    assert risk.clears_min_rr is True
    assert tp_model == 'Scalp Liquidity'
    assert target_reason == 'Nearest execution liquidity fits the 40-50 point scalp band.'
