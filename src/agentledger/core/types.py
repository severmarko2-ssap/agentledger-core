"""Core type definitions for AgentLedger Core."""

from enum import Enum
from typing import TypeAlias

# Type aliases for identifiers
RunId: TypeAlias = str      # Format: "run_{ulid}"
SpanId: TypeAlias = str     # Format: "sp_{ulid}"
AgentId: TypeAlias = str    # User-defined agent identifier
BranchId: TypeAlias = str   # Branch identifier, default "main"
BlobRef: TypeAlias = str    # Format: "blob_{hash}"
EventId: TypeAlias = str    # Format: "evt_{ulid}"
TraceId: TypeAlias = str    # Format: "trc_{ulid}"


class RunStatus(str, Enum):
    """Status of an agent run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class Actor(str, Enum):
    """Event actor types."""

    AGENT = "agent"
    RUNTIME = "runtime"
    TOOL = "tool"
    HUMAN = "human"
    SYSTEM = "system"


class EventType(str, Enum):
    """Canonical event types for AgentLedger Core v0.1.

    The standard defines these 9 canonical event types.
    Implementations may emit additional custom events,
    but only these are part of the compliance set.
    """

    # === CANONICAL EVENT TYPES (v0.1 Standard) ===

    # Run lifecycle (2)
    RUN_START = "run.start"
    RUN_END = "run.end"

    # Step lifecycle (2)
    STEP_START = "step.start"
    STEP_END = "step.end"

    # Tool execution (2)
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"

    # Decision (1)
    DECISION = "decision"

    # State (1)
    STATE_PATCH = "state.patch"

    # Error (1)
    ERROR = "error"

    # === EXTENSION EVENTS (not part of standard, but supported) ===
    # These are common extensions that don't break replay/inspect

    # State extensions
    STATE_SNAPSHOT = "state.snapshot"

    # Custom/extension
    CUSTOM = "custom"


class PatchOp(str, Enum):
    """State patch operations."""

    SET = "set"
    DELETE = "delete"
    APPEND = "append"
    INCREMENT = "increment"


class DecisionType(str, Enum):
    """Types of decisions an agent can make."""

    CONTINUE = "continue"
    STOP = "stop"
    BRANCH = "branch"
    RETRY = "retry"


class EventCategory(str, Enum):
    """Event categories for grouping and filtering."""

    RUN = "RUN"
    GOAL = "GOAL"
    TOOLS = "TOOLS"
    MODEL = "MODEL"
    DECISIONS = "DECISIONS"
    STATE = "STATE"
    CONFIG = "CONFIG"
    PLANNING = "PLANNING"
    MEMORY = "MEMORY"
    ERRORS = "ERRORS"
    REPLAY = "REPLAY"


# Mapping from EventType to EventCategory
EVENT_TYPE_CATEGORY: dict[EventType, EventCategory] = {
    # Canonical events
    EventType.RUN_START: EventCategory.RUN,
    EventType.RUN_END: EventCategory.RUN,
    EventType.STEP_START: EventCategory.RUN,
    EventType.STEP_END: EventCategory.RUN,
    EventType.TOOL_CALL: EventCategory.TOOLS,
    EventType.TOOL_RESULT: EventCategory.TOOLS,
    EventType.DECISION: EventCategory.DECISIONS,
    EventType.STATE_PATCH: EventCategory.STATE,
    EventType.ERROR: EventCategory.ERRORS,
    # Extension events
    EventType.STATE_SNAPSHOT: EventCategory.STATE,
    EventType.CUSTOM: EventCategory.STATE,
}


# Schema version constants
SCHEMA_VERSION = "1.0"
GENESIS_HASH = "GENESIS"
