"""
Curatyn Email Provider abstraction.

Everything above this layer (the send/draft route handlers) talks only to
EmailProvider. It never imports google-api-python-client or msgraph SDKs
directly. This is what keeps the Application object decoupled from any
single provider's success/failure state (PRD Section 29).
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailAttachment:
    filename: str
    content_bytes: bytes
    mime_type: str = "application/pdf"


@dataclass
class SendResult:
    provider_message_id: str
    raw_response: dict


@dataclass
class DraftResult:
    draft_id: str
    raw_response: dict


class EmailProviderError(Exception):
    """Raised by any provider implementation on a non-retryable failure."""

    def __init__(self, message: str, retryable: bool = True, provider_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.provider_status = provider_status


class EmailProvider(ABC):
    """
    Abstract base class. GmailProvider, MicrosoftProvider, and
    MockEmailProvider all implement this exact surface, so calling code
    never branches on provider type.
    """

    @abstractmethod
    async def send_email(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> SendResult:
        raise NotImplementedError

    @abstractmethod
    async def create_draft(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> DraftResult:
        raise NotImplementedError


class MockEmailProvider(EmailProvider):
    """
    Used when EMAIL_BACKEND=mock. Simulates a provider without any network
    call, so the whole send/draft/idempotency/failure-recovery path is
    exercisable without real Gmail/Outlook credentials.

    force_failure is set per-instance from SendRequest.simulateFailure
    (mock-backend-only) so tests can trigger the failure path
    deterministically over HTTP, without relying on any state shared
    between the test process and the server process.
    """

    def __init__(self, force_failure: bool = False):
        self.force_failure = force_failure

    async def send_email(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> SendResult:
        if self.force_failure:
            raise EmailProviderError("Mock provider: simulated send failure", retryable=True, provider_status=503)
        return SendResult(provider_message_id=f"mock-sent-{uuid.uuid4()}", raw_response={"to": recipient, "subject": subject})

    async def create_draft(self, recipient: str, subject: str, body: str, attachment: EmailAttachment) -> DraftResult:
        if self.force_failure:
            raise EmailProviderError("Mock provider: simulated draft failure", retryable=True, provider_status=503)
        return DraftResult(draft_id=f"mock-draft-{uuid.uuid4()}", raw_response={"to": recipient, "subject": subject})
