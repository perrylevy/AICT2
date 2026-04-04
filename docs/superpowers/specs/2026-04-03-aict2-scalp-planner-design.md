# AICT2 Scalp Planner Design

Date: 2026-04-03
Owner: Codex
Status: Draft for review

## Goal

Make AICT2 produce execution-ready scalp setups for the user's actual trading style.

The blocker audit on the Feb 2-13 2026 `9:40 AM ET` batch showed that AICT2 is still constructing many trades with stops that are too wide for scalp trading. Even after confirmation tuning, the system still produced `0` `LIVE SETUP` cases because:

1. `5M` execution plans often used broad structure-derived stops of `60-170+` points.
2. The risk gate rejected many otherwise directional setups because those stops implied `max_contracts=0`.
3. Some mixed higher-timeframe cases still collapsed into `mixed` / `no_trade` before a scalp-style execution plan could be expressed.

The user would never take a `100+` point stop. AICT2 should therefore treat `5M` and `1M` execution as scalp planning by default.

## Desired Behavior

### Execution-Timeframe Default

Scalp planning should attach to the execution timeframe, not to a specific bundle.

- `1D / 1H / 5M` bundles should use a default scalp planner on `5M`.
- `4H / 15M / 1M` bundles should use a default scalp planner on `1M`.
- Higher timeframes continue to shape thesis, context, and draw on liquidity.
- The execution timeframe becomes the primary source for entry, stop, and target construction.

### Trigger-First Invalidation

The scalp planner should use local setup invalidation before broader structure.

Priority:

1. liquidity sweep reclaim / close-back-in invalidation
2. `IFVG` invalidation
3. `Breaker` invalidation
4. nearest execution swing only as fallback

The stop should sit just beyond the trigger invalidation, with a small execution buffer.

### Scalp Stop Envelope

AICT2 should no longer default to broad execution stops on `5M` or `1M`.

- minimum stop floor: roughly `12-15` points
- preferred stop shape: honest local invalidation with a small buffer
- if the only valid stop is much wider than a scalp should allow, the setup should be rejected instead of silently becoming a swing-style trade

This is meant to stop cases like Feb 2 / 10 / 11 / 13 from producing `100+` point stops for a scalp workflow.

### Liquidity-Led Scalp Targeting

Targets should be built from nearby liquidity inside a scalp band instead of defaulting to broad `2R`.

Target policy:

- first search for the nearest valid directional liquidity target in the execution chart or immediate intraday context
- if that target is inside roughly `40-50` points, use it
- if liquidity is farther away, cap the target inside the scalp band instead of forcing a large move
- if liquidity is too close to support acceptable RR with the trigger-based stop, return `NO TRADE`

This keeps the system aligned to the user's real objective: capture a realistic `40-50` point move, not a structure-maximizing expansion.

## Status Funnel Changes

The status funnel should remain recognizable, but its inputs should better reflect scalp trading.

- `WAIT` still means the setup is not mature enough yet.
- `NO TRADE` should mean the setup is mature enough to evaluate, but the scalp construction does not support a valid trade.
- `LIVE SETUP` should mean confirmation is clear, retrace is not required, and the scalp plan passes risk and RR checks.

This means AICT2 should stop using `WAIT` as a catch-all for setups that are actually directionally valid but untradeable for scalp reasons.

## Proposed Changes

### 1. Add An Explicit Scalp Trade Constructor

Introduce an execution-timeframe trade constructor dedicated to scalp planning.

Inputs:

- execution timeframe
- execution frame facts
- derived entry trigger
- draw on liquidity
- recent execution candles

Outputs:

- scalp entry
- scalp stop
- scalp target
- target model label
- target reason

The constructor should activate by default for execution timeframes `5M` and `1M`.

### 2. Keep Thesis And Confirmation Separate From Trade Construction

The thesis engine and confirmation engine should still answer:

- what direction is allowed?
- is the setup mature enough?

The scalp planner should answer:

- where is the honest invalidation?
- where is the nearest realistic scalp target?
- does the trade make sense for the user's stop and objective constraints?

This separation is important so AICT2 does not confuse setup maturity with trade sizing.

### 3. Rework Default Target Selection For Scalp Execution

Current behavior often prefers `2R` unless nearby external liquidity is closer.

For scalp execution:

- liquidity should drive target selection first
- the scalp band should cap oversized targets
- `2R` can still be used when it naturally falls inside the scalp band and the liquidity picture supports it

### 4. Tighten Rejection Semantics

For `5M` and `1M` scalp plans:

- if no clear directional plan exists, keep `WAIT`
- if a directional plan exists but valid scalp invalidation and target cannot produce sane RR or sizing, mark `NO TRADE`
- do not allow wide stops to drift into `LIVE SETUP` just because higher timeframe context is strong

## Non-Goals

- Do not change replay scoring behavior.
- Do not rewrite the entire thesis engine.
- Do not remove higher-timeframe context from AICT2.
- Do not turn every directional candle into a live scalp setup.

## Testing Strategy

### Unit Tests

Add tests showing that:

- `5M` scalp plans use trigger-first invalidation before swing fallback
- `1M` scalp plans use the same logic
- scalp stops respect a `12-15` point minimum floor
- scalp targets prefer nearby liquidity inside the `40-50` point band
- setups that require `100+` point stops are rejected rather than promoted

### Regression Checks

Rerun the Feb 2-13 2026 `9:40 AM ET` batch and record:

- how many cases move from `WAIT` or `NO TRADE` to `LIVE SETUP`
- how many cases still fail because of confirmation
- how many still fail because the scalp plan is genuinely invalid
- whether the new stops now match the user's actual risk tolerance

### Safety Checks

- Existing repo tests must continue to pass.
- Confirmation tuning behavior must remain intact unless explicitly superseded by the scalp planner.
- `4H / 15M / 1M` support must be covered so the new planner is not `5M`-only in practice.

## Rollback

The scalp planner should be isolated to trade construction and status interpretation for execution timeframes `5M` and `1M`, so it can be reverted cleanly if it creates too many low-quality setups.
