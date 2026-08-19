"""Drive CLI commands."""

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
from pygog.services.drive import DriveService, validate_remote_filename

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def get_service() -> DriveService:
    """Get Drive service for current account."""
    from pygog.cli import state

    return DriveService(account=state.account, client=state.client)


def should_json() -> bool:
    from pygog.cli import state

    return state.json_output


def should_plain() -> bool:
    from pygog.cli import state

    return state.plain_output


def _account_preview() -> str:
    from pygog.cli import state

    return state.account or "(current account)"


def _file_row(file: dict) -> dict[str, str]:
    """Return the stable TSV representation shared by Drive list commands."""
    mime_type = file.get("mimeType", "")
    return {
        "id": file.get("id", ""),
        "name": file.get("name", ""),
        "type": "folder" if mime_type == "application/vnd.google-apps.folder" else "file",
        "size": DriveService.format_size(file.get("size")),
        "modified": file.get("modifiedTime", "")[:10] if file.get("modifiedTime") else "",
    }


@app.command("ls")
def ls_cmd(
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent folder ID"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
    page_token: str | None = typer.Option(
        None, "--page-token", help="Continue from a response page token"
    ),
    drive_id: str | None = typer.Option(None, "--drive-id", help="Shared drive ID"),
):
    """List files in Drive."""
    service = get_service()
    result = service.list_files(
        parent_id=parent,
        max_results=max_results,
        page_token=page_token,
        drive_id=drive_id,
        all_drives=drive_id is not None,
    )
    files = result.get("files", [])

    if should_json():
        print_json(result)
        return

    data = [_file_row(file) for file in files]

    if should_plain():
        print_plain(
            data,
            columns=["id", "name", "type", "size", "modified"],
            header_on_empty=True,
        )
        return

    if not files:
        console.print("[yellow]No files found.[/yellow]")
        return

    table = Table(title="Files")
    table.add_column("Name", style="cyan", max_width=50)
    table.add_column("Type")
    table.add_column("Size", justify="right")
    table.add_column("Modified")
    table.add_column("ID", style="dim")

    for d in data:
        table.add_row(d["name"], d["type"], d["size"], d["modified"], d["id"])

    console.print(table)


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
    page_token: str | None = typer.Option(
        None, "--page-token", help="Continue from a response page token"
    ),
    drive_id: str | None = typer.Option(None, "--drive-id", help="Shared drive ID"),
):
    """Search for files."""
    service = get_service()
    result = service.search_files(
        query,
        max_results=max_results,
        page_token=page_token,
        drive_id=drive_id,
        all_drives=drive_id is not None,
    )
    files = result.get("files", [])

    if should_json():
        print_json(result)
        return

    data = [_file_row(file) for file in files]

    if should_plain():
        print_plain(
            data,
            columns=["id", "name", "type", "size", "modified"],
            header_on_empty=True,
        )
        return

    table = Table(title=f"Files matching: {query}")
    table.add_column("Name", style="cyan", max_width=50)
    table.add_column("Type")
    table.add_column("Size", justify="right")
    table.add_column("ID", style="dim")

    for d in data:
        table.add_row(
            d["name"],
            d["type"],
            d["size"],
            d["id"],
        )

    if not files:
        console.print(f"[yellow]No files matching '{query}'[/yellow]")
        return

    console.print(table)


@app.command("get")
def get_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
):
    """Get file metadata."""
    service = get_service()
    file = service.get_file(file_id)

    if should_json():
        print_json({"file": file})
        return

    if should_plain():
        print_plain(
            [_file_row(file)],
            columns=["id", "name", "type", "size", "modified"],
        )
        return

    console.print(f"[bold]Name:[/bold] {file.get('name', '')}")
    console.print(f"[bold]ID:[/bold] {file['id']}")
    console.print(f"[bold]Type:[/bold] {file.get('mimeType', '')}")
    if file.get("size"):
        console.print(f"[bold]Size:[/bold] {DriveService.format_size(file['size'])}")
    console.print(f"[bold]Created:[/bold] {file.get('createdTime', '')}")
    console.print(f"[bold]Modified:[/bold] {file.get('modifiedTime', '')}")
    if file.get("webViewLink"):
        console.print(f"[bold]Link:[/bold] {file['webViewLink']}")


@app.command("download")
def download_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output path"),
    format: str | None = typer.Option(
        None, "--format", "-f", help="Export format (pdf, docx, xlsx, pptx)"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace an existing local file"),
):
    """Download or export a file."""
    service = get_service()

    file_info = service.get_file(file_id)
    default_name = validate_remote_filename(file_info.get("name") or file_id)

    if format:
        output_path = out or Path(f"{default_name}.{format}")
        service.export_file(file_id, format, output_path, overwrite=overwrite)
        console.print(f"[green][OK][/green] Exported to: {output_path}")
    else:
        output_path = out or Path(default_name)
        service.download_file(file_id, output_path, overwrite=overwrite)
        console.print(f"[green][OK][/green] Downloaded to: {output_path}")


