# AICT2 Confirmation Tuning Design

Date: 2026-04-03
Owner: Codex
Status: Draft for review

## Goal

Reduce false `WAIT` decisions in AICT2 when the execution chart presents a credible trading opportunity, while preserving guardrails against weak or unstructured setups.

This change is motivated by the `9:40 AM ET` Feb 2-13 2026 backtest batch, where all 10 cases resolved to `WAIT`. Investigation showed two main causes:

1. Mixed higher-timeframe context (`Daily` / `1H` disagreement with `5M`) forces confirmation in the base gate.
2. Even when all uploaded charts align, reversal setups default back to `needs_confirmation=True` unless a narrow stop-run confirmation path is satisfied.

The target trading style is an intraday scalp that aims for roughly `40-50` points and is willing to trust a strong `5M` execution trigger even when higher timeframes are mixed.

## Desired Behavior

### Mixed-Signal Execution Override

AICT2 should no longer treat mixed higher-timeframe context as an automatic block when the execution chart shows a strong, named trigger.

For canonical `Daily / 1H / 5M` bundles:

- Keep `WAIT` when the `5M` chart is weak, neutral, or lacks a recognizable setup trigger.
- Allow a mixed-context execution override when all of the following are true:
  - the `5M` execution chart has a directional bias
  - the execution trigger is one of:
    - `IFVG`
    - `Breaker`
    - a clear liquidity sweep with reclaim / close-back-in behavior
  - `requires_retrace` is `False`
  - the existing risk gate still clears
- Do not allow displacement alone to trigger the override.

This preserves higher-timeframe context as a preference, but not as an absolute veto when the execution chart is clearly tradable.

### Aligned Reversal Relaxation

When all uploaded charts are directionally aligned, AICT2 should not default back to `WAIT` for reversal-style setups if the execution chart already provides a valid named trigger.

For aligned cases:

- keep stop-run confirmation as a strong positive signal
- allow aligned reversal setups to become market-ready without requiring the current narrow stop-run proximity check
- still require a real execution trigger and respect retrace and risk constraints

This should unlock cases like the current Feb 2 / Feb 3 examples without broadly weakening mixed-signal handling.

## Non-Goals

- Do not change replay scoring behavior.
- Do not change the existing risk gate thresholds in this pass.
- Do not remove retrace requirements.
- Do not turn AICT2 into an execution-first model that ignores higher-timeframe context entirely.

## Proposed Changes

### 1. Add Explicit Execution Override Logic

Introduce a small decision helper in the setup/confirmation pipeline that answers whether the execution chart is strong enough to override mixed higher-timeframe context.

Inputs should include:

- resolved thesis bias
- execution timeframe facts
- entry model
- liquidity summary
- base confirmation result
- retrace requirement

The helper should return `True` only when:

- bias is directional (`bullish` or `bearish`)
- retrace is not required
- execution chart has a recognized trigger
- execution chart direction agrees with the allowed setup direction

### 2. Loosen the Final Confirmation Resolver

Update the final confirmation resolver so it does not default all aligned reversal setups back to `needs_confirmation=True`.

The resolver should distinguish between:

- weak reversal setup: still `WAIT`
- aligned reversal with named execution trigger: allow progression
- mixed HTF context with no execution trigger: still `WAIT`
- mixed HTF context with guarded execution override: allow progression

### 3. Keep Status Priorities Stable

The status funnel should remain structurally the same:

- `WATCH` for unsupported bundle shape or missing context
- `WAIT` for unresolved setup quality
- `NO TRADE` for invalid business/risk conditions
- `LIVE SETUP` only when confirmation and retrace requirements are both cleared

Only the logic that determines whether confirmation is truly still required should change.

## Backtest Comparison Mode

Add a diagnostic comparison mode to the backtester so one case can be analyzed two ways:

1. normal `3-chart` bundle (`1D / 60 / 5`)
2. `5M-only` execution-chart analysis using the same case timestamp

This mode is diagnostic, not the default scoring path.

The comparison output should show:

- case id
- `3-chart` status
- `5M-only` status
- whether the statuses differ
- if either side is `LIVE SETUP`, the derived entry / stop / target

This allows the user to see when higher-timeframe context is suppressing a setup that the execution chart alone would have taken.

## Testing Strategy

### Unit Tests

Add focused tests for:

- mixed context plus `IFVG` -> confirmation can clear
- mixed context plus `Breaker` -> confirmation can clear
- mixed context plus clear sweep-reclaim -> confirmation can clear
- mixed context plus displacement-only -> still `WAIT`
- aligned reversal plus named trigger -> confirmation can clear
- mixed context plus retrace required -> still `WAIT`

### Regression Checks

Rerun the Feb 2-13 2026 `9:40 AM ET` batch after the change and compare:

- count of `WAIT`
- count of `LIVE SETUP`
- which specific dates changed

Also run the same batch in diagnostic `5M-only` mode to identify where higher-timeframe context still differs materially from the execution chart.

### Safety Checks

- Existing repo tests must continue to pass.
- Existing backtest engine tests must continue to pass.
- The tuning should increase setup availability without turning obviously mixed or weak charts into live setups.

## Rollback

This change should be isolated to the confirmation pipeline and backtest comparison plumbing so it can be reverted cleanly if the new behavior proves too loose.

## Validation Notes

- Before tuning on the Feb 2-13 2026 `9:40 AM ET` batch:
  `SUMMARY total_cases=10 valid_cases=10 invalid_cases=0 watch=0 wait=10 no_trade=0 live_setup=0 tp_hit=0 sl_hit=0 no_entry=0 unresolved=0 no_setup=0`
- After tuning in normal mode:
  `SUMMARY total_cases=10 valid_cases=10 invalid_cases=0 watch=0 wait=7 no_trade=3 live_setup=0 tp_hit=0 sl_hit=0 no_entry=0 unresolved=0 no_setup=0`
- Execution-only comparison differences:
  - `2026-02-04	WAIT	-	three_chart=WAIT	execution_only=NO TRADE	differs=yes`
  - `2026-02-10	NO TRADE	-	three_chart=NO TRADE	execution_only=WAIT	differs=yes`
- Observation:
  The tuned confirmation policy reduced pure `WAIT` outcomes and produced meaningful `3-chart` versus `5M-only` differences, but this sample still produced `0` `LIVE SETUP` cases. The next investigation should focus on whether risk, target sizing, or the execution trigger thresholds remain too restrictive for the user's `40-50` point objective.
