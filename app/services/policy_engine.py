from datetime import datetime, timezone

from app.core.recovery_actions import RecoveryAction
from app.schemas.policy_decision import PolicyDecision
from app.schemas.recovery_context import RecoveryContext


class PolicyEngine:
    def evaluate(
        self,
        context: RecoveryContext,
        action: str,
        expected_net_recovery: float = 0,
    ) -> PolicyDecision:
        reasons: list[str] = []

        try:
            resolved_action = RecoveryAction(action)
        except ValueError:
            return PolicyDecision(
                approved=False,
                action=action,
                expected_net_recovery=expected_net_recovery,
                reasons=[f"Invalid action: {action}"],
            )

        if not context.merchant.recovery_enabled:
            return PolicyDecision(
                approved=False,
                action=action,
                expected_net_recovery=expected_net_recovery,
                reasons=["Recovery is disabled for this merchant."],
            )

        allowed_actions = {
            RecoveryAction(allowed_action).value
            for allowed_action in context.merchant.allowed_recovery_actions
            if allowed_action in RecoveryAction._value2member_map_
        }
        if resolved_action.value not in allowed_actions:
            return PolicyDecision(
                approved=False,
                action=action,
                expected_net_recovery=expected_net_recovery,
                reasons=[f"Action '{action}' is not allowed for this merchant."],
            )

        history = context.merchant_recovery_history
        if (
            history.recovery_attempt_count >= context.merchant.max_recovery_attempts
            and resolved_action not in {
                RecoveryAction.ESCALATE,
                RecoveryAction.STOP,
            }
        ):
            return PolicyDecision(
                approved=False,
                action=action,
                expected_net_recovery=expected_net_recovery,
                reasons=[
                    f"Maximum recovery attempts ({context.merchant.max_recovery_attempts}) reached."
                ],
            )

        if (
            resolved_action
            in {
                RecoveryAction.RETRY_PAYMENT,
                RecoveryAction.ALTERNATE_PAYMENT_METHOD,
                RecoveryAction.SEND_PAYMENT_LINK,
            }
            and history.last_recovery_at is not None
        ):
            now = datetime.now(timezone.utc)
            last_recovery_at = history.last_recovery_at

            if last_recovery_at.tzinfo is None:
                last_recovery_at = last_recovery_at.replace(tzinfo=timezone.utc)

            elapsed_time = (now - last_recovery_at).total_seconds()

            if elapsed_time < context.merchant.retry_cooldown_seconds:
                return PolicyDecision(
                    approved=False,
                    action=action,
                    expected_net_recovery=expected_net_recovery,
                    reasons=["Cooldown period is still active."],
                )

        if history.last_recovery_action == resolved_action.value:
            return PolicyDecision(
                approved=False,
                action=action,
                expected_net_recovery=expected_net_recovery,
                reasons=[f"Action '{action}' was already attempted in the last attempt."],
            )

        if expected_net_recovery <= 0:
            return PolicyDecision(
                approved=False,
                action=action,
                expected_net_recovery=expected_net_recovery,
                reasons=["Expected net recovery must be positive."],
            )

        reasons.extend(
            [
                "Recovery is enabled",
                "Action is allowed",
                "Recovery attempt limit is satisfied",
                "Cooldown is satisfied",
                "No duplicate last recovery action",
                "Expected net recovery is positive",
            ]
        )

        return PolicyDecision(
            approved=True,
            action=action,
            expected_net_recovery=expected_net_recovery,
            reasons=reasons,
        )
