## Objective

Increase valid AICT2 trade scenarios without reopening broad wrong-direction behavior.

## Constraint

Keep the strict counter-draw exception for strong higher-timeframe opposition. Only revisit the cases where the full stack is already mixed, but the 5M reversal is strong enough that the remaining higher-timeframe disagreement looks stale rather than decisive.

## Plan

1. Add a narrow confirmation override for `raw_bias == mixed` cases where:
   - the higher timeframe opposes the final bias,
   - the setup is a `5M` reversal,
   - the execution trigger is named,
   - displacement plus hold are already present,
   - no retrace is still required.
2. Keep the existing strong counter-draw exception untouched for directional higher-timeframe opposition.
3. Verify the change with focused confirmation tests and the February replay windows.
