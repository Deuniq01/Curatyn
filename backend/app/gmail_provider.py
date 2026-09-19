"""
Gmail implementation of EmailProvider. Needs both gmail.send (to deliver mail)
and gmail.compose (to build a draft) — see GOOGLE_SCOPES in
app/routers/auth_routes.py. PRD Section 8 and 16.
"""
import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.email_provider import DraftResult, EmailAttachment, EmailProvider, EmailProviderError, SendResult

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailProvider(EmailProvider):
    def __init__(self, access_token: str):
        self._access_token = access_token

    def _build_mime_message(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> str:
        message = MIMEMultipart()
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        part = MIMEApplication(attachment.content_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=attachment.filename)
        message.attach(part)

        raw_bytes = message.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

    async def send_email(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> SendResult:
        raw = self._build_mime_message(recipient, subject, body, attachment)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/messages/send",
                headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
                json={"raw": raw},
            )
        if response.status_code >= 400:
            retryable = response.status_code >= 500 or response.status_code == 429
            raise EmailProviderError(f"Gmail send failed: {response.status_code} {response.text}", retryable, response.status_code)
        data = response.json()
        return SendResult(provider_message_id=data["id"], raw_response=data)

    async def create_draft(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> DraftResult:
        raw = self._build_mime_message(recipient, subject, body, attachment)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/drafts",
                headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
                json={"message": {"raw": raw}},
            )
        if response.status_code >= 400:
            retryable = response.status_code >= 500 or response.status_code == 429
            raise EmailProviderError(f"Gmail draft creation failed: {response.status_code} {response.text}", retryable, response.status_code)
        data = response.json()
        return DraftResult(draft_id=data["id"], raw_response=data)
