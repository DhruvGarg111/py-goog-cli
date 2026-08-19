"""Gmail CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pygog.interaction import (
    confirm_destructive,
    dry_run_output,
    execute_mutation,
    fail_interaction,
)
from pygog.output import print_json, print_plain
from pygog.services.gmail import GmailService

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def get_service() -> GmailService:
    """Get Gmail service for current account."""
    from pygog.cli import state

    return GmailService(account=state.account, client=state.client)


def should_json() -> bool:
    """Check if JSON output is enabled."""
    from pygog.cli import state

    return state.json_output


def should_plain() -> bool:
    """Check if plain output is enabled."""
    from pygog.cli import state

    return state.plain_output


def _account_preview() -> str:
    from pygog.cli import state

    return state.account or "(current account)"


labels_app = typer.Typer(no_args_is_help=True, help="Manage Gmail labels")
app.add_typer(labels_app, name="labels")


@labels_app.command("list")
def labels_list():
    """List all labels."""
    service = get_service()
    labels = service.list_labels()

    if should_json():
        print_json({"labels": labels})
        return

    labels.sort(key=lambda x: x.get("name", ""))

    if should_plain():
        data = [{"id": label["id"], "name": label.get("name", "")} for label in labels]
        print_plain(data, columns=["id", "name"], header_on_empty=True)
        return

    table = Table(title="Gmail Labels")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Type")

    for label in labels:
        table.add_row(
            label["id"],
            label.get("name", ""),
            label.get("type", "user"),
        )

    console.print(table)


@labels_app.command("get")
def labels_get(
    label_id: str = typer.Argument(..., help="Label ID"),
):
    """Get label details."""
    service = get_service()
    label = service.get_label(label_id)

    if should_json():
        print_json({"label": label})
        return

    console.print(f"Name: [cyan]{label.get('name', '')}[/cyan]")
    console.print(f"ID: {label['id']}")
    console.print(f"Type: {label.get('type', 'user')}")

    if "messagesTotal" in label:
        console.print(f"Messages: {label['messagesTotal']}")
        console.print(f"Unread: {label.get('messagesUnread', 0)}")


@labels_app.command("create")
def labels_create(
    name: str = typer.Argument(..., help="Label name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Create a new label."""
    if dry_run:
        dry_run_output(
            "create Gmail label",
            {"name": name},
            plain_columns=["dryRun", "action", "name"],
            console=console,
        )
        return

    confirm_destructive(
        "create Gmail label",
        f"name={name!r}, account={_account_preview()}",
        local_force=force,
    )
    label = execute_mutation(
        lambda: get_service().create_label(name),
        action="create Gmail label",
    )

    if should_json():
        print_json({"label": label})
        return

    if should_plain():
        print_plain([{"id": label["id"], "name": label.get("name", name)}], columns=["id", "name"])
        return

    console.print(f"[green][OK][/green] Label created: [cyan]{label.get('name', '')}[/cyan]")
    console.print(f"  ID: {label['id']}")


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Gmail search query"),
    max_results: int = typer.Option(10, "--max", "-m", help="Maximum results"),
    page_token: str | None = typer.Option(
        None, "--page-token", help="Continue from a response page token"
    ),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages (bounded)"),
):
    """Search for threads."""
    service = get_service()
    result = service.search_threads(
        query, max_results=max_results, page_token=page_token, all_pages=all_pages
    )
    threads = result.get("threads", [])

    if should_json():
        print_json(result)
        return

    detailed = []
    for t in threads[:max_results]:
        try:
            thread = service.get_thread(t["id"], format="metadata")
            row = {"id": t["id"], "subject": "(no subject)", "from": "", "date": ""}
            if thread.get("messages"):
                msg = thread["messages"][0]
                headers = service.extract_headers(msg)
                row.update(
                    {
                        "subject": headers.get("Subject", "(no subject)"),
                        "from": headers.get("From", ""),
                        "date": headers.get("Date", ""),
                    }
                )
            detailed.append(row)
        except Exception:
            detailed.append({"id": t["id"], "subject": "(error)", "from": "", "date": ""})

    if should_plain():
        print_plain(detailed, columns=["id", "subject", "from", "date"], header_on_empty=True)
        return

    if not threads:
        console.print("[yellow]No threads found.[/yellow]")
        return

    table = Table(title=f"Threads matching: {query}")
    table.add_column("Thread ID", style="dim")
    table.add_column("Subject", style="cyan", max_width=50)
    table.add_column("From", max_width=30)
    table.add_column("Date")

    for t in detailed:
        table.add_row(t["id"], t["subject"], t["from"], t["date"])

    console.print(table)


messages_app = typer.Typer(no_args_is_help=True, help="Message-level operations")
app.add_typer(messages_app, name="messages")


