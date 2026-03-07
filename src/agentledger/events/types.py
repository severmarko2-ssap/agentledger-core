"""Event type definitions for AgentLedger Core.

Each event type has a corresponding Pydantic model that defines
the structure of the 'data' field in the event envelope.
"""

from typing import Any

from pydantic import BaseModel, Field

from agentledger.core.types import (
    RunStatus,
    PatchOp,
    DecisionType,
)


# =============================================================================
# Run Lifecycle Events
# =============================================================================


class RunStartData(BaseModel):
    """Data for run.start events.

    Emitted when an agent run begins. All fields are optional to support
    diverse agent architectures.
    """

    goal: str | None = Field(default=None, description="Optional goal for this run")
    agent_config: dict[str, Any] = Field(
        default_factory=dict, description="Agent configuration"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class RunEndData(BaseModel):
    """Data for run.end events.

    Emitted when an agent run completes (successfully or not).
    """

    status: RunStatus = Field(..., description="Final run status")
    reason: str | None = Field(default=None, description="Reason for status")
    summary: str | None = Field(default=None, description="Run summary")
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Run metrics (duration, token count, etc.)"
    )


# =============================================================================
# Step Lifecycle Events (Canonical v0.1)
# =============================================================================


class StepStartData(BaseModel):
    """Data for step.start events.

    Emitted when a step begins within a run.
    """

    step_id: int = Field(..., description="Step identifier within the run")
    description: str | None = Field(default=None, description="Step description")


class StepEndData(BaseModel):
    """Data for step.end events.

    Emitted when a step completes.
    """

    step_id: int = Field(..., description="Step identifier within the run")
    status: str = Field(default="completed", description="Step completion status")


# =============================================================================
# Goal and Planning Events (Extension - not part of v0.1 standard)
# =============================================================================


class GoalSetData(BaseModel):
    """Data for goal.set events.

    Emitted when a goal is set or updated.
    """

    goal: str = Field(..., description="The goal text")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context for the goal"
    )


class PlanStep(BaseModel):
    """A single step in a plan."""

    action: str = Field(..., description="Action to take")
    description: str | None = Field(default=None, description="Step description")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Step parameters"
    )


class PlanProposedData(BaseModel):
    """Data for plan.proposed events.

    Emitted when the agent proposes a plan.
    """

    plan: list[PlanStep] = Field(..., description="List of planned steps")
    reasoning: str | None = Field(default=None, description="Reasoning behind the plan")


# =============================================================================
# State Events
# =============================================================================


class StatePatch(BaseModel):
    """A single state patch operation."""

    op: PatchOp = Field(..., description="Patch operation type")
    path: str = Field(..., description="Path in the state tree (e.g., '/foo/bar')")
    value: Any = Field(default=None, description="Value for set/append/increment")


class StatePatchData(BaseModel):
    """Data for state.patch events.

    Emitted when the world state is modified.
    """

    patch: list[StatePatch] = Field(..., description="List of patch operations")


class StateSnapshotData(BaseModel):
    """Data for state.snapshot events.

    Emitted periodically to capture full state for efficient replay.
    """

    state: dict[str, Any] = Field(..., description="Full state snapshot")


# =============================================================================
# LLM Events
# =============================================================================


class LLMCallData(BaseModel):
    """Data for llm.call events.

    Emitted when calling an LLM.
    """

    model: str = Field(..., description="Model identifier")
    messages: list[dict[str, Any]] = Field(..., description="Input messages")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Model parameters (temperature, etc.)"
    )
    prompt_blob_ref: str | None = Field(
        default=None, description="Blob reference for large prompts"
    )


class LLMUsage(BaseModel):
    """Token usage information from LLM calls."""

    prompt_tokens: int = Field(default=0, description="Input tokens")
    completion_tokens: int = Field(default=0, description="Output tokens")
    total_tokens: int = Field(default=0, description="Total tokens")


class LLMResultData(BaseModel):
    """Data for llm.result events.

    Emitted when receiving an LLM response.
    """

    content: str = Field(..., description="Response content")
    usage: LLMUsage = Field(default_factory=LLMUsage, description="Token usage")
    finish_reason: str | None = Field(
        default=None, description="Why the response ended"
    )
    model: str | None = Field(default=None, description="Actual model used")
    response_blob_ref: str | None = Field(
        default=None, description="Blob reference for large responses"
    )


# =============================================================================
# Tool Events
# =============================================================================


class ToolCallData(BaseModel):
    """Data for tool.call events.

    Emitted when calling a tool.
    """

    tool: str = Field(..., description="Tool name")
    input: dict[str, Any] = Field(..., description="Tool input")


class ToolResultData(BaseModel):
    """Data for tool.result events.

    Emitted when receiving a tool result.
    """

    output: Any = Field(default=None, description="Tool output")
    error: str | None = Field(default=None, description="Error message if failed")
    duration_ms: int | None = Field(default=None, description="Execution time in ms")


# =============================================================================
# Decision Events
# =============================================================================


class DecisionData(BaseModel):
    """Data for decision events.

    Emitted at decision points in the agent loop.
    """

    decision: DecisionType = Field(..., description="The decision made")
    reasoning: str | None = Field(default=None, description="Reasoning for decision")
    next_action: str | None = Field(default=None, description="Next planned action")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in decision"
    )


# =============================================================================
# Error Events
# =============================================================================


class ErrorData(BaseModel):
    """Data for error events.

    Emitted when an error occurs during execution.
    """

    type: str = Field(..., description="Error type (e.g., 'tool_failure', 'llm_error')")
    message: str = Field(..., description="Error message")
    stack_trace: str | None = Field(default=None, description="Stack trace if available")
    recoverable: bool = Field(default=True, description="Whether the error is recoverable")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )


# =============================================================================
# Custom Events
# =============================================================================


class CustomEventData(BaseModel):
    """Data for custom events.

    Allows agents to emit domain-specific events.
    """

    type: str = Field(..., description="Custom event type identifier")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Custom event payload"
    )
