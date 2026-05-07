"""Tests for credential providers."""

import time
from unittest.mock import patch

import pytest

from woodwork.identity.provider import GoogleCredentialProvider


class TestGoogleCredentialProvider:
    def test_is_valid_when_credentials_exist(self):
        provider = GoogleCredentialProvider()
        with patch("woodwork.identity.provider.has_valid_credentials", return_value=True):
            assert provider.is_valid() is True

    def test_is_valid_when_no_credentials(self):
        provider = GoogleCredentialProvider()
        with patch("woodwork.identity.provider.has_valid_credentials", return_value=False):
            assert provider.is_valid() is False

    def test_get_credentials_raises_when_missing(self):
        provider = GoogleCredentialProvider()
        with patch("woodwork.identity.provider.load_credentials", return_value=None):
            with patch("woodwork.identity.oauth.refresh_access_token"):
                with pytest.raises(ValueError, match="No Google credentials found"):
                    provider.get_credentials()

    def test_get_access_token(self):
        provider = GoogleCredentialProvider()
        creds = {"access_token": "test_token", "expiry": time.time() + 3600}
        with patch.object(provider, "get_credentials", return_value=creds):
            assert provider.get_access_token() == "test_token"

    def test_get_env_vars(self):
        provider = GoogleCredentialProvider()
        creds = {"access_token": "test_token", "expiry": time.time() + 3600}
        with patch.object(provider, "get_credentials", return_value=creds):
            env_vars = provider.get_env_vars()
            assert env_vars == {"GOOGLE_ACCESS_TOKEN": "test_token"}
