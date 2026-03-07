# AgentLedger Core Specification v0.1

**Status**: Draft
**Version**: 0.1.0
**Date**: 2026-03-07

---

## 1. Purpose

AgentLedger Core defines a minimal, deterministic format for recording AI agent executions.

### What This Standard Defines

- **Run layout**: Directory and file structure for storing agent runs
- **Event envelope**: Required and optional fields for each event
- **Hash chain**: Cryptographic linking of events for integrity verification
- **Replay validity**: What constitutes a valid deterministic replay

### What This Standard Does NOT Define

- Agent cognition, planning, or reasoning architecture
- Memory systems or knowledge retrieval
- Orchestration or multi-agent coordination
- LLM provider interfaces or adapters
- Deployment, certification, or incident management

Implementations MAY extend the standard with additional capabilities, but extensions MUST NOT break replay or inspection of compliant runs.

---

## 2. Run Layout

A compliant run MUST be stored in the following canonical layout:

```
runs/<run_id>/
  run.json          # Run manifest (metadata)
  ledger/
    events.jsonl    # Append-only event log
  blobs/            # Optional: binary blob storage
    blob_<hash>     # Content-addressable blobs
```

### 2.1 Run Manifest (`run.json`)

Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | string | Unique run identifier (format: `run_{ulid}`) |
| `created_at` | string | ISO 8601 timestamp |
| `event_count` | integer | Number of events in the run |

Optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `updated_at` | string | ISO 8601 timestamp of last update |
| `status` | string | Run status (`running`, `completed`, `failed`, `cancelled`) |
| `agent_id` | string | Agent identifier |
| `branch_id` | string | Branch identifier (default: `main`) |

### 2.2 Event Log (`events.jsonl`)

Events MUST be stored in JSON Lines format (one JSON object per line).

Events MUST be append-only. Implementations MUST NOT modify or delete existing events.

Events MUST be ordered by sequence number (`seq`), starting at 0.

---

## 3. Event Envelope

Every event MUST contain the following required fields:

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | string | Parent run identifier |
| `seq` | integer | Sequence number (0-indexed, monotonically increasing) |
| `ts` | string | ISO 8601 timestamp with timezone |
| `event` | string | Event type (see Section 4) |
| `data` | object | Event-specific payload |
| `prev_hash` | string | Hash of previous event (or `GENESIS` for first event) |
| `hash` | string | Hash of this event |

Optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `branch_id` | string | Branch identifier |
| `span_id` | string | Span identifier for tracing |
| `parent_span_id` | string | Parent span identifier |
| `agent_id` | string | Agent that emitted this event |
| `category` | string | Event category for filtering |

---

## 4. Canonical Event Types

The v0.1 standard defines 9 canonical event types. Implementations MUST support these types.

### 4.1 Run Lifecycle

| Type | Description | Required Data Fields |
|------|-------------|---------------------|
| `run.start` | Run begins | `{}` (all optional) |
| `run.end` | Run completes | `status` |

### 4.2 Step Lifecycle

| Type | Description | Required Data Fields |
|------|-------------|---------------------|
| `step.start` | Step begins | `step_id` |
| `step.end` | Step completes | `step_id`, `status` |

### 4.3 Tool Execution

| Type | Description | Required Data Fields |
|------|-------------|---------------------|
| `tool.call` | Tool invocation | `tool`, `input` |
| `tool.result` | Tool response | `output` or `error` |

### 4.4 Decision

| Type | Description | Required Data Fields |
|------|-------------|---------------------|
| `decision` | Agent decision point | `decision` |

### 4.5 State

| Type | Description | Required Data Fields |
|------|-------------|---------------------|
| `state.patch` | Optional state mutation event | `patch` (array of operations) |

### 4.6 Error

| Type | Description | Required Data Fields |
|------|-------------|---------------------|
| `error` | Error occurrence | `type`, `message` |

### 4.7 Payload Encoding

