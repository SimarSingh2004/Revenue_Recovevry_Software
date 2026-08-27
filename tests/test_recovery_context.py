import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.recovery_actions import RecoveryAction
from app.models import MerchantContext, MerchantHistory, PaymentHistory, RecoveryCase, RecoveryEvent
from app.services.recovery_context import build_recovery_context, load_recovery_context


class PersistedContextSession:
    """Minimal read-only session fixture for the context loader."""

    def __init__(self, recovery_case, recovery_event, merchant, merchant_history, payment_history):
        self.records = {
            (RecoveryCase, recovery_case.case_id): recovery_case,
            (RecoveryEvent, recovery_event.event_id): recovery_event,
            (MerchantContext, merchant.merchant_id): merchant,
        }
        self.merchant_history = merchant_history
        self.payment_history = payment_history

    def get(self, model, key):
        return self.records.get((model, key))

    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is MerchantHistory:
            return iter(self.merchant_history)
        if entity is PaymentHistory:
            return iter(self.payment_history)
        raise AssertionError(f"Unexpected context query: {entity}")


class RecoveryContextTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 24, tzinfo=timezone.utc)
        self.event = RecoveryEvent(
            event_id="event_current", event_type="PAYMENT_FAILED", occurred_at=self.now,
            payment_id="payment_current", merchant_id="merchant_a", customer_id="customer_a",
            amount=Decimal("125.50"), currency="INR", failure_code="DECLINED",
            failure_category="TEMPORARY_FAILURE", payment_method="CARD", attempt_number=1,
        )
        self.case = RecoveryCase(
            case_id="case_current", event_id=self.event.event_id, payment_id=self.event.payment_id,
            status="PENDING", created_at=self.now,
        )
        self.merchant = MerchantContext(
            merchant_id="merchant_a",
            recovery_enabled=True,
            allowed_recovery_actions=[RecoveryAction.RETRY_PAYMENT.value],
            merchant_segment="SMB", retry_cooldown_seconds=60, max_recovery_attempts=3,
        )

    def payment(self, payment_id, status, *, merchant_id="merchant_a", customer_id="customer_a"):
        return PaymentHistory(
            id=1, payment_id=payment_id, customer_id=customer_id, merchant_id=merchant_id,
            amount=Decimal("10.00"), currency="INR", payment_method="CARD", status=status,
            event_type="PAYMENT_COMPLETED", occurred_at=self.now - timedelta(days=1),
        )

    def test_builds_all_context_categories_from_filtered_history(self):
        recent_history = MerchantHistory(
            id=2, merchant_id="merchant_a", case_id="case_current",
            action=RecoveryAction.RETRY_PAYMENT.value,
            outcome="SUCCESS", amount=Decimal("20.00"), intervention_cost=Decimal("1.00"),
            occurred_at=self.now - timedelta(hours=1),
        )
        older_history = MerchantHistory(
            id=1, merchant_id="merchant_a", case_id="case_older",
            action=RecoveryAction.SEND_PAYMENT_LINK.value,
            outcome="FAILED", amount=Decimal("10.00"), intervention_cost=Decimal("0.50"),
            occurred_at=self.now - timedelta(days=1),
        )
        other_merchant_history = MerchantHistory(
            id=3, merchant_id="merchant_b", case_id="case_other",
            action=RecoveryAction.RETRY_PAYMENT.value,
            outcome="SUCCESS", amount=Decimal("5.00"), intervention_cost=Decimal("0.20"),
            occurred_at=self.now,
        )

        history = [older_history, other_merchant_history, recent_history]
        payments = [
                self.payment("payment_success", "SUCCESS"),
                self.payment("payment_failed", "FAILED"),
                self.payment("payment_current", "FAILED"),
                self.payment("payment_other_merchant", "SUCCESS", merchant_id="merchant_b"),
            ]
        context = load_recovery_context(
            PersistedContextSession(self.case, self.event, self.merchant, history, payments),
            self.case.case_id,
        )

        self.assertEqual(context.case.case_id, "case_current")
        self.assertEqual(context.current_payment_failure.payment_attempt_number, 1)
        self.assertEqual(context.merchant.merchant_id, "merchant_a")
        self.assertEqual(context.merchant_recovery_history.recovery_attempt_count, 1)
        self.assertEqual(
            context.merchant_recovery_history.last_recovery_action,
            RecoveryAction.RETRY_PAYMENT.value,
        )
        self.assertEqual(context.customer_payment_history.customer_payment_count, 2)
        self.assertEqual(context.customer_payment_history.customer_failed_payment_count, 1)
        self.assertEqual(context.customer_payment_history.customer_successful_payment_count, 1)
        self.assertEqual(context.customer_payment_history.customer_failure_rate, Decimal("0.5"))
        self.assertEqual(
            [payment.payment_id for payment in context.customer_payment_history.historical_payments],
            ["payment_success", "payment_failed"],
        )
        self.assertNotIn(
            self.event.payment_id,
            [payment.payment_id for payment in context.customer_payment_history.historical_payments],
        )
        self.assertEqual(self.case.status, "PENDING")

    def test_empty_histories_produce_zeroed_summaries(self):
        context = build_recovery_context(
            recovery_case=self.case, recovery_event=self.event, merchant=self.merchant,
            merchant_history=[], payment_history=[],
        )

        self.assertEqual(context.merchant_recovery_history.history, [])
        self.assertEqual(context.merchant_recovery_history.recovery_attempt_count, 0)
        self.assertIsNone(context.merchant_recovery_history.last_recovery_at)
        self.assertEqual(context.customer_payment_history.customer_payment_count, 0)
        self.assertEqual(context.customer_payment_history.customer_failure_rate, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
