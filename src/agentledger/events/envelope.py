"""Event envelope model for the execution ledger."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agentledger.core.types import (
    RunId,
    SpanId,
    AgentId,
    BranchId,
    EventType,
    EventCategory,
    EVENT_TYPE_CATEGORY,
    SCHEMA_VERSION,
    GENESIS_HASH,
)
from agentledger.core.hash import compute_event_hash, canonical_json


class EventEnvelope(BaseModel):
    """Common envelope for all events in the execution ledger.

    Every event uses this structure to ensure consistent metadata
    for replay, debugging, and analytics.

    Attributes:
        v: Schema version for forward compatibility.
        schema_version: Ledger schema version string (e.g., "1.0").
        ts: Timestamp in UTC.
        run_id: Unique identifier for the run.
        branch_id: Branch identifier (default "main").
        seq: Sequence number within the run (monotonically increasing).
        event: Event type from EventType enum.
        category: Event category for grouping.
        span_id: Current span identifier for grouping related events.
        parent_span_id: Parent span for nested operations.
        agent_id: Identifier of the agent that emitted this event.
        data: Event-specific payload.
        prev_hash: Hash of the previous event in the chain.
        hash: Hash of this event (computed from prev_hash + content).
    """

    v: int = Field(default=1, ge=1, description="Schema version (integer)")
    schema_version: str = Field(default=SCHEMA_VERSION, description="Ledger schema version")
    ts: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp in UTC",
    )
    run_id: RunId = Field(..., description="Run identifier")
    branch_id: BranchId = Field(default="main", description="Branch identifier")
    seq: int = Field(..., ge=0, description="Sequence number within run")
    event: EventType = Field(..., description="Event type")
    category: EventCategory = Field(..., description="Event category")
    span_id: SpanId = Field(..., description="Current span identifier")
    parent_span_id: SpanId | None = Field(
        default=None, description="Parent span identifier"
    )
    agent_id: AgentId = Field(..., description="Agent identifier")
    tags: dict[str, str] = Field(default_factory=dict, description="Event metadata tags")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    prev_hash: str = Field(default=GENESIS_HASH, description="Previous event hash")
    hash: str = Field(default="", description="This event's hash")

    model_config = {
        "use_enum_values": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat().replace("+00:00", "Z"),
        },
    }

    def compute_hash(self, prev_hash: str | None = None) -> str:
        """Compute the hash for this event.

        Args:
            prev_hash: Previous event hash. If None, uses self.prev_hash.

        Returns:
            Computed hash string.
        """
        if prev_hash is not None:
            self.prev_hash = prev_hash

        ts_str = self.ts.isoformat().replace("+00:00", "Z")
        event_type = self.event.value if isinstance(self.event, EventType) else self.event
        category_str = self.category.value if isinstance(self.category, EventCategory) else self.category

        self.hash = compute_event_hash(
            prev_hash=self.prev_hash,
            seq=self.seq,
            ts=ts_str,
            event_type=event_type,
            category=category_str,
            payload=self.data,
        )
        return self.hash

    def to_jsonl(self) -> str:
        """Serialize to a single-line JSON string for JSONL format.

        Uses canonical JSON for deterministic output.
        """
        data = self.model_dump()
        # Convert datetime to ISO string
        if isinstance(data.get("ts"), datetime):
            data["ts"] = data["ts"].isoformat().replace("+00:00", "Z")
        return canonical_json(data)

    @classmethod
    def from_jsonl(cls, line: str) -> "EventEnvelope":
        """Deserialize from a JSONL line."""
        return cls.model_validate_json(line.strip())
