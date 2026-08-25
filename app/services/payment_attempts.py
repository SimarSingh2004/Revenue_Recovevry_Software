from app.core.recovery_actions import RecoveryAction
from app.schemas.recovery_context import RecoveryContext


PAYMENT_ATTEMPT_ACTIONS = {
    RecoveryAction.RETRY_PAYMENT,
    RecoveryAction.ALTERNATE_PAYMENT_METHOD,
    RecoveryAction.SEND_PAYMENT_LINK,
}


def increment_payment_attempt_number(
    context: RecoveryContext, action: RecoveryAction | str
) -> int:
    if RecoveryAction(action) in PAYMENT_ATTEMPT_ACTIONS:
        context.current_payment_failure.payment_attempt_number += 1
    return context.current_payment_failure.payment_attempt_number
