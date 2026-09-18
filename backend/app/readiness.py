"""
One definition of "this application is ready to send".

Both the review endpoints (which expose it to the UI) and the send/draft
endpoints (which enforce it) read from here. Keeping it in a single place is the
whole point: the send gate and the reason shown to the user can't disagree, and
a field added to the review screen can't be quietly forgotten by the check.
"""
from app.models import Application

# Attribute -> how the field is named to the user in the review screen.
_SEND_FIELD_LABELS: dict[str, str] = {
    "recipient_email": "recipient email",
    "email_subject": "subject",
    "email_body": "email body",
    "selected_cv_id": "CV attachment",
    "cover_letter": "cover letter",
}


def missing_send_fields(application: Application) -> list[str]:
    """User-facing names of the fields still missing before this can be sent.
    Empty list means ready. Scalar columns only — never touches a relationship,
    so it is safe to call from _serialize()."""
    return [
        label
        for attribute, label in _SEND_FIELD_LABELS.items()
        if not getattr(application, attribute)
    ]


def is_ready_to_send(application: Application) -> bool:
    return not missing_send_fields(application)
