# AICT2 Backtest Engine Design

## Goal

Add an AICT2-only historical backtest engine that replays deterministic AICT2 analysis against raw TradingView CSV case folders, then scores both the top-level outcome (`WAIT`, `NO TRADE`, `LIVE SETUP`) and the downstream trade path (`NO_ENTRY`, `SL_HIT`, `TP_HIT`, unresolved at EOD) without ever leaking future 1-minute price action into analysis.

## Non-Goals

- Do not modify or depend on AICT v1 runtime behavior.
- Do not call LLM APIs or the AICT v1 Claude harness.
- Do not require manifests or metadata files for case setup.
- Do not reinterpret AICT2 analysis rules during backtesting; the engine must reuse the same deterministic analysis path already used in AICT2.

## Reference Reuse

Useful ideas from `C:\Users\Psus\aict-bot\backtest` may be reused conceptually:

- Separate loader/orchestrator/scorer responsibilities.
- Bulk folder scanning for many historical cases.
- Clear aggregate reporting over per-case outcomes.

The implementation itself must stay AICT2-native and live only in `C:\Users\Psus\aict-bot-v2`.

## Backtest Case Contract

Each historical case lives in its own folder under a root such as `C:\Users\Psus\aict-bot-v2\backtests`.

Example:

```text
backtests/
  2026-03-25-0832/
    analysis/
      CME_MINI_MNQ1!, 1D.csv
      CME_MINI_MNQ1!, 60.csv
      CME_MINI_MNQ1!, 5.csv
    score/
      CME_MINI_MNQ1!, 1.csv
```

Rules:

- `analysis/` contains the raw CSVs AICT2 is allowed to see.
- `score/` contains exactly one raw 1-minute CSV used only for post-decision replay.
- No manifest or sidecar metadata is required.
- `analysis/` supports either 3-chart bundles or single-chart fallback bundles.
- The bundle instrument must be uniform across all charts in the case.

## No-Cheating Boundary

The engine must make future leakage structurally impossible:

- Analysis loader reads only `analysis/`.
- Score loader reads only `score/`.
- The score CSV path is never passed into AICT2 analysis functions.
- Trade replay begins at or after the inferred analysis timestamp and uses only the score stream.

This boundary should be enforced in both implementation and tests.

## Timestamp Inference

The case analysis timestamp is inferred from the last candle in the bundle execution timeframe, not by taking the latest timestamp across all files.

Rules:

- `Daily / 1H / 5M` bundles use the last `5M` candle timestamp.
- `4H / 15M / 1M` bundles use the last `1M` candle timestamp.
- Other supported 3-chart bundles use the last candle from AICT2's execution timeframe.
- Single-chart bundles use the last candle in the only analysis CSV.

Rationale:

- Higher timeframe files are context only.
- The execution timeframe marks the actual decision point that should start scoring.
- This avoids silently shifting the analysis point if a higher timeframe export extends past the execution chart.

## Architecture

Add a new package under `src/aict2/backtest/` with focused modules.

### `models.py`

Responsibilities:

- Define typed dataclasses for a discovered case, per-case analysis result, trade replay result, and aggregate summary.
- Keep the boundary between loader data, AICT2 snapshot data, and report output explicit.

Expected model concepts:

- `BacktestCase`
- `BacktestCaseBundle`
- `BacktestTradeReplay`
- `BacktestCaseResult`
- `BacktestSummary`

### `loader.py`

Responsibilities:

- Scan a root backtest directory for case folders.
- Validate `analysis/` and `score/` structure.
- Read analysis chart metadata without mixing in scoring data.
- Infer the execution timeframe and analysis timestamp from filenames and CSV contents.
- Return typed case objects ready for execution.

Validation behavior:

- Reject missing `analysis/` or `score/`.
- Reject `score/` folders with zero or multiple CSVs.
- Reject mixed instruments.
- Reject malformed or unsupported timeframe bundles.
- Reject cases where the execution timeframe required for timestamp inference is absent.
- Preserve invalid-case reasons in a user-visible result instead of crashing the full run.

### `scoring.py`

Responsibilities:

- Reuse or wrap the existing `aict2.reporting.scoredata` trade-resolution logic.
- Convert AICT2 analysis output into trade replay inputs only when status is `LIVE SETUP`.
- Produce distinct trade replay outcomes.

Trade replay rules:

- `WAIT` and `NO TRADE` are valid decision outcomes and do not enter trade replay.
- `LIVE SETUP` replays the 1-minute score stream from the inferred timestamp forward.
- Entry, stop, and target semantics follow the existing AICT2 scorer behavior.
- Outcome labels should preserve current semantics where possible: `NO_ENTRY`, `SL_HIT`, `TP_HIT`, `ENTRY_NO_RESOLUTION`, or `NO_SETUP` if analysis did not produce usable trade parameters.

### `engine.py`

Responsibilities:

- Run one case end-to-end.
- Call AICT2 deterministic analysis using only `analysis/` files.
- Reuse `build_analysis_snapshot` from `src/aict2/analysis/analysis_service.py`.
- Capture status, thesis, entry, stop, target, and timestamp.
- Invoke trade replay when appropriate.
- Return a typed case result that includes validation or runtime notes.

Behavior:

