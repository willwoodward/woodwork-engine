"""Credential storage for OAuth tokens and API keys.

Stores credentials in ~/.woodwork/credentials/<provider>.json
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

CREDENTIALS_DIR = Path.home() / ".woodwork" / "credentials"


class CredentialStore:
    """File-based credential storage."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or CREDENTIALS_DIR

    def _ensure_dir(self) -> None:
        """Create credentials directory if it doesn't exist."""
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, provider: str, data: dict[str, Any]) -> None:
        """Save credentials for a provider."""
        self._ensure_dir()
        path = self._base_dir / f"{provider}.json"
        path.write_text(json.dumps(data, indent=2))
        # Restrict file permissions (owner read/write only)
        path.chmod(0o600)
        log.debug(f"Saved credentials for {provider}")

    def load(self, provider: str) -> Optional[dict[str, Any]]:
        """Load credentials for a provider. Returns None if not found."""
        path = self._base_dir / f"{provider}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"Failed to load credentials for {provider}: {e}")
            return None

    def delete(self, provider: str) -> bool:
        """Delete credentials for a provider. Returns True if deleted."""
        path = self._base_dir / f"{provider}.json"
        if path.exists():
            path.unlink()
            log.debug(f"Deleted credentials for {provider}")
            return True
        return False

    def has_valid_credentials(self, provider: str) -> bool:
        """Check if valid (non-expired) credentials exist for a provider."""
        data = self.load(provider)
        if data is None:
            return False
        # Check expiry if present
        expiry = data.get("expiry")
        if expiry and time.time() >= expiry:
            return False
        return True


# Module-level convenience functions
_default_store = CredentialStore()


def save_credentials(provider: str, data: dict[str, Any]) -> None:
    """Save credentials for a provider."""
    _default_store.save(provider, data)


def load_credentials(provider: str) -> Optional[dict[str, Any]]:
    """Load credentials for a provider."""
    return _default_store.load(provider)


def delete_credentials(provider: str) -> bool:
    """Delete credentials for a provider."""
    return _default_store.delete(provider)


def has_valid_credentials(provider: str) -> bool:
    """Check if valid credentials exist."""
    return _default_store.has_valid_credentials(provider)
