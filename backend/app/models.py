import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EMBEDDING_DIM = 768  # matches app/ai_client.py mock embedding size; adjust if you switch models


def _uuid():
    return str(uuid.uuid4())


class EmailProviderType(str, enum.Enum):
    GMAIL = "GMAIL"
    OUTLOOK = "OUTLOOK"


class ApplicationStatus(str, enum.Enum):
    CREATED = "CREATED"
    PROCESSING_JD = "PROCESSING_JD"
    JD_ANALYZED = "JD_ANALYZED"
    CV_MATCHED = "CV_MATCHED"
    CV_CONFIRMED = "CV_CONFIRMED"
    COVER_LETTER_GENERATED = "COVER_LETTER_GENERATED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    USER_REVIEWING = "USER_REVIEWING"
    READY_TO_SEND = "READY_TO_SEND"
    SENDING = "SENDING"
    SAVING_DRAFT = "SAVING_DRAFT"
    SENT = "SENT"
    DRAFT_CREATED = "DRAFT_CREATED"
    JD_ANALYSIS_FAILED = "JD_ANALYSIS_FAILED"
    CV_PROCESSING_FAILED = "CV_PROCESSING_FAILED"
    COVER_LETTER_FAILED = "COVER_LETTER_FAILED"
    OAUTH_FAILED = "OAUTH_FAILED"
    SEND_FAILED = "SEND_FAILED"
    DRAFT_CREATION_FAILED = "DRAFT_CREATION_FAILED"
    CANCELLED = "CANCELLED"


class ApplicationEventType(str, enum.Enum):
    APPLICATION_CREATED = "APPLICATION_CREATED"
    JD_ANALYZED = "JD_ANALYZED"
    CV_MATCHED = "CV_MATCHED"
    CV_CONFIRMED = "CV_CONFIRMED"
    COVER_LETTER_GENERATED = "COVER_LETTER_GENERATED"
    USER_REVIEWED = "USER_REVIEWED"
    DRAFT_CREATED = "DRAFT_CREATED"
    SEND_INITIATED = "SEND_INITIATED"
    EMAIL_SENT = "EMAIL_SENT"
    SEND_FAILED = "SEND_FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    email_provider: Mapped[EmailProviderType | None] = mapped_column(Enum(EmailProviderType, name="email_provider_type"), nullable=True)
    email_provider_account_id: Mapped[str | None] = mapped_column(nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cvs: Mapped[list["CV"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    job_descriptions: Mapped[list["JobDescription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class CV(Base):
    __tablename__ = "cvs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str]
    file_url: Mapped[str]
    raw_text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="cvs")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str]  # "text" | "image"
    raw_input: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(nullable=True)
    company_name: Mapped[str | None] = mapped_column(nullable=True)
    role_title: Mapped[str | None] = mapped_column(nullable=True)
    structured_json = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="job_descriptions")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_applications_idempotency_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_description_id: Mapped[str] = mapped_column(ForeignKey("job_descriptions.id"))
    selected_cv_id: Mapped[str | None] = mapped_column(ForeignKey("cvs.id"), nullable=True)

    recipient_email: Mapped[str | None] = mapped_column(nullable=True)
    email_subject: Mapped[str | None] = mapped_column(nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[float | None] = mapped_column(nullable=True)

    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus, name="application_status"), default=ApplicationStatus.CREATED, index=True)

    email_provider: Mapped[EmailProviderType | None] = mapped_column(Enum(EmailProviderType, name="email_provider_type"), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft_id: Mapped[str | None] = mapped_column(nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(nullable=True)
    last_send_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="applications")
    job_description: Mapped["JobDescription"] = relationship()
    selected_cv: Mapped["CV | None"] = relationship()
    events: Mapped[list["ApplicationEvent"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[ApplicationEventType] = mapped_column(Enum(ApplicationEventType, name="application_event_type"))
    provider: Mapped[EmailProviderType | None] = mapped_column(Enum(EmailProviderType, name="email_provider_type"), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(nullable=True)
    event_metadata = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="events")
