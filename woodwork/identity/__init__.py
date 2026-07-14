"""Identity module for credential management and OAuth2 flows."""

from woodwork.identity.store import CredentialStore
from woodwork.identity.provider import CredentialProvider, GoogleCredentialProvider

__all__ = [
    "CredentialStore",
    "CredentialProvider",
    "GoogleCredentialProvider",
]
