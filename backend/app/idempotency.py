"""
Idempotency guard for POST /applications/:id/send and .../draft.
"""
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, ApplicationStatus


class IdempotencyOutcome(str, Enum):
    PROCEED = "proceed"
    ALREADY_SUCCEEDED = "already_succeeded"
    ALREADY_FAILED = "already_failed"
    IN_FLIGHT = "in_flight"


@dataclass
class IdempotencyCheckResult:
    outcome: IdempotencyOutcome
    application: Application


TERMINAL_SUCCESS_STATUSES = {ApplicationStatus.SENT, ApplicationStatus.DRAFT_CREATED}
TERMINAL_FAILURE_STATUSES = {ApplicationStatus.SEND_FAILED, ApplicationStatus.DRAFT_CREATION_FAILED}
IN_FLIGHT_STATUSES = {ApplicationStatus.SENDING, ApplicationStatus.SAVING_DRAFT}

# The states a send or draft may start from. Both claim functions used to carry
# their own private copy of this list, which is how a state that one of them
# accepted ended up rejected by the other.
#
# READY_FOR_REVIEW and USER_REVIEWING are deliberately absent: the review gate is
# cleared by an explicit user action, never by reaching for a send.
CLAIMABLE_STATUSES = {
    ApplicationStatus.READY_TO_SEND,
    ApplicationStatus.SEND_FAILED,
    ApplicationStatus.DRAFT_CREATED,          # saving a draft does not block sending
    ApplicationStatus.DRAFT_CREATION_FAILED,  # a draft that failed can be retried
}


async def check_idempotency(session: AsyncSession, application_id: str, idempotency_key: str) -> IdempotencyCheckResult:
    result = await session.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one()

    if application.idempotency_key == idempotency_key:
        if application.status in TERMINAL_SUCCESS_STATUSES:
            return IdempotencyCheckResult(IdempotencyOutcome.ALREADY_SUCCEEDED, application)
        if application.status in TERMINAL_FAILURE_STATUSES:
            return IdempotencyCheckResult(IdempotencyOutcome.ALREADY_FAILED, application)
        if application.status in IN_FLIGHT_STATUSES:
            return IdempotencyCheckResult(IdempotencyOutcome.IN_FLIGHT, application)

    return IdempotencyCheckResult(IdempotencyOutcome.PROCEED, application)


async def claim_for_sending(session: AsyncSession, application: Application, idempotency_key: str) -> bool:
    """Atomically claims send: conditional UPDATE so concurrent requests with
    the same key cannot both proceed to call the provider. See
    CLAIMABLE_STATUSES for the allowed starting states."""
    stmt = (
        update(Application)
        .where(
            Application.id == application.id,
            Application.status.in_(CLAIMABLE_STATUSES),
        )
        .values(idempotency_key=idempotency_key, status=ApplicationStatus.SENDING)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount == 1


async def claim_for_drafting(session: AsyncSession, application: Application, idempotency_key: str) -> bool:
    """Same contract as claim_for_sending, for the draft path."""
    stmt = (
        update(Application)
        .where(
            Application.id == application.id,
            Application.status.in_(CLAIMABLE_STATUSES),
        )
        .values(idempotency_key=idempotency_key, status=ApplicationStatus.SAVING_DRAFT)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount == 1
