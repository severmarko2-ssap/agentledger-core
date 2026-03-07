"""Run Differ for AgentLedger Core.

Compares two runs and produces a diff report.
"""

from dataclasses import dataclass, field
from typing import Any

from agentledger.core.types import RunId


@dataclass
class EventDivergence:
    """A single event divergence between two runs."""

    step_id: int
    event_type_a: str
    event_type_b: str
    data_a: dict[str, Any]
    data_b: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "event_type_a": self.event_type_a,
            "event_type_b": self.event_type_b,
            "data_a": self.data_a,
            "data_b": self.data_b,
        }


@dataclass
class EnvironmentDiff:
    """Environment differences between runs."""

    engine_version_a: str = ""
    engine_version_b: str = ""
    engine_version_changed: bool = False
    config_changes: list[str] = field(default_factory=list)
    tool_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_version_a": self.engine_version_a,
            "engine_version_b": self.engine_version_b,
            "engine_version_changed": self.engine_version_changed,
            "config_changes": self.config_changes,
            "tool_changes": self.tool_changes,
        }

    @property
    def has_changes(self) -> bool:
        """Check if there are any environment changes."""
        return (
            self.engine_version_changed
            or bool(self.config_changes)
            or bool(self.tool_changes)
        )


@dataclass
class DiffReport:
    """Complete diff report between two runs."""

    run_a: RunId
    run_b: RunId
    events_a_count: int = 0
    events_b_count: int = 0
    environment_diff: EnvironmentDiff = field(default_factory=EnvironmentDiff)
    divergences: list[EventDivergence] = field(default_factory=list)
    first_divergence_step: int | None = None
    identical: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_a": self.run_a,
            "run_b": self.run_b,
            "events_a_count": self.events_a_count,
            "events_b_count": self.events_b_count,
            "environment_diff": self.environment_diff.to_dict(),
            "divergences": [d.to_dict() for d in self.divergences],
            "first_divergence_step": self.first_divergence_step,
            "identical": self.identical,
        }

    @property
    def has_differences(self) -> bool:
        """Check if there are any differences."""
        return not self.identical


class RunDiffer:
    """Compares two runs and produces a diff report.

    Example:
        differ = RunDiffer()
        report = differ.diff(events_a, events_b, run_a, run_b)
    """

    def diff(
        self,
        events_a: list[dict[str, Any]],
        events_b: list[dict[str, Any]],
        run_a: RunId,
        run_b: RunId,
    ) -> DiffReport:
        """Compare two runs.

        Args:
            events_a: Events from run A.
            events_b: Events from run B.
            run_a: Run A ID.
            run_b: Run B ID.

        Returns:
            DiffReport with comparison.
        """
        report = DiffReport(
            run_a=run_a,
            run_b=run_b,
            events_a_count=len(events_a),
            events_b_count=len(events_b),
        )

        # Environment diff
        report.environment_diff = self._diff_environment(events_a, events_b)

        # Find divergences
        divergences = self._find_divergences(events_a, events_b)
        report.divergences = divergences

        # First divergence
        if divergences:
            report.first_divergence_step = divergences[0].step_id
            report.identical = False
        elif len(events_a) != len(events_b):
            report.identical = False
        else:
            report.identical = not report.environment_diff.has_changes

        return report

    def _find_divergences(
        self,
        events_a: list[dict[str, Any]],
        events_b: list[dict[str, Any]],
    ) -> list[EventDivergence]:
        """Find divergences between event lists."""
        divergences = []
        min_len = min(len(events_a), len(events_b))

        for i in range(min_len):
            e_a = events_a[i]
            e_b = events_b[i]

            type_a = e_a.get("event_type") or e_a.get("event", "")
            type_b = e_b.get("event_type") or e_b.get("event", "")
            data_a = e_a.get("payload", e_a.get("data", {}))
            data_b = e_b.get("payload", e_b.get("data", {}))

            if type_a != type_b or data_a != data_b:
                step_id = e_a.get("step_id", e_a.get("seq", i))
                divergences.append(EventDivergence(
                    step_id=step_id,
                    event_type_a=type_a,
                    event_type_b=type_b,
                    data_a=data_a,
                    data_b=data_b,
                ))

        return divergences

    def _diff_environment(
        self,
        events_a: list[dict[str, Any]],
        events_b: list[dict[str, Any]],
    ) -> EnvironmentDiff:
        """Compare environment configurations."""
        diff = EnvironmentDiff()

        # Extract environment info
        env_a = self._extract_environment(events_a)
        env_b = self._extract_environment(events_b)

        # Compare versions
        diff.engine_version_a = env_a.get("engine_version", "")
        diff.engine_version_b = env_b.get("engine_version", "")
        diff.engine_version_changed = diff.engine_version_a != diff.engine_version_b

        # Compare config keys
        config_a = env_a.get("config", {})
        config_b = env_b.get("config", {})
        all_keys = set(config_a.keys()) | set(config_b.keys())
        for key in all_keys:
            if config_a.get(key) != config_b.get(key):
                diff.config_changes.append(key)

        # Compare tools
        tools_a = set(env_a.get("tools", []))
        tools_b = set(env_b.get("tools", []))
        for tool in tools_a - tools_b:
            diff.tool_changes.append(f"-{tool}")
        for tool in tools_b - tools_a:
            diff.tool_changes.append(f"+{tool}")

        return diff

    def _extract_environment(
        self,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract environment info from events."""
        env: dict[str, Any] = {"config": {}, "tools": []}

        for event in events:
            event_type = event.get("event_type") or event.get("event", "")
            payload = event.get("payload", event.get("data", {}))

            # Engine version
            if "engine_version" in payload:
                env["engine_version"] = payload["engine_version"]
            if "engine_version" in event:
                env["engine_version"] = event["engine_version"]

            # Config events
            if "config" in event_type.lower():
                env["config"].update(payload)

            # Tool events
            if "tool" in event_type.lower():
                tool_name = payload.get("tool", payload.get("tool_name", ""))
                if tool_name and tool_name not in env["tools"]:
                    env["tools"].append(tool_name)

        return env


def diff_runs(
    events_a: list[dict[str, Any]],
    events_b: list[dict[str, Any]],
    run_a: RunId = "run_a",
    run_b: RunId = "run_b",
) -> DiffReport:
    """Convenience function to diff two runs.

    Args:
        events_a: Events from run A.
        events_b: Events from run B.
        run_a: Run A ID.
        run_b: Run B ID.

    Returns:
        DiffReport.
    """
    differ = RunDiffer()
    return differ.diff(events_a, events_b, run_a, run_b)
