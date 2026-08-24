from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import RecoveryCase, RecoveryEvent
from app.schemas import (
    RecoveryEventCreate,
    RecoveryEventIngestionResponse,
    ValidationErrorResponse,
)

router = APIRouter(prefix="/recovery-events", tags=["recovery-events"])


@router.post(
    "",
    response_model=RecoveryEventIngestionResponse,
    responses={422: {"model": ValidationErrorResponse}},
    status_code=status.HTTP_201_CREATED,
)
def create_recovery_event(
    payload: RecoveryEventCreate,
    response: Response,
    db: Session = Depends(get_db_session),
) -> RecoveryEventIngestionResponse:
    existing_event = db.get(RecoveryEvent, payload.event_id)
    if existing_event is not None:
        existing_case = db.scalar(
            select(RecoveryCase).where(RecoveryCase.event_id == payload.event_id)
        )
        if existing_case is None:
            raise HTTPException(status_code=500, detail="Recovery case is missing")
        response.status_code = status.HTTP_200_OK
        return RecoveryEventIngestionResponse(
            status="duplicate",
            recovery_event=existing_event,
            recovery_case=existing_case,
        )

    recovery_event = RecoveryEvent(**payload.model_dump(),attempt_number=1)
    recovery_case = RecoveryCase(
        case_id=f"case_{uuid4().hex}",
        event_id=recovery_event.event_id,
        payment_id=recovery_event.payment_id,
        status="PENDING",
    )

    try:
        db.add(recovery_event)
        db.flush()
        db.add(recovery_case)
        db.commit()
        db.refresh(recovery_event)
        db.refresh(recovery_case)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create recovery event",
        ) from error

    return RecoveryEventIngestionResponse(
        status="created",
        recovery_event=recovery_event,
        recovery_case=recovery_case,
    )
