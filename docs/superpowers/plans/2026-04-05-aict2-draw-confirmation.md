# AICT2 Draw Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AICT2 decide 5M setups from draw-on-liquidity first, so aligned displacement-plus-hold setups can go live sooner while counter-draw trades stay rare and heavily confirmed.

**Architecture:** Split higher-timeframe draw bias from execution bias inside the setup engine, then route confirmation through aligned-versus-counter-draw rules instead of the current generic gate. Keep the existing scalp geometry guardrails and historical WAIT acceptance fixtures as the regression boundary.

**Tech Stack:** Python, pytest, pandas

---

### Task 1: Lock the intended behavior in tests

**Files:**
- Modify: `tests/test_setup_engine.py`
- Modify: `tests/test_analysis_service.py`
- Test: `tests/test_real_session_regressions.py`

- [ ] Add failing unit tests for aligned 5M displacement-plus-hold clearing confirmation without a stop run.
- [ ] Add failing unit tests for counter-draw setups staying blocked unless sweep/reclaim, displacement-plus-hold, and target-distance rules all pass.
- [ ] Add or tighten snapshot-level assertions so the new confirmation behavior still produces `WAIT` for the protected historical conflict cases.

### Task 2: Rework setup-engine confirmation around draw alignment

**Files:**
- Modify: `src/aict2/analysis/setup_engine.py`

- [ ] Add helper logic to derive a higher-timeframe draw bias separately from the execution override path.
- [ ] Add helper logic for draw alignment, displacement-plus-hold confirmation, and strict counter-draw exceptions.
- [ ] Update confirmation and retrace resolution to use the new helpers while preserving existing stop/target construction.

### Task 3: Verify the regression boundary and measure behavior

**Files:**
- Modify: `docs/superpowers/plans/2026-04-05-aict2-draw-confirmation.md`

- [ ] Run the focused pytest targets for setup-engine and analysis-service coverage first.
- [ ] Run the historical/regression tests that protect known WAIT cases.
- [ ] Run the full suite, then replay the Feb 2-13 and Feb 17-27 backtest windows to see whether the new confirmation model improves setup frequency without broad regressions.
