from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.session import get_db_session
from app.models.recovery import PaymentHistory
from app.schemas.payment import PaymentCreate
from app.schemas.recovery_event import RecoveryEventCreate
from app.services.llm_decision import LLMDecisionService, get_llm_decision_service
from app.services.policy_engine import PolicyEngine
from app.services.recovery_event import create_recovery_event_service
from app.simulator.payments import PaymentOutcome, PaymentSimulator, get_failure_category
from app.simulator.payment_provider import PaymentProviderSimulator

router = APIRouter(prefix="/payments", tags=["payments"])

def get_recovery_llm_service() -> LLMDecisionService:
    return get_llm_decision_service()

def get_payment_simulator() -> PaymentSimulator:
    return PaymentSimulator()

def get_payment_provider()-> PaymentProviderSimulator:
    return PaymentProviderSimulator()

def get_policy_engine() -> PolicyEngine:
    return PolicyEngine()

@router.post("")
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db_session),
    payment_simulator: PaymentSimulator = Depends(get_payment_simulator),
    llm_decision_service: LLMDecisionService = Depends(
        get_recovery_llm_service
    ),
    policy_engine: PolicyEngine = Depends(get_policy_engine),
    payment_provider: PaymentProviderSimulator = Depends(
        get_payment_provider
    ),
):
    payment_method = payload.payment_method.upper()
    currency = payload.currency.upper()

    simulation_result = payment_simulator.process(
        payload.payment_id,
        outcome=payload.simulation_outcome,
    )

    occurred_at=datetime.now(timezone.utc)

    payment_history=PaymentHistory(
        customer_id=payload.customer_id,
        merchant_id=payload.merchant_id,
        payment_id=payload.payment_id,
        amount=payload.amount,
        currency=currency,
        payment_method=payment_method,
        status=simulation_result.outcome.value,
        event_type=(
            "PAYMENT_COMPLETED"
            if simulation_result.outcome == PaymentOutcome.SUCCESS
            else "PAYMENT_FAILED"
        ),
        occurred_at=occurred_at,
    )

    db.add(payment_history)

    if simulation_result.outcome == PaymentOutcome.SUCCESS:
        db.commit()
        return {
            "status": "success",
            "payment_id": simulation_result.payment_id,
            "merchant_id": payload.merchant_id,
            "customer_id": payload.customer_id,
            "amount": payload.amount,
            "currency": currency,
            "payment_method":payment_method,
        }

    recovery_event = RecoveryEventCreate(
        event_id=f"recovery_event_{uuid4().hex}",
        event_type="PAYMENT_FAILED",
        occurred_at=occurred_at,
        payment_id=payload.payment_id,
        merchant_id=payload.merchant_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        currency=currency,
        failure_code="SIMULATED_FAILURE",
        failure_category=get_failure_category(payment_method),
        payment_method=payment_method,
    )

    recovery_result = create_recovery_event_service(
        payload=recovery_event,
        db=db,
        llm_decision_service=llm_decision_service,
        policy_engine=policy_engine,
        payment_provider=payment_provider,
    )

    return {
        "status": "failed",
        "payment_id": simulation_result.payment_id,
        "recovery": recovery_result,
    }