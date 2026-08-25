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
from app.simulator.ground_truth import ground_truth_probability


NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def make_context(
    *,
    payment_method="CARD",
    failure_category="UNKNOWN",
    occurred_at=None,
    payment_count=0,
    successful_count=0,
    previous_attempts=0,
) -> RecoveryContext:
    occurred_at = occurred_at or NOW - timedelta(hours=2)
    return RecoveryContext(
        case=RecoveryCaseContext(
            case_id="case_001", event_id="event_001", payment_id="payment_001",
            status="PENDING", case_created_at=occurred_at,
        ),
        current_payment_failure=CurrentPaymentFailureContext(
            customer_id="customer_001", amount=Decimal("125.50"), currency="INR",
            event_type="PAYMENT_FAILED", event_occurred_at=occurred_at,
            failure_code="DECLINED", failure_category=failure_category,
            payment_method=payment_method, payment_attempt_number=1,
        ),
        merchant=MerchantContextData(
            merchant_id="merchant_001", recovery_enabled=True,
            allowed_recovery_actions=["RETRY_PAYMENT"], merchant_segment="SMB",
            retry_cooldown_seconds=60, max_recovery_attempts=3,
        ),
        merchant_recovery_history=MerchantRecoveryHistoryContext(
            history=[], recovery_attempt_count=previous_attempts,
            last_recovery_action=None, last_recovery_outcome=None, last_recovery_at=None,
        ),
        customer_payment_history=CustomerPaymentHistoryContext(
            historical_payments=[], customer_payment_count=payment_count,
            customer_failed_payment_count=payment_count - successful_count,
            customer_successful_payment_count=successful_count,
            customer_failure_rate=Decimal("0"),
        ),
    )


class GroundTruthProbabilityTests(unittest.TestCase):
    def probability(self, **context_options):
        return ground_truth_probability(
            make_context(**context_options), RecoveryAction.RETRY_PAYMENT, NOW
        )

    def test_customer_history_and_no_history_effects(self):
        self.assertEqual(self.probability(), 0.60)
        self.assertAlmostEqual(self.probability(payment_count=4, successful_count=4), 0.675)
        self.assertAlmostEqual(self.probability(payment_count=4, successful_count=0), 0.525)

    def test_payment_method_effects(self):
        expected = {"UPI": 0.65, "CARD": 0.60, "NETBANKING": 0.62, "WALLET": 0.63}
        for method, probability in expected.items():
            with self.subTest(method=method):
                self.assertAlmostEqual(self.probability(payment_method=method), probability)

    def test_failure_category_effects(self):
        expected = {
            "TEMPORARY_FAILURE": 0.72, "INSUFFICIENT_FUNDS": 0.70,
            "NETWORK_ERROR": 0.72, "PROCESSING_ERROR": 0.68,
            "EXPIRED_CARD": 0.42, "INVALID_CARD": 0.40,
            "FRAUD": 0.35, "UNKNOWN": 0.60,
        }
        for category, probability in expected.items():
            with self.subTest(category=category):
                self.assertAlmostEqual(self.probability(failure_category=category), probability)

    def test_time_since_failure_buckets(self):
        expected = [
            (timedelta(minutes=5), 0.65),
            (timedelta(minutes=30), 0.63),
            (timedelta(hours=1), 0.60),
            (timedelta(hours=6), 0.56),
            (timedelta(hours=24), 0.56),
            (timedelta(days=2), 0.52),
        ]
        for elapsed, probability in expected:
            with self.subTest(elapsed=elapsed):
                self.assertAlmostEqual(self.probability(occurred_at=NOW - elapsed), probability)

    def test_previous_recovery_attempt_buckets(self):
        expected = {0: 0.60, 1: 0.56, 2: 0.52, 3: 0.48, 4: 0.44, 5: 0.44}
        for attempts, probability in expected.items():
            with self.subTest(attempts=attempts):
                self.assertAlmostEqual(self.probability(previous_attempts=attempts), probability)

    def test_low_probability_is_clamped(self):
        self.assertEqual(
            ground_truth_probability(
                make_context(failure_category="FRAUD", occurred_at=NOW - timedelta(days=8),
                             payment_count=4, successful_count=0, previous_attempts=4),
                "SEND_PAYMENT_LINK", NOW,
            ),
            0.05,
        )

    def test_result_is_deterministic(self):
        context = make_context(failure_category="TEMPORARY_FAILURE")
        self.assertEqual(
            ground_truth_probability(context, "RETRY_PAYMENT", NOW),
            ground_truth_probability(context, "RETRY_PAYMENT", NOW),
        )

    def test_escalate_and_stop_have_their_locked_probabilities(self):
        context = make_context()
        self.assertEqual(ground_truth_probability(context, "ESCALATE", NOW), 0.15)
        self.assertEqual(ground_truth_probability(context, "STOP", NOW), 0.0)

    def test_invalid_action_is_rejected(self):
        with self.assertRaises(ValueError):
            ground_truth_probability(make_context(), "CALL_CUSTOMER", NOW)

    def test_unsupported_payment_method_and_failure_category_are_rejected(self):
        with self.assertRaises(ValueError):
            self.probability(payment_method="CASH")
        with self.assertRaises(ValueError):
            self.probability(failure_category="DO_NOT_HONOR")


if __name__ == "__main__":
    unittest.main()
