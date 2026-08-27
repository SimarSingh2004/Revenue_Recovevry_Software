from datetime import datetime, timedelta

from app.core.recovery_actions import RecoveryAction
from app.schemas.recovery_context import RecoveryContext


BASE_ACTION_PROBABILITIES = {
    RecoveryAction.RETRY_PAYMENT: 0.70,
    RecoveryAction.ALTERNATE_PAYMENT_METHOD: 0.65,
    RecoveryAction.SEND_PAYMENT_LINK: 0.55,
    RecoveryAction.ESCALATE: 0.10,
}

def baseline_probability(
    action: RecoveryAction | str, context: RecoveryContext, now: datetime
)-> float:
    resolved_action=RecoveryAction(action)
    if resolved_action==RecoveryAction.STOP:
        return 0.0
    
    if resolved_action not in BASE_ACTION_PROBABILITIES:
        raise ValueError(f"{resolved_action.value} has no provider payment probability")

    failure = context.current_payment_failure
    raw_probability = (
        BASE_ACTION_PROBABILITIES[resolved_action]
        + _customer_history_effect(context)
        + _time_since_failure_effect(now - failure.event_occurred_at)
    )
    return _clamp_probability(raw_probability)


def _clamp_probability(probability: float) -> float:
    return max(0.00, min(1.00, probability))

def _customer_history_effect(context: RecoveryContext) -> float:
    history = context.customer_payment_history
    if history.customer_payment_count == 0:
        return 0.0
    success_rate = history.customer_successful_payment_count / history.customer_payment_count
    return (success_rate - 0.5) * 0.2  

def _time_since_failure_effect(time_since_failure: timedelta) -> float:
    minutes_since_failure = time_since_failure.total_seconds() / 60
    if minutes_since_failure < 15:
        return 0.05
    elif minutes_since_failure < 60:
        return 0.00
    else:
        return -0.05