"""Interactive replay player for step-by-step execution."""

from dataclasses import dataclass, field
from typing import Any, Callable

from agentledger.core.types import RunId, EventType
from agentledger.ledger.base import BaseLedger
from agentledger.events.envelope import EventEnvelope
from agentledger.state.world_state import WorldState


@dataclass
class PlayerState:
    """State of the replay player."""

    run_id: RunId
    current_index: int = 0
    total_events: int = 0
    world_state: WorldState = field(default_factory=WorldState)
    is_paused: bool = True
    is_complete: bool = False


class ReplayPlayer:
    """Interactive player for stepping through agent runs.

    Provides VCR-like controls for replaying agent execution:
    - Step forward/backward
    - Jump to specific points
    - Pause/resume

    Example:
        player = ReplayPlayer(ledger)
        player.load("run_123")

        # Step through
        player.step_forward()
        print(player.current_event)
        print(player.state)

        # Jump to specific point
        player.goto(10)

        # Get state at current position
        state = player.get_state()
    """

    def __init__(self, ledger: BaseLedger):
        """Initialize the replay player.

        Args:
            ledger: Ledger to read events from.
        """
        self.ledger = ledger
        self._events: list[EventEnvelope] = []
        self._state = PlayerState(run_id="")
        self._callbacks: dict[str, list[Callable]] = {}

    @property
    def current_event(self) -> EventEnvelope | None:
        """Get the current event."""
        if 0 <= self._state.current_index < len(self._events):
            return self._events[self._state.current_index]
        return None

    @property
    def state(self) -> PlayerState:
        """Get the current player state."""
        return self._state

    @property
    def position(self) -> int:
        """Get current position (0-indexed)."""
        return self._state.current_index

    @property
    def total(self) -> int:
        """Get total number of events."""
        return self._state.total_events

    def load(self, run_id: RunId) -> None:
        """Load a run for replay.

        Args:
            run_id: ID of the run to load.
        """
        self._events = list(self.ledger.get_events(run_id))
        self._state = PlayerState(
            run_id=run_id,
            current_index=0,
            total_events=len(self._events),
            world_state=WorldState(),
            is_paused=True,
            is_complete=False,
        )
        self._trigger("on_load", run_id)

    def step_forward(self) -> EventEnvelope | None:
        """Step forward one event.

        Returns:
            The event that was played, or None if at end.
        """
        if self._state.current_index >= len(self._events):
            self._state.is_complete = True
            return None

        event = self._events[self._state.current_index]
        self._apply_event(event)
        self._state.current_index += 1

        if self._state.current_index >= len(self._events):
            self._state.is_complete = True

        self._trigger("on_step", event)
        return event

    def step_backward(self) -> EventEnvelope | None:
        """Step backward one event (rebuilds state from start).

        Returns:
            The event at the new position, or None if at start.
        """
        if self._state.current_index <= 0:
            return None

        self._state.current_index -= 1
        self._state.is_complete = False

        # Rebuild state from start
        self._rebuild_state()

        event = self._events[self._state.current_index] if self._events else None
        self._trigger("on_step", event)
        return event

    def goto(self, index: int) -> EventEnvelope | None:
        """Jump to a specific event index.

        Args:
            index: 0-based index to jump to.

        Returns:
            The event at that position, or None if invalid.
        """
        if index < 0 or index >= len(self._events):
            return None

        self._state.current_index = index
        self._state.is_complete = (index >= len(self._events) - 1)

        # Rebuild state up to this point
        self._rebuild_state()

        event = self._events[self._state.current_index]
        self._trigger("on_goto", event, index)
        return event

    def reset(self) -> None:
        """Reset to the beginning."""
        self._state.current_index = 0
        self._state.world_state = WorldState()
        self._state.is_paused = True
        self._state.is_complete = False
        self._trigger("on_reset")

    def get_state(self) -> dict[str, Any]:
        """Get the current world state."""
        return self._state.world_state.snapshot()

    def get_events_in_range(
        self, start: int, end: int
    ) -> list[EventEnvelope]:
        """Get events in a range.

        Args:
            start: Start index (inclusive).
            end: End index (exclusive).

        Returns:
            List of events in the range.
        """
        return self._events[start:end]

    def find_events(
        self, event_type: EventType | None = None
    ) -> list[tuple[int, EventEnvelope]]:
        """Find events by type.

        Args:
            event_type: Event type to find (None for all).

        Returns:
            List of (index, event) tuples.
        """
        results = []
        for i, event in enumerate(self._events):
            if event_type is None or event.event == event_type:
                results.append((i, event))
        return results

    def get_timeline(self) -> list[dict[str, Any]]:
        """Get a timeline summary of events.

        Returns:
            List of event summaries for timeline display.
        """
        timeline = []
        for i, event in enumerate(self._events):
            timeline.append({
                "index": i,
                "seq": event.seq,
                "event": event.event.value if hasattr(event.event, 'value') else str(event.event),
                "ts": event.ts.isoformat() if event.ts else None,
                "span_id": event.span_id,
                "is_current": i == self._state.current_index,
            })
        return timeline

    def _apply_event(self, event: EventEnvelope) -> None:
        """Apply an event to the current state."""
        if event.event == EventType.STATE_PATCH:
            patches = event.data.get("patch", [])
            for patch in patches:
                self._state.world_state.apply_patch(patch)
        elif event.event == EventType.STATE_SNAPSHOT:
            self._state.world_state.restore(event.data.get("state", {}))

    def _rebuild_state(self) -> None:
        """Rebuild state from start to current position."""
        self._state.world_state = WorldState()
        for i in range(self._state.current_index):
            self._apply_event(self._events[i])

    def on(self, event_name: str, callback: Callable) -> None:
        """Register an event callback.

        Args:
            event_name: Event name (on_step, on_load, on_reset, on_goto).
            callback: Function to call.
        """
        if event_name not in self._callbacks:
            self._callbacks[event_name] = []
        self._callbacks[event_name].append(callback)

    def _trigger(self, event_name: str, *args: Any) -> None:
        """Trigger callbacks for an event."""
        for callback in self._callbacks.get(event_name, []):
            callback(*args)
