"""Run Inspector for AgentLedger Core.

Produces human-readable forensic reports of agent runs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agentledger.core.types import RunId


@dataclass
class DeterminismStatus:
    """Status of determinism checks for a run."""

    content_hash_valid: bool = True
    belief_hash_valid: bool = True
    memory_hits_hash_valid: bool = True
    index_fingerprint_valid: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def all_valid(self) -> bool:
        """Check if all determinism checks pass."""
        return (
            self.content_hash_valid
            and self.belief_hash_valid
            and self.memory_hits_hash_valid
            and self.index_fingerprint_valid
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_hash_valid": self.content_hash_valid,
            "belief_hash_valid": self.belief_hash_valid,
            "memory_hits_hash_valid": self.memory_hits_hash_valid,
            "index_fingerprint_valid": self.index_fingerprint_valid,
            "all_valid": self.all_valid,
            "details": self.details,
        }


@dataclass
class TimelineEvent:
    """A single event in the run timeline."""

    step_id: int
    event_type: str
    summary: str = ""
    timestamp: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "event_type": self.event_type,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "details": self.details,
        }


@dataclass
class FailureAnalysisResult:
    """Result of failure analysis."""

    failure_type: str = "NONE"
    divergence_type: str = "NONE"
    root_cause_candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "failure_type": self.failure_type,
            "divergence_type": self.divergence_type,
            "root_cause_candidates": self.root_cause_candidates,
        }


@dataclass
class InspectReport:
    """Complete inspection report for a run."""

    run_id: RunId
    engine_version: str = ""
    started: datetime | None = None
    ended: datetime | None = None
    duration_seconds: float = 0.0
    determinism_status: DeterminismStatus = field(default_factory=DeterminismStatus)
    timeline: list[TimelineEvent] = field(default_factory=list)
    failure_analysis: FailureAnalysisResult = field(default_factory=FailureAnalysisResult)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "engine_version": self.engine_version,
            "started": self.started.isoformat() if self.started else None,
            "ended": self.ended.isoformat() if self.ended else None,
            "duration_seconds": self.duration_seconds,
            "determinism_status": self.determinism_status.to_dict(),
            "timeline": [e.to_dict() for e in self.timeline],
            "failure_analysis": self.failure_analysis.to_dict(),
            "metadata": self.metadata,
        }


class RunInspector:
    """Inspects a run and produces a forensic report.

    Example:
        inspector = RunInspector()
        report = inspector.inspect(events, run_id)
    """

    def __init__(self, engine_version: str = "0.1"):
        """Initialize inspector.

        Args:
            engine_version: Current engine version.
        """
        self.engine_version = engine_version

    def inspect(
        self,
        events: list[dict[str, Any]],
        run_id: RunId,
    ) -> InspectReport:
        """Inspect a run and produce a report.

        Args:
            events: List of event dictionaries.
            run_id: The run ID.

        Returns:
            InspectReport with analysis results.
        """
        report = InspectReport(run_id=run_id, engine_version=self.engine_version)

        if not events:
            return report

        # Extract timeline
        report.timeline = self._build_timeline(events)

        # Extract timing
        report.started, report.ended, report.duration_seconds = self._extract_timing(events)

        # Check determinism
        report.determinism_status = self._check_determinism(events)

        # Run failure analysis if needed
        report.failure_analysis = self._analyze_failures(events)

        # Extract metadata
        report.metadata = self._extract_metadata(events)

        return report

    def _build_timeline(self, events: list[dict[str, Any]]) -> list[TimelineEvent]:
        """Build timeline from events."""
        timeline: list[TimelineEvent] = []

        for event in events:
            step_id = event.get("step_id", event.get("seq", 0))
            event_type = event.get("event_type") or event.get("event", "unknown")
            payload = event.get("payload", event.get("data", {}))

            # Build summary based on event type
            summary = self._summarize_event(event_type, payload)

            # Parse timestamp
            ts = None
            if "ts" in event:
                try:
                    ts_val = event["ts"]
                    if isinstance(ts_val, datetime):
                        ts = ts_val
                    elif isinstance(ts_val, str):
                        ts = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                except (ValueError, AttributeError, TypeError):
                    pass

            timeline.append(TimelineEvent(
                step_id=step_id,
                event_type=event_type,
                summary=summary,
                timestamp=ts,
                details=payload,
            ))

        return timeline

    def _summarize_event(self, event_type: str, payload: dict[str, Any]) -> str:
        """Create a short summary for an event."""
        # Tool calls
        if "tool" in event_type.lower():
            tool_name = payload.get("tool", payload.get("tool_name", ""))
            if tool_name:
                return f"tool: {tool_name}"

        # Memory events
        if "memory" in event_type.lower():
            query = payload.get("query_text", "")
            if query:
                return f"query: {query[:30]}..."
            hits_count = len(payload.get("hits", []))
            if hits_count:
                return f"{hits_count} hits"

        # Decision events
        if "decision" in event_type.lower():
            decision = payload.get("decision", "")
            if decision:
                return f"decision: {decision[:30]}..."

        return ""

    def _extract_timing(
        self,
        events: list[dict[str, Any]],
    ) -> tuple[datetime | None, datetime | None, float]:
        """Extract start/end times and duration."""
        started = None
        ended = None

        for event in events:
            ts_val = event.get("ts")

            if not ts_val:
                continue

            try:
                if isinstance(ts_val, datetime):
                    ts = ts_val
                elif isinstance(ts_val, str):
                    ts = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                else:
                    continue
            except (ValueError, AttributeError, TypeError):
                continue

            # Track first and last timestamps
            if started is None or ts < started:
                started = ts
            if ended is None or ts > ended:
                ended = ts

        duration = 0.0
        if started and ended:
            duration = (ended - started).total_seconds()

        return started, ended, duration

    def _check_determinism(self, events: list[dict[str, Any]]) -> DeterminismStatus:
        """Check determinism status from events."""
        status = DeterminismStatus()
        details: dict[str, Any] = {}

        for event in events:
            event_type = event.get("event_type") or event.get("event", "")
            payload = event.get("payload", event.get("data", {}))

            # Check for determinism violations
            if "violation" in event_type.lower() or "mismatch" in event_type.lower():
                if "snapshot" in event_type.lower() or "content" in event_type.lower():
                    status.content_hash_valid = False
                    details["content_hash_error"] = payload
                elif "decision" in event_type.lower() or "belief" in event_type.lower():
                    status.belief_hash_valid = False
                    details["belief_hash_error"] = payload
                elif "memory" in event_type.lower():
                    status.memory_hits_hash_valid = False
                    details["memory_hash_error"] = payload
                elif "index" in event_type.lower():
                    status.index_fingerprint_valid = False
                    details["index_error"] = payload

        status.details = details
        return status

    def _analyze_failures(self, events: list[dict[str, Any]]) -> FailureAnalysisResult:
        """Run failure analysis on events."""
        result = FailureAnalysisResult()

        # Check for failure events
        failure_events = []
        for event in events:
            event_type = event.get("event_type") or event.get("event", "")
            if any(f in event_type.lower() for f in ["failed", "error", "violation", "guardrail"]):
                failure_events.append(event)

        if not failure_events:
            return result

        # Determine failure type
        for event in failure_events:
            event_type = event.get("event_type") or event.get("event", "")
            if "assertion" in event_type.lower():
                result.failure_type = "ASSERTION_FAILED"
                break
            elif "guardrail" in event_type.lower():
                result.failure_type = "GUARDRAIL_TRIGGERED"
                break
            elif "run" in event_type.lower() and "failed" in event_type.lower():
                result.failure_type = "RUN_FAILED"
                break
            elif "mismatch" in event_type.lower():
                result.failure_type = "HASH_MISMATCH"
                result.divergence_type = "DECISION" if "decision" in event_type.lower() else "BELIEF"
                break

        return result

    def _extract_metadata(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract metadata from events."""
        metadata: dict[str, Any] = {}

        for event in events:
            event_type = event.get("event_type") or event.get("event", "")
            payload = event.get("payload", event.get("data", {}))

            # Extract config/environment info
            if "config" in event_type.lower() or "environment" in event_type.lower():
                metadata.update(payload)

            # Extract version info
            if "engine_version" in payload:
                metadata["engine_version"] = payload["engine_version"]

        return metadata
