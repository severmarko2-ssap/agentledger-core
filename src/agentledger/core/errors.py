"""Exception hierarchy for AgentLedger Core."""


class AgentLedgerError(Exception):
    """Base exception for all AgentLedger errors."""

    pass


class RuntimeError(AgentLedgerError):
    """Runtime execution errors.

    Raised when there are issues with agent execution lifecycle,
    such as starting a run without proper initialization or
    calling methods outside of an active run.
    """

    pass


class LedgerError(AgentLedgerError):
    """Ledger storage errors.

    Raised when there are issues with the execution ledger,
    such as failed writes, missing runs, or corrupted data.
    """

    pass


class EventValidationError(AgentLedgerError):
    """Event validation errors.

    Raised when an event fails validation, such as missing
    required fields or invalid event types.
    """

    pass


class StateError(AgentLedgerError):
    """State management errors.

    Raised when there are issues with world state operations,
    such as invalid paths or incompatible patch operations.
    """

    pass


class HashChainError(AgentLedgerError):
    """Hash chain integrity errors.

    Raised when the hash chain verification fails,
    indicating potential tampering or corruption.
    """

    pass


class ReplayError(AgentLedgerError):
    """Replay errors.

    Raised when there are issues during deterministic replay,
    such as missing cassette data or decision mismatches.
    """

    pass


class ConfigurationError(AgentLedgerError):
    """Configuration errors.

    Raised when there are issues with agent or runtime configuration.
    """

    pass
