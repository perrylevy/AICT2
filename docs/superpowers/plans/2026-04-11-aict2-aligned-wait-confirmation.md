# AICT2 Aligned Wait Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase valid `LIVE SETUP` frequency by releasing aligned `5M` wait cases that are mature enough to trade, without changing counter-draw behavior.

**Architecture:** Keep the draw-first confirmation model from the previous checkpoint, but distinguish “higher timeframe is mixed” from “higher timeframe is opposite.” When there is no opposing higher-timeframe draw and the `5M` setup is already aligned, strong displacement-plus-hold should be able to clear confirmation without touching the strict counter-draw exception.

**Tech Stack:** Python, pytest, pandas

---

### Task 1: Lock the aligned false negatives in tests

**Files:**
- Modify: `tests/test_setup_engine.py`
- Modify: `tests/test_analysis_service.py`
- Test: `tests/test_historical_acceptance.py`

- [ ] Add a failing unit test showing a mixed-HTF but aligned `5M` setup can clear confirmation when there is no opposing draw.
- [ ] Restore a snapshot-level failing test for a mature mixed-HTF `5M IFVG` setup that should be `LIVE SETUP`, not `WAIT`.
- [ ] Keep the historical acceptance `WAIT` cases unchanged to prove the loosening stays scoped.

### Task 2: Implement the minimal aligned confirmation loosening

**Files:**
- Modify: `src/aict2/analysis/setup_engine.py`

- [ ] Add helper logic that treats `higher_timeframe_bias == "mixed"` as eligible for aligned confirmation only when the execution setup is directional and there is no explicit opposing higher-timeframe draw.
- [ ] Reuse the existing displacement-plus-hold and retrace guardrails instead of adding a new confirmation ladder.
- [ ] Leave the strict counter-draw exception unchanged.

### Task 3: Verify behavior on the real February windows

**Files:**
- Modify: `docs/superpowers/plans/2026-04-11-aict2-aligned-wait-confirmation.md`

- [ ] Run the focused setup-engine and analysis-service tests first.
- [ ] Run the full pytest suite.
- [ ] Replay the February 2-13 and February 17-27 `9:40 AM ET` windows and compare `WAIT / NO TRADE / LIVE SETUP` plus `TP / SL` outcomes against commit `0c935db`.
