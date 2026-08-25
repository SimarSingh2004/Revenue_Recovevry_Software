from datetime import datetime, timezone
from decimal import Decimal
from random import Random
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
from app.simulator import PaymentProviderSimulator, SimulationOutcome


def make_context() -> RecoveryContext:
    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    return RecoveryContext(
        case=RecoveryCaseContext(
            case_id="case_001", event_id="event_001", payment_id="payment_001",
            status="PENDING", case_created_at=now,
        ),
        current_payment_failure=CurrentPaymentFailureContext(
            customer_id="customer_001", amount=Decimal("125.50"), currency="INR",
            event_type="PAYMENT_FAILED", event_occurred_at=now, failure_code="DECLINED",
            failure_category="TEMPORARY_FAILURE", payment_method="CARD",
            payment_attempt_number=1,
        ),
        merchant=MerchantContextData(
            merchant_id="merchant_001", recovery_enabled=True,
            allowed_recovery_actions=["RETRY_PAYMENT"], merchant_segment="SMB",
            retry_cooldown_seconds=60, max_recovery_attempts=3,
        ),
        merchant_recovery_history=MerchantRecoveryHistoryContext(
            history=[], recovery_attempt_count=0, last_recovery_action=None,
            last_recovery_outcome=None, last_recovery_at=None,
        ),
        customer_payment_history=CustomerPaymentHistoryContext(
            historical_payments=[], customer_payment_count=0,
            customer_failed_payment_count=0, customer_successful_payment_count=0,
            customer_failure_rate=Decimal("0"),
        ),
    )


class PaymentProviderSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.context = make_context()

    def test_executes_a_payment_action_with_provider_reference(self):
        result = PaymentProviderSimulator(Random(1)).execute(
            RecoveryAction.RETRY_PAYMENT, self.context, success_probability=1.0
        )

        self.assertEqual(result.outcome, SimulationOutcome.SUCCESS)
        self.assertTrue(result.is_payment_attempt)
        self.assertTrue(result.is_provider_execution)
        self.assertEqual(result.provider_reference, "sim_retry_payment_payment_001_1")

    def test_probability_can_produce_success_or_failure(self):
        simulator = PaymentProviderSimulator(Random(1))

        self.assertEqual(
            simulator.execute("RETRY_PAYMENT", self.context, success_probability=1.0).outcome,
            SimulationOutcome.SUCCESS,
        )
        self.assertEqual(
            simulator.execute("RETRY_PAYMENT", self.context, success_probability=0.0).outcome,
            SimulationOutcome.FAILURE,
        )

    def test_seeded_randomness_is_reproducible(self):
        first = PaymentProviderSimulator(Random(7)).execute(
            "ALTERNATE_PAYMENT_METHOD", self.context, success_probability=0.5
        )
        second = PaymentProviderSimulator(Random(7)).execute(
            "ALTERNATE_PAYMENT_METHOD", self.context, success_probability=0.5
        )

        self.assertEqual(first.outcome, second.outcome)

    def test_payment_link_flow_counts_as_payment_attempt(self):
        result = PaymentProviderSimulator(Random(1)).execute(
            "SEND_PAYMENT_LINK", self.context, success_probability=1.0
        )

        self.assertEqual(result.outcome, SimulationOutcome.SUCCESS)
        self.assertTrue(result.is_payment_attempt)
        self.assertTrue(result.is_provider_execution)
        self.assertIsNotNone(result.provider_reference)

    def test_non_payment_actions_are_handled_explicitly(self):
        escalated = PaymentProviderSimulator(Random(1)).execute(
            "ESCALATE", self.context, success_probability=1.0
        )
        stopped = PaymentProviderSimulator(Random(1)).execute(
            "STOP", self.context, success_probability=0.5
        )

        self.assertFalse(escalated.is_payment_attempt)
        self.assertFalse(escalated.is_provider_execution)
        self.assertEqual(escalated.outcome, SimulationOutcome.NOT_EXECUTED)
        self.assertIsNone(escalated.provider_reference)
        self.assertEqual(stopped.outcome, SimulationOutcome.NOT_EXECUTED)
        self.assertFalse(stopped.is_payment_attempt)
        self.assertFalse(stopped.is_provider_execution)

    def test_invalid_action_and_probability_are_rejected(self):
        simulator = PaymentProviderSimulator(Random(1))

        with self.assertRaises(ValueError):
            simulator.execute("CALL_CUSTOMER", self.context, success_probability=0.5)
        with self.assertRaises(ValueError):
            simulator.execute("RETRY_PAYMENT", self.context, success_probability=1.1)


if __name__ == "__main__":
    unittest.main()
