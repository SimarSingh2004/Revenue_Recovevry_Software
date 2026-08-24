from enum import Enum


class RecoveryAction(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    ALTERNATE_PAYMENT_METHOD = "ALTERNATE_PAYMENT_METHOD"
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"
    ESCALATE = "ESCALATE"
    STOP = "STOP"


ACTION_COSTS = {
    RecoveryAction.RETRY_PAYMENT: 2,
    RecoveryAction.ALTERNATE_PAYMENT_METHOD: 3,
    RecoveryAction.SEND_PAYMENT_LINK: 1,
    RecoveryAction.ESCALATE: 5,
    RecoveryAction.STOP: 0,
}


PAYMENT_ATTEMPT_BEHAVIOR = {
    RecoveryAction.RETRY_PAYMENT: "ON_ACTUAL_PAYMENT_ATTEMPT",
    RecoveryAction.ALTERNATE_PAYMENT_METHOD: "ON_ACTUAL_PAYMENT_ATTEMPT",
    RecoveryAction.SEND_PAYMENT_LINK: "ON_CUSTOMER_PAYMENT_ATTEMPT_VIA_LINK",
    RecoveryAction.ESCALATE: "DOES_NOT_INCREMENT",
    RecoveryAction.STOP: "DOES_NOT_INCREMENT",
}


def get_action_cost(action: RecoveryAction | str) -> int:
    return ACTION_COSTS[RecoveryAction(action)]


def get_payment_attempt_behavior(action: RecoveryAction | str) -> str:
    return PAYMENT_ATTEMPT_BEHAVIOR[RecoveryAction(action)]