from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas import (
    RecoveryEventCreate,
    RecoveryEventIngestionResponse,
    ValidationErrorResponse,
)
from app.services.llm_decision import (
    LLMDecisionService,
    get_llm_decision_service
)
from app.services.policy_engine import PolicyEngine
from app.simulator.payment_provider import PaymentProviderSimulator
from app.services.recovery_event import create_recovery_event_service
from app.services.recovery_dashboard import get_latest_recovery_dashboard

router = APIRouter(prefix="/recovery-events", tags=["recovery-events"])

def get_policy_engine() -> PolicyEngine:
    return PolicyEngine()

def get_payment_provider() -> PaymentProviderSimulator:
    return PaymentProviderSimulator()

def get_recovery_llm_service()-> LLMDecisionService:
    return get_llm_decision_service()


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
    llm_decision_service: LLMDecisionService = Depends(get_recovery_llm_service),
    policy_engine: PolicyEngine = Depends(get_policy_engine),
    payment_provider: PaymentProviderSimulator = Depends(get_payment_provider)
) -> RecoveryEventIngestionResponse:
        result=create_recovery_event_service(
            payload=payload,
            db=db,
            llm_decision_service=llm_decision_service,
            policy_engine=policy_engine,
            payment_provider=payment_provider
        )

        if result.status=="duplicate":
            response.status_code=status.HTTP_200_OK

        return result

@router.get("/latest")
def latest_recovery_dashboard(
     db:Session=Depends(get_db_session)
)-> dict:
     return get_latest_recovery_dashboard(db=db)