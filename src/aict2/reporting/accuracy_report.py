from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def build_accuracy_report(results: Sequence[dict[str, Any]]) -> str:
    if not results:
        return 'No scored analyses yet.'

    total = len(results)
    scored = [result for result in results if result.get('score') is not None]
    if not scored:
        return f'Total analyses: {total}\nScored: 0\nAverage score: n/a'

    average_score = sum(float(result['score']) for result in scored) / len(scored)
    return (
        f'Total analyses: {total}\n'
        f'Scored: {len(scored)}\n'
        f'Average score: {average_score:.2f}'
    )
