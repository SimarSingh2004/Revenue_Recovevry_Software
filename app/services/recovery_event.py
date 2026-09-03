from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


from app.models import RecoveryCase, RecoveryEvent
from app.schemas import (
    RecoveryEventCreate,
    RecoveryEventIngestionResponse,
)
from app.services.llm_decision import LLMDecisionService
from app.services.policy_engine import PolicyEngine
from app.services.recovery_pipeline import run_recovery_until_resolved
from app.simulator.payment_provider import PaymentProviderSimulator


def create_recovery_event_service(
    payload: RecoveryEventCreate,
    db: Session ,
    llm_decision_service: LLMDecisionService ,
    policy_engine: PolicyEngine,
    payment_provider: PaymentProviderSimulator 
) -> RecoveryEventIngestionResponse:
    existing_event = db.get(RecoveryEvent, payload.event_id)
    if existing_event is not None:
        existing_case = db.scalar(
            select(RecoveryCase).where(RecoveryCase.event_id == payload.event_id)
        )
        if existing_case is None:
            raise HTTPException(status_code=500, detail="Recovery case is missing")
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

        decision_capture = {}

        run_recovery_until_resolved(
            db=db,
            recovery_case=recovery_case,
            llm_decision_service=llm_decision_service,
            policy_engine=policy_engine,
            payment_provider=payment_provider,
            decision_capture=decision_capture
        )
    except (SQLAlchemyError,RuntimeError) as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to create recovery event: {error}",
        ) from error

    return RecoveryEventIngestionResponse(
        status="created",
        recovery_event=recovery_event,
        recovery_case=recovery_case,
        rationale=decision_capture.get("rationale")
    )