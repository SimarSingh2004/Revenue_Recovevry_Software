from decimal import Decimal
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services.llm_decision import get_llm_decision_service
from app.schemas.recovery_context import (
    RecoveryContext,
    RecoveryCaseContext,
    CurrentPaymentFailureContext,
    MerchantContextData,
    MerchantRecoveryHistoryContext,
    CustomerPaymentHistoryContext,
)
from app.schemas.recovery_memory import HistoricalRecoveryInsight


def build_context() -> RecoveryContext:
    now = datetime.now(timezone.utc)

    return RecoveryContext(
        case=RecoveryCaseContext(
            case_id="eval_case_001",
            event_id="eval_event_001",
            payment_id="eval_payment_001",
            status="PENDING",
            case_created_at=now,
        ),
        current_payment_failure=CurrentPaymentFailureContext(
            customer_id="eval_customer_001",
            amount=Decimal("1000.00"),
            currency="INR",
            event_type="PAYMENT_FAILED",
            event_occurred_at=now,
            failure_code="SIMULATED_FAILURE",
            failure_category="TEMPORARY_FAILURE",
            payment_method="UPI",
            payment_attempt_number=1,
        ),
        merchant=MerchantContextData(
            merchant_id="merchant_001",
            recovery_enabled=True,
            allowed_recovery_actions=[
                "RETRY_PAYMENT",
                "ALTERNATE_PAYMENT_METHOD",
                "SEND_PAYMENT_LINK",
            ],
            merchant_segment="SMB",
            retry_cooldown_seconds=60,
            max_recovery_attempts=3,
        ),
        merchant_recovery_history=MerchantRecoveryHistoryContext(
            history=[],
            recovery_attempt_count=0,
            last_recovery_action=None,
            last_recovery_outcome=None,
            last_recovery_at=None,
        ),
        customer_payment_history=CustomerPaymentHistoryContext(
            historical_payments=[],
            customer_payment_count=0,
            customer_failed_payment_count=0,
            customer_successful_payment_count=0,
            customer_failure_rate=Decimal("0"),
        ),
    )


def main() -> None:
    settings = get_settings()
    llm = get_llm_decision_service(settings)

    context = build_context()

    historical_insights = [
        HistoricalRecoveryInsight(
            failure_code="SIMULATED_FAILURE",
            failure_category="TEMPORARY_FAILURE",
            payment_method="UPI",
            action="SEND_PAYMENT_LINK",
            outcome="SUCCESS",
            financial_impact="POSITIVE_RECOVERY",
        ),
        HistoricalRecoveryInsight(
            failure_code="SIMULATED_FAILURE",
            failure_category="TEMPORARY_FAILURE",
            payment_method="UPI",
            action="ALTERNATE_PAYMENT_METHOD",
            outcome="FAILED",
            financial_impact="FEE_LOSS",
        ),
        HistoricalRecoveryInsight(
            failure_code="SIMULATED_FAILURE",
            failure_category="TEMPORARY_FAILURE",
            payment_method="UPI",
            action="RETRY_PAYMENT",
            outcome="FAILED",
            financial_impact="FEE_LOSS",
        ),
    ]

    print("\n=== MEMORY OFF ===")
    without_memory = llm.decide(
        context,
        historical_insights=[],
    )

    print("Action:", without_memory.action)
    print("Predicted recovery:", without_memory.predicted_p_recovery)
    print("Rationale:", without_memory.rationale)

    print("\n=== MEMORY ON ===")
    with_memory = llm.decide(
        context,
        historical_insights=historical_insights,
    )

    print("Action:", with_memory.action)
    print("Predicted recovery:", with_memory.predicted_p_recovery)
    print("Rationale:", with_memory.rationale)

    print("\n=== COMPARISON ===")
    print("Action changed:", without_memory.action != with_memory.action)
    print(
        "Prediction changed:",
        without_memory.predicted_p_recovery
        != with_memory.predicted_p_recovery,
    )


if __name__ == "__main__":
    main()