@app.command("upload")
def upload_cmd(
    file_path: Path = typer.Argument(..., help="File to upload"),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent folder ID"),
    name: str | None = typer.Option(None, "--name", "-n", help="Name for uploaded file"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Upload a file."""
    if not file_path.exists():
        fail_interaction(f"File not found: {file_path}", code="file_not_found")

    upload_name = name or file_path.name
    details = {
        "filePath": str(file_path),
        "name": upload_name,
        "parent": parent or "(root)",
    }
    if dry_run:
        dry_run_output(
            "upload Drive file",
            details,
            plain_columns=["dryRun", "action", "filePath", "name", "parent"],
            console=console,
        )
        return

    confirm_destructive(
        "upload Drive file",
        f"path={file_path}, name={upload_name!r}, parent={parent or '(root)'}, "
        f"account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().upload_file(file_path, name=name, parent_id=parent),
        action="upload Drive file",
    )

    if should_json():
        print_json({"file": result})
        return

    if should_plain():
        print_plain(
            [{"id": result.get("id", ""), "name": result.get("name", upload_name)}],
            columns=["id", "name"],
        )
        return

    console.print(f"[green][OK][/green] Uploaded: [cyan]{result.get('name', '')}[/cyan]")
    console.print(f"  ID: {result['id']}")
    if result.get("webViewLink"):
        console.print(f"  Link: {result['webViewLink']}")


@app.command("mkdir")
def mkdir_cmd(
    name: str = typer.Argument(..., help="Folder name"),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent folder ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Create a folder."""
    details = {"name": name, "parent": parent or "(root)"}
    if dry_run:
        dry_run_output(
            "create Drive folder",
            details,
            plain_columns=["dryRun", "action", "name", "parent"],
            console=console,
        )
        return

    confirm_destructive(
        "create Drive folder",
        f"name={name!r}, parent={parent or '(root)'}, account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().create_folder(name, parent_id=parent),
        action="create Drive folder",
    )

    if should_json():
        print_json({"folder": result})
        return

    if should_plain():
        print_plain(
            [{"id": result.get("id", ""), "name": result.get("name", name)}],
            columns=["id", "name"],
        )
        return

    console.print(f"[green][OK][/green] Folder created: [cyan]{name}[/cyan]")
    console.print(f"  ID: {result['id']}")


@app.command("copy")
def copy_cmd(
    file_id: str = typer.Argument(..., help="File ID to copy"),
    name: str = typer.Argument(..., help="Name for the copy"),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent folder for copy"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Copy a file."""
    details = {"fileId": file_id, "name": name, "parent": parent or "(current folder)"}
    if dry_run:
        dry_run_output(
            "copy Drive file",
            details,
            plain_columns=["dryRun", "action", "fileId", "name", "parent"],
            console=console,
        )
        return

    confirm_destructive(
        "copy Drive file",
        f"source={file_id}, name={name!r}, parent={parent or '(current folder)'}, "
        f"account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().copy_file(file_id, name, parent_id=parent),
        action="copy Drive file",
    )

    if should_json():
        print_json({"file": result})
        return

    if should_plain():
        print_plain(
            [{"id": result.get("id", ""), "name": result.get("name", name)}],
            columns=["id", "name"],
        )
        return

    console.print(f"[green][OK][/green] Copied to: [cyan]{name}[/cyan]")
    console.print(f"  ID: {result['id']}")


@app.command("rename")
def rename_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    name: str = typer.Argument(..., help="New name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Rename a file."""
    if dry_run:
        if should_json():
            print_json(
                {
                    "dryRun": True,
                    "message": "DRY RUN, NO FILES AFFECTED",
                    "status": "success",
                    "action": "renamed",
                    "fileId": file_id,
                    "newName": name,
                }
            )
            return

        if should_plain():
            dry_run_output(
                "rename Drive file",
                {"fileId": file_id, "newName": name},
                plain_columns=["dryRun", "action", "fileId", "newName"],
                console=console,
            )
            return

        console.print(
            f"[DRY RUN, NO FILES AFFECTED] [green][OK][/green] Renamed file '{file_id}' to '{name}'"
        )
        return

    confirm_destructive(
        "rename Drive file",
        f"file={file_id}, new_name={name!r}, account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().rename_file(file_id, name),
        action="rename Drive file",
    )

    if should_json():
        print_json({"file": result})
        return

    if should_plain():
        print_plain([{"fileId": file_id, "newName": name}], columns=["fileId", "newName"])
        return

    console.print(f"[green][OK][/green] Renamed to: [cyan]{name}[/cyan]")


@app.command("move")
def move_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    parent: str = typer.Option(..., "--parent", "-p", help="Destination folder ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Move a file to a different folder."""
    if dry_run:
        if should_json():
            print_json(
                {
                    "dryRun": True,
                    "message": "DRY RUN, NO FILES AFFECTED",
                    "status": "success",
                    "action": "moved",
                    "fileId": file_id,
                    "parent": parent,
                }
            )
            return

        if should_plain():
            dry_run_output(
                "move Drive file",
                {"fileId": file_id, "parent": parent},
                plain_columns=["dryRun", "action", "fileId", "parent"],
                console=console,
            )
            return

        console.print(
            f"[DRY RUN, NO FILES AFFECTED] [green][OK][/green] Moved file '{file_id}' to folder {parent}"
        )
        return

    confirm_destructive(
        "move Drive file",
        f"file={file_id}, parent={parent}, account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().move_file(file_id, parent),
        action="move Drive file",
    )

    if should_json():
        print_json({"file": result})
        return

    if should_plain():
        print_plain([{"fileId": file_id, "parent": parent}], columns=["fileId", "parent"])
        return

    console.print(f"[green][OK][/green] Moved: {result.get('name', file_id)}")


@app.command("delete")
def delete_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Move a file to trash."""
    if dry_run:
        if should_json():
            print_json(
                {
                    "dryRun": True,
                    "message": "DRY RUN, NO FILES AFFECTED",
                    "status": "success",
                    "action": "deleted",
                    "fileId": file_id,
                }
            )
            return

        if should_plain():
            dry_run_output(
                "move Drive file to trash",
                {"fileId": file_id},
                plain_columns=["dryRun", "action", "fileId"],
                console=console,
            )
            return

        console.print(f"[DRY RUN, NO FILES AFFECTED] [green][OK][/green] Moved to trash: {file_id}")
        return

    confirm_destructive(
        "move Drive file to trash",
        f"file={file_id}, account={_account_preview()}",
        local_force=force,
    )

    execute_mutation(
        lambda: get_service().delete_file(file_id),
        action="move Drive file to trash",
    )

    if should_json():
        print_json({"deleted": True, "fileId": file_id})
        return

    if should_plain():
        print_plain([{"deleted": True, "fileId": file_id}], columns=["deleted", "fileId"])
        return

    console.print(f"[green][OK][/green] Moved to trash: {file_id}")


@app.command("permissions")
def permissions_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
):
    """List file permissions."""
    service = get_service()
    permissions = service.list_permissions(file_id)

    if should_json():
        print_json({"permissions": permissions})
        return

    if not permissions:
        console.print("[yellow]No permissions found.[/yellow]")
        return

    table = Table(title="Permissions")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Role", style="cyan")
    table.add_column("Email")

    for p in permissions:
        table.add_row(p["id"], p.get("type", ""), p.get("role", ""), p.get("emailAddress", ""))

    console.print(table)


@app.command("share")
def share_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    email: str = typer.Option(..., "--email", "-e", help="User email to share with"),
    role: str = typer.Option("reader", "--role", "-r", help="Role: reader, writer, commenter"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Share a file with a user."""
    role = role.strip().lower()
    valid_roles = {"reader", "writer", "commenter"}
    if role not in valid_roles:
        fail_interaction(
            f"Invalid Drive share role '{role}'. Valid options: {', '.join(sorted(valid_roles))}.",
            code="invalid_role",
        )

    if dry_run:
        dry_run_output(
            "share Drive file",
            {"fileId": file_id, "email": email, "role": role},
            plain_columns=["dryRun", "action", "fileId", "email", "role"],
            console=console,
        )
        return

    confirm_destructive(
        "share Drive file",
        f"file={file_id}, recipient={email}, role={role}, account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().share_file(file_id, email, role=role),
        action="share Drive file",
    )

    if should_json():
        print_json({"permission": result})
        return

    if should_plain():
        print_plain(
            [{"fileId": file_id, "email": email, "role": role}],
            columns=["fileId", "email", "role"],
        )
        return

    console.print(f"[green][OK][/green] Shared with {email} as {role}")


@app.command("unshare")
def unshare_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    permission_id: str = typer.Option(..., "--permission-id", help="Permission ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Remove a permission from a file."""
    if dry_run:
        dry_run_output(
            "remove Drive permission",
            {"fileId": file_id, "permissionId": permission_id},
            plain_columns=["dryRun", "action", "fileId", "permissionId"],
            console=console,
        )
        return

    confirm_destructive(
        "remove Drive permission",
        f"file={file_id}, permission={permission_id}, account={_account_preview()}",
        local_force=force,
    )
    execute_mutation(
        lambda: get_service().unshare_file(file_id, permission_id),
        action="remove Drive permission",
    )

    if should_json():
        print_json({"removed": True, "permissionId": permission_id})
        return

    if should_plain():
        print_plain(
            [{"removed": True, "permissionId": permission_id}],
            columns=["removed", "permissionId"],
        )
        return

    console.print(f"[green][OK][/green] Permission removed: {permission_id}")


@app.command("drives")
def drives_cmd(
    max_results: int = typer.Option(100, "--max", "-m", help="Maximum results"),
):
    """List shared drives."""
    service = get_service()
    drives = service.list_drives(max_results=max_results)

    if should_json():
        print_json({"drives": drives})
        return

    if not drives:
        console.print("[yellow]No shared drives found.[/yellow]")
        return

    table = Table(title="Shared Drives")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")

    for d in drives:
        table.add_row(d["id"], d.get("name", ""))

    console.print(table)


@app.command("url")
def url_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
):
    """Get Drive web URL for a file."""
    url = DriveService.get_drive_url(file_id)
    console.print(url)
