"""Event factory helpers for creating events."""

from typing import Any
from ulid import ULID

from agentledger.core.types import (
    RunId,
    SpanId,
    AgentId,
    BranchId,
    EventType,
    EventCategory,
    EVENT_TYPE_CATEGORY,
    RunStatus,
    DecisionType,
    GENESIS_HASH,
)
from .envelope import EventEnvelope
from .types import (
    RunStartData,
    RunEndData,
    StepStartData,
    StepEndData,
    StatePatchData,
    StatePatch,
    ToolCallData,
    ToolResultData,
    DecisionData,
    ErrorData,
)


def generate_run_id() -> RunId:
    """Generate a unique run ID."""
    return f"run_{ULID()}"


def generate_span_id() -> SpanId:
    """Generate a unique span ID."""
    return f"sp_{ULID()}"


class EventFactory:
    """Factory for creating canonical event envelopes.

    Creates events conforming to AgentLedger Core v0.1 standard.
    Maintains hash chain state for deterministic ledger verification.

    Canonical event types:
    - run.start / run.end
    - step.start / step.end
    - tool.call / tool.result
    - decision
    - state.patch
    - error
    """

    def __init__(
        self,
        run_id: RunId,
        agent_id: AgentId,
        branch_id: BranchId = "main",
        initial_prev_hash: str = GENESIS_HASH,
    ):
        self.run_id = run_id
        self.agent_id = agent_id
        self.branch_id = branch_id
        self._seq = 0
        self._span_stack: list[SpanId] = []
        self._current_span_id = generate_span_id()
        self._prev_hash = initial_prev_hash

    def next_seq(self) -> int:
        """Get the next sequence number."""
        seq = self._seq
        self._seq += 1
        return seq

    @property
    def current_span_id(self) -> SpanId:
        """Get the current span ID."""
        return self._current_span_id

    @property
    def parent_span_id(self) -> SpanId | None:
        """Get the parent span ID."""
        return self._span_stack[-1] if self._span_stack else None

    def push_span(self) -> SpanId:
        """Start a new span and return its ID."""
        self._span_stack.append(self._current_span_id)
        self._current_span_id = generate_span_id()
        return self._current_span_id

    def pop_span(self) -> SpanId | None:
        """End the current span and return to the parent."""
        if self._span_stack:
            self._current_span_id = self._span_stack.pop()
        return self._current_span_id

    @property
    def current_hash(self) -> str:
        """Get the current (last) hash in the chain."""
        return self._prev_hash

    def _create_envelope(
        self, event_type: EventType, data: dict[str, Any]
    ) -> EventEnvelope:
        """Create an event envelope with current context."""
        category = EVENT_TYPE_CATEGORY.get(event_type, EventCategory.STATE)

        envelope = EventEnvelope(
            run_id=self.run_id,
            branch_id=self.branch_id,
            seq=self.next_seq(),
            event=event_type,
            category=category,
            span_id=self._current_span_id,
            parent_span_id=self.parent_span_id,
            agent_id=self.agent_id,
            data=data,
            prev_hash=self._prev_hash,
        )

        envelope.compute_hash()
        self._prev_hash = envelope.hash

        return envelope

    # =========================================================================
    # CANONICAL EVENTS (v0.1 Standard)
    # =========================================================================

    def run_start(
        self,
        goal: str | None = None,
        agent_config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        """Create a run.start event.

        All fields are optional to support diverse agent architectures.
        """
        data = RunStartData(
            goal=goal,
            agent_config=agent_config or {},
            metadata=metadata or {},
        )
        return self._create_envelope(EventType.RUN_START, data.model_dump())

    def run_end(
        self,
        status: RunStatus,
        reason: str | None = None,
        summary: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        """Create a run.end event."""
        data = RunEndData(
            status=status,
            reason=reason,
            summary=summary,
            metrics=metrics or {},
        )
        return self._create_envelope(EventType.RUN_END, data.model_dump())

    def step_start(
        self,
        step_id: int,
        description: str | None = None,
    ) -> EventEnvelope:
        """Create a step.start event."""
        data = StepStartData(step_id=step_id, description=description)
        return self._create_envelope(EventType.STEP_START, data.model_dump())

    def step_end(
        self,
        step_id: int,
        status: str = "completed",
    ) -> EventEnvelope:
        """Create a step.end event."""
        data = StepEndData(step_id=step_id, status=status)
        return self._create_envelope(EventType.STEP_END, data.model_dump())

    def tool_call(self, tool: str, input: dict[str, Any]) -> EventEnvelope:
        """Create a tool.call event."""
        data = ToolCallData(tool=tool, input=input)
        return self._create_envelope(EventType.TOOL_CALL, data.model_dump())

    def tool_result(
        self,
        output: Any = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> EventEnvelope:
        """Create a tool.result event."""
        data = ToolResultData(output=output, error=error, duration_ms=duration_ms)
        return self._create_envelope(EventType.TOOL_RESULT, data.model_dump())

    def decision(
        self,
        decision: DecisionType | str,
        reasoning: str | None = None,
        next_action: str | None = None,
        confidence: float | None = None,
    ) -> EventEnvelope:
        """Create a decision event."""
        if isinstance(decision, str):
            decision = DecisionType(decision)
        data = DecisionData(
            decision=decision,
            reasoning=reasoning,
            next_action=next_action,
            confidence=confidence,
        )
        return self._create_envelope(EventType.DECISION, data.model_dump())

    def state_patch(self, *patches: dict[str, Any]) -> EventEnvelope:
        """Create a state.patch event."""
        patch_list = [StatePatch(**p) for p in patches]
        data = StatePatchData(patch=patch_list)
        return self._create_envelope(EventType.STATE_PATCH, data.model_dump())

    def error(
        self,
        error_type: str,
        message: str,
        stack_trace: str | None = None,
        recoverable: bool = True,
        context: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        """Create an error event."""
        data = ErrorData(
            type=error_type,
            message=message,
            stack_trace=stack_trace,
            recoverable=recoverable,
            context=context or {},
        )
        return self._create_envelope(EventType.ERROR, data.model_dump())

    # =========================================================================
    # EXTENSION EVENTS (not part of standard)
    # =========================================================================

    def state_snapshot(self, state: dict[str, Any]) -> EventEnvelope:
        """Create a state.snapshot event (extension)."""
        return self._create_envelope(
            EventType.STATE_SNAPSHOT, {"state": state}
        )

    def custom(self, event_type: str, data: dict[str, Any]) -> EventEnvelope:
        """Create a custom event (extension)."""
        return self._create_envelope(EventType.CUSTOM, {"type": event_type, **data})
