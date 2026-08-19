"""Drive API service wrapper."""

from __future__ import annotations

import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, cast

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from pygog.services.base import BaseService

EXPORT_FORMATS = {
    "application/vnd.google-apps.document": {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "html": "text/html",
        "odt": "application/vnd.oasis.opendocument.text",
    },
    "application/vnd.google-apps.spreadsheet": {
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
    },
    "application/vnd.google-apps.presentation": {
        "pdf": "application/pdf",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "odp": "application/vnd.oasis.opendocument.presentation",
    },
}

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def validate_remote_filename(filename: str) -> str:
    """Validate a Drive-provided default filename as a basename."""
    if not isinstance(filename, str) or not filename or filename in {".", ".."}:
        raise ValueError("Remote filename must be a non-empty basename")
    if "/" in filename or "\\" in filename:
        raise ValueError("Remote filename must not contain separators")
    stem = filename.rsplit(".", 1)[0].upper().rstrip(" .")
    if stem in _WINDOWS_RESERVED_NAMES or filename.endswith((" ", ".")):
        raise ValueError("Remote filename is not valid on Windows")
    return filename


def validate_transfer_path(output_path: Path | str, *, overwrite: bool = False) -> Path:
    """Validate a local transfer destination without following remote path data."""
    path = Path(output_path)
    name = path.name
    if not name or name in {".", ".."} or ".." in path.parts or "/" in name or "\\" in name:
        raise ValueError("Output filename must be a safe basename")
    stem = name.rsplit(".", 1)[0].upper().rstrip(" .")
    if stem in _WINDOWS_RESERVED_NAMES or name.endswith((" ", ".")):
        raise ValueError("Output filename is not valid on Windows")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")
    return path


