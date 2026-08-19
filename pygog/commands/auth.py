"""Authentication CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pygog.auth.client import SCOPES, GoogleAuthClient, get_scopes_for_services
from pygog.auth.credentials import CredentialsManager
from pygog.auth.keyring import KeyringStorageError, configure_keyring_backend
from pygog.config import get_config
from pygog.interaction import confirm_destructive, execute_mutation
from pygog.output import print_json, print_plain

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def _get_auth_client_name(
    client: str | None,
    account: str | None = None,
) -> str:
    """Resolve an auth client from explicit, global, account, or config routing."""
    from pygog.cli import state

    if client is not None:
        return client
    if state.client is not None:
        return state.client

    config = get_config()
    if account is not None:
        return config.get_client_for_account(account)
    return config.client


def _get_auth_client(
    client: str | None,
    account: str | None = None,
) -> GoogleAuthClient:
    """Construct an auth client using the shared routing precedence."""
    return GoogleAuthClient(_get_auth_client_name(client, account))


@app.command("credentials")
def credentials_cmd(
    path: Path | None = typer.Argument(
        None,
        help="Path to OAuth client credentials JSON (downloaded from Google Cloud Console)",
    ),
    domain: str | None = typer.Option(
        None,
        "--domain",
        help="Associate this client with a domain for auto-selection",
    ),
    list_creds: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List stored credentials",
    ),
    client: str | None = typer.Option(
        None,
        "--client",
        help="OAuth client name (default: 'default')",
    ),
):
    """Store or list OAuth client credentials."""
    if list_creds or path is None:
        clients = CredentialsManager.list_clients()
        if not clients:
            console.print("[yellow]No credentials stored.[/yellow]")
            console.print("\nTo store credentials:")
            console.print("  pygog auth credentials <path-to-credentials.json>")
            raise typer.Exit(0)

        table = Table(title="Stored OAuth Clients")
        table.add_column("Name", style="cyan")
        table.add_column("Path")

        for c in clients:
            table.add_row(c["name"], c["path"])

        console.print(table)
        return

    client_name = _get_auth_client_name(client)
    manager = CredentialsManager(client_name)

    try:
        manager.store(path, domain=domain)
        console.print(f"[green][OK][/green] Credentials stored for client '{client_name}'")
        if domain:
            console.print(f"  Domain mapping: {domain} -> {client_name}")
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] File not found: {path}")
        raise typer.Exit(1)
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("add")
def add_cmd(
    email: str = typer.Argument(..., help="Google account email"),
    services: str | None = typer.Option(
        None,
        "--services",
        help="Comma-separated services to authorize (default: gmail,calendar,drive,tasks)",
    ),
    readonly: bool = typer.Option(
        False,
        "--readonly",
        help="Request read-only access",
    ),
    force_consent: bool = typer.Option(
        False,
        "--force-consent",
        help="Force consent screen even if already authorized",
    ),
    client: str | None = typer.Option(
        None,
        "--client",
        help="OAuth client name",
    ),
):
    """Authorize a Google account via OAuth."""
    auth_client = _get_auth_client(client)

    service_list = None
    if services:
        service_list = [s.strip() for s in services.split(",")]

    console.print(f"Authorizing {email}...")

    try:
        scopes = get_scopes_for_services(service_list, readonly)
        console.print(f"Requesting {len(scopes)} scopes for services")

        auth_client.authorize(
            account=email,
            services=service_list,
            readonly=readonly,
            force_consent=force_consent,
        )
        console.print(f"[green][OK][/green] Account '{email}' authorized successfully")
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("list")
def list_cmd(
    check: bool = typer.Option(
        False,
        "--check",
        help="Verify tokens are still valid",
    ),
    client: str | None = typer.Option(
        None,
        "--client",
        help="OAuth client name",
    ),
):
    """List authorized accounts."""
    auth_client = _get_auth_client(client)
    accounts = auth_client.list_accounts()

    if not accounts:
        console.print("[yellow]No accounts stored.[/yellow]")
        console.print("\nTo add an account:")
        console.print("  pygog auth add <email>")
        return

    table = Table(title="Authorized Accounts")
    table.add_column("Email", style="cyan")
    table.add_column("Client")
    table.add_column("Auth Type")
    if check:
        table.add_column("Status")

    for acc in accounts:
        row = [acc["email"], acc["client"], acc["auth_type"]]
        if check:
            status = auth_client.check_token(acc["email"])
            if status.get("valid"):
                row.append("[green][OK] Valid[/green]")
            else:
                row.append(f"[red][X] {status.get('error', 'Invalid')}[/red]")
        table.add_row(*row)

    console.print(table)


@app.command("remove")
def remove_cmd(
    email: str = typer.Argument(..., help="Account email to remove"),
    client: str | None = typer.Option(
        None,
        "--client",
        help="OAuth client name",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation",
    ),
):
    """Remove an authorized account."""
    confirm_destructive(
        "remove authorized account",
        f"account={email}",
        local_force=force,
    )

    removed = execute_mutation(
        lambda: _get_auth_client(client).remove_account(email),
        action="remove authorized account",
    )

    from pygog.cli import state

    if state.json_output:
        print_json({"removed": bool(removed), "account": email})
        return

    if state.plain_output:
        print_plain([{"removed": bool(removed), "account": email}], columns=["removed", "account"])
        return

    if removed:
        console.print(f"[green][OK][/green] Account '{email}' removed")
    else:
        err_console.print(f"[yellow]Account '{email}' not found[/yellow]")


@app.command("status")
def status_cmd(
    account: str | None = typer.Option(
        None,
        "--account",
        "-a",
        help="Account to check",
    ),
):
    """Show authentication status for current account."""
    from pygog.cli import state

    config = get_config()
    email = config.resolve_account(account) or state.account

    if not email:
        err_console.print("[red]No account specified.[/red]")
        err_console.print("Use --account or set GOG_ACCOUNT environment variable")
        raise typer.Exit(1)

    client_name = _get_auth_client_name(None, email)
    auth_client = GoogleAuthClient(client_name)

    status = auth_client.check_token(email)

    console.print(f"Account: [cyan]{email}[/cyan]")
    console.print(f"Client: {client_name}")

    if status.get("valid"):
        console.print("Status: [green]Authenticated[/green]")
        if status.get("refreshed"):
            console.print("  (token was refreshed)")
        if status.get("scopes"):
            console.print(f"Scopes: {len(status['scopes'])} authorized")
    else:
        console.print("Status: [red]Not authenticated[/red]")
        if status.get("error"):
            console.print(f"  Error: {status['error']}")


@app.command("services")
def services_cmd():
    """List available services and their OAuth scopes."""
    table = Table(title="Available Services")
    table.add_column("Service", style="cyan")
    table.add_column("Scopes")

    for service, scopes in sorted(SCOPES.items()):
        scope_text = "\n".join(scopes)
        table.add_row(service, scope_text)

    console.print(table)


alias_app = typer.Typer(no_args_is_help=True, help="Manage account aliases")
app.add_typer(alias_app, name="alias")


@alias_app.command("set")
def alias_set(
    name: str = typer.Argument(..., help="Alias name"),
    email: str = typer.Argument(..., help="Account email"),
):
    """Set an account alias."""
    config = get_config()
    aliases = config.get("account_aliases", {})
    aliases[name] = email
    config.set("account_aliases", aliases)
    console.print(f"[green][OK][/green] Alias '{name}' -> '{email}'")


@alias_app.command("list")
def alias_list():
    """List account aliases."""
    config = get_config()
    aliases = config.get("account_aliases", {})

    if not aliases:
        console.print("[yellow]No aliases configured.[/yellow]")
        return

    table = Table(title="Account Aliases")
    table.add_column("Alias", style="cyan")
    table.add_column("Email")

    for name, email in sorted(aliases.items()):
        table.add_row(name, email)

    console.print(table)


@alias_app.command("unset")
def alias_unset(
    name: str = typer.Argument(..., help="Alias name to remove"),
):
    """Remove an account alias."""
    config = get_config()
    aliases = config.get("account_aliases", {})

    if name in aliases:
        del aliases[name]
        config.set("account_aliases", aliases)
        console.print(f"[green][OK][/green] Alias '{name}' removed")
    else:
        err_console.print(f"[yellow]Alias '{name}' not found[/yellow]")


@app.command("keyring")
def keyring_cmd(
    backend: str | None = typer.Argument(
        None,
        help="Backend to set: auto or keychain",
    ),
):
    """Show or set keyring backend."""
    config = get_config()

    if backend is None:
        current = config.keyring_backend
        console.print(f"Keyring backend: [cyan]{current}[/cyan]")
        console.print(f"Config path: {config.path}")
    else:
        if backend not in ("auto", "keychain", "native"):
            err_console.print(f"[red]Invalid backend:[/red] {backend}")
            err_console.print("Valid options: auto, keychain")
            raise typer.Exit(1)
        try:
            configure_keyring_backend(backend)
        except KeyringStorageError as error:
            err_console.print(f"[red]Error:[/red] {error}")
            raise typer.Exit(1)
        config.set("keyring_backend", backend)
        console.print(f"[green][OK][/green] Keyring backend set to '{backend}'")
