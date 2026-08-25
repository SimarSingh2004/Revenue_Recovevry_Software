from datetime import datetime, timedelta, timezone
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
from app.simulator.baseline import baseline_probability


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
            allowed_recovery_actions=[
                "RETRY_PAYMENT",
                "ALTERNATE_PAYMENT_METHOD",
                "SEND_PAYMENT_LINK",
                "ESCALATE",
                "STOP",
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


class BaselineProbabilityTests(unittest.TestCase):

    def setUp(self):
        self.context = make_context()
        self.now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        self.context.current_payment_failure.event_occurred_at = (
            self.now - timedelta(minutes=30)
        )

    def test_returns_base_probability_for_each_action(self):
        self.context.current_payment_failure.payment_attempt_number = 2

        self.assertAlmostEqual(
            baseline_probability(
                "RETRY_PAYMENT",
                self.context,
                self.now,
            ),
            0.70,
        )

        self.assertAlmostEqual(
            baseline_probability(
                "ALTERNATE_PAYMENT_METHOD",
                self.context,
                self.now,
            ),
            0.65,
        )

        self.assertAlmostEqual(
            baseline_probability(
                "SEND_PAYMENT_LINK",
                self.context,
                self.now,
            ),
            0.55,
        )

        self.assertAlmostEqual(
            baseline_probability(
                "ESCALATE",
                self.context,
                self.now,
            ),
            0.10,
        )

    def test_stop_has_zero_probability(self):
        probability = baseline_probability(
            "STOP",
            self.context,
            self.now,
        )

        self.assertEqual(probability, 0.0)

    def test_customer_history_adjusts_probability(self):
        self.context.current_payment_failure.payment_attempt_number = 2
        self.context.customer_payment_history.customer_payment_count = 10
        self.context.customer_payment_history.customer_successful_payment_count = 10

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        # 0.70 + 0.10
        self.assertAlmostEqual(probability, 0.80)

    def test_failed_customer_history_reduces_probability(self):
        self.context.current_payment_failure.payment_attempt_number = 2
        self.context.customer_payment_history.customer_payment_count = 10
        self.context.customer_payment_history.customer_successful_payment_count = 0

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        # 0.70 - 0.10
        self.assertAlmostEqual(probability, 0.60)

    def test_no_customer_history_has_no_adjustment(self):
        self.context.current_payment_failure.payment_attempt_number = 2

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        self.assertAlmostEqual(probability, 0.70)

    def test_first_payment_attempt_increases_probability(self):
        self.context.current_payment_failure.payment_attempt_number = 1

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        # 0.70 + 0.05
        self.assertAlmostEqual(probability, 0.75)

    def test_second_payment_attempt_has_no_adjustment(self):
        self.context.current_payment_failure.payment_attempt_number = 2

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        self.assertAlmostEqual(probability, 0.70)

    def test_three_or_more_payment_attempts_reduce_probability(self):
        self.context.current_payment_failure.payment_attempt_number = 3

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        # 0.70 - 0.10
        self.assertAlmostEqual(probability, 0.60)

    def test_recent_failure_increases_probability(self):
        self.context.current_payment_failure.payment_attempt_number = 2
        self.context.current_payment_failure.event_occurred_at = (
            self.now - timedelta(minutes=5)
        )

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        # 0.70 + 0.05
        self.assertAlmostEqual(probability, 0.75)

    def test_moderately_recent_failure_has_no_time_adjustment(self):
        self.context.current_payment_failure.payment_attempt_number = 2
        self.context.current_payment_failure.event_occurred_at = (
            self.now - timedelta(minutes=30)
        )

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        self.assertAlmostEqual(probability, 0.70)

    def test_old_failure_reduces_probability(self):
        self.context.current_payment_failure.payment_attempt_number = 2
        self.context.current_payment_failure.event_occurred_at = (
            self.now - timedelta(hours=2)
        )

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        # 0.70 - 0.05
        self.assertAlmostEqual(probability, 0.65)

    def test_probability_is_clamped_to_zero(self):
        self.context.current_payment_failure.payment_attempt_number = 10
        self.context.current_payment_failure.event_occurred_at = (
            self.now - timedelta(days=10)
        )
        self.context.customer_payment_history.customer_payment_count = 10
        self.context.customer_payment_history.customer_successful_payment_count = 0

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        self.assertGreaterEqual(probability, 0.0)
        self.assertEqual(probability, 0.0)

    def test_strong_positive_adjustments_remain_within_probability_bounds(self):
        self.context.current_payment_failure.payment_attempt_number = 1
        self.context.current_payment_failure.event_occurred_at = (
            self.now - timedelta(minutes=5)
        )
        self.context.customer_payment_history.customer_payment_count = 10
        self.context.customer_payment_history.customer_successful_payment_count = 10

        probability = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        # 0.70 + 0.10 + 0.05 + 0.05 = 0.90
        self.assertAlmostEqual(probability, 0.90)

    def test_baseline_is_deterministic(self):
        first = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )
        second = baseline_probability(
            "RETRY_PAYMENT",
            self.context,
            self.now,
        )

        self.assertEqual(first, second)

    def test_invalid_action_is_rejected(self):
        with self.assertRaises(ValueError):
            baseline_probability(
                "CALL_CUSTOMER",
                self.context,
                self.now,
            )


if __name__ == "__main__":
    unittest.main()