@messages_app.command("search")
def messages_search(
    query: str = typer.Argument(..., help="Gmail search query"),
    max_results: int = typer.Option(10, "--max", "-m", help="Maximum results"),
    include_body: bool = typer.Option(False, "--include-body", help="Include message body"),
    page_token: str | None = typer.Option(
        None, "--page-token", help="Continue from a response page token"
    ),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages (bounded)"),
):
    """Search for messages."""
    service = get_service()
    result = service.search_messages(
        query,
        max_results=max_results,
        page_token=page_token,
        all_pages=all_pages,
        include_body=include_body,
    )
    messages = result.get("messages", [])

    if should_json():
        print_json(result)
        return

    detailed = []
    for m in messages[:max_results]:
        msg = m if include_body else service.get_message(m["id"], format="metadata")
        headers = service.extract_headers(msg)
        item = {
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
        }
        if include_body:
            item["body"] = service.extract_body(msg)
        detailed.append(item)

    if should_plain():
        cols = ["id", "thread_id", "subject", "from", "date"]
        if include_body:
            cols.append("body")
        print_plain(detailed, columns=cols, header_on_empty=True)
        return

    if not messages:
        console.print("[yellow]No messages found.[/yellow]")
        return

    table = Table(title=f"Messages matching: {query}")
    table.add_column("ID", style="dim")
    table.add_column("Thread", style="dim")
    table.add_column("Subject", style="cyan", max_width=40)
    table.add_column("From", max_width=25)
    table.add_column("Date")

    for m in detailed:
        table.add_row(m["id"], m["thread_id"], m["subject"], m["from"], m["date"])

    console.print(table)


thread_app = typer.Typer(no_args_is_help=True, help="Thread operations")
app.add_typer(thread_app, name="thread")


@thread_app.command("get")
def thread_get(
    thread_id: str = typer.Argument(..., help="Thread ID"),
):
    """Get a thread."""
    service = get_service()
    thread = service.get_thread(thread_id)

    if should_json():
        print_json({"thread": thread})
        return

    messages = thread.get("messages", [])
    console.print(f"Thread: [cyan]{thread_id}[/cyan] ({len(messages)} messages)")
    console.print()

    for msg in messages:
        headers = service.extract_headers(msg)
        console.print(f"[bold]From:[/bold] {headers.get('From', '')}")
        console.print(f"[bold]Date:[/bold] {headers.get('Date', '')}")
        console.print(f"[bold]Subject:[/bold] {headers.get('Subject', '')}")
        console.print()

        body = service.extract_body(msg)
        if body:
            console.print(body[:1000])
            if len(body) > 1000:
                console.print("\n[dim]... (truncated)[/dim]")
        console.print()
        console.print("─" * 60)
        console.print()


@app.command("get")
def get_message_cmd(
    message_id: str = typer.Argument(..., help="Message ID"),
    format: str = typer.Option(
        "full", "--format", "-f", help="Format: full, metadata, minimal, raw"
    ),
):
    """Get a message."""
    service = get_service()
    message = service.get_message(message_id, format=format)

    if should_json():
        print_json({"message": message})
        return

    headers = service.extract_headers(message)
    console.print(f"[bold]From:[/bold] {headers.get('From', '')}")
    console.print(f"[bold]To:[/bold] {headers.get('To', '')}")
    console.print(f"[bold]Date:[/bold] {headers.get('Date', '')}")
    console.print(f"[bold]Subject:[/bold] {headers.get('Subject', '')}")
    console.print()

    body = service.extract_body(message)
    if body:
        console.print(body)


