"""Local file-based ledger implementation."""

import json
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Any

from agentledger.core.types import RunId
from agentledger.core.errors import LedgerError
from agentledger.events.envelope import EventEnvelope
from .base import BaseLedger


# Storage constants
RUN_ID_PREFIX = "run_"
CANONICAL_MANIFEST = "run.json"
LEGACY_MANIFEST = "metadata.json"


def normalize_run_id(run_id: str) -> str:
    """Normalize a user-provided run ID.

    Ensures run ID has the canonical 'run_' prefix.

    Args:
        run_id: User-provided run identifier.

    Returns:
        Normalized run ID with 'run_' prefix.
    """
    if run_id.startswith(RUN_ID_PREFIX):
        return run_id
    return f"{RUN_ID_PREFIX}{run_id}"


def resolve_run_manifest(run_dir: Path) -> Path:
    """Resolve the manifest path for a run directory.

    Uses canonical + legacy fallback resolution:
    1. If metadata.json exists -> return it
    2. Else if run.json exists -> return it
    3. Else raise LedgerError

    Args:
        run_dir: Path to the run directory.

    Returns:
        Path to the manifest file.

    Raises:
        LedgerError: If neither manifest file exists.
    """
    # Try canonical manifest first
    canonical_path = run_dir / CANONICAL_MANIFEST
    if canonical_path.exists():
        return canonical_path

    # Fall back to legacy manifest
    legacy_path = run_dir / LEGACY_MANIFEST
    if legacy_path.exists():
        return legacy_path

    # Neither exists - raise explicit error
    raise LedgerError(f"Run manifest not found in {run_dir}")


