from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass(frozen=True, slots=True)
class RiskGateResult:
    stop_distance: float
    rr: float
    max_contracts: int
    clears_min_rr: bool


def evaluate_risk_gate(
    entry: float,
    stop: float,
    target: float,
    point_value: float = 2.0,
    risk_per_trade: float = 120.0,
    min_rr: float = 1.75,
) -> RiskGateResult:
    stop_distance = abs(entry - stop)
    reward_distance = abs(target - entry)
    rr = 0.0 if stop_distance == 0 else reward_distance / stop_distance
    cost_per_contract = stop_distance * point_value
    max_contracts = 0 if cost_per_contract == 0 else floor(risk_per_trade / cost_per_contract)
    return RiskGateResult(
        stop_distance=stop_distance,
        rr=rr,
        max_contracts=max_contracts,
        clears_min_rr=rr >= min_rr,
    )