@app.command("send")
def send_cmd(
    to: str = typer.Option(..., "--to", help="Recipient email(s), comma-separated"),
    subject: str = typer.Option(..., "--subject", "-s", help="Email subject"),
    body: str | None = typer.Option(None, "--body", "-b", help="Plain text body"),
    body_html: str | None = typer.Option(None, "--body-html", help="HTML body"),
    body_file: Path | None = typer.Option(
        None, "--body-file", help="File to read body from (- for stdin)"
    ),
    cc: str | None = typer.Option(None, "--cc", help="CC recipients, comma-separated"),
    bcc: str | None = typer.Option(None, "--bcc", help="BCC recipients, comma-separated"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Send an email."""
    email_body = body or ""
    if body_file and not dry_run:
        try:
            if str(body_file) == "-":
                import sys

                email_body = sys.stdin.read()
            else:
                email_body = body_file.read_text()
        except OSError as exc:
            fail_interaction(f"Unable to read email body: {exc}", code="body_read_failed")

    if not email_body and not body_html and not (dry_run and body_file):
        fail_interaction(
            "No body provided. Use --body, --body-html, or --body-file.",
            code="missing_body",
        )

    recipients = [r.strip() for r in to.split(",")]
    cc_list = [r.strip() for r in cc.split(",")] if cc else None
    bcc_list = [r.strip() for r in bcc.split(",")] if bcc else None

    details = {
        "to": ",".join(recipients),
        "subject": subject,
        "cc": ",".join(cc_list or []),
        "bcc": ",".join(bcc_list or []),
    }
    if dry_run:
        dry_run_output(
            "send email",
            details,
            plain_columns=["dryRun", "action", "to", "subject", "cc", "bcc"],
            console=console,
        )
        return

    confirm_destructive(
        "send email",
        f"to={','.join(recipients)}, subject={subject!r}, cc={','.join(cc_list or []) or '(none)'}, "
        f"bcc={','.join(bcc_list or []) or '(none)'}, account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().send_message(
            to=recipients,
            subject=subject,
            body=email_body,
            body_html=body_html,
            cc=cc_list,
            bcc=bcc_list,
        ),
        action="send email",
    )

    if should_json():
        print_json({"message": result})
        return

    if should_plain():
        print_plain([{"id": result.get("id", ""), "to": to}], columns=["id", "to"])
        return

    console.print(f"[green][OK][/green] Email sent to {to}")
    console.print(f"  Message ID: {result.get('id', '')}")


@app.command("url")
def url_cmd(
    thread_id: str = typer.Argument(..., help="Thread ID"),
):
    """Get Gmail web URL for a thread."""
    service = get_service()
    url = GmailService.get_gmail_url(thread_id, service.account)
    console.print(url)


@thread_app.command("modify")
def thread_modify(
    thread_id: str = typer.Argument(..., help="Thread ID"),
    add: str | None = typer.Option(None, "--add", help="Labels to add, comma-separated"),
    remove: str | None = typer.Option(None, "--remove", help="Labels to remove, comma-separated"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Modify thread labels."""
    add_labels = [label.strip() for label in add.split(",")] if add else None
    remove_labels = [label.strip() for label in remove.split(",")] if remove else None

    details = {
        "threadId": thread_id,
        "add": ",".join(add_labels or []),
        "remove": ",".join(remove_labels or []),
    }
    if dry_run:
        dry_run_output(
            "modify Gmail thread",
            details,
            plain_columns=["dryRun", "action", "threadId", "add", "remove"],
            console=console,
        )
        return

    confirm_destructive(
        "modify Gmail thread",
        f"thread={thread_id}, add={','.join(add_labels or []) or '(none)'}, "
        f"remove={','.join(remove_labels or []) or '(none)'}, account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().modify_thread(
            thread_id,
            add_labels=add_labels,
            remove_labels=remove_labels,
        ),
        action="modify Gmail thread",
    )

    if should_json():
        print_json({"thread": result})
        return

    if should_plain():
        print_plain(
            [{"threadId": thread_id, "add": details["add"], "remove": details["remove"]}],
            columns=["threadId", "add", "remove"],
        )
        return

    console.print(f"[green][OK][/green] Thread modified: {thread_id}")


drafts_app = typer.Typer(no_args_is_help=True, help="Manage drafts")
app.add_typer(drafts_app, name="drafts")


@drafts_app.command("list")
def drafts_list(
    max_results: int = typer.Option(10, "--max", "-m", help="Maximum results"),
):
    """List drafts."""
    service = get_service()
    drafts = service.list_drafts(max_results=max_results)

    if should_json():
        print_json({"drafts": drafts})
        return

    if not drafts:
        console.print("[yellow]No drafts found.[/yellow]")
        return

    table = Table(title="Drafts")
    table.add_column("Draft ID", style="cyan")
    table.add_column("Message ID", style="dim")

    for draft in drafts:
        table.add_row(draft["id"], draft.get("message", {}).get("id", ""))

    console.print(table)


@drafts_app.command("create")
def drafts_create(
    to: str | None = typer.Option(None, "--to", help="Recipient email"),
    subject: str = typer.Option("", "--subject", "-s", help="Email subject"),
    body: str = typer.Option("", "--body", "-b", help="Plain text body"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Create a draft."""
    recipients = [r.strip() for r in to.split(",")] if to else None
    details = {
        "to": ",".join(recipients or []),
        "subject": subject,
    }
    if dry_run:
        dry_run_output(
            "create Gmail draft",
            details,
            plain_columns=["dryRun", "action", "to", "subject"],
            console=console,
        )
        return

    confirm_destructive(
        "create Gmail draft",
        f"to={','.join(recipients or []) or '(none)'}, subject={subject!r}, account={_account_preview()}",
        local_force=force,
    )
    draft = execute_mutation(
        lambda: get_service().create_draft(to=recipients, subject=subject, body=body),
        action="create Gmail draft",
    )

    if should_json():
        print_json({"draft": draft})
        return

    if should_plain():
        print_plain([{"id": draft["id"]}], columns=["id"])
        return

    console.print(f"[green][OK][/green] Draft created: {draft['id']}")
