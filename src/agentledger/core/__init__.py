"""Core types, errors, and utilities for AgentLedger."""

from .types import (
    RunId,
    SpanId,
    AgentId,
    BranchId,
    BlobRef,
    EventId,
    TraceId,
    RunStatus,
    Actor,
    EventType,
    PatchOp,
    DecisionType,
    EventCategory,
    EVENT_TYPE_CATEGORY,
    SCHEMA_VERSION,
    GENESIS_HASH,
)

from .errors import (
    AgentLedgerError,
    RuntimeError,
    LedgerError,
    EventValidationError,
    StateError,
    HashChainError,
    ReplayError,
    ConfigurationError,
)

from .hash import (
    canonical_json,
    compute_event_hash,
    verify_hash_chain,
    compute_final_hash,
)

__all__ = [
    # Type aliases
    "RunId",
    "SpanId",
    "AgentId",
    "BranchId",
    "BlobRef",
    "EventId",
    "TraceId",
    # Enums
    "RunStatus",
    "Actor",
    "EventType",
    "PatchOp",
    "DecisionType",
    "EventCategory",
    # Mappings
    "EVENT_TYPE_CATEGORY",
    # Constants
    "SCHEMA_VERSION",
    "GENESIS_HASH",
    # Errors
    "AgentLedgerError",
    "RuntimeError",
    "LedgerError",
    "EventValidationError",
    "StateError",
    "HashChainError",
    "ReplayError",
    "ConfigurationError",
    # Hash utilities
    "canonical_json",
    "compute_event_hash",
    "verify_hash_chain",
    "compute_final_hash",
]
