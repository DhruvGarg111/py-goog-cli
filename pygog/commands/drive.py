"""Drive CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from pygog.services.drive import DriveService
from pygog.output import print_json, print_plain

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



@app.command("ls")
def ls_cmd(
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="Parent folder ID"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
):
    """List files in Drive."""
    service = get_service()
    result = service.list_files(parent_id=parent, max_results=max_results)
    files = result.get("files", [])

    if should_json():
        print_json(result)
        return

    if not files:
        console.print("[yellow]No files found.[/yellow]")
        return

    data = []
    for f in files:
        data.append({
            "id": f["id"],
            "name": f["name"],
            "type": "folder" if f["mimeType"] == "application/vnd.google-apps.folder" else "file",
            "size": DriveService.format_size(f.get("size")),
            "modified": f.get("modifiedTime", "")[:10] if f.get("modifiedTime") else "",
        })

    if should_plain():
        print_plain(data, columns=["id", "name", "type", "size", "modified"])
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
):
    """Search for files."""
    service = get_service()
    result = service.search_files(query, max_results=max_results)
    files = result.get("files", [])

    if should_json():
        print_json(result)
        return

    if not files:
        console.print(f"[yellow]No files matching '{query}'[/yellow]")
        return

    table = Table(title=f"Files matching: {query}")
    table.add_column("Name", style="cyan", max_width=50)
    table.add_column("Type")
    table.add_column("Size", justify="right")
    table.add_column("ID", style="dim")

    for f in files:
        is_folder = f["mimeType"] == "application/vnd.google-apps.folder"
        table.add_row(
            f["name"],
            "folder" if is_folder else "file",
            DriveService.format_size(f.get("size")),
            f["id"],
        )

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
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output path"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Export format (pdf, docx, xlsx, pptx)"),
):
    """Download or export a file."""
    service = get_service()

    file_info = service.get_file(file_id)
    default_name = file_info.get("name", file_id)

    if format:
        output_path = out or Path(f"{default_name}.{format}")
        service.export_file(file_id, format, output_path)
        console.print(f"[green][OK][/green] Exported to: {output_path}")
    else:
        output_path = out or Path(default_name)
        service.download_file(file_id, output_path)
        console.print(f"[green][OK][/green] Downloaded to: {output_path}")


@app.command("upload")
def upload_cmd(
    file_path: Path = typer.Argument(..., help="File to upload"),
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="Parent folder ID"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name for uploaded file"),
):
    """Upload a file."""
    service = get_service()

    if not file_path.exists():
        err_console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    result = service.upload_file(file_path, name=name, parent_id=parent)

    if should_json():
        print_json({"file": result})
        return

    console.print(f"[green][OK][/green] Uploaded: [cyan]{result.get('name', '')}[/cyan]")
    console.print(f"  ID: {result['id']}")
    if result.get("webViewLink"):
        console.print(f"  Link: {result['webViewLink']}")



@app.command("mkdir")
def mkdir_cmd(
    name: str = typer.Argument(..., help="Folder name"),
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="Parent folder ID"),
):
    """Create a folder."""
    service = get_service()
    result = service.create_folder(name, parent_id=parent)

    if should_json():
        print_json({"folder": result})
        return

    console.print(f"[green][OK][/green] Folder created: [cyan]{name}[/cyan]")
    console.print(f"  ID: {result['id']}")


@app.command("copy")
def copy_cmd(
    file_id: str = typer.Argument(..., help="File ID to copy"),
    name: str = typer.Argument(..., help="Name for the copy"),
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="Parent folder for copy"),
):
    """Copy a file."""
    service = get_service()
    result = service.copy_file(file_id, name, parent_id=parent)

    if should_json():
        print_json({"file": result})
        return

    console.print(f"[green][OK][/green] Copied to: [cyan]{name}[/cyan]")
    console.print(f"  ID: {result['id']}")


@app.command("rename")
def rename_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    name: str = typer.Argument(..., help="New name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Rename a file."""
    if dry_run:
        if should_json():
            print_json({
                "dryRun": True,
                "message": "DRY RUN, NO FILES AFFECTED",
                "status": "success",
                "action": "renamed",
                "fileId": file_id,
                "newName": name,
            })
            return

        if should_plain():
            print(f"[DRY RUN, NO FILES AFFECTED] Renamed file '{file_id}' to '{name}'")
            return

        console.print(f"[DRY RUN, NO FILES AFFECTED] [green][OK][/green] Renamed file '{file_id}' to '{name}'")
        return

    service = get_service()
    result = service.rename_file(file_id, name)

    if should_json():
        print_json({"file": result})
        return

    if should_plain():
        print(f"Renamed to: {name}")
        return

    console.print(f"[green][OK][/green] Renamed to: [cyan]{name}[/cyan]")


@app.command("move")
def move_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    parent: str = typer.Option(..., "--parent", "-p", help="Destination folder ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Move a file to a different folder."""
    if dry_run:
        if should_json():
            print_json({
                "dryRun": True,
                "message": "DRY RUN, NO FILES AFFECTED",
                "status": "success",
                "action": "moved",
                "fileId": file_id,
                "parent": parent,
            })
            return

        if should_plain():
            print(f"[DRY RUN, NO FILES AFFECTED] Moved file '{file_id}' to folder {parent}")
            return

        console.print(f"[DRY RUN, NO FILES AFFECTED] [green][OK][/green] Moved file '{file_id}' to folder {parent}")
        return

    service = get_service()
    result = service.move_file(file_id, parent)

    if should_json():
        print_json({"file": result})
        return

    if should_plain():
        print(f"Moved: {result.get('name', file_id)}")
        return

    console.print(f"[green][OK][/green] Moved: {result.get('name', file_id)}")


@app.command("delete")
def delete_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Move a file to trash."""
    from pygog.cli import state

    if dry_run:
        if should_json():
            print_json({
                "dryRun": True,
                "message": "DRY RUN, NO FILES AFFECTED",
                "status": "success",
                "action": "deleted",
                "fileId": file_id,
            })
            return

        if should_plain():
            print(f"[DRY RUN, NO FILES AFFECTED] Moved to trash: {file_id}")
            return

        console.print(f"[DRY RUN, NO FILES AFFECTED] [green][OK][/green] Moved to trash: {file_id}")
        return

    if not force and not state.force:
        confirm = typer.confirm(f"Move file {file_id} to trash?")
        if not confirm:
            raise typer.Exit(0)

    service = get_service()
    service.delete_file(file_id)

    if should_json():
        print_json({"deleted": True, "fileId": file_id})
        return

    if should_plain():
        print(f"Moved to trash: {file_id}")
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
):
    """Share a file with a user."""
    service = get_service()
    result = service.share_file(file_id, email, role=role)

    if should_json():
        print_json({"permission": result})
        return

    console.print(f"[green][OK][/green] Shared with {email} as {role}")


@app.command("unshare")
def unshare_cmd(
    file_id: str = typer.Argument(..., help="File ID"),
    permission_id: str = typer.Option(..., "--permission-id", help="Permission ID to remove"),
):
    """Remove a permission from a file."""
    service = get_service()
    service.unshare_file(file_id, permission_id)

    if should_json():
        print_json({"removed": True, "permissionId": permission_id})
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
