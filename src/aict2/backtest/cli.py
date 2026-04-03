from __future__ import annotations

import argparse
from pathlib import Path

from aict2.backtest.engine import run_backtest_case, summarize_results
from aict2.backtest.loader import discover_backtest_cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aict2.backtest")
    parser.add_argument("cases_dir", help="Directory containing per-case backtest folders")
    args = parser.parse_args(argv)

    cases = discover_backtest_cases(Path(args.cases_dir))
    results = [run_backtest_case(case) for case in cases]
    summary = summarize_results(results)

    for result in results:
        status = result.validation_error or result.status or "UNKNOWN"
        replay = result.trade_outcome or "-"
        print(f"{result.case_id}\t{status}\t{replay}")

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
        f"unresolved={summary.unresolved_count}"
    )
    return 0
