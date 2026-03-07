"""Compliance tests for AgentLedger Core v0.1 specification.

These tests verify compliance with SPEC.md, not internal implementation.
A compliant implementation MUST pass all tests in this suite.
"""

import json
import tempfile
from pathlib import Path

import pytest

from agentledger import (
    LocalLedger,
    EventFactory,
    EventEnvelope,
    ReplayEngine,
    RunInspector,
    RunStatus,
    EventType,
    diff_runs,
    verify_hash_chain,
    GENESIS_HASH,
)


class TestRunLayoutCompliance:
    """D1: Verify canonical run layout from SPEC.md Section 2."""

    def test_run_directory_created(self):
        """Run directory must be created with correct name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            run_dir = Path(tmpdir) / "run_001"
            assert run_dir.exists()
            assert run_dir.is_dir()

    def test_run_manifest_exists(self):
        """run.json manifest must exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            manifest = Path(tmpdir) / "run_001" / "run.json"
            assert manifest.exists()

    def test_run_manifest_required_fields(self):
        """run.json must have required fields per SPEC.md Section 2.1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            manifest = Path(tmpdir) / "run_001" / "run.json"
            data = json.loads(manifest.read_text())

            # Required fields
            assert "run_id" in data
            assert "created_at" in data
            assert "event_count" in data

            assert data["run_id"] == "run_001"
            assert isinstance(data["event_count"], int)

    def test_events_file_exists(self):
        """events.jsonl must exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            events_file = Path(tmpdir) / "run_001" / "events.jsonl"
            assert events_file.exists()

    def test_blobs_directory_exists(self):
        """blobs/ directory must exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            blobs_dir = Path(tmpdir) / "run_001" / "blobs"
            assert blobs_dir.exists()
            assert blobs_dir.is_dir()


class TestEventEnvelopeCompliance:
    """D2: Verify event envelope required fields per SPEC.md Section 3."""

    def test_required_fields_present(self):
        """Every event must have required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            event = factory.run_start(goal="Test")
            ledger.append(event)

            # Read back from JSONL
            events_file = Path(tmpdir) / "run_001" / "events.jsonl"
            line = events_file.read_text().strip()
            data = json.loads(line)

            # Required fields per SPEC.md Section 3
            required = ["run_id", "seq", "ts", "event", "data", "prev_hash", "hash"]
            for field in required:
                assert field in data, f"Missing required field: {field}"

    def test_seq_starts_at_zero(self):
        """Sequence numbers must start at 0."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.run_start(goal="Test")
        assert event.seq == 0

    def test_seq_monotonically_increases(self):
        """Sequence numbers must increase monotonically."""
        factory = EventFactory(run_id="run_001", agent_id="agent")

        e1 = factory.run_start(goal="Test")
        e2 = factory.tool_call("search", {"q": "a"})
        e3 = factory.run_end(status=RunStatus.COMPLETED)

        assert e1.seq == 0
        assert e2.seq == 1
        assert e3.seq == 2

    def test_first_event_has_genesis_hash(self):
        """First event must have prev_hash = GENESIS."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.run_start(goal="Test")
        assert event.prev_hash == GENESIS_HASH

    def test_event_has_computed_hash(self):
        """Every event must have a computed hash."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.run_start(goal="Test")
        assert event.hash is not None
        assert len(event.hash) == 16  # Truncated SHA-256


class TestHashChainCompliance:
    """D3: Verify hash chain rules per SPEC.md Section 5."""

    def test_first_event_genesis(self):
        """First event must reference GENESIS hash."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        e1 = factory.run_start(goal="Test")
        assert e1.prev_hash == "GENESIS"

    def test_chain_links_correctly(self):
        """Each event must reference previous event's hash."""
        factory = EventFactory(run_id="run_001", agent_id="agent")

        e1 = factory.run_start(goal="Test")
        e2 = factory.tool_call("search", {"q": "a"})
        e3 = factory.run_end(status=RunStatus.COMPLETED)

        assert e1.prev_hash == GENESIS_HASH
        assert e2.prev_hash == e1.hash
        assert e3.prev_hash == e2.hash

    def test_tamper_invalidates_chain(self):
        """Modifying an event must invalidate the chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            # Read events
            events = list(ledger.get_events("run_001"))
            event_dicts = []
            for e in events:
                # Use same timestamp format as EventEnvelope.compute_hash
                ts_str = e.ts.isoformat().replace("+00:00", "Z") if hasattr(e.ts, "isoformat") else e.ts
                event_dicts.append({
                    "seq": e.seq,
                    "ts": ts_str,
                    "event": e.event.value if hasattr(e.event, "value") else e.event,
                    "category": e.category.value if hasattr(e.category, "value") else e.category,
                    "data": e.data,
                    "prev_hash": e.prev_hash,
                    "hash": e.hash,
                })

            # Verify original chain is valid
            valid, error = verify_hash_chain(event_dicts)
            assert valid, f"Original chain should be valid: {error}"

            # Tamper with data
            event_dicts[0]["data"]["goal"] = "TAMPERED"

            # Chain should now be invalid
            valid, error = verify_hash_chain(event_dicts)
            assert not valid, "Tampered chain should be invalid"

    def test_hash_is_16_chars(self):
        """Hash must be 16 hex characters (truncated SHA-256)."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.run_start(goal="Test")

        assert len(event.hash) == 16
        assert all(c in "0123456789abcdef" for c in event.hash)


