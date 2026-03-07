"""AgentLedger Core - Deterministic Run Ledger for AI Agents.

Record. Inspect. Replay. Diff.

AgentLedger Core provides an append-only execution ledger with hash chain
integrity for AI agent runs.

Example:
    from agentledger import LocalLedger, EventFactory, ReplayEngine, RunStatus

    # Create ledger and run
    ledger = LocalLedger("./runs")
    ledger.create_run("run_001")

    # Record events
    factory = EventFactory(run_id="run_001", agent_id="agent")
    ledger.append(factory.run_start(goal="Complete task"))
    ledger.append(factory.tool_call("search", {"query": "example"}))
    ledger.append(factory.run_end(status=RunStatus.COMPLETED))

    # Verify determinism
    engine = ReplayEngine(ledger)
    result = engine.verify_determinism("run_001")
    print(f"Hash chain valid: {result['hash_chain_valid']}")

    # Inspect run
    from agentledger import RunInspector
    inspector = RunInspector()
    events = [e.model_dump() for e in ledger.get_events("run_001")]
    report = inspector.inspect(events, "run_001")
"""

__version__ = "0.1.0"

# =============================================================================
# Core Public API (Minimal v0.1)
# =============================================================================

# Core types and enums
from agentledger.core.types import (
    RunId,
    EventType,
    EventCategory,
    RunStatus,
    DecisionType,
    GENESIS_HASH,
)

# Hash utilities
from agentledger.core.hash import (
    canonical_json,
    compute_event_hash,
    verify_hash_chain,
)

# Events
from agentledger.events.envelope import EventEnvelope
from agentledger.events.factory import EventFactory, generate_run_id

# Ledger
from agentledger.ledger.local import LocalLedger

# Replay
from agentledger.replay.engine import ReplayEngine, ReplayMode, ReplayResult

# Inspect
from agentledger.inspect.run_inspector import RunInspector
from agentledger.inspect.run_differ import RunDiffer, diff_runs

# State (used internally but exposed for advanced usage)
from agentledger.state.world_state import WorldState


__all__ = [
    # Version
    "__version__",
    # Core types
    "RunId",
    "EventType",
    "EventCategory",
    "RunStatus",
    "DecisionType",
    "GENESIS_HASH",
    # Hash utilities
    "canonical_json",
    "compute_event_hash",
    "verify_hash_chain",
    # Events
    "EventEnvelope",
    "EventFactory",
    "generate_run_id",
    # Ledger
    "LocalLedger",
    # Replay
    "ReplayEngine",
    "ReplayMode",
    "ReplayResult",
    # Inspect
    "RunInspector",
    "RunDiffer",
    "diff_runs",
    # State
    "WorldState",
]
