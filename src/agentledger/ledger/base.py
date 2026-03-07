"""Base ledger interface for AgentLedger Core."""

from abc import ABC, abstractmethod
from typing import Iterator, Any

from agentledger.core.types import RunId
from agentledger.events.envelope import EventEnvelope


class BaseLedger(ABC):
    """Abstract base class for ledger implementations.

    A ledger stores the complete execution history of agent runs,
    including events and associated blobs (large data like prompts/responses).

    Implementations must handle:
    - Run lifecycle (create, list, metadata)
    - Event storage and retrieval
    - Blob storage for large data
    """

    @abstractmethod
    def create_run(self, run_id: RunId) -> None:
        """Initialize storage for a new run.

        Args:
            run_id: Unique identifier for the run.

        Raises:
            LedgerError: If the run already exists.
        """
        pass

    @abstractmethod
    def run_exists(self, run_id: RunId) -> bool:
        """Check if a run exists.

        Args:
            run_id: Run identifier to check.

        Returns:
            True if the run exists.
        """
        pass

    @abstractmethod
    def append(self, event: EventEnvelope) -> None:
        """Append an event to a run's event log.

        Args:
            event: Event to append.

        Raises:
            LedgerError: If the run doesn't exist.
        """
        pass

    @abstractmethod
    def store_blob(
        self, run_id: RunId, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Store a blob and return its reference.

        Blobs are used for large data that shouldn't be inline in events,
        such as long prompts or responses.

        Args:
            run_id: Run to associate the blob with.
            data: Binary data to store.
            content_type: MIME type of the data.

        Returns:
            Blob reference string (e.g., "blob_abc123").

        Raises:
            LedgerError: If the run doesn't exist.
        """
        pass

    @abstractmethod
    def get_blob(self, run_id: RunId, blob_ref: str) -> bytes:
        """Retrieve a blob by reference.

        Args:
            run_id: Run the blob belongs to.
            blob_ref: Blob reference from store_blob.

        Returns:
            Binary blob data.

        Raises:
            LedgerError: If the run or blob doesn't exist.
        """
        pass

    @abstractmethod
    def get_events(
        self,
        run_id: RunId,
        start_seq: int = 0,
        end_seq: int | None = None,
    ) -> Iterator[EventEnvelope]:
        """Iterate over events in a run.

        Args:
            run_id: Run to get events from.
            start_seq: Starting sequence number (inclusive).
            end_seq: Ending sequence number (inclusive), None for all.

        Yields:
            Events in sequence order.

        Raises:
            LedgerError: If the run doesn't exist.
        """
        pass

    @abstractmethod
    def get_event_count(self, run_id: RunId) -> int:
        """Get the number of events in a run.

        Args:
            run_id: Run to count events for.

        Returns:
            Number of events.

        Raises:
            LedgerError: If the run doesn't exist.
        """
        pass

    @abstractmethod
    def list_runs(self) -> list[RunId]:
        """List all run IDs.

        Returns:
            List of run IDs, sorted by creation time (newest first).
        """
        pass

    @abstractmethod
    def get_run_metadata(self, run_id: RunId) -> dict[str, Any]:
        """Get metadata about a run.

        Args:
            run_id: Run to get metadata for.

        Returns:
            Dict with run metadata (created_at, event_count, etc.).

        Raises:
            LedgerError: If the run doesn't exist.
        """
        pass

    @abstractmethod
    def delete_run(self, run_id: RunId) -> bool:
        """Delete a run and all its data.

        Args:
            run_id: Run to delete.

        Returns:
            True if the run was deleted, False if it didn't exist.
        """
        pass
