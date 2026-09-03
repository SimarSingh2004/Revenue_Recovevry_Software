from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MerchantHistory,
    RecoveryCase,
    RecoveryEvent,
    RecoveryLearningMemory,
)


def get_latest_recovery_dashboard(db: Session) -> dict:
    recovery_case = db.scalar(
        select(RecoveryCase)
        .order_by(RecoveryCase.updated_at.desc(), RecoveryCase.created_at.desc())
        .limit(1)
    )

    if recovery_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recovery cases found",
        )

    recovery_event = db.get(RecoveryEvent, recovery_case.event_id)

    if recovery_event is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recovery event is missing for the latest recovery case",
        )

    merchant_history = db.scalar(
        select(MerchantHistory)
        .where(MerchantHistory.case_id == recovery_case.case_id)
        .order_by(MerchantHistory.occurred_at.desc(), MerchantHistory.id.desc())
        .limit(1)
    )

    if merchant_history is None:
        return {
            "case": {
                "case_id": recovery_case.case_id,
                "payment_id": recovery_case.payment_id,
                "status": recovery_case.status,
                "amount": float(recovery_event.amount),
                "currency": recovery_event.currency,
                "failure_code": recovery_event.failure_code,
                "failure_category": recovery_event.failure_category,
                "payment_method": recovery_event.payment_method,
                "created_at": recovery_case.created_at,
                "updated_at": recovery_case.updated_at,
            },
            "ai_decision": None,
            "policy": None,
            "execution": None,
            "outcome": {
                "status": recovery_case.status,
                "recovered_value": 0.0,
                "net_recovery_value": 0.0,
            },
        }

    learning_memory = db.scalar(
        select(RecoveryLearningMemory)
        .where(
            RecoveryLearningMemory.failure_code == recovery_event.failure_code,
            RecoveryLearningMemory.failure_category
            == recovery_event.failure_category,
            RecoveryLearningMemory.payment_method
            == recovery_event.payment_method,
            RecoveryLearningMemory.action == merchant_history.action,
        )
        .order_by(
            RecoveryLearningMemory.created_at.desc(),
            RecoveryLearningMemory.id.desc(),
        )
        .limit(1)
    )

    net_recovery_value = float(learning_memory.net_recovery_value) if learning_memory else 0.0

    recovered_value = (
        float(recovery_event.amount)
        if merchant_history.outcome == "SUCCESS"
        else 0.0
    )

    return {
        "case": {
            "case_id": recovery_case.case_id,
            "payment_id": recovery_case.payment_id,
            "status": recovery_case.status,
            "amount": float(recovery_event.amount),
            "currency": recovery_event.currency,
            "failure_code": recovery_event.failure_code,
            "failure_category": recovery_event.failure_category,
            "payment_method": recovery_event.payment_method,
            "created_at": recovery_case.created_at,
            "updated_at": recovery_case.updated_at,
        },
        "ai_decision": {
            "action": learning_memory.action if learning_memory else merchant_history.action,
            "predicted_p_recovery": (
                float(learning_memory.llm_p_pred)
                if learning_memory
                else None
            ),
        },
        "policy": {
            "final_action":merchant_history.action,
            "execution_authorized":True
        },
        "execution": {
            "action": merchant_history.action,
            "outcome": merchant_history.outcome,
            "intervention_cost": float(merchant_history.intervention_cost),
        },
        "outcome": {
            "status": recovery_case.status,
            "recovered_value": recovered_value,
            "net_recovery_value": net_recovery_value,
        },
    }