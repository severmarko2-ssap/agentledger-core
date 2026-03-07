# OSS Extraction Plan - AgentLedger Core v0.1

**Date**: 2026-03-07
**Source**: agent-factory (v0.30)
**Target**: agentledger-core (v0.1.0)

---

## Table A — KEEP

| Module | Files | Reason |
|--------|-------|--------|
| `events/` | `__init__.py`, `envelope.py`, `types.py`, `factory.py` | Canonical event model - core of the system |
| `ledger/` | `__init__.py`, `base.py`, `local.py` | Local JSONL ledger - essential for recording |
| `replay/` | `__init__.py`, `engine.py`, `player.py` | Deterministic replay - core capability |
| `inspect/` | `__init__.py`, `run_inspector.py`, `run_differ.py` | Inspect & diff - core user-facing features |
| `core/` | `__init__.py`, `types.py`, `errors.py`, `hash.py` | Base types, errors, hashing |
| `runtime/` | `__init__.py`, `context.py` (minimal) | Execution context only |
| `cli/` | `main.py` (minimal) | CLI: run, inspect, replay, diff only |

---

## Table B — DROP

| Module | Reason |
|--------|--------|
| `bundle/` | Evidence bundles - higher layer (v0.17+) |
| `ci/` | CI gate - higher layer (v0.17+) |
| `proof/` | Execution proof - higher layer (v0.18+) |
| `certification/` | Agent certification - higher layer (v0.19+) |
| `incident/` | Incident replay - higher layer (v0.20+) |
| `cognitive/` | Cognitive runtime - higher layer (v0.21+) |
| `temporal/` | Temporal cognition - higher layer (v0.30+) |
| `aao/` | Advanced agent orchestration |
| `economy/` | Token economy |
| `governance/` | Advanced governance |
| `adapters/` | LLM adapters (OpenAI, Anthropic) |
| `agent/` | Agent framework layer |
| `platform/` | Platform integration |
| `run_registry/` | SQLite run registry |
| `state/` | State management |
| `devtools/` | Development tools |
| `tools/` | Tool utilities |
| Root files | `agent_run.py`, `analysis.py`, `causal.py`, `compare.py`, etc. |

---

## Table C — REVIEW

| Module | Files | Decision | Notes |
|--------|-------|----------|-------|
| `ledger/index.py` | SQLite index | SKIP v0.1 | Nice-to-have, not essential |
| `snapshots/` | All | SKIP v0.1 | Replay works without |
| `memory/hashing.py` | Fingerprinting | SKIP v0.1 | Advanced feature |
| `kernel/schema_registry.py` | Schema versions | SKIP v0.1 | Full kernel not needed |
| `kernel/validate.py` | Validation | SKIP v0.1 | Can add later |
| `replay_debugger/` | All | SKIP v0.1 | Advanced replay, not core |
| `runtime/policy.py` | Policy engine | SKIP v0.1 | Advanced feature |
| `runtime/run_sandbox.py` | Sandbox | SKIP v0.1 | Simpler layout for v0.1 |
| `runtime/span.py` | Span tracking | SKIP v0.1 | Nice-to-have |
| `core/protocols.py` | Protocols | INCLUDE | May be needed for contracts |
| `inspect/run_exporter.py` | Export | SKIP v0.1 | Advanced inspect feature |
| `inspect/divergence_locator.py` | Divergence | SKIP v0.1 | Advanced diff feature |
| `inspect/report_formatter.py` | Reports | SKIP v0.1 | Formatting helper |
| `replay/debug.py` | Debug mode | SKIP v0.1 | Advanced replay |

---

## Public API v0.1

### Python API

```python
# Run lifecycle
create_run(run_id: str, base_path: Path) -> RunContext
open_run(run_id: str, base_path: Path) -> RunContext
close_run(ctx: RunContext) -> None

# Events
append_event(ctx: RunContext, event: EventEnvelope) -> None
read_events(run_path: Path) -> list[EventEnvelope]

# Inspection
inspect_run(run_path: Path) -> RunSummary
diff_runs(run_a: Path, run_b: Path) -> DiffResult

# Replay
replay_run(run_path: Path) -> ReplayResult
```

### CLI

```bash
agent run <command>           # Create and run
agent inspect <run_id>        # Show run details
agent replay <run_id>         # Deterministic replay
agent diff <run_a> <run_b>    # Compare runs
```

---

## Minimal Run Layout

```
runs/<run_id>/
├── run.json              # Run manifest
├── ledger/
│   └── events.jsonl      # Event log
└── blobs/                # (optional) Binary storage
```

---

## Event ABI (Canonical Fields)

**Required**:
- `ts` - ISO timestamp
- `event` - Event type
- `run_id` - Run identifier
- `trace_id` - Trace identifier
- `step_id` - Step number
- `engine_version` - Engine version
- `schema_version` - Schema version

**Optional Hashes**:
- `content_hash`
- `decision_hash`
- `tool_input_hash`
- `tool_output_hash`

---

## Extraction Waves

### Wave 1 - Clean Core [COMPLETE]
- [x] Create folder structure
- [x] Copy `core/` (types, errors, hash)
- [x] Copy `events/` (envelope, types, factory)
- [x] Copy `ledger/` (base, local)
- [x] Copy `state/` (world_state)
- [x] Verify package imports

### Wave 2 - Replay & Inspect [COMPLETE]
- [x] Copy `replay/` (engine, player)
- [x] Copy `inspect/` (run_inspector, run_differ)
- [x] Verify replay works

### Wave 3 - Tests & Packaging [COMPLETE]
- [x] Create pyproject.toml
- [x] Create README.md
- [x] Port core tests (22 tests)
- [x] Verify full flow - ALL TESTS PASS

---

## Acceptance Tests

- [x] Test A: Create run, write events, close (TestLocalLedger)
- [x] Test B: Inspect run shows timeline (TestRunInspector)
- [x] Test C: Replay runs deterministically (TestReplayEngine)
- [x] Test D: Hash chain verification works (TestHashUtilities, verify_determinism)
- [x] Test E: Diff shows changes (TestRunDiffer)

---

## Dependencies to Remove

Any import from:
- `agentledger.cognitive.*`
- `agentledger.temporal.*`
- `agentledger.proof.*`
- `agentledger.incident.*`
- `agentledger.certification.*`
- `agentledger.bundle.*`
- `agentledger.ci.*`
- `agentledger.adapters.*` (LLM specific)
