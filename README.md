# AgentLedger Core

**Deterministic Run Ledger for AI Agents**

Record. Inspect. Replay. Diff.

AgentLedger Core provides an append-only execution ledger with hash chain integrity for AI agent runs.

## Features

- **Append-only Event Ledger** - Immutable record of agent execution
- **Hash Chain Integrity** - SHA-256 hash chain for tamper detection
- **Deterministic Replay** - Replay runs from recorded outputs
- **Run Inspection** - Timeline and failure analysis
- **Run Diff** - Compare runs to identify divergences

## What AgentLedger Core is NOT

AgentLedger Core defines a minimal execution ledger format.

It does NOT define:

- Agent cognition
- Planning systems
- Memory architectures
- Orchestration frameworks
- LLM adapters
- Deployment systems

## Installation

```bash
pip install agentledger-core
```

## Quick Start

```python
from agentledger import (
    LocalLedger,
    EventFactory,
    ReplayEngine,
    RunInspector,
    RunStatus,
)

# Create ledger and run
ledger = LocalLedger("./runs")
ledger.create_run("run_001")

# Record events
factory = EventFactory(run_id="run_001", agent_id="my_agent")
ledger.append(factory.run_start())  # goal is optional
ledger.append(factory.tool_call("search", {"query": "example"}))
ledger.append(factory.tool_result(output={"results": ["a", "b"]}))
ledger.append(factory.run_end(status=RunStatus.COMPLETED))

# Verify determinism
engine = ReplayEngine(ledger)
result = engine.verify_determinism("run_001")
print(f"Hash chain valid: {result['hash_chain_valid']}")
print(f"Deterministic: {result['deterministic']}")

# Inspect the run
inspector = RunInspector()
events = [e.model_dump() for e in ledger.get_events("run_001")]
report = inspector.inspect(events, "run_001")
print(f"Events: {len(report.timeline)}")
print(f"Duration: {report.duration_seconds}s")
```

## Core Event Types

The v0.1 standard defines 9 canonical event types:

| Category | Events |
|----------|--------|
| Run lifecycle | `run.start`, `run.end` |
| Step lifecycle | `step.start`, `step.end` |
| Tool execution | `tool.call`, `tool.result` |
| Decision | `decision` |
| State | `state.patch` |
| Error | `error` |

Custom extension events are supported but not part of the compliance set.

## Storage Layout

```
runs/
  run_{id}/
    run.json          # Run manifest
    ledger/
      events.jsonl    # Append-only event log
    blobs/            # Optional blob storage
```

## API Reference

### LocalLedger

```python
ledger = LocalLedger("./runs")

ledger.create_run(run_id)           # Initialize new run
ledger.append(event)                # Append event
ledger.get_events(run_id)           # Iterate events
ledger.get_run_metadata(run_id)     # Get run manifest
ledger.store_blob(run_id, data)     # Store large data
```

### EventFactory

```python
factory = EventFactory(run_id, agent_id)

factory.run_start()                 # Run start (all fields optional)
factory.run_end(status)             # Run end
factory.step_start(step_id)         # Step start
factory.step_end(step_id)           # Step end
factory.tool_call(tool, input)      # Tool invocation
factory.tool_result(output)         # Tool response
factory.decision(decision_type)     # Decision point
factory.state_patch(*patches)       # Optional state mutation
factory.error(type, message)        # Error event
```

### ReplayEngine

```python
engine = ReplayEngine(ledger)

engine.replay(run_id)               # Full replay
engine.step(run_id)                 # Step-by-step iterator
engine.get_state_at(run_id, seq)    # State at sequence
engine.verify_determinism(run_id)   # Hash chain verification
engine.compare(run_a, run_b)        # Compare two runs
```

### RunInspector / RunDiffer

```python
inspector = RunInspector()
report = inspector.inspect(events, run_id)

from agentledger import diff_runs
diff = diff_runs(events_a, events_b, "run_a", "run_b")
```

## Standard

AgentLedger Core v0.1 defines the minimal execution ledger standard for AI agents.

This package is the reference implementation of the standard. See [SPEC.md](SPEC.md) for the full specification.

## CLI Usage

```bash
# Inspect a run
agent inspect run_001

# Replay a run
agent replay run_001

# Diff two runs
agent diff run_a run_b
```

## License

MIT License
