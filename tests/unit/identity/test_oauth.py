"""Tests for the OAuth module."""

import time
from unittest.mock import patch, MagicMock

import pytest

from woodwork.identity.store import CredentialStore


class TestRefreshAccessToken:
    """Test token refresh logic."""

    def test_no_refresh_when_token_still_valid(self, tmp_path):
        """Should not refresh when token has more than 5 minutes remaining."""
        store = CredentialStore(base_dir=tmp_path)
        creds = {
            "access_token": "valid_token",
            "refresh_token": "refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client_id",
            "client_secret": "client_secret",
            "scopes": ["https://www.googleapis.com/auth/calendar.events"],
            "expiry": time.time() + 3600,  # 1 hour from now
        }
        store.save("google", creds)

        from woodwork.identity.oauth import refresh_access_token

        result = refresh_access_token(creds)
        # Should return unchanged since token is still valid
        assert result["access_token"] == "valid_token"

    def test_raises_when_no_credentials(self):
        """Should raise ValueError when no credentials exist."""
        from woodwork.identity.oauth import refresh_access_token

        with patch("woodwork.identity.oauth.load_credentials", return_value=None):
            with pytest.raises(ValueError, match="No Google credentials found"):
                refresh_access_token(None)

    @patch("woodwork.identity.oauth.save_credentials")
    def test_refresh_when_expired(self, mock_save):
        """Should refresh when token is expired."""
        from woodwork.identity.oauth import refresh_access_token

        creds = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client_id",
            "client_secret": "client_secret",
            "scopes": ["https://www.googleapis.com/auth/calendar.events"],
            "expiry": time.time() - 100,  # Expired
        }

        mock_credentials = MagicMock()
        mock_credentials.token = "new_token"
        mock_credentials.expiry = MagicMock()
        mock_credentials.expiry.timestamp.return_value = time.time() + 3600

        with patch("google.oauth2.credentials.Credentials", return_value=mock_credentials):
            with patch("google.auth.transport.requests.Request"):
                result = refresh_access_token(creds)
                assert result["access_token"] == "new_token"
                mock_save.assert_called_once()


class TestGetAccessToken:
    """Test get_access_token convenience function."""

    def test_raises_when_no_credentials(self):
        from woodwork.identity.oauth import get_access_token

        with patch("woodwork.identity.oauth.load_credentials", return_value=None):
            with pytest.raises(ValueError, match="No Google credentials found"):
                get_access_token()

    def test_returns_valid_token(self):
        from woodwork.identity.oauth import get_access_token

        creds = {
            "access_token": "my_token",
            "expiry": time.time() + 3600,
        }
        with patch("woodwork.identity.oauth.load_credentials", return_value=creds):
            with patch("woodwork.identity.oauth.refresh_access_token", return_value=creds):
                token = get_access_token()
                assert token == "my_token"
