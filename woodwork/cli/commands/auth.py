"""Auth command - manage OAuth credentials for external services."""

import time

import click


@click.group("auth")
def auth_group():
    """Manage authentication credentials for external services."""
    pass


@auth_group.command("google")
@click.option("--status", is_flag=True, help="Check if Google credentials are valid.")
@click.option("--revoke", is_flag=True, help="Remove stored Google credentials.")
@click.option(
    "--client-secrets",
    type=click.Path(exists=True),
    default=None,
    help="Path to OAuth client secrets JSON file.",
)
def google_cmd(status, revoke, client_secrets):
    """Authenticate with Google (Calendar, Gmail)."""
    from woodwork.identity.store import delete_credentials

    if status:
        _show_status()
        return

    if revoke:
        if delete_credentials("google"):
            click.echo("Google credentials revoked.")
        else:
            click.echo("No Google credentials found.")
        return

    # Run OAuth flow
    from woodwork.identity.oauth import run_oauth_flow

    click.echo("Opening browser for Google authentication...")
    try:
        creds = run_oauth_flow(client_secrets_file=client_secrets)
        click.echo("Google authentication successful!")
        click.echo(f"Scopes: {', '.join(creds.get('scopes', []))}")
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Authentication failed: {e}", err=True)
        raise SystemExit(1)


def _show_status():
    """Display credential status."""
    from woodwork.identity.store import load_credentials, has_valid_credentials

    if not has_valid_credentials("google"):
        creds = load_credentials("google")
        if creds is None:
            click.echo("Google: Not authenticated. Run 'woodwork auth google' to authenticate.")
        else:
            click.echo("Google: Expired. Run 'woodwork auth google' to re-authenticate.")
        return

    creds = load_credentials("google")
    expiry = creds.get("expiry")
    if expiry:
        remaining = int(expiry - time.time())
        minutes = remaining // 60
        click.echo(f"Google: Valid, expires in {minutes} minutes")
    else:
        click.echo("Google: Valid (no expiry set)")

    scopes = creds.get("scopes", [])
    if scopes:
        click.echo(f"Scopes: {', '.join(scopes)}")