class LocalLedger(BaseLedger):
    """Local file-based ledger implementation.

    Storage structure:
        base_path/
            run_{id}/
                events.jsonl    # Append-only event log
                blobs/          # Binary blob storage
                    blob_{hash} # Individual blobs
                    blob_{hash}.meta  # Blob metadata
                metadata.json   # Run metadata

    This implementation is suitable for development, testing, and
    single-machine deployments.
    """

    def __init__(self, base_path: Path | str):
        """Initialize the local ledger.

        Args:
            base_path: Directory to store ledger data.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _run_path(self, run_id: RunId) -> Path:
        """Get the directory path for a run.

        Normalizes run_id to ensure canonical 'run_' prefix.
        """
        return self.base_path / normalize_run_id(run_id)

    def _events_path(self, run_id: RunId) -> Path:
        """Get the events file path for a run."""
        return self._run_path(run_id) / "events.jsonl"

    def _blobs_path(self, run_id: RunId) -> Path:
        """Get the blobs directory path for a run."""
        return self._run_path(run_id) / "blobs"

    def _metadata_path(self, run_id: RunId) -> Path:
        """Get the metadata file path for a run (canonical location)."""
        return self._run_path(run_id) / CANONICAL_MANIFEST

    def create_run(self, run_id: RunId) -> None:
        """Initialize storage for a new run."""
        run_path = self._run_path(run_id)
        if run_path.exists():
            raise LedgerError(f"Run {run_id} already exists")

        # Create directories
        run_path.mkdir(parents=True)
        self._blobs_path(run_id).mkdir()

        # Initialize empty events file
        self._events_path(run_id).touch()

        # Initialize metadata
        metadata = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "event_count": 0,
        }
        self._metadata_path(run_id).write_text(json.dumps(metadata, indent=2))

    def run_exists(self, run_id: RunId) -> bool:
        """Check if a run exists."""
        return self._run_path(run_id).exists()

    def append(self, event: EventEnvelope) -> None:
        """Append an event to a run's event log."""
        events_path = self._events_path(event.run_id)
        if not events_path.exists():
            raise LedgerError(f"Run {event.run_id} does not exist")

        # Append as single line (JSONL format)
        with events_path.open("a", encoding="utf-8") as f:
            f.write(event.to_jsonl() + "\n")

        # Update metadata event count
        self._increment_event_count(event.run_id)

    def _increment_event_count(self, run_id: RunId) -> None:
        """Increment the event count in metadata."""
        metadata_path = self._metadata_path(run_id)
        metadata = json.loads(metadata_path.read_text())
        metadata["event_count"] = metadata.get("event_count", 0) + 1
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(metadata, indent=2))

    def store_blob(
        self, run_id: RunId, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Store a blob and return its reference."""
        blobs_path = self._blobs_path(run_id)
        if not blobs_path.exists():
            raise LedgerError(f"Run {run_id} does not exist")

        # Content-addressable storage using SHA-256
        blob_hash = hashlib.sha256(data).hexdigest()[:16]
        blob_ref = f"blob_{blob_hash}"

        blob_path = blobs_path / blob_ref
        if not blob_path.exists():
            # Store the blob
            blob_path.write_bytes(data)

            # Store metadata
            meta = {
                "content_type": content_type,
                "size": len(data),
                "hash": blob_hash,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            (blobs_path / f"{blob_ref}.meta").write_text(json.dumps(meta))

        return blob_ref

    def get_blob(self, run_id: RunId, blob_ref: str) -> bytes:
        """Retrieve a blob by reference."""
        blob_path = self._blobs_path(run_id) / blob_ref
        if not blob_path.exists():
            raise LedgerError(f"Blob {blob_ref} not found in run {run_id}")
        return blob_path.read_bytes()

    def get_blob_metadata(self, run_id: RunId, blob_ref: str) -> dict[str, Any]:
        """Get metadata for a blob."""
        meta_path = self._blobs_path(run_id) / f"{blob_ref}.meta"
        if not meta_path.exists():
            raise LedgerError(f"Blob metadata for {blob_ref} not found in run {run_id}")
        return json.loads(meta_path.read_text())

    def get_events(
        self,
        run_id: RunId,
        start_seq: int = 0,
        end_seq: int | None = None,
    ) -> Iterator[EventEnvelope]:
        """Iterate over events in a run."""
        events_path = self._events_path(run_id)
        if not events_path.exists():
            raise LedgerError(f"Run {run_id} does not exist")

        with events_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                event = EventEnvelope.from_jsonl(line)

                if event.seq < start_seq:
                    continue

                if end_seq is not None and event.seq > end_seq:
                    break

                yield event

    def get_event_count(self, run_id: RunId) -> int:
        """Get the number of events in a run."""
        metadata = self.get_run_metadata(run_id)
        return metadata.get("event_count", 0)

    def list_runs(self) -> list[RunId]:
        """List all run IDs, sorted by creation time (newest first)."""
        runs: list[tuple[str, datetime]] = []

        for path in self.base_path.iterdir():
            if path.is_dir() and path.name.startswith("run_"):
                try:
                    manifest_path = resolve_run_manifest(path)
                    metadata = json.loads(manifest_path.read_text())
                    created_at = datetime.fromisoformat(
                        metadata.get("created_at", "1970-01-01T00:00:00+00:00")
                    )
                    runs.append((path.name, created_at))
                except (LedgerError, json.JSONDecodeError, ValueError):
                    pass

        # Sort by creation time, newest first
        runs.sort(key=lambda x: x[1], reverse=True)
        return [run_id for run_id, _ in runs]

    def get_run_metadata(self, run_id: RunId) -> dict[str, Any]:
        """Get metadata about a run."""
        run_path = self._run_path(run_id)
        if not run_path.exists():
            raise LedgerError(f"Run {normalize_run_id(run_id)} does not exist")

        try:
            manifest_path = resolve_run_manifest(run_path)
            return json.loads(manifest_path.read_text())
        except LedgerError:
            raise LedgerError(f"Run {normalize_run_id(run_id)} manifest not found")

    def update_run_metadata(self, run_id: RunId, **kwargs: Any) -> None:
        """Update run metadata with additional fields."""
        metadata_path = self._metadata_path(run_id)
        if not metadata_path.exists():
            raise LedgerError(f"Run {run_id} does not exist")

        metadata = json.loads(metadata_path.read_text())
        metadata.update(kwargs)
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(metadata, indent=2))

    def delete_run(self, run_id: RunId) -> bool:
        """Delete a run and all its data."""
        run_path = self._run_path(run_id)
        if not run_path.exists():
            return False

        shutil.rmtree(run_path)
        return True

    def get_last_event(self, run_id: RunId) -> EventEnvelope | None:
        """Get the last event in a run.

        Args:
            run_id: Run to get last event from.

        Returns:
            Last event or None if run is empty.
        """
        events_path = self._events_path(run_id)
        if not events_path.exists():
            raise LedgerError(f"Run {run_id} does not exist")

        last_line = None
        with events_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line

        if last_line:
            return EventEnvelope.from_jsonl(last_line)
        return None
