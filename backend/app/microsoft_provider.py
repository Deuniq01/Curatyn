"""
Microsoft Graph implementation of EmailProvider. Requires Mail.Send for
send_email() and Mail.ReadWrite for create_draft(). Graph's sendMail
returns no body on success, so we mint a local message id.
"""
import base64
import uuid

import httpx

from app.email_provider import DraftResult, EmailAttachment, EmailProvider, EmailProviderError, SendResult

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0/me"


class MicrosoftProvider(EmailProvider):
    def __init__(self, access_token: str):
        self._access_token = access_token

    def _build_message_payload(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> dict:
        encoded = base64.b64encode(attachment.content_bytes).decode("utf-8")
        return {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
            "attachments": [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": attachment.filename,
                "contentType": attachment.mime_type,
                "contentBytes": encoded,
            }],
        }

    async def send_email(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> SendResult:
        message = self._build_message_payload(recipient, subject, body, attachment)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{GRAPH_API_BASE}/sendMail",
                headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
                json={"message": message, "saveToSentItems": True},
            )
        if response.status_code >= 400:
            retryable = response.status_code >= 500 or response.status_code == 429
            raise EmailProviderError(f"Graph sendMail failed: {response.status_code} {response.text}", retryable, response.status_code)
        return SendResult(provider_message_id=f"graph-sent-{uuid.uuid4()}", raw_response={})

    async def create_draft(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> DraftResult:
        message = self._build_message_payload(recipient, subject, body, attachment)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{GRAPH_API_BASE}/messages",
                headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
                json=message,
            )
        if response.status_code >= 400:
            retryable = response.status_code >= 500 or response.status_code == 429
            raise EmailProviderError(f"Graph draft creation failed: {response.status_code} {response.text}", retryable, response.status_code)
        data = response.json()
        return DraftResult(draft_id=data["id"], raw_response=data)
