from app.core.recovery_actions import RecoveryAction, get_action_cost, get_risk_penalty
from app.schemas.recovery_context import RecoveryContext

def expected_net_recovery_value(
    context: RecoveryContext, action: RecoveryAction | str, probability: float
) -> float:
    resolved_action = RecoveryAction(action)
    if not 0.0 <= probability <= 1.0:
        raise ValueError("Probability must be between 0 and 1.")
    if resolved_action == RecoveryAction.STOP:
        return 0.0

    expected_revenue = probability * float(context.current_payment_failure.amount)
    action_cost = get_action_cost(resolved_action)
    risk_penalty = get_risk_penalty(resolved_action)
    return expected_revenue - action_cost - risk_penalty
