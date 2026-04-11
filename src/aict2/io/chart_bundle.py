from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True, slots=True)
class ChartFrameBundle:
    instrument: str
    analysis_frames: dict[str, pd.DataFrame]
    score_frame: pd.DataFrame | None = None
    source_labels: tuple[str, ...] = field(default_factory=tuple)
