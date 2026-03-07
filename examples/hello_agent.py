#!/usr/bin/env python3
"""Hello Agent - Minimal example of AgentLedger Core.

This example demonstrates:
- Creating a run
- Recording events
- Inspecting the run
- Replaying the run
- Verifying determinism
- Comparing two runs

No external APIs required - fully local.
"""

import tempfile
from pathlib import Path

from agentledger import (
    LocalLedger,
    EventFactory,
    ReplayEngine,
    RunInspector,
    RunStatus,
    diff_runs,
)


def main():
    # Create a temporary directory for the ledger
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Ledger directory: {tmpdir}\n")

        # Initialize ledger
        ledger = LocalLedger(tmpdir)

        # =====================================================================
        # Run 1: A simple agent run
        # =====================================================================
        print("=== Recording Run 1 ===")
        run_id = "run_hello_001"
        ledger.create_run(run_id)

        # Create event factory
        factory = EventFactory(run_id=run_id, agent_id="hello_agent")

        # Record run start (goal is optional)
        ledger.append(factory.run_start())
        print("  - run.start (no goal required)")

        # Record a step
        ledger.append(factory.step_start(step_id=1, description="Prepare greeting"))
        print("  - step.start: Prepare greeting")

        # Record tool call and result
        ledger.append(factory.tool_call("get_greeting", {"language": "en"}))
        print("  - tool.call: get_greeting")

        ledger.append(factory.tool_result(output={"greeting": "Hello, World!"}))
        print("  - tool.result: Hello, World!")

        # Record a decision
        ledger.append(factory.decision("continue", reasoning="Greeting received"))
        print("  - decision: continue")

        # Record state change
        ledger.append(factory.state_patch(
            {"op": "set", "path": "/greeting", "value": "Hello, World!"}
        ))
        print("  - state.patch: /greeting = Hello, World!")

        # End step
        ledger.append(factory.step_end(step_id=1, status="completed"))
        print("  - step.end: completed")

        # End run
        ledger.append(factory.run_end(
            status=RunStatus.COMPLETED,
            summary="Successfully greeted the world"
        ))
        print("  - run.end: completed\n")

        # =====================================================================
        # Inspect the run
        # =====================================================================
        print("=== Inspecting Run 1 ===")
        events = [e.model_dump() for e in ledger.get_events(run_id)]
        inspector = RunInspector()
        report = inspector.inspect(events, run_id)

        print(f"  Run ID: {report.run_id}")
        print(f"  Events: {len(report.timeline)}")
        print(f"  Duration: {report.duration_seconds}s")
        print(f"  Determinism valid: {report.determinism_status.all_valid}\n")

        # =====================================================================
        # Replay and verify determinism
        # =====================================================================
        print("=== Replaying Run 1 ===")
        engine = ReplayEngine(ledger)

        # Replay
        replay_result = engine.replay(run_id)
        print(f"  Events replayed: {replay_result.events_replayed}")
        print(f"  Success: {replay_result.success}")

        # Verify determinism
        det_result = engine.verify_determinism(run_id)
        print(f"  Hash chain valid: {det_result['hash_chain_valid']}")
        print(f"  Deterministic: {det_result['deterministic']}\n")

        # =====================================================================
        # Run 2: A slightly different run
        # =====================================================================
        print("=== Recording Run 2 (different goal) ===")
        run_id_2 = "run_hello_002"
        ledger.create_run(run_id_2)

        factory_2 = EventFactory(run_id=run_id_2, agent_id="hello_agent")

        # Same structure but different goal
        ledger.append(factory_2.run_start(goal="Say goodbye to the world"))
        ledger.append(factory_2.step_start(step_id=1, description="Prepare farewell"))
        ledger.append(factory_2.tool_call("get_greeting", {"language": "en", "type": "farewell"}))
        ledger.append(factory_2.tool_result(output={"greeting": "Goodbye, World!"}))
        ledger.append(factory_2.decision("continue", reasoning="Farewell received"))
        ledger.append(factory_2.state_patch(
            {"op": "set", "path": "/greeting", "value": "Goodbye, World!"}
        ))
        ledger.append(factory_2.step_end(step_id=1, status="completed"))
        ledger.append(factory_2.run_end(
            status=RunStatus.COMPLETED,
            summary="Successfully said goodbye"
        ))
        print("  Recorded 8 events\n")

        # =====================================================================
        # Compare the two runs
        # =====================================================================
        print("=== Comparing Run 1 vs Run 2 ===")
        events_1 = [e.model_dump() for e in ledger.get_events(run_id)]
        events_2 = [e.model_dump() for e in ledger.get_events(run_id_2)]

        diff_report = diff_runs(events_1, events_2, run_id, run_id_2)
        print(f"  Identical: {diff_report.identical}")
        print(f"  Divergences: {len(diff_report.divergences)}")
        if diff_report.first_divergence_step is not None:
            print(f"  First divergence at step: {diff_report.first_divergence_step}")

        # =====================================================================
        # Show storage layout
        # =====================================================================
        print("\n=== Storage Layout ===")
        for run in [run_id, run_id_2]:
            run_path = Path(tmpdir) / run
            print(f"  {run}/")
            for item in sorted(run_path.iterdir()):
                if item.is_file():
                    print(f"    {item.name} ({item.stat().st_size} bytes)")
                else:
                    print(f"    {item.name}/")

        print("\nDone!")


if __name__ == "__main__":
    main()
