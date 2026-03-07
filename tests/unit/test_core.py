"""Core tests for AgentLedger Core OSS."""

import pytest
import tempfile
from pathlib import Path

from agentledger import (
    # Core types
    RunId,
    EventType,
    RunStatus,
    EventCategory,
    GENESIS_HASH,
    # Hash utilities
    canonical_json,
    compute_event_hash,
    verify_hash_chain,
    # Events
    EventEnvelope,
    EventFactory,
    generate_run_id,
    # Ledger
    LocalLedger,
    # State
    WorldState,
    # Replay
    ReplayEngine,
    ReplayMode,
    # Inspect
    RunInspector,
    RunDiffer,
    diff_runs,
)


class TestCoreTypes:
    """Test core type definitions."""

    def test_event_types_exist(self):
        """Test that core event types are defined."""
        assert EventType.RUN_START.value == "run.start"
        assert EventType.RUN_END.value == "run.end"
        assert EventType.TOOL_CALL.value == "tool.call"
        assert EventType.TOOL_RESULT.value == "tool.result"
        assert EventType.DECISION.value == "decision"

    def test_run_status(self):
        """Test run status enum."""
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"

    def test_event_categories(self):
        """Test event categories."""
        assert EventCategory.RUN.value == "RUN"
        assert EventCategory.TOOLS.value == "TOOLS"
        assert EventCategory.DECISIONS.value == "DECISIONS"


class TestHashUtilities:
    """Test hash chain utilities."""

    def test_canonical_json(self):
        """Test canonical JSON serialization."""
        obj = {"b": 2, "a": 1}
        result = canonical_json(obj)
        assert result == '{"a":1,"b":2}'

    def test_compute_event_hash(self):
        """Test event hash computation."""
        hash1 = compute_event_hash(
            prev_hash=GENESIS_HASH,
            seq=0,
            ts="2024-01-01T00:00:00Z",
            event_type="run.start",
            category="RUN",
            payload={"goal": "test"},
        )
        assert len(hash1) == 16
        assert hash1.isalnum()

    def test_verify_hash_chain_empty(self):
        """Test hash chain verification with empty list."""
        valid, error = verify_hash_chain([])
        assert valid is True
        assert error is None


class TestEventFactory:
    """Test event factory."""

    def test_generate_run_id(self):
        """Test run ID generation."""
        run_id = generate_run_id()
        assert run_id.startswith("run_")

    def test_create_run_start_event(self):
        """Test creating run start event."""
        factory = EventFactory(run_id="run_001", agent_id="agent_1")
        event = factory.run_start(goal="Test goal")

        assert event.run_id == "run_001"
        assert event.agent_id == "agent_1"
        assert event.event == EventType.RUN_START
        assert event.data["goal"] == "Test goal"
        assert event.hash != ""
        assert event.prev_hash == GENESIS_HASH

    def test_create_tool_call_event(self):
        """Test creating tool call event."""
        factory = EventFactory(run_id="run_001", agent_id="agent_1")
        event = factory.tool_call("search", {"query": "test"})

        assert event.event == EventType.TOOL_CALL
        assert event.data["tool"] == "search"
        assert event.data["input"]["query"] == "test"

    def test_hash_chain_grows(self):
        """Test that hash chain links correctly."""
        factory = EventFactory(run_id="run_001", agent_id="agent_1")

        e1 = factory.run_start(goal="Test")
        e2 = factory.tool_call("search", {"q": "a"})
        e3 = factory.run_end(status=RunStatus.COMPLETED)

        assert e1.prev_hash == GENESIS_HASH
        assert e2.prev_hash == e1.hash
        assert e3.prev_hash == e2.hash


