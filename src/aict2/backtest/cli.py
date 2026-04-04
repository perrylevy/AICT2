from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aict2.backtest.engine import run_backtest_cases, summarize_results
from aict2.backtest.loader import discover_backtest_cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aict2.backtest")
    parser.add_argument(
        "--compare-execution-only",
        action="store_true",
        help="Also run each case as execution-timeframe-only analysis for comparison",
    )
    parser.add_argument("cases_dir", help="Directory containing per-case backtest folders")
    args = parser.parse_args(argv)
    cases_dir = Path(args.cases_dir)

    if not cases_dir.is_dir():
        print(f"Backtest cases directory not found: {cases_dir}", file=sys.stderr)
        return 1

    cases = discover_backtest_cases(cases_dir)
    results = run_backtest_cases(cases, compare_execution_only=args.compare_execution_only)
    summary = summarize_results(results)

    for result in results:
        status = result.validation_error or result.status or "UNKNOWN"
        replay = result.trade_outcome or "-"
        parts = [result.case_id, status, replay]
        if result.comparison is not None:
            parts.extend(
                [
                    f"three_chart={result.comparison.primary_status or '-'}",
                    f"execution_only={result.comparison.execution_only_status or '-'}",
                    f"differs={'yes' if result.comparison.differs else 'no'}",
                ]
            )
        print("\t".join(parts))

    print(
        "SUMMARY "
        f"total_cases={summary.total_cases} "
        f"valid_cases={summary.valid_cases} "
        f"invalid_cases={summary.invalid_cases} "
        f"watch={summary.watch_count} "
        f"wait={summary.wait_count} "
        f"no_trade={summary.no_trade_count} "
        f"live_setup={summary.live_setup_count} "
        f"tp_hit={summary.tp_hit_count} "
        f"sl_hit={summary.sl_hit_count} "
        f"no_entry={summary.no_entry_count} "
        f"unresolved={summary.unresolved_count} "
        f"no_setup={summary.no_setup_count}"
    )
    return 0
