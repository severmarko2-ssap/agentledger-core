"""Event system for AgentLedger Core."""

from .envelope import EventEnvelope
from .factory import EventFactory, generate_run_id, generate_span_id
from .types import (
    RunStartData,
    RunEndData,
    StepStartData,
    StepEndData,
    GoalSetData,
    PlanStep,
    PlanProposedData,
    StatePatch,
    StatePatchData,
    StateSnapshotData,
    LLMCallData,
    LLMUsage,
    LLMResultData,
    ToolCallData,
    ToolResultData,
    DecisionData,
    ErrorData,
    CustomEventData,
)

__all__ = [
    # Envelope
    "EventEnvelope",
    # Factory
    "EventFactory",
    "generate_run_id",
    "generate_span_id",
    # Event data types - Canonical (v0.1)
    "RunStartData",
    "RunEndData",
    "StepStartData",
    "StepEndData",
    "ToolCallData",
    "ToolResultData",
    "DecisionData",
    "StatePatch",
    "StatePatchData",
    "ErrorData",
    # Event data types - Extensions
    "GoalSetData",
    "PlanStep",
    "PlanProposedData",
    "StateSnapshotData",
    "LLMCallData",
    "LLMUsage",
    "LLMResultData",
    "CustomEventData",
]
