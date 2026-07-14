"""Credential provider interface and implementations."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from woodwork.identity.store import load_credentials, has_valid_credentials

log = logging.getLogger(__name__)


class CredentialProvider(ABC):
    """Abstract base class for credential providers."""

    @abstractmethod
    def get_credentials(self) -> dict[str, Any]:
        """Get current credentials."""
        ...

    @abstractmethod
    def refresh_if_needed(self) -> None:
        """Refresh credentials if expired or near expiry."""
        ...

    @abstractmethod
    def is_valid(self) -> bool:
        """Check if credentials are currently valid."""
        ...


class GoogleCredentialProvider(CredentialProvider):
    """Provides Google OAuth credentials with auto-refresh."""

    def get_credentials(self) -> dict[str, Any]:
        """Get current Google credentials, refreshing if needed."""
        self.refresh_if_needed()
        creds = load_credentials("google")
        if creds is None:
            raise ValueError("No Google credentials found. Run 'woodwork auth google' first.")
        return creds

    def refresh_if_needed(self) -> None:
        """Refresh Google access token if expired."""
        creds = load_credentials("google")
        if creds is None:
            return

        from woodwork.identity.oauth import refresh_access_token

        refresh_access_token(creds)

    def is_valid(self) -> bool:
        """Check if Google credentials exist and are valid."""
        return has_valid_credentials("google")

    def get_access_token(self) -> str:
        """Get a valid access token string."""
        creds = self.get_credentials()
        return creds["access_token"]

    def get_env_vars(self) -> dict[str, str]:
        """Get credentials as environment variables for MCP servers."""
        creds = self.get_credentials()
        return {
            "GOOGLE_ACCESS_TOKEN": creds["access_token"],
        }