class TestReplayCompliance:
    """D4: Verify replay validity per SPEC.md Section 6."""

    def test_replay_succeeds_for_valid_run(self):
        """Valid run must replay successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.tool_call("search", {"q": "test"}))
            ledger.append(factory.tool_result(output={"results": []}))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            engine = ReplayEngine(ledger)
            result = engine.replay("run_001")

            assert result.success
            assert result.events_replayed == 4

    def test_determinism_verification(self):
        """Determinism verification must succeed for valid run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            engine = ReplayEngine(ledger)
            result = engine.verify_determinism("run_001")

            assert result["hash_chain_valid"]
            assert result["deterministic"]
            assert result["event_count"] == 2


class TestExtensionEventsCompliance:
    """D5: Verify extension events don't break core functionality."""

    def test_state_snapshot_extension(self):
        """state.snapshot extension must not break replay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.state_snapshot({"key": "value"}))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            engine = ReplayEngine(ledger)
            result = engine.replay("run_001")

            assert result.success
            assert result.events_replayed == 3

    def test_custom_event_extension(self):
        """custom event extension must not break replay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.custom("my.custom.event", {"foo": "bar"}))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            engine = ReplayEngine(ledger)
            result = engine.replay("run_001")

            assert result.success

    def test_extension_events_in_inspection(self):
        """Extension events must be visible in inspection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.custom("my.event", {"x": 1}))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            events = [e.model_dump() for e in ledger.get_events("run_001")]
            inspector = RunInspector()
            report = inspector.inspect(events, "run_001")

            assert len(report.timeline) == 3


class TestDiffCompliance:
    """D6: Verify diff functionality per SPEC.md."""

    def test_diff_identical_runs(self):
        """Identical runs must show no divergences."""
        events = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test"}},
            {"seq": 1, "event": "run.end", "data": {"status": "completed"}},
        ]

        report = diff_runs(events, events, "run_a", "run_b")

        assert report.identical
        assert len(report.divergences) == 0

    def test_diff_changed_event(self):
        """Changed event must be detected."""
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

    def test_diff_added_event(self):
        """Added event must be detected."""
        events_a = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test"}},
        ]
        events_b = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test"}},
            {"seq": 1, "event": "run.end", "data": {"status": "completed"}},
        ]

        report = diff_runs(events_a, events_b, "run_a", "run_b")

        assert not report.identical
        # Length difference means not identical

    def test_diff_removed_event(self):
        """Removed event must be detected."""
        events_a = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test"}},
            {"seq": 1, "event": "run.end", "data": {"status": "completed"}},
        ]
        events_b = [
            {"seq": 0, "event": "run.start", "data": {"goal": "Test"}},
        ]

        report = diff_runs(events_a, events_b, "run_a", "run_b")

        assert not report.identical


class TestAppendOnlySemantics:
    """D7: Verify append-only semantics per SPEC.md Section 2.2."""

    def test_events_append_to_file(self):
        """Events must append to existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")

            # Append first event
            ledger.append(factory.run_start(goal="Test"))
            events_file = Path(tmpdir) / "run_001" / "events.jsonl"
            content_1 = events_file.read_text()
            lines_1 = [l for l in content_1.strip().split("\n") if l]

            # Append second event
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))
            content_2 = events_file.read_text()
            lines_2 = [l for l in content_2.strip().split("\n") if l]

            # First line should be unchanged
            assert lines_1[0] == lines_2[0]
            # Should have one more line
            assert len(lines_2) == len(lines_1) + 1

    def test_event_count_increments(self):
        """Event count in manifest must increment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")

            assert ledger.get_event_count("run_001") == 0

            ledger.append(factory.run_start(goal="Test"))
            assert ledger.get_event_count("run_001") == 1

            ledger.append(factory.run_end(status=RunStatus.COMPLETED))
            assert ledger.get_event_count("run_001") == 2

    def test_jsonl_format(self):
        """Events must be stored in valid JSON Lines format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = LocalLedger(tmpdir)
            ledger.create_run("run_001")

            factory = EventFactory(run_id="run_001", agent_id="agent")
            ledger.append(factory.run_start(goal="Test"))
            ledger.append(factory.run_end(status=RunStatus.COMPLETED))

            events_file = Path(tmpdir) / "run_001" / "events.jsonl"
            content = events_file.read_text()

            # Each line must be valid JSON
            for line in content.strip().split("\n"):
                if line:
                    data = json.loads(line)  # Should not raise
                    assert isinstance(data, dict)