- The engine must not alter AICT2 production logic just for backtesting.
- `macro_state`, `vix`, and optional bias/profile inputs should have a deterministic default for CLI runs.
- A first version may use stable defaults such as `macro_state="Mixed"` and `vix=18.0` unless later extended with richer scenario inputs.

### `cli.py`

Responsibilities:

- Provide a minimal operator interface.
- Accept a root cases directory.
- Run all cases, print compact per-case output, and print aggregate totals.
- Optionally write machine-readable output such as JSON or TSV if straightforward.

Suggested command shape:

```text
python -m aict2.backtest C:\Users\Psus\aict-bot-v2\backtests
```

## Per-Case Lifecycle

For each case:

1. Discover `analysis/` CSVs.
2. Parse filenames with AICT2's existing chart filename logic.
3. Infer the bundle execution timeframe.
4. Read only enough OHLC data to determine the execution timestamp from the execution chart's last candle.
5. Run `build_analysis_snapshot(...)` using the `analysis/` file list and paths only.
6. Load the separate scoring 1-minute CSV.
7. Replay price action from the inferred analysis timestamp forward only.
8. Produce a result object with decision fields and optional trade replay fields.

Captured output should include:

- Case id / folder name
- Instrument
- Ordered timeframes
- Execution timeframe
- Inferred analysis timestamp
- AICT2 status
- AICT2 thesis state
- Entry / stop / target
- Trade replay outcome
- Score value when applicable
- Validation or execution notes

## Scoring Semantics

The engine should evaluate two layers separately.

### Decision Layer

Track the distribution of AICT2's top-level statuses:

- `WAIT`
- `NO TRADE`
- `LIVE SETUP`
- invalid or skipped cases

These are analysis outcomes, not trade outcomes.

### Trade Replay Layer

Only `LIVE SETUP` cases enter replay scoring.

Track:

- `TP_HIT`
- `SL_HIT`
- `NO_ENTRY`
- `ENTRY_NO_RESOLUTION`
- `NO_SETUP`

Aggregate metrics should keep these dimensions separate:

- total cases
- valid cases
- `WAIT` count
- `NO TRADE` count
- `LIVE SETUP` count
- live-setup entered trade count
- `TP_HIT` count
- `SL_HIT` count
- `NO_ENTRY` count
- unresolved count
- optional win rate over entered trades
- optional setup rate over all valid cases

`WAIT` and `NO TRADE` must not be treated as failed trades.

## Integration Points

The backtester should reuse AICT2 components wherever possible:

- `src/aict2/analysis/analysis_service.py`
- `src/aict2/io/chart_intake.py`
- `src/aict2/io/filename_parsing.py`
- `src/aict2/reporting/scoredata.py`

Preferred approach for scoring reuse:

- Extract a small helper in the new backtest package that uses `score_csv_against_records(...)`, or
- Refactor shared score-resolution internals just enough to let backtest and reporting call the same code.

The backtest package should not reach into Discord-specific execution paths unless a small shared helper naturally belongs there.

## Error Handling

Backtest execution should be batch-friendly:

- A bad case should become a failed case result, not abort the whole run.
- Validation errors should be explicit and actionable.
- CLI output should summarize invalid cases separately from analyzed cases.

Examples of expected invalid reasons:

- missing `analysis/`
- missing `score/`
- unsupported bundle size
- missing execution timeframe CSV
- mixed instruments
- malformed OHLC columns
- empty execution chart
- non-1-minute score chart

## Testing Strategy

Follow TDD for implementation.

Required test areas:

1. Loader tests
   - valid 3-chart case
   - valid single-chart case
   - missing `analysis/`
   - missing `score/`
   - multiple score CSVs
   - mixed instruments
   - unsupported bundle shape
2. Timestamp inference tests
   - `Daily / 1H / 5M` uses `5M`
   - `4H / 15M / 1M` uses `1M`
   - single-chart uses that chart
3. No-cheating tests
   - engine passes only `analysis/` paths into analysis
   - score file cannot affect inferred timestamp or snapshot inputs
4. Scoring tests
   - `LIVE SETUP` resolves through TP/SL/no-entry flows
   - `WAIT` and `NO TRADE` skip replay cleanly
5. End-to-end tests
   - one synthetic case folder runs fully
   - one invalid case folder is reported without aborting the run

Existing tests in `tests/test_scoredata.py`, `tests/test_csv_driven_analysis.py`, and `tests/test_historical_acceptance.py` should be reused as guidance and extended rather than duplicated blindly.

## Initial Delivery Scope

The first implementation should deliver:

- backtest case discovery from folders
- deterministic case execution
- separated status and trade replay scoring
- CLI output for per-case and aggregate summaries
- tests covering loader, inference, replay gating, and at least one end-to-end run

Nice-to-have but not required for the first pass:

- persisted JSON/TSV exports
- richer macro scenario injection
- parallel execution
- database persistence of backtest runs

## Open Decisions Resolved

The following design decisions are finalized for implementation:

- Use per-case folders.
- Use `analysis/` and `score/` subfolders.
- Require raw CSVs only; no manifest.
- Infer timestamp from the execution timeframe's last candle.
- Support both 3-chart bundles and single-chart fallback bundles.
- Score `WAIT`, `NO TRADE`, and `LIVE SETUP` distinctly, then replay only `LIVE SETUP`.
