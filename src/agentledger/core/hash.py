"""Hash chain and canonical JSON utilities for deterministic ledger."""

import hashlib
import json
from typing import Any

from .types import GENESIS_HASH


def canonical_json(obj: Any) -> str:
    """Serialize object to canonical JSON format.

    Ensures deterministic serialization with:
    - Sorted keys
    - UTF-8 encoding
    - No whitespace differences
    - Consistent float formatting

    Args:
        obj: Object to serialize.

    Returns:
        Canonical JSON string.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,  # Handle datetime and other non-serializable types
    )


def compute_event_hash(
    prev_hash: str,
    seq: int,
    ts: str,
    event_type: str,
    category: str,
    payload: dict[str, Any],
) -> str:
    """Compute SHA-256 hash for an event.

    Hash formula: sha256(prev_hash + seq + ts + type + category + canonical_json(payload))

    Args:
        prev_hash: Hash of the previous event (or GENESIS for first event).
        seq: Sequence number.
        ts: ISO timestamp string.
        event_type: Event type string.
        category: Category enum value.
        payload: Event data payload.

    Returns:
        Hex-encoded SHA-256 hash (first 16 chars for brevity).
    """
    # Build the hash input string
    hash_input = f"{prev_hash}{seq}{ts}{event_type}{category}{canonical_json(payload)}"

    # Compute SHA-256
    hash_bytes = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    # Return first 16 characters for brevity while maintaining uniqueness
    return hash_bytes[:16]


def verify_hash_chain(events: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Verify the integrity of a hash chain.

    Args:
        events: List of event dictionaries with hash fields.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is None.
    """
    if not events:
        return True, None

    prev_hash = GENESIS_HASH

    for i, event in enumerate(events):
        stored_hash = event.get("hash")
        stored_prev_hash = event.get("prev_hash")

        # Verify prev_hash links correctly
        if stored_prev_hash != prev_hash:
            return False, f"Event {i} (seq {event.get('seq')}): prev_hash mismatch. Expected {prev_hash}, got {stored_prev_hash}"

        # Recompute hash
        computed_hash = compute_event_hash(
            prev_hash=stored_prev_hash,
            seq=event.get("seq", 0),
            ts=event.get("ts", ""),
            event_type=event.get("event", event.get("type", "")),
            category=event.get("category", ""),
            payload=event.get("data", event.get("payload", {})),
        )

        if stored_hash != computed_hash:
            return False, f"Event {i} (seq {event.get('seq')}): hash mismatch. Expected {computed_hash}, got {stored_hash}"

        prev_hash = stored_hash

    return True, None


def compute_final_hash(events: list[dict[str, Any]]) -> str:
    """Compute the final hash of a ledger.

    Args:
        events: List of event dictionaries.

    Returns:
        Final hash of the chain, or GENESIS if empty.
    """
    if not events:
        return GENESIS_HASH

    # Return the hash of the last event
    return events[-1].get("hash", GENESIS_HASH)