Event-specific fields are stored inside the `data` object of the event envelope.

Example:
```json
{
  "event": "tool.call",
  "data": {
    "tool": "search",
    "input": {"query": "example"}
  }
}
```

### 4.8 Extension Events

Implementations MAY emit additional event types. Extension events:

- MUST follow the same envelope format
- MUST NOT use canonical type names for different semantics
- MUST NOT break replay or inspection of compliant runs
- Are NOT part of the compliance set

Common extensions include: `state.snapshot`, `custom`.

---

## 5. Hash Chain

Events MUST be cryptographically linked using a hash chain.

### 5.1 Hash Computation

The hash of an event is computed as:

```
hash = truncate(SHA256(canonical_json({
  prev_hash: <previous_hash>,
  seq: <sequence_number>,
  ts: <timestamp>,
  event: <event_type>,
  category: <category>,
  data: <event_data>
})), 16)
```

Where:
- `canonical_json` produces deterministic JSON with sorted keys and no whitespace
- `truncate(hash, 16)` takes the first 16 hex characters of the SHA-256 digest (64-bit provides sufficient collision resistance for typical run sizes <10^7 events while reducing storage overhead)
- The first event uses `prev_hash = "GENESIS"`

### 5.2 Chain Verification

A hash chain is valid if and only if:

1. The first event has `prev_hash = "GENESIS"`
2. Each subsequent event has `prev_hash` equal to the `hash` of the previous event
3. Each event's `hash` can be recomputed and matches the stored value

---

## 6. Replay Validity

A run is **replay-valid** if:

1. The hash chain is valid (Section 5.2)
2. Events are ordered by sequence number (no gaps, no duplicates)
3. All canonical events have required data fields
4. State can be reconstructed by applying `state.patch` events in order

### 6.1 Deterministic Replay

Replay is **deterministic** if replaying the same run twice produces:

1. Identical sequence of events
2. Identical final state
3. Identical final hash

---

## 7. Compatibility

An implementation is **compliant** with AgentLedger Core v0.1 if it:

1. Reads and writes the canonical run layout (Section 2)
2. Produces valid event envelopes (Section 3)
3. Supports all canonical event types (Section 4)
4. Maintains valid hash chains (Section 5)
5. Enables replay validity verification (Section 6)

### 7.1 Forward Compatibility

Compliant implementations MUST:

- Ignore unknown fields in event envelopes
- Ignore unknown event types during replay (treat as no-op)
- Preserve unknown fields when copying events

### 7.2 Interoperability

Two compliant implementations MUST be able to:

- Read runs produced by each other
- Verify hash chains of runs from each other
- Produce identical hash chains given identical input

---

## 8. Reference Implementation

The `agentledger-core` Python package provides a reference implementation of this specification.

```python
from agentledger import LocalLedger, EventFactory, ReplayEngine, RunStatus

# Create a run
ledger = LocalLedger("./runs")
ledger.create_run("run_001")

# Record events
factory = EventFactory(run_id="run_001", agent_id="agent_1")
ledger.append(factory.run_start())  # all fields optional
ledger.append(factory.run_end(status=RunStatus.COMPLETED))

# Replay and verify
engine = ReplayEngine(ledger)
result = engine.verify_determinism("run_001")
assert result["deterministic"]
```

---

## Appendix A: JSON Schema

Event envelope schema (JSON Schema draft-07):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["run_id", "seq", "ts", "event", "data", "prev_hash", "hash"],
  "properties": {
    "run_id": {"type": "string"},
    "seq": {"type": "integer", "minimum": 0},
    "ts": {"type": "string", "format": "date-time"},
    "event": {"type": "string"},
    "data": {"type": "object"},
    "prev_hash": {"type": "string"},
    "hash": {"type": "string"},
    "branch_id": {"type": "string"},
    "span_id": {"type": "string"},
    "parent_span_id": {"type": "string"},
    "agent_id": {"type": "string"},
    "category": {"type": "string"}
  }
}
```
