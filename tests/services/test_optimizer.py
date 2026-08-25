from datetime import datetime, timezone
from decimal import Decimal
import unittest

from app.core.recovery_actions import RecoveryAction
from app.schemas.recovery_context import (
    CurrentPaymentFailureContext,
    CustomerPaymentHistoryContext,
    MerchantContextData,
    MerchantRecoveryHistoryContext,
    RecoveryCaseContext,
    RecoveryContext,
)
from app.services.optimizer import expected_net_recovery_value


def make_context() -> RecoveryContext:
    now = datetime(2026, 8, 25, tzinfo=timezone.utc)

    return RecoveryContext(
        case=RecoveryCaseContext(
            case_id="case_001",
            event_id="event_001",
            payment_id="payment_001",
            status="PENDING",
            case_created_at=now,
        ),
        current_payment_failure=CurrentPaymentFailureContext(
            customer_id="customer_001",
            amount=Decimal("125.50"),
            currency="INR",
            event_type="PAYMENT_FAILED",
            event_occurred_at=now,
            failure_code="DECLINED",
            failure_category="TEMPORARY_FAILURE",
            payment_method="CARD",
            payment_attempt_number=1,
        ),
        merchant=MerchantContextData(
            merchant_id="merchant_001",
            recovery_enabled=True,
            allowed_recovery_actions=["RETRY_PAYMENT"],
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


class ExpectedNetRecoveryValueTests(unittest.TestCase):

    def setUp(self):
        self.context = make_context()
        self.context.current_payment_failure.amount = Decimal("1000")

    def test_retry_payment_expected_net_recovery(self):
        value = expected_net_recovery_value(
            self.context,
            RecoveryAction.RETRY_PAYMENT,
            0.70,
        )

        # 0.70 * 1000 - 2 - 1
        self.assertAlmostEqual(value, 697.0)

    def test_each_action_uses_its_locked_cost_and_risk_penalty(self):
        expected_values = {
            RecoveryAction.RETRY_PAYMENT: 697.0,
            RecoveryAction.ALTERNATE_PAYMENT_METHOD: 696.0,
            RecoveryAction.SEND_PAYMENT_LINK: 698.5,
            RecoveryAction.ESCALATE: 693.0,
        }

        for action, expected in expected_values.items():
            with self.subTest(action=action):
                value = expected_net_recovery_value(
                    self.context,
                    action,
                    0.70,
                )

                self.assertAlmostEqual(value, expected)

    def test_zero_probability(self):
        value = expected_net_recovery_value(
            self.context,
            RecoveryAction.RETRY_PAYMENT,
            0.0,
        )

        # 0 - 2 - 1
        self.assertAlmostEqual(value, -3.0)

    def test_one_probability(self):
        value = expected_net_recovery_value(
            self.context,
            RecoveryAction.RETRY_PAYMENT,
            1.0,
        )

        # 1000 - 2 - 1
        self.assertAlmostEqual(value, 997.0)

    def test_fractional_probability(self):
        value = expected_net_recovery_value(
            self.context,
            RecoveryAction.SEND_PAYMENT_LINK,
            0.40,
        )

        # 0.40 * 1000 - 1 - 0.50
        self.assertAlmostEqual(value, 398.5)

    def test_stop_returns_zero(self):
        value = expected_net_recovery_value(
            self.context,
            RecoveryAction.STOP,
            0.80,
        )

        self.assertEqual(value, 0.0)

    def test_negative_expected_net_recovery_is_preserved(self):
        self.context.current_payment_failure.amount = Decimal("10")

        value = expected_net_recovery_value(
            self.context,
            RecoveryAction.RETRY_PAYMENT,
            0.10,
        )

        # 0.10 * 10 - 2 - 1
        self.assertAlmostEqual(value, -2.0)

    def test_probability_below_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            expected_net_recovery_value(
                self.context,
                RecoveryAction.RETRY_PAYMENT,
                -0.01,
            )

    def test_probability_above_one_is_rejected(self):
        with self.assertRaises(ValueError):
            expected_net_recovery_value(
                self.context,
                RecoveryAction.RETRY_PAYMENT,
                1.01,
            )

    def test_stop_still_requires_a_valid_probability(self):
        with self.assertRaises(ValueError):
            expected_net_recovery_value(
                self.context,
                RecoveryAction.STOP,
                1.01,
            )


if __name__ == "__main__":
    unittest.main()