class DriveService(BaseService):
    """Drive API service wrapper."""

    SERVICE_NAME = "drive"
    SERVICE_VERSION = "v3"

    def _files(self):
        """Get files API."""
        return self._get_service().files()

    def _drives(self):
        """Get drives API (shared drives)."""
        return self._get_service().drives()

    def _permissions(self):
        """Get permissions API."""
        return self._get_service().permissions()

    def list_files(
        self,
        parent_id: str | None = None,
        max_results: int = 100,
        page_token: str | None = None,
        order_by: str = "modifiedTime desc",
        fields: str = "nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)",
        drive_id: str | None = None,
        all_drives: bool = False,
    ) -> dict[str, Any]:
        """List files in Drive.

        Args:
            parent_id: Optional parent folder ID
            max_results: Maximum files to return
            page_token: Token for pagination
            order_by: Sort order
            fields: Fields to include

        Returns:
            Dict with 'files' list and optional 'nextPageToken'
        """
        query_parts = ["trashed = false"]
        if parent_id:
            safe_parent_id = parent_id.replace("\\", "\\\\").replace("'", "\\'")
            query_parts.append(f"'{safe_parent_id}' in parents")

        params = {
            "q": " and ".join(query_parts),
            "pageSize": max_results,
            "orderBy": order_by,
            "fields": fields,
            "supportsAllDrives": all_drives,
            "includeItemsFromAllDrives": all_drives,
        }
        if page_token:
            params["pageToken"] = page_token
        if drive_id:
            params["driveId"] = drive_id
            params["corpora"] = "drive"
        return self._execute(self._files().list(**params))

    def search_files(
        self,
        query: str,
        max_results: int = 100,
        page_token: str | None = None,
        drive_id: str | None = None,
        all_drives: bool = False,
    ) -> dict[str, Any]:
        """Search for files.

        Args:
            query: Search query (supports fullText contains, name contains, etc.)
            max_results: Maximum files to return
            page_token: Token for pagination

        Returns:
            Dict with 'files' list and optional 'nextPageToken'
        """
        safe_query = query.replace("\\", "\\\\").replace("'", "\\'")
        q = f"(name contains '{safe_query}' or fullText contains '{safe_query}') and trashed = false"

        params = {
            "q": q,
            "pageSize": max_results,
            "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime)",
            "supportsAllDrives": all_drives,
            "includeItemsFromAllDrives": all_drives,
        }
        if page_token:
            params["pageToken"] = page_token
        if drive_id:
            params["driveId"] = drive_id
            params["corpora"] = "drive"
        return self._execute(self._files().list(**params))

    def get_file(self, file_id: str) -> dict[str, Any]:
        """Get file metadata.

        Args:
            file_id: File ID

        Returns:
            File metadata dict
        """
        return self._execute(
            self._files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime, createdTime, parents, webViewLink",
                supportsAllDrives=True,
            )
        )

    def download_file(
        self, file_id: str, output_path: Path | str, *, overwrite: bool = False
    ) -> None:
        """Download atomically; an existing destination is preserved by default."""
        destination = validate_transfer_path(output_path, overwrite=overwrite)
        request = self._files().get_media(fileId=file_id, supportsAllDrives=True)
        self._transfer(request, destination, overwrite=overwrite)

    @staticmethod
    def _transfer(request: Any, destination: Path, *, overwrite: bool) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        reserved = False

        if not overwrite:
            try:
                fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                reserved = True
            except FileExistsError:
                raise FileExistsError(f"Output already exists: {destination}")
        fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                downloader = MediaIoBaseDownload(handle, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, destination)
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            if reserved and destination.exists() and destination.stat().st_size == 0:
                try:
                    destination.unlink()
                except FileNotFoundError:
                    pass

    def export_file(
        self,
        file_id: str,
        format: str,
        output_path: Path | str,
        *,
        overwrite: bool = False,
    ) -> None:
        """Export a Google Workspace file.

        Args:
            file_id: File ID
            format: Export format (pdf, docx, xlsx, pptx, csv, txt)
            output_path: Path to save file
        """
        destination = validate_transfer_path(output_path, overwrite=overwrite)
        file_meta = self.get_file(file_id)
        mime_type = file_meta.get("mimeType", "")

        format_lower = format.lower()
        export_mimes = EXPORT_FORMATS.get(mime_type, {})
        export_mime = export_mimes.get(format_lower)

        if not export_mime:
            common_mimes = {
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "csv": "text/csv",
                "txt": "text/plain",
            }
            export_mime = common_mimes.get(format_lower)

        if not export_mime:
            raise ValueError(f"Unknown export format: {format}")

        request = self._files().export_media(
            fileId=file_id, mimeType=export_mime, supportsAllDrives=True
        )
        self._transfer(request, destination, overwrite=overwrite)

    def upload_file(
        self,
        file_path: Path | str,
        name: str | None = None,
        parent_id: str | None = None,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """Upload a file.

        Args:
            file_path: Path to file to upload
            name: Optional name (defaults to filename)
            parent_id: Optional parent folder ID
            mime_type: Optional MIME type (auto-detected if not provided)

        Returns:
            Created file metadata
        """
        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Upload file not found: {file_path}")
        file_name = name or file_path.name

        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            mime_type = mime_type or "application/octet-stream"

        file_metadata: dict[str, Any] = {"name": file_name}
        if parent_id:
            file_metadata["parents"] = [parent_id]

        media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)

        return cast(
            dict[str, Any],
            (
                self._files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, mimeType, size, webViewLink",
                )
                .execute()
            ),
        )

    def create_folder(
        self,
        name: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a folder.

        Args:
            name: Folder name
            parent_id: Optional parent folder ID

        Returns:
            Created folder metadata
        """
        file_metadata: dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]

        return cast(
            dict[str, Any],
            (
                self._files()
                .create(
                    body=file_metadata,
                    fields="id, name, mimeType, webViewLink",
                )
                .execute()
            ),
        )

    def copy_file(
        self,
        file_id: str,
        name: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Copy a file.

        Args:
            file_id: File ID to copy
            name: Name for the copy
            parent_id: Optional parent folder for the copy

        Returns:
            Copied file metadata
        """
        file_metadata: dict[str, Any] = {"name": name}
        if parent_id:
            file_metadata["parents"] = [parent_id]

        return cast(
            dict[str, Any],
            (
                self._files()
                .copy(
                    fileId=file_id,
                    body=file_metadata,
                    fields="id, name, mimeType, webViewLink",
                )
                .execute()
            ),
        )

    def rename_file(self, file_id: str, name: str) -> dict[str, Any]:
        """Rename a file.

        Args:
            file_id: File ID
            name: New name

        Returns:
            Updated file metadata
        """
        return cast(
            dict[str, Any],
            (
                self._files()
                .update(
                    fileId=file_id,
                    body={"name": name},
                    fields="id, name, mimeType",
                )
                .execute()
            ),
        )

    def move_file(self, file_id: str, new_parent_id: str) -> dict[str, Any]:
        """Move a file to a new folder.

        Args:
            file_id: File ID
            new_parent_id: New parent folder ID

        Returns:
            Updated file metadata
        """
        file = self._files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents", []))

        return cast(
            dict[str, Any],
            (
                self._files()
                .update(
                    fileId=file_id,
                    addParents=new_parent_id,
                    removeParents=previous_parents,
                    fields="id, name, parents",
                )
                .execute()
            ),
        )

    def delete_file(self, file_id: str) -> None:
        """Move a file to trash.

        Args:
            file_id: File ID
        """
        self._files().update(
            fileId=file_id,
            body={"trashed": True},
        ).execute()

    def list_permissions(self, file_id: str) -> list[dict[str, Any]]:
        """List file permissions.

        Args:
            file_id: File ID

        Returns:
            List of permission dicts
        """
        result = (
            self._permissions()
            .list(
                fileId=file_id,
                fields="permissions(id, type, role, emailAddress)",
            )
            .execute()
        )
        return cast(list[dict[str, Any]], result.get("permissions", []))

    def share_file(
        self,
        file_id: str,
        email: str,
        role: str = "reader",
        send_notification: bool = True,
    ) -> dict[str, Any]:
        """Share a file with a user.

        Args:
            file_id: File ID
            email: User email
            role: 'reader', 'writer', 'commenter', or 'owner'
            send_notification: Whether to send email notification

        Returns:
            Created permission
        """
        permission = {
            "type": "user",
            "role": role,
            "emailAddress": email,
        }

        return cast(
            dict[str, Any],
            (
                self._permissions()
                .create(
                    fileId=file_id,
                    body=permission,
                    sendNotificationEmail=send_notification,
                    fields="id, type, role, emailAddress",
                )
                .execute()
            ),
        )

    def unshare_file(self, file_id: str, permission_id: str) -> None:
        """Remove a permission from a file.

        Args:
            file_id: File ID
            permission_id: Permission ID
        """
        self._permissions().delete(
            fileId=file_id,
            permissionId=permission_id,
        ).execute()

    def list_drives(self, max_results: int = 100) -> list[dict[str, Any]]:
        """List shared drives.

        Args:
            max_results: Maximum drives to return

        Returns:
            List of shared drive dicts
        """
        result = (
            self._drives()
            .list(
                pageSize=max_results,
                fields="drives(id, name)",
            )
            .execute()
        )
        return cast(list[dict[str, Any]], result.get("drives", []))

    @staticmethod
    def get_drive_url(file_id: str) -> str:
        """Get Drive web URL for a file.

        Args:
            file_id: File ID

        Returns:
            Drive URL
        """
        return f"https://drive.google.com/file/d/{file_id}/view"

    @staticmethod
    def format_size(size_bytes: int | str | None) -> str:
        """Format file size for display.

        Args:
            size_bytes: Size in bytes

        Returns:
            Human-readable size string
        """
        if size_bytes is None:
            return "-"
        size: float = int(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
