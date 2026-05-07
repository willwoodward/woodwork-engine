"""Google OAuth2 flow for credential acquisition.

Uses google-auth-oauthlib for browser-based consent flow.
Stores refresh + access tokens via the credential store.
"""

import datetime
import logging
import time
from pathlib import Path
from typing import Optional

from woodwork.identity.store import save_credentials, load_credentials

log = logging.getLogger(__name__)

# Default scopes for the life assistant
DEFAULT_SCOPES = [
    # Calendar MCP scopes
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    # Gmail scopes
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def run_oauth_flow(
    client_secrets_file: Optional[str] = None,
    scopes: Optional[list[str]] = None,
) -> dict:
    """Run the Google OAuth2 browser-based consent flow.

    Args:
        client_secrets_file: Path to OAuth client secrets JSON file.
            Defaults to ~/.woodwork/client_secrets.json
        scopes: OAuth scopes to request. Defaults to calendar + gmail scopes.

    Returns:
        Dict with access_token, refresh_token, expiry, and scopes.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ImportError(
            "google-auth-oauthlib is required for Google OAuth. Install with: pip install woodwork-engine[all]"
        )

    if client_secrets_file is None:
        client_secrets_file = str(Path.home() / ".woodwork" / "client_secrets.json")

    if not Path(client_secrets_file).exists():
        raise FileNotFoundError(
            f"OAuth client secrets file not found: {client_secrets_file}\n"
            "Download from Google Cloud Console > APIs & Services > Credentials"
        )

    scopes = scopes or DEFAULT_SCOPES

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes=scopes)

    # Try local server first (fixed port, no auto-browser for WSL compat)
    try:
        credentials = flow.run_local_server(
            port=8085,
            open_browser=False,
            prompt="consent",
        )
    except Exception as e:
        log.warning(f"Local server flow failed ({e}), falling back to manual code entry")
        credentials = _run_manual_flow(flow)

    if credentials is None or credentials.token is None:
        raise RuntimeError("OAuth flow did not return valid credentials. Please try again.")

    # Build credentials data
    creds_data = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else scopes,
        "expiry": credentials.expiry.replace(tzinfo=datetime.timezone.utc).timestamp() if credentials.expiry else None,
    }

    # Save to store
    save_credentials("google", creds_data)
    log.info("Google OAuth credentials saved successfully")

    return creds_data


def _run_manual_flow(flow):
    """Fallback: manual code entry for environments where localhost redirect doesn't work (e.g. WSL)."""
    auth_url, _ = flow.authorization_url(prompt="consent")
    print(f"\nOpen this URL in your browser:\n\n  {auth_url}\n")
    code = input("Enter the authorization code: ").strip()
    flow.fetch_token(code=code)
    return flow.credentials


def refresh_access_token(creds_data: Optional[dict] = None) -> dict:
    """Refresh the Google access token if expired or near expiry.

    Args:
        creds_data: Existing credentials dict. If None, loads from store.

    Returns:
        Updated credentials dict with fresh access token.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise ImportError("google-auth is required for token refresh. Install with: pip install woodwork-engine[all]")

    if creds_data is None:
        creds_data = load_credentials("google")
        if creds_data is None:
            raise ValueError("No Google credentials found. Run 'woodwork auth google' first.")

    # Check if refresh is needed (expired or within 5 minutes of expiry)
    expiry = creds_data.get("expiry")
    if expiry and time.time() < (expiry - 300):
        return creds_data  # Still valid

    # Build google credentials object
    credentials = Credentials(
        token=creds_data.get("access_token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes"),
    )

    # Refresh
    credentials.refresh(Request())

    # Update stored data
    creds_data["access_token"] = credentials.token
    creds_data["expiry"] = credentials.expiry.replace(tzinfo=datetime.timezone.utc).timestamp() if credentials.expiry else None

    # Save updated credentials
    save_credentials("google", creds_data)
    log.info("Google access token refreshed successfully")

    return creds_data


def get_access_token() -> str:
    """Get a valid Google access token, refreshing if needed.

    Returns:
        Valid access token string.
    """
    creds_data = load_credentials("google")
    if creds_data is None:
        raise ValueError("No Google credentials found. Run 'woodwork auth google' first.")

    creds_data = refresh_access_token(creds_data)
    return creds_data["access_token"]