class TestLocalLedger:
    """Test local ledger implementation."""

    def test_create_run(self):
        """Test creating a new run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            assert ledger.run_exists("run_001")
            assert (Path(tmpdir) / "run_001" / "events.jsonl").exists()
            assert (Path(tmpdir) / "run_001" / "run.json").exists()

    def test_append_and_read_events(self):
        """Test appending and reading events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            e1 = factory.run_start(goal="Test")
            e2 = factory.run_end(status=RunStatus.COMPLETED)

            ledger.append(e1)
            ledger.append(e2)

            events = list(ledger.get_events("run_001"))
            assert len(events) == 2
            assert events[0].event == EventType.RUN_START
            assert events[1].event == EventType.RUN_END

    def test_blob_storage(self):
        """Test blob storage and retrieval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            data = b"Test blob data"
            blob_ref = ledger.store_blob("run_001", data)

            assert blob_ref.startswith("blob_")
            retrieved = ledger.get_blob("run_001", blob_ref)
            assert retrieved == data


class TestWorldState:
    """Test world state management."""

    def test_set_and_get(self):
        """Test setting and getting values."""
        state = WorldState()
        state.set("/progress", 0.5)
        state.set("/sources/count", 3)

        assert state.get("/progress") == 0.5
        assert state.get("/sources/count") == 3

    def test_apply_patch(self):
        """Test applying patches."""
        state = WorldState()
        state.apply_patch({"op": "set", "path": "/count", "value": 0})
        state.apply_patch({"op": "increment", "path": "/count", "value": 5})

        assert state.get("/count") == 5

    def test_snapshot_and_restore(self):
        """Test snapshot and restore."""
        state = WorldState()
        state.set("/a", 1)
        state.set("/b", 2)

        snapshot = state.snapshot()
        state.set("/a", 100)

        state.restore(snapshot)
        assert state.get("/a") == 1


class TestReplayEngine:
    """Test replay engine."""

    def test_replay_run(self):
        """Test replaying a run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.tool_call("search", {"q": "test"}))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            engine = ReplayEngine(ledger)
            result = engine.replay("run_001")

            assert result.success
            assert result.events_replayed == 3
            assert result.run_id == "run_001"

    def test_verify_determinism(self):
        """Test determinism verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            engine = ReplayEngine(ledger)
            result = engine.verify_determinism("run_001")

            assert result["event_count"] == 2
            assert result["hash_chain_valid"]
            assert result["deterministic"]


class TestRunInspector:
    """Test run inspector."""

    def test_inspect_run(self):
        """Test inspecting a run."""
        events = [
            {
                "seq": 0,
                "event": "run.start",
                "ts": "2024-01-01T00:00:00Z",
                "data": {"goal": "Test"},
            },
            {
                "seq": 1,
                "event": "tool.call",
                "ts": "2024-01-01T00:00:01Z",
                "data": {"tool": "search"},
            },
            {
                "seq": 2,
                "event": "run.end",
                "ts": "2024-01-01T00:00:02Z",
                "data": {"status": "completed"},
            },
        ]

        inspector = RunInspector()
        report = inspector.inspect(events, "run_001")

        assert report.run_id == "run_001"
        assert len(report.timeline) == 3
        assert report.duration_seconds == 2.0
        assert report.determinism_status.all_valid


class TestRunDiffer:
    """Test run differ."""

    def test_diff_identical_runs(self):
        """Test diffing identical runs."""
        events = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test"}},
            {"seq": 1, "event": "run.end", "data": {"status": "completed"}},
        ]

        report = diff_runs(events, events, "run_a", "run_b")

        assert report.identical
        assert len(report.divergences) == 0

    def test_diff_different_runs(self):
        """Test diffing different runs."""
        events_a = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test A"}},
        ]
        events_b = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test B"}},
        ]

        report = diff_runs(events_a, events_b, "run_a", "run_b")

        assert not report.identical
        assert len(report.divergences) == 1
        assert report.first_divergence_step == 0


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self):
        """Test complete workflow: create, record, replay, inspect."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create ledger and run
            ledger = LocalLedger(tmpdir)
            run_id = "run_integration_test"
            ledger.create_run(run_id)

            # Record events
            factory = EventFactory(run_id=run_id, agent_id="test_agent")
            ledger.append(factory.run_start(goal="Integration test"))
            ledger.append(factory.step_start(step_id=1, description="Find information"))
            ledger.append(factory.tool_call("search", {"query": "test"}))
            ledger.append(factory.tool_result(output={"results": ["a", "b"]}))
            ledger.append(factory.state_patch(
                {"op": "set", "path": "/found", "value": 2}
            ))
            ledger.append(factory.run_end(
                status=RunStatus.COMPLETED,
                summary="Found 2 results"
            ))

            # Verify storage
            assert ledger.get_event_count(run_id) == 6

            # Replay
            engine = ReplayEngine(ledger)
            replay_result = engine.replay(run_id)
            assert replay_result.success
            assert replay_result.events_replayed == 6
            assert replay_result.final_state.get("found") == 2

            # Verify determinism
            det_result = engine.verify_determinism(run_id)
            assert det_result["deterministic"]
            assert det_result["hash_chain_valid"]

            # Inspect
            events = [e.model_dump() for e in ledger.get_events(run_id)]
            inspector = RunInspector()
            report = inspector.inspect(events, run_id)

            assert report.run_id == run_id
            assert len(report.timeline) == 6
            assert report.determinism_status.all_valid
