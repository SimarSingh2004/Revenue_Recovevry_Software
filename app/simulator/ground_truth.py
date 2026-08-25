from datetime import datetime, timedelta

from app.core.recovery_actions import RecoveryAction
from app.schemas.recovery_context import RecoveryContext


BASE_ACTION_PROBABILITIES = {
    RecoveryAction.RETRY_PAYMENT: 0.60,
    RecoveryAction.ALTERNATE_PAYMENT_METHOD: 0.55,
    RecoveryAction.SEND_PAYMENT_LINK: 0.50,
    RecoveryAction.ESCALATE: 0.15,
}

PAYMENT_METHOD_EFFECTS = {
    "UPI": 0.05,
    "CARD": 0.00,
    "NETBANKING": 0.02,
    "WALLET": 0.03,
}

FAILURE_CATEGORY_EFFECTS = {
    "TEMPORARY_FAILURE": 0.12,
    "INSUFFICIENT_FUNDS": 0.10,
    "NETWORK_ERROR": 0.12,
    "PROCESSING_ERROR": 0.08,
    "EXPIRED_CARD": -0.18,
    "INVALID_CARD": -0.20,
    "FRAUD": -0.25,
    "UNKNOWN": 0.00,
}


def ground_truth_probability(
    context: RecoveryContext, action: RecoveryAction | str, now: datetime
) -> float:
    resolved_action = RecoveryAction(action)
    if resolved_action == RecoveryAction.STOP:
        return 0.0
    if resolved_action not in BASE_ACTION_PROBABILITIES:
        raise ValueError(f"{resolved_action.value} has no provider payment probability")

    failure = context.current_payment_failure
    raw_probability = (
        BASE_ACTION_PROBABILITIES[resolved_action]
        + _customer_history_effect(context)
        + _payment_method_effect(failure.payment_method)
        + _failure_category_effect(failure.failure_category)
        + _time_since_failure_effect(now - failure.event_occurred_at)
        + _previous_recovery_attempt_effect(
            context.merchant_recovery_history.recovery_attempt_count
        )
    )
    return _clamp_probability(raw_probability)


def _clamp_probability(probability: float) -> float:
    return max(0.05, min(0.95, probability))


def _customer_history_effect(context: RecoveryContext) -> float:
    
    history = context.customer_payment_history
    if history.customer_payment_count == 0:
        return 0.0
    customer_success_rate = (
        history.customer_successful_payment_count / history.customer_payment_count
    )
    return 0.15 * (customer_success_rate - 0.50)


def _payment_method_effect(payment_method: str) -> float:
    try:
        return PAYMENT_METHOD_EFFECTS[payment_method]
    except KeyError as error:
        raise ValueError(f"Unsupported payment method: {payment_method}") from error


def _failure_category_effect(failure_category: str | None) -> float:
    category = failure_category or "UNKNOWN"
    try:
        return FAILURE_CATEGORY_EFFECTS[category]
    except KeyError as error:
        raise ValueError(f"Unsupported failure category: {category}") from error


def _time_since_failure_effect(elapsed: timedelta) -> float:
    if elapsed < timedelta(minutes=15):
        return 0.05
    if elapsed < timedelta(hours=1):
        return 0.03
    if elapsed < timedelta(hours=6):
        return 0.00
    if elapsed <= timedelta(hours=24):
        return -0.04
    return -0.08


def _previous_recovery_attempt_effect(previous_attempts: int) -> float:
    return -0.04 * min(previous_attempts, 4)
