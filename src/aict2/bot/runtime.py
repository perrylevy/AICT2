from __future__ import annotations

from dataclasses import dataclass

from aict2.context.macro_memory import MacroSnapshotStore
from aict2.bot.settings import BotSettings
from aict2.context.store import ContextStore
from aict2.context.structural_memory import StructuralMemoryStore
from aict2.reporting.analysis_records import AnalysisRecordStore


@dataclass(frozen=True, slots=True)
class BotRuntime:
    settings: BotSettings
    context_store: ContextStore
    memory_store: StructuralMemoryStore
    macro_store: MacroSnapshotStore
    record_store: AnalysisRecordStore


def build_runtime(settings: BotSettings) -> BotRuntime:
    context_store = ContextStore(settings.db_path)
    context_store.initialize()
    memory_store = StructuralMemoryStore(context_store)
    macro_store = MacroSnapshotStore(context_store)
    record_store = AnalysisRecordStore(context_store)
    return BotRuntime(
        settings=settings,
        context_store=context_store,
        memory_store=memory_store,
        macro_store=macro_store,
        record_store=record_store,
    )