class TestCanonicalEventTypes:
    """Verify all 9 canonical event types are supported."""

    def test_run_start(self):
        """run.start must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.run_start(goal="Test")
        assert event.event == EventType.RUN_START
        assert event.data["goal"] == "Test"

    def test_run_end(self):
        """run.end must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        factory.run_start(goal="Test")  # Need to advance seq
        event = factory.run_end(status=RunStatus.COMPLETED)
        assert event.event == EventType.RUN_END
        assert event.data["status"] == "completed"

    def test_step_start(self):
        """step.start must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.step_start(step_id=1, description="Step 1")
        assert event.event == EventType.STEP_START
        assert event.data["step_id"] == 1

    def test_step_end(self):
        """step.end must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.step_end(step_id=1, status="completed")
        assert event.event == EventType.STEP_END
        assert event.data["step_id"] == 1

    def test_tool_call(self):
        """tool.call must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.tool_call("search", {"query": "test"})
        assert event.event == EventType.TOOL_CALL
        assert event.data["tool"] == "search"

    def test_tool_result(self):
        """tool.result must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.tool_result(output={"results": []})
        assert event.event == EventType.TOOL_RESULT
        assert event.data["output"] == {"results": []}

    def test_decision(self):
        """decision must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.decision("continue", reasoning="All good")
        assert event.event == EventType.DECISION
        assert event.data["decision"] == "continue"

    def test_state_patch(self):
        """state.patch must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.state_patch({"op": "set", "path": "/count", "value": 1})
        assert event.event == EventType.STATE_PATCH
        assert len(event.data["patch"]) == 1

    def test_error(self):
        """error must be supported."""
        factory = EventFactory(run_id="run_001", agent_id="agent")
        event = factory.error("tool_failure", "Tool crashed")
        assert event.event == EventType.ERROR
        assert event.data["type"] == "tool_failure"
        assert event.data["message"] == "Tool crashed"
