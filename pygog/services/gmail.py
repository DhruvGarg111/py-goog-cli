"""Gmail API service wrapper."""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

from pygog.services.base import BaseService


class GmailService(BaseService):
    """Gmail API service wrapper."""

    SERVICE_NAME = "gmail"
    SERVICE_VERSION = "v1"

    def _users(self):
        """Get users API."""
        return self._get_service().users()


    def list_labels(self) -> list[dict[str, Any]]:
        """List all labels.
        
        Returns:
            List of label dicts
        """
        result = self._users().labels().list(userId="me").execute()
        return result.get("labels", [])

    def get_label(self, label_id: str) -> dict[str, Any]:
        """Get a label by ID.
        
        Args:
            label_id: Label ID (e.g., 'INBOX', 'Label_123')
            
        Returns:
            Label dict with details
        """
        return self._users().labels().get(userId="me", id=label_id).execute()

    def create_label(self, name: str, **kwargs) -> dict[str, Any]:
        """Create a new label.
        
        Args:
            name: Label name
            **kwargs: Additional label properties
            
        Returns:
            Created label dict
        """
        body = {"name": name, **kwargs}
        return self._users().labels().create(userId="me", body=body).execute()


    def search_threads(
        self,
        query: str,
        max_results: int = 10,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """Search for threads.
        
        Args:
            query: Gmail search query
            max_results: Maximum threads to return
            page_token: Token for pagination
            
        Returns:
            Dict with 'threads' list and optional 'nextPageToken'
        """
        result = self._users().threads().list(
            userId="me",
            q=query,
            maxResults=max_results,
            pageToken=page_token,
        ).execute()
        return result

    def search_messages(
        self,
        query: str,
        max_results: int = 10,
        page_token: str | None = None,
        include_body: bool = False,
    ) -> dict[str, Any]:
        """Search for messages.
        
        Args:
            query: Gmail search query
            max_results: Maximum messages to return
            page_token: Token for pagination
            include_body: Whether to fetch full message bodies
            
        Returns:
            Dict with 'messages' list and optional 'nextPageToken'
        """
        result = self._users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
            pageToken=page_token,
        ).execute()

        messages = result.get("messages", [])
        
        if include_body and messages:
            detailed = []
            for msg in messages:
                full_msg = self.get_message(msg["id"], format="full")
                detailed.append(full_msg)
            result["messages"] = detailed

        return result

    def get_message(
        self,
        message_id: str,
        format: str = "full",
    ) -> dict[str, Any]:
        """Get a message by ID.
        
        Args:
            message_id: Message ID
            format: 'minimal', 'full', 'raw', or 'metadata'
            
        Returns:
            Message dict
        """
        return self._users().messages().get(
            userId="me",
            id=message_id,
            format=format,
        ).execute()

    def get_thread(
        self,
        thread_id: str,
        format: str = "full",
    ) -> dict[str, Any]:
        """Get a thread by ID.
        
        Args:
            thread_id: Thread ID
            format: 'minimal', 'full', or 'metadata'
            
        Returns:
            Thread dict with messages
        """
        return self._users().threads().get(
            userId="me",
            id=thread_id,
            format=format,
        ).execute()


    def send_message(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        body_html: str | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
        reply_to: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an email.
        
        Args:
            to: Recipient(s)
            subject: Email subject
            body: Plain text body
            body_html: Optional HTML body
            cc: CC recipient(s)
            bcc: BCC recipient(s)
            reply_to: Reply-to address
            thread_id: Thread ID if replying
            
        Returns:
            Sent message dict
        """
        if body_html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(body_html, "html"))
        else:
            msg = MIMEText(body)

        msg["To"] = ", ".join(to) if isinstance(to, list) else to
        msg["Subject"] = subject
        
        if cc:
            msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc
        if bcc:
            msg["Bcc"] = ", ".join(bcc) if isinstance(bcc, list) else bcc
        if reply_to:
            msg["Reply-To"] = reply_to

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        
        body = {"raw": raw}
        if thread_id:
            body["threadId"] = thread_id

        return self._users().messages().send(userId="me", body=body).execute()

    def create_draft(
        self,
        to: str | list[str] | None = None,
        subject: str = "",
        body: str = "",
    ) -> dict[str, Any]:
        """Create a draft.
        
        Args:
            to: Recipient(s)
            subject: Email subject
            body: Plain text body
            
        Returns:
            Created draft dict
        """
        msg = MIMEText(body)
        if to:
            msg["To"] = ", ".join(to) if isinstance(to, list) else to
        msg["Subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        
        return self._users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}},
        ).execute()

    def list_drafts(self, max_results: int = 10) -> list[dict[str, Any]]:
        """List drafts.
        
        Args:
            max_results: Maximum drafts to return
            
        Returns:
            List of draft dicts
        """
        result = self._users().drafts().list(
            userId="me",
            maxResults=max_results,
        ).execute()
        return result.get("drafts", [])


    def get_attachment(
        self,
        message_id: str,
        attachment_id: str,
    ) -> bytes:
        """Get an attachment.
        
        Args:
            message_id: Message ID
            attachment_id: Attachment ID
            
        Returns:
            Attachment data as bytes
        """
        result = self._users().messages().attachments().get(
            userId="me",
            messageId=message_id,
            id=attachment_id,
        ).execute()
        
        data = result.get("data", "")
        return base64.urlsafe_b64decode(data)


    def modify_thread(
        self,
        thread_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Modify thread labels.
        
        Args:
            thread_id: Thread ID
            add_labels: Labels to add
            remove_labels: Labels to remove
            
        Returns:
            Modified thread dict
        """
        body = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels

        return self._users().threads().modify(
            userId="me",
            id=thread_id,
            body=body,
        ).execute()

    def modify_message(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Modify message labels.
        
        Args:
            message_id: Message ID
            add_labels: Labels to add
            remove_labels: Labels to remove
            
        Returns:
            Modified message dict
        """
        body = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels

        return self._users().messages().modify(
            userId="me",
            id=message_id,
            body=body,
        ).execute()


    @staticmethod
    def extract_headers(message: dict[str, Any]) -> dict[str, str]:
        """Extract headers from a message.
        
        Args:
            message: Message dict with payload.headers
            
        Returns:
            Dict of header name -> value
        """
        headers = {}
        payload = message.get("payload", {})
        for header in payload.get("headers", []):
            headers[header["name"]] = header["value"]
        return headers

    @staticmethod
    def extract_body(message: dict[str, Any]) -> str:
        """Extract body text from a message.
        
        Args:
            message: Message dict
            
        Returns:
            Body text (plain text preferred)
        """
        payload = message.get("payload", {})
        
        body_data = payload.get("body", {}).get("data")
        if body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        
        return ""

    @staticmethod
    def get_gmail_url(thread_id: str, account: str | None = None) -> str:
        """Get Gmail web URL for a thread.
        
        Args:
            thread_id: Thread ID
            account: Account email for multi-account URL
            
        Returns:
            Gmail URL
        """
        base = "https://mail.google.com/mail/u/0"
        if account:
            base = f"https://mail.google.com/mail/u/{account}"
        return f"{base}/#inbox/{thread_id}"
