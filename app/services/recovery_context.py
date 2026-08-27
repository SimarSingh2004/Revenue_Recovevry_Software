from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MerchantContext,
    MerchantHistory,
    PaymentHistory,
    RecoveryCase,
    RecoveryEvent,
)
from app.schemas.recovery_context import (
    CurrentPaymentFailureContext,
    CustomerPaymentHistoryContext,
    HistoricalPayment,
    MerchantContextData,
    MerchantRecoveryHistoryContext,
    MerchantRecoveryHistoryItem,
    RecoveryCaseContext,
    RecoveryContext,
)


def load_recovery_context(db: Session, case_id: str) -> RecoveryContext:
    recovery_case = db.get(RecoveryCase, case_id)
    if recovery_case is None:
        raise ValueError(f"Recovery case '{case_id}' was not found")

    recovery_event = db.get(RecoveryEvent, recovery_case.event_id)
    if recovery_event is None:
        raise ValueError(f"Recovery event '{recovery_case.event_id}' was not found")

    merchant = db.get(MerchantContext, recovery_event.merchant_id)
    if merchant is None:
        raise ValueError(f"Merchant context '{recovery_event.merchant_id}' was not found")

    merchant_history = list(
        db.scalars(
            select(MerchantHistory)
            .where(MerchantHistory.merchant_id == recovery_event.merchant_id)
            .order_by(MerchantHistory.occurred_at.desc(), MerchantHistory.id.desc())
        )
    )
    payment_history = list(
        db.scalars(
            select(PaymentHistory)
            .where(PaymentHistory.customer_id == recovery_event.customer_id)
            .where(PaymentHistory.merchant_id == recovery_event.merchant_id)
            .where(PaymentHistory.payment_id != recovery_event.payment_id)
            .where(PaymentHistory.occurred_at < recovery_event.occurred_at)
            .order_by(PaymentHistory.occurred_at.asc(), PaymentHistory.id.asc())
        )
    )

    return build_recovery_context(
        recovery_case=recovery_case,
        recovery_event=recovery_event,
        merchant=merchant,
        merchant_history=merchant_history,
        payment_history=payment_history,
    )


def build_recovery_context(
    *,
    recovery_case: RecoveryCase,
    recovery_event: RecoveryEvent,
    merchant: MerchantContext,
    merchant_history: list[MerchantHistory],
    payment_history: list[PaymentHistory],
) -> RecoveryContext:
    relevant_merchant_history = [
        item for item in merchant_history if item.merchant_id == recovery_event.merchant_id
    ]
    current_case_history = [
        item for item in relevant_merchant_history if item.case_id == recovery_case.case_id
    ]
    latest_history = max(
        current_case_history, key=lambda item: (item.occurred_at, item.id), default=None
    )
    historical_payments = [
        item
        for item in payment_history
        if item.customer_id == recovery_event.customer_id
        and item.merchant_id == recovery_event.merchant_id
        and item.payment_id != recovery_event.payment_id
        and item.occurred_at < recovery_event.occurred_at
    ]
    failed_count = sum(item.status.upper() == "FAILED" for item in historical_payments)
    successful_count = sum(item.status.upper() == "SUCCESS" for item in historical_payments)
    payment_count = len(historical_payments)

    return RecoveryContext(
        case=RecoveryCaseContext(
            case_id=recovery_case.case_id,
            event_id=recovery_case.event_id,
            payment_id=recovery_case.payment_id,
            status=recovery_case.status,
            case_created_at=recovery_case.created_at,
        ),
        current_payment_failure=CurrentPaymentFailureContext(
            customer_id=recovery_event.customer_id,
            amount=recovery_event.amount,
            currency=recovery_event.currency,
            event_type=recovery_event.event_type,
            event_occurred_at=recovery_event.occurred_at,
            failure_code=recovery_event.failure_code,
            failure_category=recovery_event.failure_category,
            payment_method=recovery_event.payment_method,
            payment_attempt_number=recovery_event.attempt_number,
        ),
        merchant=MerchantContextData(
            merchant_id=merchant.merchant_id,
            recovery_enabled=merchant.recovery_enabled,
            allowed_recovery_actions=merchant.allowed_recovery_actions,
            merchant_segment=merchant.merchant_segment,
            retry_cooldown_seconds=merchant.retry_cooldown_seconds,
            max_recovery_attempts=merchant.max_recovery_attempts,
        ),
        merchant_recovery_history=MerchantRecoveryHistoryContext(
            history=[
                MerchantRecoveryHistoryItem(
                    action=item.action,
                    outcome=item.outcome,
                    amount=item.amount,
                    intervention_cost=item.intervention_cost,
                    occurred_at=item.occurred_at,
                )
                for item in current_case_history
            ],
            recovery_attempt_count=len(current_case_history),
            last_recovery_action=latest_history.action if latest_history else None,
            last_recovery_outcome=latest_history.outcome if latest_history else None,
            last_recovery_at=latest_history.occurred_at if latest_history else None,
        ),
        customer_payment_history=CustomerPaymentHistoryContext(
            historical_payments=[
                HistoricalPayment(
                    payment_id=item.payment_id,
                    amount=item.amount,
                    currency=item.currency,
                    payment_method=item.payment_method,
                    status=item.status,
                    event_type=item.event_type,
                    occurred_at=item.occurred_at,
                )
                for item in historical_payments
            ],
            customer_payment_count=payment_count,
            customer_failed_payment_count=failed_count,
            customer_successful_payment_count=successful_count,
            customer_failure_rate=(Decimal(failed_count) / Decimal(payment_count))
            if payment_count
            else Decimal("0"),
        ),
    )
