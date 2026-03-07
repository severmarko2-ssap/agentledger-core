"""Replay engine for reconstructing agent runs from the ledger."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Callable

from agentledger.core.types import RunId, EventType, EventCategory, EVENT_TYPE_CATEGORY, GENESIS_HASH
from agentledger.core.hash import compute_event_hash, verify_hash_chain
from agentledger.ledger.base import BaseLedger
from agentledger.events.envelope import EventEnvelope
from agentledger.state.world_state import WorldState


class ReplayMode(str, Enum):
    """Replay execution modes."""

    STUB = "stub"      # Use recorded outputs (deterministic)
    LIVE = "live"      # Re-execute LLM and tool calls


@dataclass
class ReplayResult:
    """Result of a replay operation."""

    run_id: RunId
    mode: ReplayMode
    events_replayed: int
    final_state: dict[str, Any]
    success: bool
    error: str | None = None
    duration_ms: int = 0
    divergences: list[dict[str, Any]] = field(default_factory=list)
    # Hash verification fields
    original_hash: str | None = None
    replay_hash: str | None = None
    deterministic: bool | None = None
    hash_chain_valid: bool | None = None


@dataclass
class ReplayState:
    """State tracked during replay."""

    current_seq: int = 0
    world_state: WorldState = field(default_factory=WorldState)
    events: list[EventEnvelope] = field(default_factory=list)
    llm_results: dict[int, dict[str, Any]] = field(default_factory=dict)
    tool_results: dict[int, Any] = field(default_factory=dict)


class ReplayEngine:
    """Engine for replaying agent runs from the ledger.

    The replay engine reconstructs agent execution by reading
    events from the ledger and using recorded outputs for deterministic replay.

    Example:
        engine = ReplayEngine(ledger)

        # Stub replay (deterministic)
        result = engine.replay("run_123", mode=ReplayMode.STUB)

        # Step through replay
        for event in engine.step("run_123"):
            print(f"Replaying: {event.event}")
    """

    def __init__(self, ledger: BaseLedger):
        """Initialize the replay engine.

        Args:
            ledger: Ledger to read events from.
        """
        self.ledger = ledger
        self._hooks: dict[str, list[Callable]] = {}

    def replay(
        self,
        run_id: RunId,
        mode: ReplayMode = ReplayMode.STUB,
        start_seq: int = 0,
        end_seq: int | None = None,
    ) -> ReplayResult:
        """Replay a run from the ledger.

        Args:
            run_id: ID of the run to replay.
            mode: Replay mode (stub or live).
            start_seq: Starting sequence number.
            end_seq: Ending sequence number (None for all).

        Returns:
            ReplayResult with replay outcome.
        """
        import time
        start_time = time.monotonic()

        state = ReplayState()
        events_replayed = 0
        error = None

        try:
            # Pre-load LLM and tool results for stub mode
            if mode == ReplayMode.STUB:
                self._preload_results(run_id, state)

            # Replay events
            for event in self.ledger.get_events(run_id, start_seq, end_seq):
                self._replay_event(event, state, mode)
                state.events.append(event)
                events_replayed += 1
                self._trigger_hook("on_event_replayed", event, state)

            success = True

        except Exception as e:
            error = str(e)
            success = False

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return ReplayResult(
            run_id=run_id,
            mode=mode,
            events_replayed=events_replayed,
            final_state=state.world_state.snapshot(),
            success=success,
            error=error,
            duration_ms=duration_ms,
        )

    def step(
        self,
        run_id: RunId,
        mode: ReplayMode = ReplayMode.STUB,
    ) -> Iterator[tuple[EventEnvelope, ReplayState]]:
        """Step through a replay, yielding each event.

        Args:
            run_id: ID of the run to replay.
            mode: Replay mode.

        Yields:
            Tuple of (event, state) for each step.
        """
        state = ReplayState()

        if mode == ReplayMode.STUB:
            self._preload_results(run_id, state)

        for event in self.ledger.get_events(run_id):
            self._replay_event(event, state, mode)
            state.events.append(event)
            yield event, state

    def get_state_at(self, run_id: RunId, seq: int) -> dict[str, Any]:
        """Get the world state at a specific sequence number.

        Args:
            run_id: ID of the run.
            seq: Sequence number to get state at.

        Returns:
            World state snapshot at that point.
        """
        state = WorldState()

        for event in self.ledger.get_events(run_id, end_seq=seq):
            if event.event == EventType.STATE_PATCH:
                patches = event.data.get("patch", [])
                for patch in patches:
                    state.apply_patch(patch)
            elif event.event == EventType.STATE_SNAPSHOT:
                state.restore(event.data.get("state", {}))

        return state.snapshot()

    def compare(
        self,
        run_id_1: RunId,
        run_id_2: RunId,
    ) -> dict[str, Any]:
        """Compare two runs.

        Args:
            run_id_1: First run ID.
            run_id_2: Second run ID.

        Returns:
            Comparison results with divergences.
        """
        events_1 = list(self.ledger.get_events(run_id_1))
        events_2 = list(self.ledger.get_events(run_id_2))

        divergences = []
        common_length = min(len(events_1), len(events_2))

        for i in range(common_length):
            e1, e2 = events_1[i], events_2[i]
            if e1.event != e2.event or e1.data != e2.data:
                divergences.append({
                    "seq": i,
                    "run_1": {"event": e1.event, "data": e1.data},
                    "run_2": {"event": e2.event, "data": e2.data},
                })

        return {
            "run_1": run_id_1,
            "run_2": run_id_2,
            "events_1": len(events_1),
            "events_2": len(events_2),
            "common_events": common_length,
            "divergences": divergences,
            "identical": len(divergences) == 0 and len(events_1) == len(events_2),
        }

    def verify_determinism(self, run_id: RunId) -> dict[str, Any]:
        """Verify that a run is deterministic by checking hash chain.

        Performs:
        1. Load events from ledger
        2. Verify hash chain integrity
        3. Recompute hashes and compare
        4. Report any divergences

        Args:
            run_id: ID of the run to verify.

        Returns:
            Verification result with determinism status.
        """
        events = list(self.ledger.get_events(run_id))

        if not events:
            return {
                "run_id": run_id,
                "event_count": 0,
                "deterministic": True,
                "hash_chain_valid": True,
                "original_hash": GENESIS_HASH,
                "computed_hash": GENESIS_HASH,
                "errors": [],
            }

        # Convert events to dict format for verification
        event_dicts = []
        for e in events:
            event_dict = {
                "seq": e.seq,
                "ts": e.ts.isoformat().replace("+00:00", "Z") if hasattr(e.ts, "isoformat") else str(e.ts),
                "event": e.event.value if hasattr(e.event, "value") else e.event,
                "category": getattr(e, "category", None),
                "data": e.data,
                "prev_hash": getattr(e, "prev_hash", GENESIS_HASH),
                "hash": getattr(e, "hash", None),
            }
            # Handle category
            if event_dict["category"] is not None and hasattr(event_dict["category"], "value"):
                event_dict["category"] = event_dict["category"].value
            event_dicts.append(event_dict)

        # Check if events have hash fields
        has_hashes = all(e.get("hash") for e in event_dicts)

        if not has_hashes:
            return {
                "run_id": run_id,
                "event_count": len(events),
                "deterministic": None,  # Cannot determine without hashes
                "hash_chain_valid": None,
                "original_hash": None,
                "computed_hash": None,
                "errors": ["Events do not have hash fields (legacy format)"],
            }

        # Verify hash chain
        chain_valid, chain_error = verify_hash_chain(event_dicts)

        # Get original final hash
        original_hash = event_dicts[-1].get("hash")

        # Recompute hashes
        computed_hash = GENESIS_HASH
        recomputed_hashes = []
        errors = []

        for i, event in enumerate(event_dicts):
            computed = compute_event_hash(
                prev_hash=computed_hash if i == 0 else recomputed_hashes[-1],
                seq=event["seq"],
                ts=event["ts"],
                event_type=event["event"],
                category=event.get("category", "STATE"),
                payload=event["data"],
            )
            recomputed_hashes.append(computed)

            if computed != event.get("hash"):
                errors.append(f"Hash mismatch at seq {event['seq']}: expected {computed}, got {event.get('hash')}")

            computed_hash = computed

        return {
            "run_id": run_id,
            "event_count": len(events),
            "deterministic": len(errors) == 0 and chain_valid,
            "hash_chain_valid": chain_valid,
            "original_hash": original_hash,
            "computed_hash": computed_hash,
            "errors": errors + ([chain_error] if chain_error else []),
        }

    def get_final_hash(self, run_id: RunId) -> str:
        """Get the final hash of a run.

        Args:
            run_id: ID of the run.

        Returns:
            Final hash or GENESIS if empty/no hashes.
        """
        last_event = self.ledger.get_last_event(run_id)
        if last_event and hasattr(last_event, "hash") and last_event.hash:
            return last_event.hash
        return GENESIS_HASH

    def _preload_results(self, run_id: RunId, state: ReplayState) -> None:
        """Preload tool results for stub replay.

        Note: LLM results are not part of the canonical v0.1 event types.
        Tool results are cached by their preceding tool.call sequence number.
        """
        for event in self.ledger.get_events(run_id):
            if event.event == EventType.TOOL_RESULT:
                state.tool_results[event.seq - 1] = event.data.get("output")

    def _replay_event(
        self,
        event: EventEnvelope,
        state: ReplayState,
        mode: ReplayMode,
    ) -> None:
        """Replay a single event."""
        state.current_seq = event.seq

        if event.event == EventType.STATE_PATCH:
            patches = event.data.get("patch", [])
            for patch in patches:
                state.world_state.apply_patch(patch)

        elif event.event == EventType.STATE_SNAPSHOT:
            state.world_state.restore(event.data.get("state", {}))

    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a replay hook."""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)

    def _trigger_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """Trigger hook callbacks."""
        for callback in self._hooks.get(hook_name, []):
            callback(*args, **kwargs)
