import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.recovery_actions import RecoveryAction
from app.services.policy_engine import PolicyEngine
from app.schemas.recovery_context import (
    RecoveryCaseContext,
    RecoveryContext,
    MerchantContextData,
    MerchantRecoveryHistoryContext,
    CurrentPaymentFailureContext,
    CustomerPaymentHistoryContext,
)


class TestPolicyEngine(unittest.TestCase):

    def setUp(self):
        self.engine = PolicyEngine()

        self.context = RecoveryContext(
            case=RecoveryCaseContext(
                case_id="case_001",
                event_id="event_001",
                payment_id="payment_001",
                status="PENDING",
                case_created_at=datetime.now(timezone.utc),
            ),
            merchant=MerchantContextData(
                merchant_id="merchant_001",
                recovery_enabled=True,
                allowed_recovery_actions=[
                    RecoveryAction.RETRY_PAYMENT.value,
                    RecoveryAction.ALTERNATE_PAYMENT_METHOD.value,
                    RecoveryAction.SEND_PAYMENT_LINK.value,
                    RecoveryAction.ESCALATE.value,
                    RecoveryAction.STOP.value,
                ],
                merchant_segment="SMB",
                max_recovery_attempts=3,
                retry_cooldown_seconds=60,
            ),
            merchant_recovery_history=MerchantRecoveryHistoryContext(
                history=[],
                recovery_attempt_count=0,
                last_recovery_at=None,
                last_recovery_action=None,
                last_recovery_outcome=None,
            ),
            current_payment_failure=CurrentPaymentFailureContext(
                customer_id="customer_001",
                amount=Decimal("100.00"),
                currency="INR",
                event_type="PAYMENT_FAILED",
                event_occurred_at=datetime.now(timezone.utc),
                failure_code="DECLINED",
                failure_category="TEMPORARY_FAILURE",
                payment_method="CARD",
                payment_attempt_number=1,
            ),
            customer_payment_history=CustomerPaymentHistoryContext(
                historical_payments=[],
                customer_payment_count=0,
                customer_failed_payment_count=0,
                customer_successful_payment_count=0,
                customer_failure_rate=Decimal("0"),
            ),
        )

    def test_approve_valid_action(self):
        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=100.0,
        )

        self.assertTrue(result.approved)
        self.assertEqual(result.action, RecoveryAction.RETRY_PAYMENT.value)
        self.assertEqual(result.expected_net_recovery, 100.0)
        self.assertIn("Expected net recovery is positive", result.reasons)

    def test_reject_invalid_action(self):
        result = self.engine.evaluate(
            context=self.context,
            action="invalid_action",
            expected_net_recovery=100.0,
        )

        self.assertFalse(result.approved)
        self.assertEqual(result.action, "invalid_action")

    def test_reject_when_recovery_disabled(self):
        self.context.merchant.recovery_enabled = False

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=100.0,
        )

        self.assertFalse(result.approved)

    def test_reject_action_not_allowed(self):
        self.context.merchant.allowed_recovery_actions = [
            RecoveryAction.ESCALATE.value,
            RecoveryAction.STOP.value,
        ]

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=100.0,
        )

        self.assertFalse(result.approved)

    def test_reject_when_max_recovery_attempts_reached(self):
        self.context.merchant_recovery_history.recovery_attempt_count = 3

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=100.0,
        )

        self.assertFalse(result.approved)

    def test_allow_escalate_when_max_recovery_attempts_reached(self):
        self.context.merchant_recovery_history.recovery_attempt_count = 3

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.ESCALATE.value,
            expected_net_recovery=100.0,
        )

        self.assertTrue(result.approved)
        self.assertEqual(result.action, RecoveryAction.ESCALATE.value)

    def test_reject_when_cooldown_is_active(self):
        self.context.merchant_recovery_history.last_recovery_at = (
            datetime.now(timezone.utc) - timedelta(seconds=30)
        )
        self.context.merchant_recovery_history.last_recovery_action = None

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=100.0,
        )

        self.assertFalse(result.approved)

    def test_allow_when_cooldown_is_satisfied(self):
        self.context.merchant_recovery_history.last_recovery_at = (
            datetime.now(timezone.utc) - timedelta(seconds=120)
        )

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=100.0,
        )

        self.assertTrue(result.approved)

    def test_reject_when_same_action_was_last_recovery(self):
        self.context.merchant_recovery_history.last_recovery_action = (
            RecoveryAction.RETRY_PAYMENT.value
        )
        self.context.merchant_recovery_history.last_recovery_outcome = "FAILURE"

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=100.0,
        )

        self.assertFalse(result.approved)
        self.assertIn("already attempted", result.reasons[0])

    def test_allow_different_action_after_previous_recovery(self):
        self.context.merchant_recovery_history.last_recovery_action = (
            RecoveryAction.RETRY_PAYMENT.value
        )

        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.ALTERNATE_PAYMENT_METHOD.value,
            expected_net_recovery=100.0,
        )

        self.assertTrue(result.approved)

    def test_reject_zero_net_recovery(self):
        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=0.0,
        )

        self.assertFalse(result.approved)

    def test_reject_negative_net_recovery(self):
        result = self.engine.evaluate(
            context=self.context,
            action=RecoveryAction.RETRY_PAYMENT.value,
            expected_net_recovery=-50.0,
        )

        self.assertFalse(result.approved)
        self.assertEqual(result.expected_net_recovery, -50.0)


if __name__ == "__main__":
    unittest.main()
