"""World state container for AgentLedger Core."""

from copy import deepcopy
from typing import Any

from agentledger.core.types import PatchOp
from agentledger.core.errors import StateError


class WorldState:
    """Container for agent world state.

    Maintains structured state that can be patched and snapshotted
    for replay purposes. State is organized as a nested dictionary
    accessed via path strings like '/foo/bar'.

    Example:
        state = WorldState()
        state.set('/progress', 0.5)
        state.set('/sources/found', 3)
        print(state.get('/progress'))  # 0.5
        state.apply_patch({'op': 'increment', 'path': '/sources/found', 'value': 1})
        print(state.get('/sources/found'))  # 4
    """

    def __init__(self, initial: dict[str, Any] | None = None):
        """Initialize the world state.

        Args:
            initial: Optional initial state dictionary.
        """
        self._data: dict[str, Any] = deepcopy(initial) if initial else {}

    def get(self, path: str, default: Any = None) -> Any:
        """Get a value by path.

        Args:
            path: Path string like '/foo/bar' or 'foo/bar'.
            default: Value to return if path doesn't exist.

        Returns:
            The value at the path, or default if not found.
        """
        keys = self._parse_path(path)
        if not keys:
            return self._data

        current: Any = self._data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def set(self, path: str, value: Any) -> None:
        """Set a value by path.

        Creates intermediate dictionaries as needed.

        Args:
            path: Path string like '/foo/bar'.
            value: Value to set.

        Raises:
            StateError: If path is empty or invalid.
        """
        keys = self._parse_path(path)
        if not keys:
            raise StateError("Cannot set root path directly; use a nested path")

        current = self._data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                raise StateError(
                    f"Cannot traverse through non-dict at '{key}' in path '{path}'"
                )
            current = current[key]

        current[keys[-1]] = value

    def delete(self, path: str) -> bool:
        """Delete a value by path.

        Args:
            path: Path string like '/foo/bar'.

        Returns:
            True if the value was deleted, False if it didn't exist.

        Raises:
            StateError: If path is empty.
        """
        keys = self._parse_path(path)
        if not keys:
            raise StateError("Cannot delete root path")

        current = self._data
        for key in keys[:-1]:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]

        if isinstance(current, dict) and keys[-1] in current:
            del current[keys[-1]]
            return True
        return False

    def apply_patch(self, patch: dict[str, Any]) -> None:
        """Apply a single patch operation.

        Args:
            patch: Dict with 'op', 'path', and optionally 'value'.

        Raises:
            StateError: If the patch operation is invalid.
        """
        op = PatchOp(patch["op"])
        path = patch["path"]
        value = patch.get("value")

        if op == PatchOp.SET:
            self.set(path, value)

        elif op == PatchOp.DELETE:
            self.delete(path)

        elif op == PatchOp.APPEND:
            current = self.get(path)
            if current is None:
                # Initialize as list if doesn't exist
                self.set(path, [value])
            elif isinstance(current, list):
                current.append(value)
                self.set(path, current)
            else:
                raise StateError(f"Cannot append to non-list at '{path}'")

        elif op == PatchOp.INCREMENT:
            current = self.get(path, 0)
            if not isinstance(current, (int, float)):
                raise StateError(f"Cannot increment non-number at '{path}'")
            self.set(path, current + value)

        else:
            raise StateError(f"Unknown patch operation: {op}")

    def apply_patches(self, patches: list[dict[str, Any]]) -> None:
        """Apply multiple patch operations.

        Args:
            patches: List of patch dicts.
        """
        for patch in patches:
            self.apply_patch(patch)

    def snapshot(self) -> dict[str, Any]:
        """Create a deep copy snapshot of current state.

        Returns:
            Deep copy of the internal state dictionary.
        """
        return deepcopy(self._data)

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore state from a snapshot.

        Args:
            snapshot: State dictionary to restore.
        """
        self._data = deepcopy(snapshot)

    def clear(self) -> None:
        """Clear all state."""
        self._data = {}

    def _parse_path(self, path: str) -> list[str]:
        """Parse a path string into keys.

        Args:
            path: Path string like '/foo/bar' or 'foo/bar'.

        Returns:
            List of path keys.
        """
        if not path or path == "/":
            return []
        # Remove leading slash and split
        return [k for k in path.lstrip("/").split("/") if k]

    def __contains__(self, path: str) -> bool:
        """Check if a path exists in the state."""
        keys = self._parse_path(path)
        if not keys:
            return True

        current: Any = self._data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        return True

    def __repr__(self) -> str:
        """Return a string representation of the state."""
        return f"WorldState({self._data})"
